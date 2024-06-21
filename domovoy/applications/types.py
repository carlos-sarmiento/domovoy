import datetime
from dataclasses import dataclass


@dataclass
class Interval:
    days: int = 0
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    milliseconds: float = 0

    def is_valid(self) -> bool:
        """Check if an interval has a non-zero duration.

        Returns
        -------
            bool: True if at least one of the fields of the interval is non-zero.

        """
        return self.days != 0 or self.hours != 0 or self.minutes != 0 or self.seconds != 0 or self.milliseconds != 0

    def to_timedelta(self) -> datetime.timedelta:
        """Convert the interval to a datetime.timedelta.

        Returns
        -------
            datetime.timedelta: The equivalent datetime.timedelta for the interval.

        """
        return datetime.timedelta(
            days=self.days,
            hours=self.hours,
            minutes=self.minutes,
            seconds=self.seconds,
            milliseconds=self.milliseconds,
        )

    def total_seconds(self) -> float:
        """Get the total duration of the interval in fractional seconds.

        Returns
        -------
            float: The total duration of the interval.

        """
        return ((self.days * 24 + self.hours) * 60 + self.minutes) * 60 + self.seconds + (self.milliseconds / 1000)
