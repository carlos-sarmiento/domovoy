import datetime
from collections.abc import Awaitable, Callable, Sequence

import strawberry
from apscheduler.job import Job

from domovoy.core.app_infra import (
    AppWrapper,
    EventCallbackRegistration,
    SchedulerCallbackRegistration,
)
from domovoy.core.utils import get_callback_name


@strawberry.interface
class AppCallback:
    def __init__(
        self,
        registration: SchedulerCallbackRegistration | EventCallbackRegistration,
    ) -> None:
        self.id = registration.id
        self.callback = get_callback_name(registration.callback)
        self.is_registered = registration.is_registered
        self.callback_type = "unknown"
        self.times_called = registration.times_called
        self.last_call_datetime = registration.last_call_datetime
        self.last_error_datetime = registration.last_error_datetime

    id: str
    callback: str
    is_registered: bool
    callback_type: str
    times_called: int
    last_call_datetime: datetime.datetime | None = None
    last_error_datetime: datetime.datetime | None = None


@strawberry.type
class AppCallbackConnection:
    def __init__(self, app_callbacks: Sequence[AppCallback]) -> None:
        self.__app_callbacks = app_callbacks

    @strawberry.field
    def nodes(self) -> Sequence[AppCallback]:
        return self.__app_callbacks

    @strawberry.field
    def count(self) -> int:
        return len(self.__app_callbacks)


@strawberry.type
class SchedulerJob:
    next_run_at: datetime.datetime
    is_pending_on_scheduler: bool

    def __init__(self, job: Job) -> None:
        self.next_run_at = job.next_run_time
        self.is_pending_on_scheduler = job.pending


@strawberry.type
class SchedulerCallback(AppCallback):
    trigger: str | None = None
    start: datetime.datetime | None = None
    job: SchedulerJob | None = None

    def __init__(self, registration: SchedulerCallbackRegistration) -> None:
        super().__init__(registration)

        self.callback_type = "scheduler"
        self.trigger = str(registration.trigger)
        self.start = registration.start

        if registration.job is not None:
            self.job = SchedulerJob(registration.job)


@strawberry.type
class EventCallback(AppCallback):
    events: list[str] | None = None

    def __init__(self, registration: EventCallbackRegistration) -> None:
        super().__init__(registration)

        self.callback_type = "event"
        self.events = registration.events


@strawberry.type
class Application:
    app_name: str
    class_name: str
    filepath: str
    module_name: str
    status: str

    def __init__(self, app_wrapper: AppWrapper) -> None:
        self.__app_wrapper = app_wrapper
        self.app_name = app_wrapper.app_name
        self.class_name = app_wrapper.class_name
        self.filepath = app_wrapper.filepath
        self.module_name = app_wrapper.module_name
        self.status = app_wrapper.status

    @strawberry.field
    async def callbacks(self) -> AppCallbackConnection:
        scheduler_callbacks = [SchedulerCallback(x) for x in self.__app_wrapper.scheduler_callbacks.values()]
        event_callbacks = [EventCallback(x) for x in self.__app_wrapper.event_callbacks.values()]

        return AppCallbackConnection(scheduler_callbacks + event_callbacks)


def build_schema(
    get_all_apps_by_name: Callable[[], Awaitable[dict[str, AppWrapper]]],
) -> strawberry.Schema:
    @strawberry.type
    class RootQuery:
        @strawberry.field
        async def applications(self) -> list[Application]:
            all_apps = await get_all_apps_by_name()

            return [Application(app_wrapper) for app_wrapper in all_apps.values()]

        @strawberry.field
        async def application(self, app_name: str) -> Application | None:
            all_apps = await get_all_apps_by_name()

            if app_name not in all_apps:
                return None

            return Application(all_apps[app_name])

    return strawberry.Schema(query=RootQuery, types=[SchedulerCallback, EventCallback])
