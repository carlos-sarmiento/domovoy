import asyncio
import datetime
import pytz

from typing import Any, Awaitable, Callable, ParamSpec, TypeVar, Union
from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppWrapper
from domovoy.plugins.plugins import AppPlugin
from domovoy.core.utils import asFloat, asInt, get_callback_name
from dateutil.parser import parse
from domovoy.core.configuration import get_main_config
from astral.location import Location

TFloat = TypeVar("TFloat", bound=Union[float, None])
TInt = TypeVar("TInt", bound=Union[float, None])

P = ParamSpec("P")


class UtilsPlugin(AppPlugin):
    def __init__(self, name: str, wrapper: AppWrapper) -> None:
        super().__init__(name, wrapper)

    def parse_float(self, val: Any, default: TFloat = None) -> float | TFloat:
        return asFloat(val, default)  # type: ignore

    def parse_int(self, val: Any, default: TInt = None) -> int | TInt:
        return asInt(val, default)  # type: ignore

    def parse_int_or_float(self, val: Any) -> int | float | None:
        as_int = self.parse_int(val)
        if as_int is not None:
            return as_int

        as_float = self.parse_float(val)
        if as_float is not None:
            return as_float

        return None

    async def sleep_for(self, interval: Interval) -> None:
        await asyncio.sleep(interval.total_seconds())

    def timedelta_from_now(
        self, date: datetime.datetime | str, target_tz: pytz.BaseTzInfo | None = None
    ) -> datetime.timedelta:
        if target_tz is None:
            target_tz = get_main_config().get_timezone()

        if isinstance(date, datetime.datetime):
            date = date
        else:
            date = parse(date)

        has_tz_info = (
            date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None
        )

        if not has_tz_info:
            if target_tz is None:
                raise ValueError(
                    "Date provided does not have timezone and a target timezone was not provided"
                )
            date = target_tz.localize(date)

        now = datetime.datetime.now(target_tz)

        delta = now - date
        return delta

    def datetime_to_local_timezone(self, dt: datetime.datetime) -> datetime.datetime:
        return dt.astimezone(get_main_config().get_timezone())

    def run_async(
        self, callback: Callable[P, Awaitable[Any]], *args: P.args, **kwargs: P.kwargs
    ) -> asyncio.Task[Any]:
        async def callback_wrapper():
            await callback(*args, **kwargs)

        return asyncio.get_event_loop().create_task(
            callback_wrapper(), name=get_callback_name(callback)
        )

    def run_in_executor(
        self, callback: Callable[P, Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        def callback_wrapper():
            callback(*args, **kwargs)

        asyncio.get_event_loop().run_in_executor(None, callback_wrapper)

    def is_now_between_dawn_and_dusk(self) -> bool:
        return self.is_between_dawn_and_dusk(
            datetime.datetime.now(tz=get_main_config().get_timezone())
        )

    def is_between_dawn_and_dusk(self, dt: datetime.datetime) -> bool:
        astral_location = get_main_config().get_astral_location()

        if astral_location is None:
            raise ValueError("No Location is set in config")

        date = dt.date()

        sun_locations = astral_location.sun(date, local=True)
        dawn = sun_locations["dawn"]
        dusk = sun_locations["dusk"]

        return dawn <= dt <= dusk
