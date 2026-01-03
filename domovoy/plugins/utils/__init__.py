import asyncio
import datetime
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar
from warnings import deprecated

import pytz
from dateutil.parser import parse

from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppWrapper
from domovoy.core.configuration import get_main_config
from domovoy.core.utils import as_float, as_int, get_callback_name
from domovoy.plugins.plugins import AppPlugin

TFloat = TypeVar("TFloat", bound=float | None)
TInt = TypeVar("TInt", bound=float | None)

P = ParamSpec("P")
T = TypeVar("T")


class UtilsPlugin(AppPlugin):
    def __init__(self, name: str, wrapper: AppWrapper) -> None:
        super().__init__(name, wrapper)

    def parse_float(self, val: object, default: TFloat = None) -> float | TFloat:
        return as_float(val, default)  # type: ignore

    def parse_int(self, val: object, default: TInt = None) -> int | TInt:
        return as_int(val, default)  # type: ignore

    def parse_int_or_float(self, val: object) -> int | float | None:
        as_int = self.parse_int(val)
        if as_int is not None:
            return as_int

        as_float = self.parse_float(val)
        if as_float is not None:
            return as_float

        return None

    def run_async(
        self,
        callback: Callable[P, Awaitable[T]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> asyncio.Task[T]:
        async def callback_wrapper() -> T:
            return await callback(*args, **kwargs)

        return asyncio.get_event_loop().create_task(
            callback_wrapper(),
            name=get_callback_name(callback),
        )

    def run_in_executor(
        self,
        callback: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> asyncio.Future[T]:
        def callback_wrapper() -> T:
            return callback(*args, **kwargs)

        return asyncio.get_event_loop().run_in_executor(None, callback_wrapper)

    @deprecated("use time plugin")
    async def sleep_for(self, interval: Interval) -> None:
        await asyncio.sleep(interval.total_seconds())

    @deprecated("use time plugin")
    def parse_date(self, string: str) -> datetime.datetime:
        return parse(string)

    @deprecated("use time plugin")
    def timedelta_from_now(
        self,
        date: datetime.datetime | str,
        target_tz: pytz.BaseTzInfo | None = None,
    ) -> datetime.timedelta:
        if target_tz is None:
            target_tz = get_main_config().get_timezone()

        date = date if isinstance(date, datetime.datetime) else parse(date)

        has_tz_info = date.tzinfo is not None and date.tzinfo.utcoffset(date) is not None

        if not has_tz_info:
            if target_tz is None:
                raise ValueError(
                    "Date provided does not have timezone and a target timezone was not provided",
                )
            date = target_tz.localize(date)

        now = datetime.datetime.now(target_tz)

        return now - date
