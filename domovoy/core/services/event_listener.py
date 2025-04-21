from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from domovoy.core.logging import get_logger
from domovoy.core.services.service import DomovoyService, DomovoyServiceResources

_logcore = get_logger(__name__)


@dataclass(frozen=True)
class ListenerRegistration:
    id: str
    events: list[str] = field(compare=False)
    callable: Callable[[str, str, dict[str, Any]], Awaitable[None]] = field(
        compare=False,
    )


class EventListener(DomovoyService):
    __registered_callbacks_by_event: dict[str, dict[str, ListenerRegistration]]
    __registered_callbacks_by_id: dict[str, ListenerRegistration]
    __is_running: bool = False
    __running_callbacks: set[asyncio.Future[Any]]

    def __init__(self, resources: DomovoyServiceResources) -> None:
        super().__init__(resources)
        self.__registered_callbacks_by_event = {}
        self.__registered_callbacks_by_id = {}
        self.__running_callbacks = set()

    def start(self) -> None:
        _logcore.info("Starting EventListener")
        self.__is_running = True

    def stop(self) -> None:
        _logcore.info("Stopping EventListener")
        self.__is_running = False

    async def publish_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        _logcore.trace(
            "Publishing event: {event_name} with data: {event_data}",
            event_name=event_name,
            event_data=event_data,
        )

        if not self.__is_running:
            _logcore.trace(
                "Attempted to publish an event, but the EventListener is not running",
            )
            return

        if event_name not in self.__registered_callbacks_by_event:
            _logcore.trace(
                "No listeners are registered for event: {event_name}",
                event_name=event_name,
            )
            return  # No listener for this event

        callbacks = self.__registered_callbacks_by_event[event_name]

        async_calls: list[Awaitable[None]] = [
            callback.callable(callback.id, event_name, event_data) for callback in callbacks.values()
        ]

        _logcore.trace(
            "Gathering all async callbacks for event {event_name}",
            event_name=event_name,
        )

        task = asyncio.ensure_future(asyncio.gather(*async_calls))
        self.__running_callbacks.add(task)
        task.add_done_callback(lambda t: self.__running_callbacks.remove(t))

    def add_listener(
        self,
        events: str | list[str],
        callback: Callable[[str, str, dict[str, Any]], Awaitable[None]],
        listener_id: str | None = None,
    ) -> str:
        _logcore.trace(
            "Adding a listener for event(s): {events}",
            events=events,
        )

        if listener_id is None:
            listener_id = uuid.uuid4().hex

        if isinstance(events, str):
            events = [events]

        registration = ListenerRegistration(listener_id, events, callback)

        self.__registered_callbacks_by_id[listener_id] = registration
        for event in events:
            if event not in self.__registered_callbacks_by_event:
                self.__registered_callbacks_by_event[event] = {}

            self.__registered_callbacks_by_event[event][listener_id] = registration

        return listener_id

    def remove_listener(self, listener_id: str, *, is_app_failed: bool) -> None:
        _logcore.trace(
            "Removing listener with id: {listener_id}",
            listener_id=listener_id,
        )

        registration = self.__registered_callbacks_by_id.get(listener_id, None)
        if not registration:
            if not is_app_failed:
                _logcore.error(
                    "There was no listener with id: {listener_id} registered",
                    listener_id=listener_id,
                )
            return

        self.__registered_callbacks_by_id.pop(listener_id)

        for event in registration.events:
            wrap = self.__registered_callbacks_by_event[event]
            wrap.pop(listener_id)
