import functools
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import TypeVar

from domovoy.core.configuration import MainConfig, get_main_config


def get_datetime_now_with_config_timezone() -> datetime:
    config: MainConfig = get_main_config()
    return datetime.now(config.get_timezone())


def as_float(x: str, default: float | None = None) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def as_int(x: str, default: int | None = None) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def is_datetime_aware(dt: datetime) -> bool:
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


def parse_state(state: str) -> int | float | str:
    int_val = as_float(state)
    if int_val is not None:
        return int_val

    float_val = as_float(state)
    if float_val is not None:
        return float_val

    return state


T = TypeVar("T")


def strip_none_and_enums_from_containers(data: T) -> T:
    if isinstance(data, dict):
        return {k: strip_none_and_enums_from_containers(v) for k, v in data.items() if k is not None and v is not None}  # type: ignore[return-value]

    if isinstance(data, list):
        return [strip_none_and_enums_from_containers(item) for item in data if item is not None]  # type: ignore[return-value]

    if isinstance(data, tuple):
        return tuple(strip_none_and_enums_from_containers(item) for item in data if item is not None)  # type: ignore[return-value]

    if isinstance(data, set):
        return {strip_none_and_enums_from_containers(item) for item in data if item is not None}  # type: ignore[return-value]

    if isinstance(data, StrEnum):
        return data.value  # type: ignore[return-value]

    return data


def get_true_callback_if_functools(callback: Callable) -> Callable:
    if isinstance(callback, functools.partial):
        return callback.func

    return callback


def get_callback_true_name(callback: Callable) -> str:
    callback = get_true_callback_if_functools(callback)
    try:
        return callback._true_name  # type: ignore[attr-defined]  # noqa: SLF001
    except AttributeError:
        return callback.__name__


def get_callback_true_class(callback: Callable) -> str:
    callback = get_true_callback_if_functools(callback)
    try:
        return callback._true_class  # type: ignore[attr-defined]  # noqa: SLF001
    except AttributeError:
        return get_callback_class(callback)


def get_callback_class(callback: Callable) -> str:
    callback = get_true_callback_if_functools(callback)
    try:
        if hasattr(callback, "__self__"):
            return callback.__self__.__class__.__name__  # type: ignore
        if hasattr(callback, "__class__"):
            return callback.__class__.__name__
        return callback.__name__  # type: ignore[attr-defined]
    except AttributeError:
        return callback.__name__


def set_callback_true_information(callback: Callable, true_callback: Callable) -> None:
    callback._true_name = get_callback_true_name(true_callback)  # type: ignore[attr-defined]  # noqa: SLF001
    callback._true_class = get_callback_class(true_callback)  # type: ignore[attr-defined]  # noqa: SLF001


def get_callback_name(callback: Callable) -> str:
    name = get_callback_true_name(callback)
    class_name = get_callback_true_class(callback)

    return f"{class_name}.{name}"
