from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from domovoy.plugins.hass.types import HassValue

EventListenerCallbackEmpty = Callable[[], None | Awaitable[None]]


# Full Callback
class EventListenerCallbackFull(Protocol):
    def __call__(self, *, event_name: str, data: dict[str, HassValue]) -> None | Awaitable[None]: ...


# Single Parameter Callback
class EventListenerCallbackWithEventName(Protocol):
    def __call__(self, *, event_name: str) -> None | Awaitable[None]: ...


class EventListenerCallbackWithEventData(Protocol):
    def __call__(self, *, data: dict[str, HassValue]) -> None | Awaitable[None]: ...


EventListenerCallback = (
    EventListenerCallbackFull
    | EventListenerCallbackWithEventName
    | EventListenerCallbackWithEventData
    | EventListenerCallbackEmpty
)
