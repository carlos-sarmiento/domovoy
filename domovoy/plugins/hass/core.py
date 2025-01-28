from __future__ import annotations

import asyncio
import datetime
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, ParamSpec

from domovoy.applications.types import Interval
from domovoy.core.logging import get_logger
from domovoy.core.services.event_listener import EventListener
from domovoy.core.services.service import DomovoyService, DomovoyServiceResources
from domovoy.core.task_utils import run_and_forget_task
from domovoy.plugins.hass.domains import get_type_instance_for_entity_id

from .api import HassApiConnectionState, HassWebsocketApi
from .exceptions import HassApiCommandError
from .types import EntityID, HassData, PrimitiveHassValue

_logcore = get_logger(__name__)

P = ParamSpec("P")


@dataclass(frozen=True)
class EntityState:
    entity_id: EntityID
    state: PrimitiveHassValue
    last_changed: datetime.datetime
    last_updated: datetime.datetime
    raw_data: HassData
    attributes: HassData = field(default_factory=dict)
    context: HassData = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntityState:
        return EntityState(
            entity_id=get_type_instance_for_entity_id(data["entity_id"]),
            state=data["state"],
            last_changed=data["last_changed"],
            last_updated=data["last_updated"],
            attributes=data["attributes"],
            context=data["context"],
            raw_data=data,
        )

    def to_dict(self) -> HassData:
        return self.raw_data

    def get_time_in_current_state(self) -> datetime.timedelta:
        now = datetime.datetime.now(tz=datetime.UTC)
        return now - self.last_changed

    def has_been_in_state_for_at_least(
        self,
        target_states: PrimitiveHassValue | Sequence[PrimitiveHassValue],
        interval: Interval,
    ) -> bool:
        if not interval.is_valid():
            raise ValueError("Hours, minutes and seconds cannot be all zero")

        entity_state = self.state

        target_states = (
            list(target_states)
            if isinstance(target_states, Sequence) and not isinstance(target_states, str)
            else [target_states]
        )

        if entity_state not in target_states:
            return False

        duration = interval.to_timedelta()
        now = datetime.datetime.now(tz=datetime.UTC)
        minimum_time = self.last_changed + duration

        _logcore.trace(
            "hass_been_in_state_calculation {vals}",
            vals={
                "entity_id": self.entity_id,
                "target_states": target_states,
                "duration": duration,
                "now": now.isoformat(),
                "last_changed": self.last_changed.isoformat(),
                "minimum_time": minimum_time.isoformat(),
                "return_value": now >= minimum_time,
            },
        )

        return now >= minimum_time

    def has_been_in_current_state_for_at_least(
        self,
        interval: Interval,
    ) -> bool:
        return self.has_been_in_state_for_at_least(self.state, interval)


