from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Concatenate, ParamSpec

from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppWrapper
from domovoy.core.context import context_callback_id, context_logger
from domovoy.core.logging import get_logger
from domovoy.plugins import callbacks
from domovoy.plugins.hass.exceptions import HassUnknownEntityError
from domovoy.plugins.plugins import AppPlugin

from .core import EntityState, HassCore
from .entities import HassSyntheticPlatforms
from .exceptions import HassApiCommandError
from .synthetic import HassSyntheticDomainsServiceCalls
from .types import HassData, HassValue

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
        self.entities = HassSyntheticPlatforms()

    def prepare(self) -> None:
        super().prepare()
        self.__callbacks = self._wrapper.get_pluginx(callbacks.CallbacksPlugin)

    def get_state(self, entity_id: str) -> str:
        full_state = self.get_full_state(entity_id)
        return full_state.state

    def get_full_state(self, entity_id: str) -> EntityState:
        entity_state = self.__hass.get_state(entity_id)

        if entity_state is None:
            raise HassUnknownEntityError(entity_id)

        return entity_state

    def warn_if_entity_doesnt_exists(self, entity_id: str | list[str] | None) -> None:
        if entity_id is None:
            return

        if isinstance(entity_id, str):
            entity_id = [entity_id]

        for eid in entity_id:
            if not self.__hass.entity_exists_in_cache(eid):
                _missing_entities_logger.warning(
                    "[{app_name}] '{entity_id}' doesn't exist in Hass.",
                    entity_id=eid,
                    app_name=self._wrapper.app_name,
                )

    def get_entity_id_by_attribute(
        self,
        attribute: str,
        value: str | None,
    ) -> list[str]:
        return self.__hass.get_entity_id_by_attribute(attribute, value)

    def get_all_entities(self) -> list[EntityState]:
        return self.__hass.get_all_entities()

    def get_all_entity_ids(self) -> frozenset[str]:
        return self.__hass.get_all_entity_ids()

    async def fire_event(
        self,
        event_type: str,
        event_data: HassData | None = None,
    ) -> None:
        await self.__hass.fire_event(event_type, event_data)

    async def get_service_definitions(self) -> HassData:
        return await self.__hass.get_service_definitions()

    async def listen_trigger(
        self,
        trigger: HassData,
        callback: Callable[Concatenate[HassData, P], None | Awaitable[None]],
        oneshot: bool = False,  # noqa: FBT001, FBT002
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def listen_trigger_callback(
            subscription_id: int,
            trigger_vars: HassData,
        ) -> None:
            self._wrapper.logger.debug(
                "Calling Listen Trigger Callback: {cls_name}.{func_name} from callback_id: {subscription_id}",
                cls_name=callback.__self__.__class__.__name__,
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
        service_name_segments = service_name.split(".")

        if len(service_name_segments) != 2:
            self._wrapper.logger.error(
                "Cannot call service {service_name}. Invalid service name",
                service_name=service_name,
            )
            return None

        domain = service_name_segments[0]
        service = service_name_segments[1]

        entity_id: str | list[str] | None = None
        if "entity_id" in kwargs and ("domovoy_drop_target" not in kwargs or not kwargs["domovoy_drop_target"]):
            # We add the ignore because there is no easy way
            # to restrict the typing of kwargs until python 3.12
            entity_id = kwargs["entity_id"]  # type: ignore

            if (
                entity_id is None
                or (isinstance(entity_id, list) and not all(isinstance(sub, str) for sub in entity_id))
                or (not isinstance(entity_id, str) and not isinstance(entity_id, list))
            ):
                self._wrapper.logger.error(
                    "Cannot call service `{service_name}`. The `entity_id` key has an invalid type."
                    " Only `str` or `list[str]` are allowed. If passing a list, make sure all the elements are str",
                    service_name=service_name,
                )
                return None

            kwargs.pop("entity_id")

        if "domovoy_drop_target" in kwargs:
            kwargs.pop("domovoy_drop_target")

        if "service_data_entity_id" in kwargs:
            val = kwargs["service_data_entity_id"]
            kwargs.pop("service_data_entity_id")
            self.warn_if_entity_doesnt_exists(str(val) if val else None)
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
            if throw_on_error:
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
        entity_id: str,
        states: str | list[str],
        duration: Interval | None = None,
        timeout: Interval | None = None,
    ) -> None:
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
        entity_id: str,
        states: str | list[str],
        duration: Interval | None = None,
    ) -> asyncio.Future[None]:
        future = asyncio.get_event_loop().create_future()

        if isinstance(states, str):
            states = [states]

        async def state_callback(
            entity: str,
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
        return await self.__hass.search_related(item_type, item_id)

    async def send_raw_command(self, command_type: str, command_args: HassData) -> HassData | list[HassData]:
        return await self.__hass.send_raw_command(command_type, command_args)
