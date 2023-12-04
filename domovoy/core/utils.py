from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

import pytz

from domovoy.core.configuration import get_main_config


def get_datetime_now_with_config_timezone() -> datetime:
    config = get_main_config()
    return datetime.now(pytz.timezone(config.timezone))


def asFloat(x: Any, default: float | None = None) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def asInt(x: Any, default: int | None = None) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def parse_state(state: str) -> int | float | str:
    as_int = asFloat(state)
    if as_int is not None:
        return as_int

    as_float = asFloat(state)
    if as_float is not None:
        return as_float

    return state


def stripNoneAndEnums(data):
    if isinstance(data, dict):
        return {
            k: stripNoneAndEnums(v)
            for k, v in data.items()
            if k is not None and v is not None
        }
    elif isinstance(data, list):
        return [stripNoneAndEnums(item) for item in data if item is not None]
    elif isinstance(data, tuple):
        return tuple(stripNoneAndEnums(item) for item in data if item is not None)
    elif isinstance(data, set):
        return {stripNoneAndEnums(item) for item in data if item is not None}
    elif isinstance(data, StrEnum):
        return data.value
    else:
        return data


def get_callback_true_name(callback: Callable) -> str:
    try:
        return callback._true_name
    except AttributeError:
        return callback.__name__


def get_callback_true_class(callback: Callable) -> str:
    try:
        return callback._true_class
    except AttributeError:
        return "Unknown"


def get_callback_class(callback) -> str:
    try:
        return callback.__self__.__class__.__name__
    except AttributeError:
        return callback.__name__


def set_callback_true_information(callback: Callable, true_callback: Callable) -> None:
    callback._true_name = true_callback.__name__
    callback._true_class = get_callback_class(true_callback)


def get_callback_name(callback: Callable) -> str:
    name = get_callback_true_name(callback)
    class_name = get_callback_true_class(callback)

    return f"{class_name}.{name}"
