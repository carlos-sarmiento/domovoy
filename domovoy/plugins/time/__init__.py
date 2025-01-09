import asyncio
import datetime

import pytz
from dateutil.parser import parse

from domovoy.applications.types import Interval
from domovoy.core.app_infra import AppWrapper
from domovoy.core.configuration import get_main_config
from domovoy.plugins.plugins import AppPlugin


class TimePlugin(AppPlugin):
    def __init__(self, name: str, wrapper: AppWrapper) -> None:
        super().__init__(name, wrapper)

    async def sleep_for(self, interval: Interval) -> None:
        await asyncio.sleep(interval.total_seconds())

    def parse_date(self, string: str) -> datetime.datetime:
        return parse(string)

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

    def datetime_to_local_timezone(self, dt: datetime.datetime) -> datetime.datetime:
        return dt.astimezone(get_main_config().get_timezone())

    def parse_timestamp_to_local_timezone(self, timestamp: float) -> datetime.datetime:
        naive_dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC)
        return self.datetime_to_local_timezone(naive_dt)

    def now(self, *, tz: datetime.tzinfo | None = None) -> datetime.datetime:
        if tz is None:
            tz = get_main_config().get_timezone()
        return datetime.datetime.now(tz=tz)

    def today(self, *, tz: datetime.tzinfo | None = None) -> datetime.date:
        return self.now(tz=tz).date()

    def make_datetime_aware(self, *, dt: datetime.datetime, tz: datetime.tzinfo | None = None) -> datetime.datetime:
        if tz is None:
            tz = get_main_config().get_timezone()

        return dt.replace(tzinfo=tz)

    def is_datetime_aware(self, dt: datetime.datetime) -> bool:
        return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None

    def is_now_between_dawn_and_dusk(self) -> bool:
        return self.is_between_dawn_and_dusk(
            datetime.datetime.now(tz=get_main_config().get_timezone()),
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
