from __future__ import annotations

import asyncio
import datetime
import inspect
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Any, Concatenate, Literal, ParamSpec, TypeVar

from astral.location import Location
from dateutil.parser import parse

from domovoy.applications.types import Interval
from domovoy.core.configuration import get_main_config
from domovoy.core.context import context_logger
from domovoy.core.errors import DomovoySchedulerError
from domovoy.core.logging import get_logger
from domovoy.core.utils import (
    get_callback_class,
    get_callback_name,
    get_callback_true_name,
    get_datetime_now_with_config_timezone,
    is_datetime_aware,
    set_callback_true_information,
)
from domovoy.plugins import hass
from domovoy.plugins.callbacks.entity_listener_callbacks import EntityListenerCallback
from domovoy.plugins.callbacks.event_listener_callbacks import EventListenerCallback
from domovoy.plugins.hass.domains import get_type_instance_for_entity_id
from domovoy.plugins.hass.types import EntityID, HassValue
from domovoy.plugins.plugins import AppPlugin

if TYPE_CHECKING:
    from domovoy.core.app_infra import AppWrapper
    from domovoy.core.services.callback_register import CallbackRegister

P = ParamSpec("P")
T = TypeVar("T")

SunEvents = Literal["dawn", "sunrise", "noon", "sunset", "dusk"]
_logcore = get_logger(__name__)


