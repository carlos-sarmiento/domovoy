import datetime
import inspect
import logging
from collections.abc import MutableMapping
from inspect import getfullargspec
from logging.handlers import RotatingFileHandler
from pathlib import Path

import coloredlogs
import pytz

from domovoy.core.configuration import LoggingConfig, get_main_config
from domovoy.core.context import context_logger
from domovoy.core.errors import DomovoyError
from domovoy.core.logging.http_json import JsonHtttpHandler
from domovoy.core.logging.logger_adapter_with_trace import LoggerAdapterWithTrace


def __add_trace_logging_level(level_num: int) -> None:
    if hasattr(logging, "trace"):
        return

    def _log_for_level(self, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
        if self.isEnabledFor(level_num):
            self._log(level_num, args, **kwargs)

    def _log_to_root(*args, **kwargs) -> None:  # noqa:   ANN002, ANN003
        logging.log(level_num, *args, **kwargs)

    logging.addLevelName(level_num, "trace")
    setattr(logging, "trace", level_num)  # noqa: B010
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
    def __init__(self, logger: logging.Logger) -> None:
        super().__init__(logger, {}, merge_extra=True)

    def log(self, level: int, msg: object, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(level):
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


def _dummy_logger_function(*_args: object, **_kwargs: object) -> None:
    # do nothing
    ...


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
    config = __get_log_config(logger_name, use_app_logger_default=use_app_logger_default)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    configured_log_level = config.get_numeric_log_level()

    formatter = (
        config.formatter
        if not include_app_name or config.formatter_with_app_name is None
        else config.formatter_with_app_name
    )

    if config.http_sink:
        handler = JsonHtttpHandler(
            url=config.http_sink.url,
            username=config.http_sink.username,
            password=config.http_sink.password,
        )
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

    if config.output_filename:
        output_filename = config.output_filename.replace("{logger_name}", logger_name)

        Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            output_filename,
            backupCount=5,
            maxBytes=5_000_000,
        )
        handler.setFormatter(__get_extended_formatter(logging.Formatter)(formatter))
        handler.setLevel(configured_log_level)

        logger.addHandler(handler)

    if config.write_to_stdout:
        handler = logging.StreamHandler(config.get_actual_output_stream())
        handler.setFormatter(
            __get_extended_formatter(coloredlogs.ColoredFormatter)(formatter),
        )
        handler.setLevel(configured_log_level)
        logger.addHandler(handler)

    _log_config[logger_name] = StyleAdapter(logger)

    return _log_config[logger_name]


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
        return __build_logger(
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
        {"app_name": app_name},
    )
