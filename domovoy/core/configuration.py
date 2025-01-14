from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Literal, TextIO

import pytz
from astral import LocationInfo
from astral.location import Location
from pytz import BaseTzInfo
from serde import deserialize
from serde.yaml import from_yaml

from domovoy.core.errors import DomovoyError


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)
class AstralConfig:
    name: str
    region: str
    timezone: str
    latitude: float
    longitude: float


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)
class LoggingHandlerConfig:
    formatter: str | None = None
    formatter_with_app_name: str | None = None
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] | None = None

    def get_numeric_log_level(self) -> int | None:  # noqa: PLR0911
        if self.log_level == "critical":
            return logging.CRITICAL

        if self.log_level == "error":
            return logging.ERROR

        if self.log_level == "warning":
            return logging.WARNING

        if self.log_level == "info":
            return logging.INFO

        if self.log_level == "debug":
            return logging.DEBUG

        if self.log_level == "trace":
            return logging.TRACE  # type: ignore

        return None


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)  # type: ignore
class StreamLoggingHandler(LoggingHandlerConfig):
    stream: Literal["stdout", "stderr"] = "stdout"

    def get_actual_output_stream(self) -> TextIO | None:
        if self.stream == "stdout":
            return sys.stdout

        if self.stream == "stderr":
            return sys.stderr

        return None


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)  # type: ignore
class FileLoggingHandler(LoggingHandlerConfig):
    filename: str  # type: ignore


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)  # type: ignore
class OpenObserveLoggingHandler(LoggingHandlerConfig):
    username: str  # type: ignore
    password: str  # type: ignore
    url: str  # type: ignore


@deserialize
@dataclass(kw_only=True, eq=True, frozen=True)  # type: ignore
class LoggingConfig(LoggingHandlerConfig):
    handlers: set[StreamLoggingHandler | FileLoggingHandler | OpenObserveLoggingHandler] = field(default_factory=set)

    def __add__(self, b: LoggingConfig) -> LoggingConfig:
        return LoggingConfig(
            handlers=self.handlers | b.handlers,
            formatter=b.formatter if b.formatter is not None else self.formatter,
            formatter_with_app_name=b.formatter_with_app_name
            if b.formatter_with_app_name is not None
            else self.formatter_with_app_name,
            log_level=b.log_level if b.log_level is not None else self.log_level,
        )


@deserialize(kw_only=True, frozen=True)
class MainConfig:
    app_suffix: str
    timezone: str
    hass_access_token: str
    hass_url: str
    app_path: str
    install_pip_dependencies: bool
    astral: AstralConfig | None = None

    logs: dict[str, LoggingConfig] = field(default_factory=dict)

    def get_timezone(self) -> BaseTzInfo:
        return pytz.timezone(self.timezone)

    def get_astral_location(self) -> Location | None:
        if self.astral is None:
            return None

        return Location(
            LocationInfo(
                self.astral.name,
                self.astral.region,
                self.astral.timezone,
                self.astral.latitude,
                self.astral.longitude,
            ),
        )


def load_main_config_from_yaml(config: str, source: str) -> None:
    from domovoy.core.logging import get_logger

    get_logger(__name__).info(
        "Loading Configuration for Domovoy from: {source}",
        source=source,
    )

    main_config = from_yaml(MainConfig, config)

    if isinstance(main_config, MainConfig):
        pass
    elif len(main_config) == 1:
        main_config = main_config[0]
    else:
        get_logger(__name__).error("Configuration is not valid")
        return

    set_main_config(main_config)


_main_config = None


def set_main_config(config: MainConfig) -> None:
    global _main_config
    from domovoy.core.logging import get_logger

    if _main_config is not None:
        e = DomovoyError(
            "Main Config is already set. It cannot be set to a new value",
        )
        get_logger(__name__).exception(e)
        raise e

    _main_config = config


def get_main_config() -> MainConfig:
    if _main_config is None:
        raise DomovoyError("Main configuration has not been set")

    return _main_config