class CallbacksPlugin(AppPlugin):
    _wrapper: AppWrapper
    __hass: hass.HassPlugin
    __register: CallbackRegister

    def __init__(
        self,
        name: str,
        wrapper: AppWrapper,
        register: CallbackRegister,
    ) -> None:
        super().__init__(name, wrapper)
        self.__register = register

    def prepare(self) -> None:
        self.__hass = self._wrapper.get_pluginx(hass.HassPlugin)

    def listen_event(
        self,
        events: str | list[str],
        callback: EventListenerCallback,
        *,
        oneshot: bool = False,
    ) -> str:
        signature = inspect.signature(callback)
        valid_params = set(signature.parameters.keys())

        async def wrapper(event_name: str, data: dict[str, Any]) -> None:
            call_args = {}
            if "event_name" in valid_params:
                call_args["event_name"] = event_name
            if "data" in valid_params:
                call_args["data"] = data

            result = callback(**call_args)

            if inspect.isawaitable(result):
                await result

        set_callback_true_information(wrapper, callback)
        return self.listen_event_extended(events, wrapper, oneshot)

    def listen_event_extended(
        self,
        events: str | list[str],
        callback: Callable[Concatenate[str, dict[str, Any], P], None | Awaitable[None]],
        oneshot: bool = False,  # noqa: FBT001, FBT002
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def listen_event_callback(
            callback_id: str,
            event: str,
            event_data: dict[str, Any],
        ) -> None:
            self._wrapper.logger.trace(
                "Calling Listen Event Callback: {cls_name}.{func_name} from callback_id: {callback_id}",
                cls_name=callback.__self__.__class__.__name__ if inspect.ismethod(callback) else callback.__class__,
                func_name=callback.__name__,
                callback_id=callback_id,
            )

            if oneshot:
                self.cancel_callback(callback_id)

            await instrumented_callback(
                callback_id,
                event,
                event_data,
                *callback_args,
                **callback_kwargs,
            )

        return self.__register.add_event_callback(
            self._wrapper,
            listen_event_callback,
            events,
        )

    def listen_state(
        self,
        entity_id: EntityID | Sequence[EntityID],
        callback: EntityListenerCallback,
        *,
        immediate: bool = False,
        oneshot: bool = False,
    ) -> list[str]:
        return self.listen_attribute(entity_id, "state", callback, immediate=immediate, oneshot=oneshot)

    def listen_attribute(
        self,
        entity_id: EntityID | Sequence[EntityID],
        attribute: str,
        callback: EntityListenerCallback,
        *,
        immediate: bool = False,
        oneshot: bool = False,
    ) -> list[str]:
        signature = inspect.signature(callback)
        valid_params = set(signature.parameters.keys())

        async def wrapper(entity_id: EntityID, attribute: str, old: HassValue, new: HassValue) -> None:
            call_args = {}
            if "entity_id" in valid_params:
                call_args["entity_id"] = entity_id
            if "attribute" in valid_params:
                call_args["attribute"] = attribute
            if "old" in valid_params:
                call_args["old"] = old
            if "new" in valid_params:
                call_args["new"] = new

            result = callback(**call_args)

            if inspect.isawaitable(result):
                await result

        set_callback_true_information(wrapper, callback)
        return self.listen_attribute_extended(entity_id, attribute, wrapper, immediate, oneshot)

    def listen_state_extended(
        self,
        entity_id: EntityID | list[EntityID],
        callback: Callable[
            Concatenate[EntityID, str, HassValue, HassValue, P],
            None | Awaitable[None],
        ],
        immediate: bool = False,  # noqa: FBT001, FBT002
        oneshot: bool = False,  # noqa: FBT001, FBT002
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> list[str]:
        return self.listen_attribute_extended(
            entity_id,
            "state",
            callback,
            immediate,
            oneshot,
            *callback_args,
            **callback_kwargs,
        )

    def listen_attribute_extended(
        self,
        entity_id: EntityID | Sequence[EntityID],
        attribute: str,
        callback: Callable[
            Concatenate[EntityID, str, HassValue, HassValue, P],
            None | Awaitable[None],
        ],
        immediate: bool = False,  # noqa: FBT001, FBT002
        oneshot: bool = False,  # noqa: FBT001, FBT002
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> list[str]:
        context_logger.set(self._wrapper.logger)
        target_entity_id = entity_id
        if not isinstance(target_entity_id, Sequence):
            target_entity_id = [target_entity_id]

        for eid in target_entity_id:
            if isinstance(eid, str):
                raise TypeError("Passed entity_id as str and not as EntityID")

        self.__hass.warn_if_entity_doesnt_exists(target_entity_id)

        target_entity_id = set(target_entity_id)

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def listen_attribute_callback(
            callback_id: str,
            _event_name: str,
            event_data: dict[str, Any],
        ) -> None:
            context_logger.set(self._wrapper.logger)
            event_entity_id = get_type_instance_for_entity_id(event_data["entity_id"])

            if event_entity_id not in target_entity_id:
                self._wrapper.logger.warning(
                    "Received callback for entity_id that should not be part of"
                    " callback. '{event_entity_id}' not in '{target_entity_id}'",
                    event_entity_id=event_entity_id,
                    target_entity_id=target_entity_id,
                )

            new_state = event_data.get("new_state", {}) or {}
            old_state = event_data.get("old_state", {}) or {}

            if attribute == "all":
                old_value = old_state
                new_value = new_state

            elif attribute == "state":
                old_value = old_state.get("state", None)
                new_value = new_state.get("state", None)

                if old_value == new_value:
                    return

            else:
                old_value = old_state.get("attributes", {}).get(attribute, None)
                new_value = new_state.get("attributes", {}).get(attribute, None)

                if old_value == new_value:
                    return

            callback_cls_name = get_callback_class(callback)

            self._wrapper.logger.trace(
                "Calling Entity Callback: {cls_name}.{func_name}",
                cls_name=callback_cls_name,
                func_name=get_callback_true_name(callback),
            )

            if oneshot:
                self.cancel_callback(callback_id)

            await instrumented_callback(
                callback_id,
                event_entity_id,
                attribute,
                old_value,
                new_value,
                *callback_args,
                **callback_kwargs,
            )

        callback_id = [
            self.__register.add_event_callback(
                self._wrapper,
                listen_attribute_callback,
                f"state_changed={eid}",
            )
            for eid in target_entity_id
        ]

        if immediate:

            @self._wrapper.handle_exception_and_logging(callback)
            async def immediate_callback(callback_id: str) -> None:
                all_eid = wrap_entity_id_as_list(entity_id)
                all_callbacks: list[Awaitable[None]] = []
                for eid in all_eid:
                    eid_state = self.__hass.get_full_state(eid)
                    if eid_state is not None:
                        all_callbacks.append(
                            listen_attribute_callback(
                                f"ephemeral_callback-{callback_id}-{entity_id}",
                                "immediate_state_notification",
                                {
                                    "entity_id": eid,
                                    "new_state": eid_state.to_dict(),
                                },
                            ),
                        )

                self.cancel_callback(callback_id)

                await asyncio.gather(*all_callbacks)

            current_date = get_datetime_now_with_config_timezone()

            self.__register.add_scheduler_callback(
                self._wrapper,
                immediate_callback,
                None,
                current_date,
            )

        return callback_id or []

    def cancel_callback(self, callback_id: str) -> None:
        context_logger.set(self._wrapper.logger)
        self.__register.cancel_callback(self._wrapper, callback_id)

    def run_once(
        self,
        time: datetime.time,
        callback: Callable[P, None | Awaitable[None]],
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)
        current_date = get_datetime_now_with_config_timezone()

        target_date = current_date.replace(
            hour=time.hour,
            minute=time.minute,
            second=time.second,
        )

        if target_date < current_date:
            target_date = target_date + datetime.timedelta(days=1)

        return self.run_at(callback, target_date, *callback_args, **callback_kwargs)

    def run_in(
        self,
        interval: Interval,
        callback: Callable[P, None | Awaitable[None]],
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        dt = get_datetime_now_with_config_timezone() + datetime.timedelta(
            days=interval.days,
            hours=interval.hours,
            minutes=interval.minutes,
            seconds=interval.seconds,
        )

        return self.run_at(
            callback=callback,
            datetime=dt,
            *callback_args,  # noqa: B026
            **callback_kwargs,
        )

    def __get_next_sun_event_date(
        self,
        sun_event: SunEvents,
        astral_location: Location,
        delta: Interval | None,
        initial_date: datetime.date,
    ) -> datetime.datetime:
        sun_locations = astral_location.sun(initial_date, local=True)
        sun_event_datetime = sun_locations[sun_event]
        if delta is not None:
            sun_event_datetime = sun_event_datetime + delta.to_timedelta()

        if sun_event_datetime < datetime.datetime.now(tz=datetime.UTC):
            sun_locations = astral_location.sun(
                initial_date + datetime.timedelta(days=1),
                local=True,
            )
            sun_event_datetime = sun_locations[sun_event]
            if delta is not None:
                sun_event_datetime = sun_event_datetime + delta.to_timedelta()

        return sun_event_datetime

    def run_daily_on_sun_event(
        self,
        callback: Callable[P, None | Awaitable[None]],
        sun_event: SunEvents,
        delta: Interval | None = None,
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)

        # calculate next event
        astral_location = get_main_config().get_astral_location()

        if astral_location is None:
            raise ValueError(
                "Domovoy config is missing Astral location information.",
            )

        sun_event_datetime = self.__get_next_sun_event_date(
            sun_event,
            astral_location,
            delta,
            datetime.datetime.now(tz=get_main_config().get_timezone()).date(),
        )

        self._wrapper.logger.trace(
            "Datetime for next `{sun_event}` sun event: {sun_event_datetime}. Delta: {delta}",
            sun_event=sun_event,
            sun_event_datetime=sun_event_datetime,
            delta=delta,
        )

        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def scheduled_callback(callback_id: str) -> None:
            self._wrapper.logger.trace(
                "Calling Sun Event Callback: {cls_name}.{func_name}",
                cls_name=get_callback_class(callback),
                func_name=callback.__name__,
            )

            tomorrow = datetime.datetime.now(tz=get_main_config().get_timezone()).date() + datetime.timedelta(days=1)
            # Calculate next sun event
            new_sun_event_datetime = self.__get_next_sun_event_date(
                sun_event,
                astral_location,
                delta,
                tomorrow,
            )

            self._wrapper.logger.trace(
                "Datetime for next `{sun_event}` sun event: {sun_event_datetime}. Delta: {delta}",
                sun_event=sun_event,
                sun_event_datetime=new_sun_event_datetime,
                delta=delta,
            )

            try:
                self.__register.add_scheduler_callback(
                    self._wrapper,
                    scheduled_callback,
                    new_sun_event_datetime,
                    new_sun_event_datetime,
                )
            except Exception as e:
                self._wrapper.logger.exception(
                    "Failed to schedule next sun event for callback_id: {callback_id}",
                    e,
                    callback_id=callback_id,
                )

            await instrumented_callback(callback_id, *callback_args, **callback_kwargs)

        return self.__register.add_scheduler_callback(
            self._wrapper,
            scheduled_callback,
            sun_event_datetime,
            sun_event_datetime,
        )

    def run_at(
        self,
        callback: Callable[P, None | Awaitable[None]],
        datetime: datetime.datetime,
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)
        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def scheduled_callback(callback_id: str) -> None:
            self._wrapper.logger.trace(
                "Calling Timer Callback: {callback_name}",
                callback_name=get_callback_name(callback),
            )

            await instrumented_callback(callback_id, *callback_args, **callback_kwargs)

        current_date = get_datetime_now_with_config_timezone()

        if datetime < current_date:
            msg = f"Cannot schedule a callback in the past (datetime={datetime}, current_time={current_date})."
            raise DomovoySchedulerError(msg)

        return self.__register.add_scheduler_callback(
            self._wrapper,
            scheduled_callback,
            datetime,
            datetime,
        )

    def run_daily(
        self,
        callback: Callable[P, None | Awaitable[None]],
        time: datetime.time | str = "now",
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        if isinstance(time, datetime.time):
            true_start = datetime.datetime.combine(
                datetime.datetime.now(tz=get_main_config().get_timezone()).date(),
                time,
            )
            true_start = get_main_config().get_timezone().localize(true_start)

            current_time = datetime.datetime.now(tz=get_main_config().get_timezone())

            _logcore.trace(
                "DT check: true_start: {true_start} [isAware: {true_start_aware}]"
                " -- current_time: {current_time} [isAware: {current_time_aware}] ",
                true_start=true_start,
                true_start_aware=is_datetime_aware(true_start),
                current_time=current_time,
                current_time_aware=is_datetime_aware(current_time),
            )

            if true_start < current_time:
                true_start = true_start + datetime.timedelta(days=1)

        else:
            true_start = time

        return self.run_every(
            Interval(days=1),
            callback,
            true_start,
            *callback_args,
            **callback_kwargs,
        )

    def run_hourly(
        self,
        callback: Callable[P, None | Awaitable[None]],
        start: datetime.datetime | str = "now",
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        return self.run_every(
            Interval(hours=1),
            callback,
            start,
            *callback_args,
            **callback_kwargs,
        )

    def run_minutely(
        self,
        callback: Callable[P, None | Awaitable[None]],
        start: datetime.datetime | str = "now",
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        return self.run_every(
            Interval(minutes=1),
            callback,
            start,
            *callback_args,
            **callback_kwargs,
        )

    def run_secondly(
        self,
        callback: Callable[P, None | Awaitable[None]],
        start: datetime.datetime | str = "now",
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        return self.run_every(
            Interval(seconds=1),
            callback,
            start,
            *callback_args,
            **callback_kwargs,
        )

    def run_every(
        self,
        interval: Interval,
        callback: Callable[P, None | Awaitable[None]],
        start: datetime.datetime | str = "now",
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        context_logger.set(self._wrapper.logger)
        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        if not interval.is_valid():
            raise DomovoySchedulerError(
                "Cannot schedule a callback with an empty interval",
            )

        if start == "now":
            start = get_datetime_now_with_config_timezone()
        elif isinstance(start, str):
            start = parse(start)

        self._wrapper.logger.trace(
            "Configuring run_every callback with interval: `{interval}` starting at `{start}`",
            interval=interval,
            start=start,
        )

        @self._wrapper.handle_exception_and_logging(callback)
        async def timer_callback(callback_id: str) -> None:
            self._wrapper.logger.trace(
                "Calling Timer Callback: {cls_name}.{func_name}",
                cls_name=callback.__self__.__class__.__name__,  # type: ignore
                func_name=callback.__name__,
            )

            await instrumented_callback(callback_id, *callback_args, **callback_kwargs)

        return self.__register.add_scheduler_callback(
            self._wrapper,
            timer_callback,
            interval,
            start,
        )


def wrap_entity_id_as_list(val: EntityID | Sequence[EntityID]) -> list[EntityID]:
    if isinstance(val, Sequence):
        return list(val)

    return [val]
