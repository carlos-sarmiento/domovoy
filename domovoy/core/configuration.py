from __future__ import annotations

import datetime
import logging
import sys
from dataclasses import dataclass, field
from typing import TextIO

import pytz
from astral import LocationInfo
from astral.location import Location
from dataclass_wizard import YAMLWizard

from domovoy.core.errors import DomovoyError


@dataclass(frozen=True)
class MainConfig(YAMLWizard):
    app_suffix: str
    timezone: str
    hass_access_token: str
    hass_url: str
    app_path: str
    install_pip_dependencies: bool
    astral: AstralConfig | None = None

    logs: dict[str, LoggingConfig] = field(default_factory=dict)
    # plugins: dict[str, dict[str, Any]] = field(default_factory=dict)  # noqa: ERA001

    def get_timezone(self) -> datetime.tzinfo:
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


@dataclass
class AstralConfig:
    name: str
    region: str
    timezone: str
    latitude: float
    longitude: float


@dataclass
class LoggingConfig:
    log_level: str | None = "info"
    output_filename: str | None = None
    write_to_stdout: bool | None = True
    formatter: str | None = "[%(asctime)s][%(levelname)s][%(name)s]  %(message)s"
    formatter_with_app_name: str | None = "[%(asctime)s][%(levelname)s][%(name)s][%(app_name)s]  %(message)s"

    def get_actual_output_stream(self) -> TextIO | None:
        if self.write_to_stdout is None or self.write_to_stdout is True:
            return sys.stdout

        if self.write_to_stdout is False:
            return None

        msg = f"Invalid value for output_stream: {self.write_to_stdout}"
        raise ValueError(msg)

    def get_numeric_log_level(self) -> int:
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

        return 0

    def __add__(self, b: LoggingConfig) -> LoggingConfig:
        result = LoggingConfig(
            log_level=self.log_level,
            output_filename=self.output_filename,
            write_to_stdout=self.write_to_stdout,
            formatter=self.formatter,
            formatter_with_app_name=self.formatter_with_app_name,
        )

        if b.log_level is not None:
            result.log_level = b.log_level

        if b.output_filename is not None:
            result.output_filename = b.output_filename

        if b.write_to_stdout is not None:
            result.write_to_stdout = b.write_to_stdout

        if b.formatter is not None:
            result.formatter = b.formatter

        if b.formatter_with_app_name is not None:
            result.formatter_with_app_name = b.formatter_with_app_name

        return result


def load_main_config_from_yaml(config: str, source: str) -> None:
    from domovoy.core.logging import get_logger

    get_logger(__name__).info(
        "Loading Configuration for Domovoy from: {source}",
        source=source,
    )

    main_config = MainConfig.from_yaml(config)

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
