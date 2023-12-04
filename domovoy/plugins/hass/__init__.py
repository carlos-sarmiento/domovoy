from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Concatenate, ParamSpec

from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppWrapper
from domovoy.core.context import context_callback_id, context_logger
from domovoy.plugins import callbacks
from domovoy.plugins.hass.exceptions import HassUnknownEntityError
from domovoy.plugins.plugins import AppPlugin

from .core import EntityState, HassCore
from .synthetic import HassSyntheticDomainsServiceCalls
from .types import HassApiDataDict, HassApiValue

P = ParamSpec("P")


class HassPlugin(AppPlugin):
    __hass: HassCore
    _wrapper: AppWrapper
    __callbacks: callbacks.CallbacksPlugin

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

    def get_state(self, entity_id: str) -> str:
        full_state = self.get_full_state(entity_id)
        return full_state.state

    def get_full_state(self, entity_id: str) -> EntityState:
        entity_state = self.__hass.get_state(entity_id)

        if entity_state is None:
            raise HassUnknownEntityError(entity_id)

        return entity_state

    def get_entity_id_by_attribute(
        self, attribute: str, value: str | None,
    ) -> list[str]:
        return self.__hass.get_entity_id_by_attribute(attribute, value)

    async def fire_event(
        self, event_type: str, event_data: HassApiDataDict | None = None,
    ) -> None:
        await self.__hass.fire_event(event_type, event_data)

    async def get_service_definitions(self) -> HassApiDataDict:
        return await self.__hass.get_service_definitions()

    async def listen_trigger(
        self,
        trigger: HassApiDataDict,
        callback: Callable[Concatenate[HassApiDataDict, P], None | Awaitable[None]],
        oneshot: bool = False,
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def listen_trigger_callback(
            subscription_id: int, trigger_vars: HassApiDataDict,
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
                subscription_id, trigger_vars, *callback_args, **callback_kwargs,
            )

        return str(
            await self.__hass.subscribe_trigger(
                listen_trigger_callback,
                trigger,
            ),
        )

    async def call_service(
        self, service_name: str, **kwargs: HassApiValue,
    ) -> HassApiDataDict | None:
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
        if "entity_id" in kwargs and (
            "domovoy_drop_target" not in kwargs or not kwargs["domovoy_drop_target"]
        ):
            # We add the ignore because there is no easy way
            # to restrict the typing of kwargs until python 3.12
            entity_id = kwargs["entity_id"]  # type: ignore

            if (
                entity_id is None
                or (
                    isinstance(entity_id, list)
                    and not all(isinstance(sub, str) for sub in entity_id)
                )
                or (not isinstance(entity_id, str) and not isinstance(entity_id, list))
            ):
                self._wrapper.logger.error(
                    "Cannot call service `{service_name}`. The `entity_id` key has an invalid type."
                    + " Only `str` or `list[str]` are allowed. If passing a list, make sure all the elements are str",
                    service_name=service_name,
                )
                return None

            kwargs.pop("entity_id")

        if "domovoy_drop_target" in kwargs:
            kwargs.pop("domovoy_drop_target")

        if "service_data_entity_id" in kwargs:
            val = kwargs["service_data_entity_id"]
            kwargs.pop("service_data_entity_id")
            kwargs["entity_id"] = val

        return await self.__hass.call_service(
            domain=domain, service=service, service_data=kwargs, entity_id=entity_id,
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
                entity_id, states, duration,
            )
        else:
            async with asyncio.timeout(timeout.total_seconds()):
                await self.__wait_for_state_to_be_implementation(
                    entity_id, states, duration,
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

        async def state_callback(entity, attribute, old, new):
            callback_id: str = context_callback_id.get()  # type: ignore

            if new in states and not future.done():
                entity_full_state = self.get_full_state(entity)
                if (
                    duration is not None
                    and not entity_full_state.has_been_in_current_state_for_at_least(
                        duration,
                    )
                ):
                    await asyncio.sleep(
                        (
                            duration.to_timedelta()
                            - entity_full_state.get_time_in_current_state()
                        ).total_seconds()
                        + 0.5,
                    )

                    if not self.get_full_state(
                        entity,
                    ).has_been_in_current_state_for_at_least(duration):
                        return

                self.__callbacks.cancel_callback(callback_id)
                future.set_result(None)

        self.__callbacks.listen_state(entity_id, state_callback, immediate=True)

        return future
