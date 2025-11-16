import datetime
import inspect
import logging
from collections.abc import MutableMapping
from inspect import getfullargspec
from logging.handlers import RotatingFileHandler
from pathlib import Path

import coloredlogs
import pytz

from domovoy.core.configuration import (
    FileLoggingHandler,
    LoggingConfig,
    OpenObserveLoggingHandler,
    StreamLoggingHandler,
    get_main_config,
)
from domovoy.core.context import context_logger
from domovoy.core.errors import DomovoyConfigurationError, DomovoyError
from domovoy.core.logging.http_json import JsonHtttpHandler
from domovoy.core.logging.logger_adapter_with_trace import LoggerAdapterWithTrace


def __add_trace_logging_level(level_num: int) -> None:
    if hasattr(logging, "trace"):
        return

    def _log_for_level(self, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
        try:
            self.log(level_num, args, **kwargs)
        except Exception as e:
            print(e, args, kwargs)  # noqa: T201

    def _log_to_root(*args, **kwargs) -> None:  # noqa:   ANN002, ANN003
        try:
            logging.log(level_num, *args, **kwargs)  # noqa: LOG015
        except Exception as e:
            print(e, args, kwargs)  # noqa: T201

    logging.addLevelName(level_num, "TRACE")
    setattr(logging, "TRACE", level_num)  # noqa: B010
    setattr(logging.getLoggerClass(), "trace", _log_for_level)  # noqa: B010
    setattr(logging, "trace", _log_to_root)  # noqa: B010


__add_trace_logging_level(logging.DEBUG - 5)


class BraceMessage:
    def __init__(self, fmt: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs

    def __str__(self) -> str:
        try:
            return self.fmt.format(*self.args, **self.kwargs)

        except BaseException:
            return str(self.fmt)

    def __repr__(self) -> str:
        try:
            return self.fmt.format(*self.args, **self.kwargs)

        except BaseException:
            return str(self.fmt)


class StyleAdapter(LoggerAdapterWithTrace):
    def __init__(self, logger: logging.Logger | logging.LoggerAdapter) -> None:
        super().__init__(logger, {}, merge_extra=True)

    def log(self, level: int, msg: object, *args: object, **kwargs: object) -> None:
        # if self.isEnabledFor(level):
        msg, log_kwargs = self.process(str(msg), kwargs)
        self.logger._log(level, BraceMessage(msg, args, kwargs), (), **log_kwargs)  # noqa: SLF001
        log_kwargs["extra"] = {}

    def process(self, msg: str, kwargs: MutableMapping[str, object]) -> tuple[str, dict[str, object]]:
        log_kwargs = getfullargspec(self.logger._log).args[1:]  # noqa: SLF001
        main_args = {key: kwargs[key] for key in log_kwargs if key in kwargs}

        extra = dict(main_args.get("extra", {}))  # type: ignore
        ad = {"_additionalArgs": {key: kwargs[key] for key in kwargs if key not in log_kwargs} | extra}

        if "extra" in main_args:
            main_args["extra"] = {**extra, **ad}
        else:
            main_args["extra"] = ad

        return (
            msg,
            main_args,
        )


_log_config: dict[str, LoggerAdapterWithTrace[logging.Logger]] = {}
_default_config = LoggingConfig()


def __get_log_config(name: str, *, use_app_logger_default: bool) -> LoggingConfig:
    try:
        config = get_main_config()

        base_config = config.logs.get("_base", _default_config)

        if use_app_logger_default and "_apps_default" in config.logs:
            final_config = config.logs["_apps_default"]

        elif "_default" in config.logs:
            final_config = config.logs["_default"]

        else:
            final_config = _default_config

        if name in config.logs:
            final_config = final_config + config.logs[name]

        return base_config + final_config

    except DomovoyError:
        return _default_config


def __get_extended_formatter(formatter: type[logging.Formatter]) -> type[logging.Formatter]:
    class Formatter(formatter):
        def converter(self, timestamp: float) -> datetime.datetime:  # type: ignore
            try:
                tz = get_main_config().get_timezone()
            except Exception:
                tz = pytz.timezone("America/Chicago")

            return datetime.datetime.fromtimestamp(timestamp, tz=tz)

        def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
            dt = self.converter(record.created)
            if datefmt:
                return dt.strftime(datefmt)

            try:
                return dt.isoformat(timespec="milliseconds")
            except TypeError:
                return dt.isoformat()

    return Formatter


def __build_logger(
    logger_name: str,
    *,
    include_app_name: bool,
    use_app_logger_default: bool,
) -> LoggerAdapterWithTrace[logging.Logger]:
    config: LoggingConfig = __get_log_config(logger_name, use_app_logger_default=use_app_logger_default)
    return __build_logger_with_config(
        config=config,
        logger_name=logger_name,
        include_app_name=include_app_name,
    )


def __build_logger_with_config(
    *,
    config: LoggingConfig,
    logger_name: str,
    include_app_name: bool,
) -> LoggerAdapterWithTrace[logging.Logger]:
    logger = logging.getLogger(logger_name)

    config_log_level = config.get_numeric_log_level()
    min_log_level = min([x.get_numeric_log_level() or logging.INFO for x in config.handlers] or [logging.INFO])

    if config_log_level:
        logger.setLevel(config_log_level)

    if not config_log_level:
        logger.setLevel(min_log_level)

    logger.propagate = False

    config_formatter = config.formatter
    if config_formatter is None:
        config_formatter = "[%(asctime)s][%(levelname)s][%(name)s]  %(message)s"

    config_formatter_with_app_name = config.formatter_with_app_name
    if config_formatter_with_app_name is None:
        config_formatter_with_app_name = "[%(asctime)s][%(levelname)s][%(name)s][%(app_name)s]  %(message)s"

    for handler_config in config.handlers:
        if include_app_name:
            formatter = (
                handler_config.formatter_with_app_name
                if handler_config.formatter_with_app_name
                else config_formatter_with_app_name
            )
        else:
            formatter = handler_config.formatter if handler_config.formatter else config_formatter

        if isinstance(handler_config, OpenObserveLoggingHandler):
            handler = JsonHtttpHandler(
                url=handler_config.url,
                username=handler_config.username,
                password=handler_config.password,
            )
            handler.setFormatter(__get_extended_formatter(logging.Formatter)(formatter))

        elif isinstance(handler_config, FileLoggingHandler):
            output_filename = handler_config.filename.replace("{logger_name}", logger_name)

            Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                output_filename,
                backupCount=5,
                maxBytes=5_000_000,
            )
            handler.setFormatter(__get_extended_formatter(logging.Formatter)(formatter))

        elif isinstance(handler_config, StreamLoggingHandler):
            handler = logging.StreamHandler(handler_config.get_actual_output_stream())
            handler.setFormatter(
                __get_extended_formatter(coloredlogs.ColoredFormatter)(formatter),
            )
        else:
            raise DomovoyConfigurationError("Unsupported LoggerConfig Handler")

        log_level = handler_config.get_numeric_log_level()

        if log_level:
            handler.setLevel(log_level)
        elif config_log_level:
            handler.setLevel(config_log_level)
        else:
            handler.setLevel(logging.INFO)

        logger.addHandler(handler)

    return StyleAdapter(logger)


_logcore = __build_logger(
    __name__,
    include_app_name=False,
    use_app_logger_default=False,
)


def get_logger(
    logger_name: str,
    *,
    include_app_name: bool = False,
    use_app_logger_default: bool = False,
) -> LoggerAdapterWithTrace[logging.Logger]:
    if logger_name not in _log_config:
        _log_config[logger_name] = __build_logger(
            logger_name,
            include_app_name=include_app_name,
            use_app_logger_default=use_app_logger_default,
        )

    return _log_config[logger_name]


def get_context_logger() -> LoggerAdapterWithTrace[logging.Logger]:
    logger = context_logger.get(None)

    if logger is None:
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])

        if mod is None:
            logger = get_logger("__main__")
            logger.warning(
                "Couldn't generate the calling module name in get_context_logger",
            )
        else:
            logger = get_logger(mod.__name__)

        logger.warning(
            "Tried to get a context_logger which wasn't set. Used closest default (module or __main__)",
        )

    return logger


def get_logger_for_app(
    logger_name: str,
    app_name: str,
    app_id: str,
) -> LoggerAdapterWithTrace[logging.Logger | LoggerAdapterWithTrace]:
    _logcore.trace(
        "Loading Logger with AppName: logger_name: {logger_name} - app_name: {app_name}",
        logger_name=logger_name,
        app_name=app_name,
    )

    return LoggerAdapterWithTrace(
        get_logger(
            logger_name,
            include_app_name=True,
            use_app_logger_default=True,
        ),
        {"app_name": app_name, "app_id": app_id},
    )


logging_infra_logger = __build_logger_with_config(
    config=LoggingConfig(
        log_level="trace",
        handlers={StreamLoggingHandler()},  # type: ignore
    ),
    logger_name="logging_infra",
    include_app_name=False,
)