class HassCore(DomovoyService):
    __event_publisher: EventListener
    __hass_api: HassWebsocketApi
    __entity_state_cache: dict[EntityID, EntityState]
    __state_subscription_id: int | None = None
    __start_future: asyncio.Future[None] | None = None
    __resources: DomovoyServiceResources
    __is_running: bool = False
    __reload_reason: Literal["init", "hass_restart", "disconnected"] | None = "init"

    def __init__(
        self,
        resources: DomovoyServiceResources,
        event_publisher: EventListener,
    ) -> None:
        super().__init__(resources)
        self.__entity_state_cache = {}
        self.__event_publisher = event_publisher
        self.__resources = resources

    async def __is_hass_up(self) -> bool:
        try:
            is_hass_up_state = await self.send_raw_command("servent/hass-state", {})
            return is_hass_up_state["is_hass_up"]  # type: ignore
        except HassApiCommandError:
            return False

    async def __connection_state_updated(
        self,
        connection_state: HassApiConnectionState,
    ) -> None:
        if connection_state == HassApiConnectionState.CONNECTED:
            _logcore.info(
                "Subscribing to all events from Home Assistant. Is Running: {is_running}. Reload Reason: {reason}",
                is_running=self.__is_running,
                reason=self.__reload_reason,
            )
            self.__state_subscription_id = await self.__hass_api.subscribe_events(
                self.__all_events_callback,
            )

            if self.__is_running and self.__reload_reason == "init":
                await self.setup()
                self.__reload_reason = None

            if self.__is_running and self.__reload_reason == "disconnected":
                is_hass_up = await self.__is_hass_up()

                if not is_hass_up:
                    count = 0
                    _logcore.info("Waiting to make sure HA is fully initialized (max 5 minutes wait)")

                    while not is_hass_up and count < 300:
                        await asyncio.sleep(0.5)  # We are waiting for HASS to fully start
                        is_hass_up = await self.__is_hass_up()
                        count += 0.5

                    if not is_hass_up:
                        _logcore.warn("Home Assistant is not up yet. Continuing Initialization")

                await self.start_apps()
                self.__reload_reason = None

        elif connection_state == HassApiConnectionState.DISCONNECTED:
            self.__hass_api.stop()

            if self.__is_running and self.__reload_reason is None:
                _logcore.warning("Unexpected Disconnection from Home Assistant")
                self.__reload_reason = "disconnected"
                await self.__resources.stop_dependent_apps_callback()

            if self.__is_running:
                self.__connect_to_hass()

    async def start_apps(self) -> None:
        await self.setup()
        await self.__resources.start_dependent_apps_callback()

    async def setup(self) -> None:
        _logcore.info("Loading state for all entities in Home Assistant")
        starting_states = await self.__hass_api.get_states()

        for state in starting_states:
            entity_id = get_type_instance_for_entity_id(state["entity_id"])  # type: ignore
            # We need to validate this is later than what we already have
            self.__update_entity_state_cache(entity_id, EntityState.from_dict(state))

        if self.__start_future is not None and not self.__start_future.done():
            self.__start_future.set_result(None)

    def start(self) -> asyncio.Future[None]:
        _logcore.info("Starting HassCore")
        self.__is_running = True
        self.__connect_to_hass()
        self.__start_future = asyncio.get_event_loop().create_future()

        return self.__start_future

    def __connect_to_hass(self) -> None:
        self.__hass_api = HassWebsocketApi(
            self.__resources.config["hass_url"],
            self.__resources.config["hass_access_token"],
            self.__connection_state_updated,
        )
        self.__hass_api.start()

    async def stop(self) -> None:
        _logcore.info("Stopping HassCore")
        self.__is_running = False
        if self.__state_subscription_id is not None:
            try:
                async with asyncio.timeout(10):
                    await self.__hass_api.unsubscribe_events(
                        self.__state_subscription_id,
                    )

            except TimeoutError:
                _logcore.warning("Failed to gracefully unsubscribe from HA")

        self.__hass_api.stop()

    async def __all_events_callback(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        if event_type == "homeassistant_started" and self.__reload_reason == "hass_restart":
            _logcore.warning(
                "Received Homeassistant started event. Starting any stopped app that use Hass API",
            )
            self.__reload_reason = None
            run_and_forget_task(self.start_apps())

        if event_type == "homeassistant_stop" and self.__reload_reason is None:
            _logcore.warning(
                "Received Homeassistant Stop event. Stopping all apps that use Hass API",
            )
            self.__reload_reason = "hass_restart"
            await self.__resources.stop_dependent_apps_callback()

        if event_type == "state_changed":
            try:
                await self.__process_state_changed(event_data)
                await self.__event_publisher.publish_event(
                    f"{event_type}={event_data['entity_id']}",
                    event_data,
                )

            except Exception as e:
                _logcore.exception(
                    "Error when processing {event_data}",
                    e,
                    event_data=event_data,
                )
        await self.__event_publisher.publish_event(event_type, event_data)

    async def __process_state_changed(self, event_data: dict[str, HassData]) -> None:
        entity_id = get_type_instance_for_entity_id(str(event_data["entity_id"]))

        if event_data.get("new_state") is None:
            _logcore.trace(
                "No New State received for `state_changed` event for {entity_id}, event_data {event_data}",
                entity_id=entity_id,
                event_data=event_data,
            )
            self.__pop_entity_state_cache(entity_id)
            return

        new_entity_data = EntityState.from_dict(event_data["new_state"])

        if entity_id not in self.__entity_state_cache:
            self.__update_entity_state_cache(entity_id, new_entity_data)
            return

        if self.__entity_state_cache[entity_id].last_updated > new_entity_data.last_updated:
            _logcore.critical(
                "Tried to replace a newer state on entity_cache with an older state. "
                f"Original State Date: {self.__entity_state_cache[entity_id].last_updated.isoformat()} "
                f"Updated State Date: {new_entity_data.last_updated.isoformat()} "
                f"Original State: {self.__entity_state_cache[entity_id]}. "
                f"Updated State: {new_entity_data}",
            )
            return

        if self.__entity_state_cache[entity_id].last_updated == new_entity_data.last_updated:
            return

        self.__update_entity_state_cache(entity_id, new_entity_data)

    def __update_entity_state_cache(self, entity_id: EntityID, entity_data: EntityState) -> None:
        if isinstance(entity_id, str):
            _logcore.warning("Tried to register a string as an EntityID: '{entity_id}'", entity_id=entity_id)
            entity_id = get_type_instance_for_entity_id(entity_id)

        self.__entity_state_cache[entity_id] = entity_data

    def __pop_entity_state_cache(self, entity_id: EntityID) -> None:
        self.__entity_state_cache.pop(entity_id)

    def get_state(self, entity_id: EntityID) -> EntityState | None:
        return self.__entity_state_cache.get(entity_id, None)

    def entity_exists_in_cache(self, entity_id: EntityID) -> bool:
        return entity_id in self.__entity_state_cache

    def get_entity_id_by_attribute(self, attribute: str, value: PrimitiveHassValue | None) -> list[EntityID]:
        return [
            x.entity_id
            for x in self.__entity_state_cache.values()
            if attribute in x.attributes and (value is None or x.attributes[attribute] == value)  # type: ignore
        ]

    def get_all_entities(self) -> list[EntityState]:
        return list(self.__entity_state_cache.values())

    def get_all_entity_ids(self) -> frozenset[EntityID]:
        return frozenset(self.__entity_state_cache.keys())

    async def fire_event(
        self,
        event_type: str,
        event_data: HassData | None = None,
    ) -> None:
        await self.__hass_api.fire_event(event_type, event_data)

    async def unsubscribe_trigger(self, subscription_id: int) -> bool:
        return await self.__hass_api.unsubscribe_events(subscription_id)

    async def subscribe_trigger(
        self,
        callback: Callable[[int, HassData], Awaitable[None]],
        trigger: HassData,
    ) -> int:
        return await self.__hass_api.subscribe_trigger(callback, trigger)

    async def call_service(
        self,
        *,
        domain: str,
        service: str,
        service_data: HassData | None = None,
        entity_id: EntityID | list[EntityID] | None = None,
        return_response: bool = False,
    ) -> HassData | None:
        return await self.__hass_api.call_service(
            domain=domain,
            service=service,
            service_data=service_data,
            entity_id=entity_id,
            return_response=return_response,
        )

    async def get_service_definitions(self) -> HassData:
        return await self.__hass_api.get_services()

    async def search_related(
        self,
        item_type: str,
        item_id: str,
    ) -> HassData:
        return await self.__hass_api.search_related(item_type, item_id)

    async def send_raw_command(self, command_type: str, command_args: HassData) -> HassData | list[HassData]:
        return await self.__hass_api.send_command(command_type, command_args)
