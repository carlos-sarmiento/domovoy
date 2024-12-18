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


class StyleAdapter(logging.LoggerAdapter):
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def log(self, level: int, msg: object, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(level):
            msg, log_kwargs = self.process(str(msg), kwargs)
            self.logger._log(level, BraceMessage(msg, args, kwargs), (), **log_kwargs)  # noqa: SLF001

    def process(self, msg: str, kwargs: MutableMapping[str, object]) -> tuple[str, dict[str, object]]:
        return msg, {key: kwargs[key] for key in getfullargspec(self.logger._log).args[1:] if key in kwargs}  # noqa: SLF001


_log_config: dict[str, logging.LoggerAdapter[logging.Logger]] = {}
_default_config = LoggingConfig()


def _dummy_logger_function(*_args: object, **_kwargs: object) -> None:
    # do nothing
    ...


def __get_log_config(name: str, *, use_app_logger_default: bool) -> LoggingConfig:
    try:
        config = get_main_config()

        if use_app_logger_default and "_apps_default" in config.logs:
            default_config = config.logs["_apps_default"]

        elif "_default" in config.logs:
            default_config = config.logs["_default"]

        else:
            default_config = _default_config

        if name in config.logs:
            return default_config + config.logs[name]

        return default_config

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
) -> logging.LoggerAdapter[logging.Logger]:
    config = __get_log_config(logger_name, use_app_logger_default=use_app_logger_default)
    logger = logging.getLogger(logger_name)
    logger.setLevel(config.get_numeric_log_level())
    logger.propagate = False

    formatter = (
        config.formatter
        if not include_app_name or config.formatter_with_app_name is None
        else config.formatter_with_app_name
    )

    if config.write_to_stdout:
        handler = logging.StreamHandler(config.get_actual_output_stream())
        handler.setFormatter(
            __get_extended_formatter(coloredlogs.ColoredFormatter)(formatter),
        )
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
        logger.addHandler(handler)

    _log_config[logger_name] = StyleAdapter(logger)

    if config.get_numeric_log_level() > logging.DEBUG:
        _log_config[logger_name].debug = _dummy_logger_function

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
) -> logging.LoggerAdapter[logging.Logger]:
    if logger_name not in _log_config:
        return __build_logger(
            logger_name,
            include_app_name=include_app_name,
            use_app_logger_default=use_app_logger_default,
        )

    return _log_config[logger_name]


def get_context_logger() -> logging.LoggerAdapter[logging.Logger]:
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
) -> logging.LoggerAdapter[logging.Logger | logging.LoggerAdapter]:
    _logcore.debug(
        "Loading Logger with AppName: logger_name: {logger_name} - app_name: {app_name}",
        logger_name=logger_name,
        app_name=app_name,
    )

    return logging.LoggerAdapter(
        get_logger(
            logger_name,
            include_app_name=True,
            use_app_logger_default=True,
        ),
        {"app_name": app_name},
    )
