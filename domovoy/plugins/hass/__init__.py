from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Concatenate, ParamSpec

from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppStatus, AppWrapper
from domovoy.core.context import context_callback_id, context_logger
from domovoy.core.logging import get_logger
from domovoy.plugins import callbacks
from domovoy.plugins.hass.domains import (
    get_type_instance_for_entity_id,
)
from domovoy.plugins.hass.exceptions import HassUnknownEntityError
from domovoy.plugins.plugins import AppPlugin
from synthetic.services import HassSyntheticDomainsServiceCalls

from .core import EntityState, HassCore
from .exceptions import HassApiCommandError
from .types import EntityID, HassData, HassValue, PrimitiveHassValue

P = ParamSpec("P")

_missing_entities_logger = get_logger("missing_entitites")


@dataclass
class ServiceDetails:
    has_response: bool


class HassPlugin(AppPlugin):
    __hass: HassCore
    _wrapper: AppWrapper
    __callbacks: callbacks.CallbacksPlugin
    __cached_service_definitions: dict[str, ServiceDetails] | None = None

    def __init__(
        self,
        name: str,
        wrapper: AppWrapper,
        hass_core: HassCore,
    ) -> None:
        super().__init__(name, wrapper)
        self.__hass = hass_core
        self.services = HassSyntheticDomainsServiceCalls(self)

    def prepare(self) -> None:
        super().prepare()
        self.__callbacks = self._wrapper.get_pluginx(callbacks.CallbacksPlugin)

    def get_full_state(self, entity_id: EntityID) -> EntityState:
        """Get the complete state object for a Home Assistant entity.

        Args:
            entity_id: The EntityID to retrieve state for. Can also accept string for backwards compatibility.

        Returns:
            EntityState object containing state, attributes, last_changed, and last_updated.

        Raises:
            HassUnknownEntityError: If the entity does not exist in the state cache.

        """
        if isinstance(entity_id, str):
            entity_id = get_type_instance_for_entity_id(entity_id)

        entity_state = self.__hass.get_state(entity_id)

        if entity_state is None:
            raise HassUnknownEntityError(entity_id)

        return entity_state

    def warn_if_entity_doesnt_exists(self, entity_id: EntityID | Sequence[EntityID] | None) -> None:
        """Log a warning if the specified entity or entities don't exist in the Home Assistant cache.

        Useful for debugging typos in entity IDs during development.

        Args:
            entity_id: Single EntityID, sequence of EntityIDs, or None. If None, no action is taken.

        """
        if entity_id is None:
            return

        entity_id = wrap_entity_id_as_list(entity_id)

        for eid in entity_id:
            if not self.__hass.entity_exists_in_cache(eid):
                _missing_entities_logger.warning(
                    "[{app_name}] '{entity_id}' doesn't exist in Hass.",
                    entity_id=eid,
                    app_name=self._wrapper.get_app_name_for_logs(),
                )

    def get_entity_id_by_attribute(
        self,
        attribute: str,
        value: str | None,
    ) -> list[EntityID]:
        """Find all entities that have a specific attribute with the given value.

        Args:
            attribute: The name of the attribute to search for.
            value: The value to match. If None, returns entities that have the attribute regardless of value.

        Returns:
            List of EntityIDs that match the criteria.

        """
        return self.__hass.get_entity_id_by_attribute(attribute, value)

    def get_all_entities(self) -> list[EntityState]:
        """Get the complete state objects for all entities in the Home Assistant cache.

        Returns:
            List of EntityState objects for every entity known to Home Assistant.

        """
        return self.__hass.get_all_entities()

    def get_all_entity_ids(self) -> frozenset[EntityID]:
        """Get all entity IDs currently in the Home Assistant cache.

        Returns:
            Frozen set of EntityID objects representing all known entities.

        """
        return self.__hass.get_all_entity_ids()

    async def fire_event(
        self,
        event_type: str,
        event_data: HassData | None = None,
    ) -> None:
        """Fire a custom event on the Home Assistant event bus.

        Args:
            event_type: The type/name of the event to fire.
            event_data: Optional dictionary of data to include with the event.

        """
        await self.__hass.fire_event(event_type, event_data)

    async def get_service_definitions(self) -> HassData:
        """Retrieve service definitions from Home Assistant.

        Returns:
            Dictionary containing all available services and their schemas.

        """
        return await self.__hass.get_service_definitions()

    async def listen_trigger(
        self,
        trigger: HassData,
        callback: Callable[Concatenate[HassData, P], None | Awaitable[None]],
        oneshot: bool = False,  # noqa: FBT001, FBT002
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        """Subscribe to a Home Assistant trigger configuration.

        Triggers are HA's automation system primitives (state, numeric_state, time, etc.).

        Args:
            trigger: Dictionary containing the trigger configuration (e.g., {"platform": "state", "entity_id": "..."}).
            callback: Function to call when trigger fires. Receives trigger variables as first argument.
            oneshot: If True, unsubscribe after the first trigger event.
            *callback_args: Additional positional arguments to pass to callback.
            **callback_kwargs: Additional keyword arguments to pass to callback.

        Returns:
            Subscription ID string that can be used to cancel the trigger subscription.

        """
        context_logger.set(self._wrapper.logger)

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def listen_trigger_callback(
            subscription_id: int,
            trigger_vars: HassData,
        ) -> None:
            self._wrapper.logger.trace(
                "Calling Listen Trigger Callback: {cls_name}.{func_name} from callback_id: {subscription_id}",
                cls_name=callback.__self__.__class__.__name__,  # type: ignore
                func_name=callback.__name__,
                subscription_id=subscription_id,
            )

            if oneshot:
                await self.__hass.unsubscribe_trigger(subscription_id)

            await instrumented_callback(
                subscription_id,
                trigger_vars,
                *callback_args,
                **callback_kwargs,
            )

        return str(
            await self.__hass.subscribe_trigger(
                listen_trigger_callback,
                trigger,
            ),
        )

    async def call_service(
        self,
        service_name: str,
        *,
        return_response: bool = False,
        throw_on_error: bool = False,
        **kwargs: HassValue,
    ) -> HassData | None:
        """Call a Home Assistant service.

        Prefer using the typed service stubs (self.services.domain.service_name) over this method.

        Args:
            service_name: Service to call in format "domain.service" (e.g., "light.turn_on").
            return_response: If True, wait for and return the service response data.
            throw_on_error: If True, raise exceptions on errors. If False, log errors without raising.
            **kwargs: Service data parameters. entity_id can be EntityID or list[EntityID].

        Returns:
            Service response data if return_response is True and service returns data, otherwise None.

        Raises:
            HassApiCommandError: If throw_on_error is True and service call fails.

        """
        service_name_segments = service_name.split(".")

        if len(service_name_segments) != 2:
            self._wrapper.logger.error(
                "Cannot call service {service_name}. Invalid service name",
                service_name=service_name,
            )
            return None

        domain = service_name_segments[0]
        service = service_name_segments[1]

        entity_id: EntityID | list[EntityID] | None = None
        if "entity_id" in kwargs and ("domovoy_drop_target" not in kwargs or not kwargs["domovoy_drop_target"]):
            # We add the ignore because there is no easy way
            # to restrict the typing of kwargs until python 3.12
            entity_id = kwargs["entity_id"]  # type: ignore

            if (
                entity_id is None
                or (isinstance(entity_id, list) and not all(isinstance(sub, EntityID) for sub in entity_id))
                or (not isinstance(entity_id, EntityID) and not isinstance(entity_id, list))
            ):
                self._wrapper.logger.error(
                    "Cannot call service `{service_name}`. The `entity_id` key has an invalid type."
                    " Only `EntityID` or `list[EntityID]` are allowed. If passing a list, make sure "
                    "all the elements are EntityID. {entity_id}",
                    service_name=service_name,
                    entity_id=entity_id,
                )
                return None

            kwargs.pop("entity_id")

        if "domovoy_drop_target" in kwargs:
            kwargs.pop("domovoy_drop_target")

        if "service_data_entity_id" in kwargs:
            val = get_type_instance_for_entity_id(str(kwargs["service_data_entity_id"]))
            kwargs.pop("service_data_entity_id")
            self.warn_if_entity_doesnt_exists(val if val else None)
            kwargs["entity_id"] = val

        self.warn_if_entity_doesnt_exists(entity_id)

        try:
            return await self.__hass.call_service(
                domain=domain,
                service=service,
                service_data=kwargs,
                entity_id=entity_id,
                return_response=return_response,
            )
        except HassApiCommandError as e:
            if throw_on_error or self._wrapper.status == AppStatus.INITIALIZING:
                raise

            if e.message == "Service call requires responses but caller did not ask for responses":
                return await self.call_service(
                    service_name,
                    return_response=True,
                    throw_on_error=throw_on_error,
                    **kwargs,
                )

            self._wrapper.logger.error(
                "There was an error when executing the command. "
                "Exception was not raised to app. Message: {exception_message}",
                exception_message=str(e),
            )

    async def wait_for_state_to_be(
        self,
        entity_id: EntityID,
        states: str | list[str],
        duration: Interval | None = None,
        timeout: Interval | None = None,  # noqa: ASYNC109
    ) -> None:
        """Asynchronously wait for an entity to reach one of the specified states.

        This is an awaitable method that blocks until the condition is met or timeout occurs.

        Args:
            entity_id: The entity to monitor.
            states: Single state string or list of state strings to wait for.
            duration: If specified, entity must stay in the target state for this duration.
            timeout: Optional timeout interval. Raises asyncio.TimeoutError if exceeded.

        Raises:
            asyncio.TimeoutError: If timeout is specified and exceeded before condition is met.

        """
        if timeout is None:
            await self.__wait_for_state_to_be_implementation(
                entity_id,
                states,
                duration,
            )
        else:
            async with asyncio.timeout(timeout.total_seconds()):
                await self.__wait_for_state_to_be_implementation(
                    entity_id,
                    states,
                    duration,
                )

    def __wait_for_state_to_be_implementation(
        self,
        entity_id: EntityID,
        states: str | list[str],
        duration: Interval | None = None,
    ) -> asyncio.Future[None]:
        future = asyncio.get_event_loop().create_future()

        if isinstance(states, str):
            states = [states]

        async def state_callback(
            entity: EntityID,
            _attribute: str,
            _old: HassValue,
            new: HassValue,
        ) -> None:
            callback_id: str = context_callback_id.get()  # type: ignore

            if new in states and not future.done():
                entity_full_state = self.get_full_state(entity)
                if duration is not None and not entity_full_state.has_been_in_current_state_for_at_least(
                    duration,
                ):
                    await asyncio.sleep(
                        (duration.to_timedelta() - entity_full_state.get_time_in_current_state()).total_seconds() + 0.5,
                    )

                    if not self.get_full_state(
                        entity,
                    ).has_been_in_current_state_for_at_least(duration):
                        return

                self.__callbacks.cancel_callback(callback_id)
                future.set_result(None)

        self.__callbacks.listen_state_extended(entity_id, state_callback, immediate=True)

        return future

    async def _get_cached_service_definitions(self, *, reset: bool = False) -> dict[str, ServiceDetails]:
        if self.__cached_service_definitions is None or reset is True:
            domains: dict[str, Any] = await self.get_service_definitions()

            service_definitions = {}

            for domain, services in sorted(domains.items()):
                for service, details in sorted(services.items()):
                    service_definitions[f"{domain}.{service}"] = ServiceDetails(has_response="response" in details)

            self.__cached_service_definitions = service_definitions

        return self.__cached_service_definitions

    async def search_related(
        self,
        item_type: str,
        item_id: str,
    ) -> HassData:
        """Search for entities and items related to a specific Home Assistant item.

        Args:
            item_type: Type of item to search for (e.g., "entity", "device", "area").
            item_id: The ID of the item to find relations for.

        Returns:
            Dictionary containing related items organized by type.

        """
        return await self.__hass.search_related(item_type, item_id)

    async def send_raw_command(self, command_type: str, command_args: HassData) -> HassData | list[HassData]:
        """Send a raw WebSocket command directly to Home Assistant.

        This is a low-level method for advanced use cases not covered by other plugin methods.

        Args:
            command_type: The WebSocket command type to send.
            command_args: Dictionary of arguments for the command.

        Returns:
            The response from Home Assistant, either a single data dict or list of dicts.

        """
        return await self.__hass.send_raw_command(command_type, command_args)

    def get_typed_state[T](self, entity_id: EntityID[T]) -> T | None:
        """Get the state of an entity, cast to the entity's native type.

        Uses the EntityID's type information to parse and cast the state value.

        Args:
            entity_id: Typed EntityID that includes parsing logic for its domain.

        Returns:
            State value cast to the appropriate type, or None if parsing fails.

        """
        full_state: EntityState = self.get_full_state(entity_id)
        return entity_id.parse_state_typed(full_state)

    def get_state(self, entity_id: EntityID) -> PrimitiveHassValue:
        """Get the current state value of an entity.

        Returns only the state value, not the full EntityState object.

        Args:
            entity_id: The entity to get state for.

        Returns:
            The entity's current state as a primitive value (str, int, float, or bool).

        """
        return self.get_full_state(entity_id).state


def wrap_entity_id_as_list(val: EntityID | Sequence[EntityID]) -> list[EntityID]:
    """Convert a single EntityID or sequence of EntityIDs into a list.

    Utility function to normalize entity ID arguments that can be either single or multiple values.

    Args:
        val: Single EntityID or sequence of EntityIDs.

    Returns:
        List containing the EntityID(s).

    """
    if isinstance(val, Sequence):
        return list(val)

    return [val]
