from __future__ import annotations
import logging
import uuid
import datetime
from typing import Awaitable, Callable, Concatenate, ParamSpec

import apscheduler
from apscheduler.events import EVENT_ALL, JobExecutionEvent, SchedulerEvent
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from domovoy.applications.types import Interval

from domovoy.core.app_infra import (
    AppStatus,
    AppWrapper,
    EventCallbackRegistration,
    SchedulerCallbackRegistration,
)
from domovoy.core.configuration import get_main_config
from domovoy.core.services.event_listener import EventListener
from domovoy.core.logging import (
    get_logger,
    get_context_logger as c_logger,
)
from domovoy.core.services.service import DomovoyService, DomovoyServiceResources
from domovoy.core.utils import get_callback_true_class, get_callback_true_name


P = ParamSpec("P")
_logcore = get_logger(__name__)


class CallbackRegister(DomovoyService):
    __scheduling_engine: AsyncIOScheduler
    __event_listener: EventListener
    __callback_to_wrapper_mappings: dict[str, AppWrapper]

    def __init__(
        self, resources: DomovoyServiceResources, event_listener: EventListener
    ) -> None:
        super().__init__(resources)
        self.__event_listener = event_listener
        self.__callback_to_wrapper_mappings = {}
        self.__scheduling_engine = AsyncIOScheduler(timezone=get_main_config().timezone)
        self.__scheduling_engine.add_listener(
            self.scheduler_event_logger, mask=EVENT_ALL
        )
        logging.getLogger("apscheduler").setLevel(logging.CRITICAL)

    def scheduler_event_logger(self, event: SchedulerEvent) -> None:
        if not isinstance(event, JobExecutionEvent):
            return

        exception = event.exception  # type: ignore
        callback_id = event.job_id  # type: ignore

        if exception is None:
            return

        if callback_id not in self.__callback_to_wrapper_mappings:
            _logcore.error(
                "Received an Exception from apscheduler for a "
                + "callback_id that is not registered. callback_id: {callback_id}",
                callback_id=callback_id,
            )

        wrapper = self.__callback_to_wrapper_mappings[callback_id]

        callback_info = wrapper.scheduler_callbacks[callback_id]

        wrapper.logger.exception(
            "Received an error for callback {callback} from apscheduler",
            exception,
            callback=get_callback_true_name(callback_info.callback),
        )

    def start(self) -> None:
        _logcore.info("Starting Callback Register")
        self.__scheduling_engine.start()

    def stop(self) -> None:
        _logcore.info("Stopping Callback Register")
        self.__scheduling_engine.shutdown()

    def register_all_callbacks(
        self,
        app_wrapper: AppWrapper,
    ) -> None:
        _logcore.debug(
            "Registering all callbacks for {app_name}",
            app_name=app_wrapper.app_name,
        )

        for registration in app_wrapper.scheduler_callbacks.values():
            if not registration.is_registered:
                self.__register_single_scheduler_callback(app_wrapper, registration)

        for registration in app_wrapper.event_callbacks.values():
            if not registration.is_registered:
                self.__register_single_event_callback(app_wrapper, registration)

    def __register_single_scheduler_callback(
        self, app_wrapper: AppWrapper, registration: SchedulerCallbackRegistration
    ) -> None:
        if registration.is_registered:
            _logcore.error(
                "Tried to re-register callback `{callback_name}` from"
                + " class `{callback_class}` with id {callback_id} for app: {app_name}",
                callback_name=get_callback_true_name(registration.callback),
                callback_class=get_callback_true_class(registration.callback),
                callback_id=registration.id,
                app_name=app_wrapper.app_name,
            )
            return

        c_logger().debug(
            "Adding Callback for {app_name} with ID: {callback_id}. Callback Name: {callback_name}",
            app_name=app_wrapper.app_name,
            callback_id=registration.id,
            callback_name=registration.callback.__name__,
        )

        registration.job = self.__scheduling_engine.add_job(
            func=registration.callback,
            trigger=registration.trigger,
            args=[registration.id],
            id=registration.id,
            next_run_time=registration.start,
        )

        registration.is_registered = True

    def __register_single_event_callback(
        self, app_wrapper: AppWrapper, registration: EventCallbackRegistration
    ) -> None:
        if registration.is_registered:
            _logcore.error(
                "Tried to re-register callback {callback_name} with id {callback_id} for app: {app_name}",
                callback_name=get_callback_true_name(registration.callback),
                callback_id=registration.id,
                app_name=app_wrapper.app_name,
            )
            return  # should throw

        c_logger().debug(
            f"Adding Callback for {app_wrapper.app_name} with ID: {registration.id}"
        )

        self.__event_listener.add_listener(
            registration.events, registration.callback, registration.id
        )

        registration.is_registered = True

    def __cancel_single_scheduler_callback(
        self, app_wrapper: AppWrapper, callback_id: str
    ) -> None:
        c_logger().debug(
            "Cancelling callback with id {callback_id} for app {app_name}",
            callback_id=callback_id,
            app_name=app_wrapper.app_name,
        )

        if callback_id not in app_wrapper.scheduler_callbacks:
            c_logger().error(
                "ID {callback_id} for app {app_name} not found in the app's existing callbacks",
                callback_id=callback_id,
                app_name=app_wrapper.app_name,
            )
            return

        registration = app_wrapper.scheduler_callbacks[callback_id]

        if not registration.is_registered:
            c_logger().debug(
                "Tried to cancel callback with ID {callback_id} for app {app_name}, but"
                + " the callback was never registered",
                callback_id=callback_id,
                app_name=app_wrapper.app_name,
            )
            return

        try:
            self.__scheduling_engine.remove_job(registration.id)
        except apscheduler.jobstores.base.JobLookupError:  # type: ignore
            ...

        try:
            self.__callback_to_wrapper_mappings.pop(callback_id)
        except KeyError:
            ...

        registration.is_registered = False

    def __cancel_single_event_callback(
        self, app_wrapper: AppWrapper, callback_id: str
    ) -> None:
        c_logger().debug(
            "Cancelling callback with id {callback_id} for app {app_name}",
            callback_id=callback_id,
            app_name=app_wrapper.app_name,
        )

        if callback_id not in app_wrapper.event_callbacks:
            c_logger().error(
                "Cancelling callback with id {callback_id} for app {app_name}",
                callback_id=callback_id,
                app_name=app_wrapper.app_name,
            )
            return

        registration = app_wrapper.event_callbacks[callback_id]

        if not registration.is_registered:
            c_logger().error(
                "Tried to cancel callback with ID {callback_id} for app {app_name}, but"
                + " the callback was never registered",
                callback_id=callback_id,
                app_name=app_wrapper.app_name,
            )
            return

        self.__event_listener.remove_listener(callback_id)
        registration.is_registered = False

    def cancel_all_callbacks(
        self,
        app_wrapper: AppWrapper,
    ) -> None:
        _logcore.debug(
            "Cancelling all callbacks for {app_name}",
            app_name=app_wrapper.app_name,
        )

        for x in app_wrapper.scheduler_callbacks.values():
            self.__cancel_single_scheduler_callback(app_wrapper, x.id)

        app_wrapper.scheduler_callbacks.clear()

        for x in app_wrapper.event_callbacks.values():
            self.__cancel_single_event_callback(app_wrapper, x.id)

        app_wrapper.event_callbacks.clear()

    def cancel_callback(self, app_wrapper: AppWrapper, id: str) -> None:
        if id.startswith("ephemeral_callback"):
            return

        if id in app_wrapper.scheduler_callbacks:
            self.__cancel_single_scheduler_callback(app_wrapper, id)
            app_wrapper.scheduler_callbacks.pop(id)
            return

        if id in app_wrapper.event_callbacks:
            self.__cancel_single_event_callback(app_wrapper, id)
            app_wrapper.event_callbacks.pop(id)
            return

        c_logger().error(
            "Callback with id {callback_id} is not registered for app {app_name}",
            callback_id=id,
            app_name=app_wrapper.app_name,
        )

    def add_scheduler_callback(
        self,
        app_wrapper: AppWrapper,
        callback: Callable[Concatenate[str, P], Awaitable[None]],
        trigger_value: datetime.datetime | Interval | None,  # BaseTrigger | None,
        start: datetime.datetime | None,
        reuse_callback_id: str | None = None,
    ) -> str:
        c_logger().debug(
            "Adding Scheduler Callback for app {app_name}",
            app_name=app_wrapper.app_name,
        )

        if reuse_callback_id is None:
            callback_id = f"scheduler-{uuid.uuid4().hex}"
        else:
            if reuse_callback_id not in app_wrapper.scheduler_callbacks:
                raise ValueError(
                    f"Provided callback_id {reuse_callback_id} is not registered to this app"
                )
            callback_id = reuse_callback_id

        trigger = None
        if isinstance(trigger_value, datetime.datetime):
            trigger = DateTrigger(run_date=trigger_value)
        elif isinstance(trigger_value, Interval):
            trigger = IntervalTrigger(
                days=trigger_value.days,
                hours=trigger_value.hours,
                minutes=trigger_value.minutes,
                seconds=trigger_value.seconds,
            )

        app_wrapper.scheduler_callbacks[callback_id] = SchedulerCallbackRegistration(
            id=callback_id,
            callback=callback,
            is_registered=False,
            trigger=trigger,
            start=start,
        )

        self.__callback_to_wrapper_mappings[callback_id] = app_wrapper

        if app_wrapper.status == AppStatus.RUNNING:
            self.register_all_callbacks(app_wrapper)

        return callback_id

    def add_event_callback(
        self,
        app_wrapper: AppWrapper,
        callback: Callable[P, Awaitable[None]],
        events: str | list[str],
    ) -> str:
        c_logger().debug(
            "Adding Event Callback for app {app_name}",
            app_name=app_wrapper.app_name,
        )
        callback_id = f"event-{uuid.uuid4().hex}"

        if isinstance(events, str):
            events = [events]

        app_wrapper.event_callbacks[callback_id] = EventCallbackRegistration(
            id=callback_id,
            callback=callback,
            is_registered=False,
            events=events,
        )

        if app_wrapper.status == AppStatus.RUNNING:
            self.register_all_callbacks(app_wrapper)

        return callback_id

    async def publish_event(self, event: str, event_data: dict[str, str]) -> None:
        await self.__event_listener.publish_event(event, event_data)
