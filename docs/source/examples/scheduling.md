# Scheduling Examples

These examples show time-based automations.

## Daily Schedule

Run tasks at specific times each day:

```python
import datetime
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase

@dataclass
class DailyRoutineConfig(AppConfigBase):
    morning_time: str  # "07:00:00"
    evening_time: str  # "22:00:00"

class DailyRoutine(AppBase[DailyRoutineConfig]):
    async def initialize(self) -> None:
        # Using string format
        self.callbacks.run_daily(
            self.morning_routine,
            self.config.morning_time,
        )

        # Using datetime.time
        self.callbacks.run_daily(
            self.evening_routine,
            datetime.time(22, 0, 0),
        )

    async def morning_routine(self) -> None:
        self.log.info("Good morning!")
        await self.hass.services.light.turn_on(
            entity_id="light.bedroom",  # type: ignore
            brightness=100,
        )

    async def evening_routine(self) -> None:
        self.log.info("Good night!")
        await self.hass.services.light.turn_off(
            entity_id="light.all_lights",  # type: ignore
        )
```

## Sun-Based Schedule

Schedule based on sunrise/sunset:

```python
from dataclasses import dataclass
from typing import Literal
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.types import Interval
from domovoy.plugins.hass.types import EntityID

@dataclass
class SunTriggerConfig:
    sun_event: Literal["dawn", "sunrise", "noon", "sunset", "dusk"]
    delta: Interval | None = None  # Offset from sun event

@dataclass
class SunScheduleConfig(AppConfigBase):
    entity_id: EntityID | list[EntityID]
    turn_on: SunTriggerConfig | None = None
    turn_off: SunTriggerConfig | None = None

class SunSchedule(AppBase[SunScheduleConfig]):
    async def initialize(self) -> None:
        if self.config.turn_on is not None:
            self.callbacks.run_daily_on_sun_event(
                self.turn_on,
                self.config.turn_on.sun_event,
                self.config.turn_on.delta,
            )

        if self.config.turn_off is not None:
            self.callbacks.run_daily_on_sun_event(
                self.turn_off,
                self.config.turn_off.sun_event,
                self.config.turn_off.delta,
            )

    async def turn_on(self) -> None:
        await self.hass.services.homeassistant.turn_on(
            entity_id=self.config.entity_id
        )

    async def turn_off(self) -> None:
        await self.hass.services.homeassistant.turn_off(
            entity_id=self.config.entity_id
        )

# Usage - turn on at sunset, off at 11 PM
register_app(
    app_class=SunSchedule,
    app_name="outdoor_lights",
    config=SunScheduleConfig(
        entity_id="light.outdoor",  # type: ignore
        turn_on=SunTriggerConfig(sun_event="sunset"),
        turn_off=SunTriggerConfig(
            sun_event="sunset",
            delta=Interval(hours=5),  # 5 hours after sunset
        ),
    ),
)

# Turn on 30 minutes before sunrise
register_app(
    app_class=SunSchedule,
    app_name="early_morning_light",
    config=SunScheduleConfig(
        entity_id="light.kitchen",  # type: ignore
        turn_on=SunTriggerConfig(
            sun_event="sunrise",
            delta=Interval(minutes=-30),  # Negative = before
        ),
        turn_off=SunTriggerConfig(sun_event="sunrise"),
    ),
)
```

## Interval-Based Schedule

Run tasks at regular intervals:

```python
from domovoy.applications.types import Interval

class PeriodicChecker(AppBase[CheckerConfig]):
    async def initialize(self) -> None:
        # Run every 5 minutes starting now
        self.callbacks.run_every(
            Interval(minutes=5),
            self.check_status,
            "now",
        )

        # Run every hour starting at the next hour
        self.callbacks.run_every(
            Interval(hours=1),
            self.hourly_task,
            datetime.time(0, 0, 0),
        )

    async def check_status(self) -> None:
        self.log.debug("Checking status...")
        # Your periodic logic here
```

## Delayed Execution

Run a task after a delay:

```python
class DelayedAction(AppBase[DelayedConfig]):
    async def initialize(self) -> None:
        # Run once after 10 seconds
        self.callbacks.run_in(
            Interval(seconds=10),
            self.delayed_start,
        )

    async def delayed_start(self) -> None:
        self.log.info("Delayed start completed")
```

## Schedule at Specific DateTime

Run at an exact date and time:

```python
import datetime

class ScheduledEvent(AppBase[EventConfig]):
    async def initialize(self) -> None:
        # Schedule for Christmas morning
        christmas = datetime.datetime(2024, 12, 25, 8, 0, 0)
        self.callbacks.run_at(self.christmas_routine, christmas)

    async def christmas_routine(self) -> None:
        self.log.info("Merry Christmas!")
```

## Sprinkler Control (Complex Scheduling)

Real-world example with zones and timing:

```python
from dataclasses import dataclass, field
from typing import Literal
from domovoy.applications.types import Interval

@dataclass
class ZoneConfig:
    switch: EntityID
    run_time: Interval | None = None  # Override default time
    days: list[Literal[1, 2, 3, 4, 5, 6, 7]] | None = None  # Override days

@dataclass
class SprinklerConfig(AppConfigBase):
    zones: dict[str, ZoneConfig]
    default_run_time: Interval
    days_to_run: list[Literal[1, 2, 3, 4, 5, 6, 7]]  # 1=Mon, 7=Sun
    start_time: datetime.time | None = None
    sunrise_offset: Interval | None = None
    gap_between_zones: Interval = field(default_factory=lambda: Interval(seconds=30))

class SprinklerController(AppBase[SprinklerConfig]):
    is_running: bool = False

    async def initialize(self) -> None:
        # Schedule based on config
        if self.config.start_time:
            self.callbacks.run_daily(
                self.start_watering,
                self.config.start_time,
            )
        elif self.config.sunrise_offset:
            self.callbacks.run_daily_on_sun_event(
                self.start_watering,
                "sunrise",
                self.config.sunrise_offset,
            )

        # Manual start button
        await self.servents.listen_button_press(
            self.start_watering,
            button_name="Start Sprinklers",
            event_name_to_fire="sprinkler_start",
        )

    async def start_watering(self) -> None:
        # Check day of week
        today = self.time.now().isoweekday()
        if today not in self.config.days_to_run:
            self.log.info("Not a watering day")
            return

        if self.is_running:
            self.log.warning("Already running")
            return

        self.is_running = True
        self.log.info("Starting sprinkler run")

        try:
            for zone_name, zone in self.config.zones.items():
                if not self.is_running:
                    break

                run_time = zone.run_time or self.config.default_run_time

                self.log.info(
                    "Watering zone {zone} for {time}",
                    zone=zone_name,
                    time=run_time,
                )

                await self.hass.services.switch.turn_on(entity_id=zone.switch)
                await self.time.sleep_for(run_time)
                await self.hass.services.switch.turn_off(entity_id=zone.switch)

                # Gap between zones
                await self.time.sleep_for(self.config.gap_between_zones)

        finally:
            self.is_running = False
            self.log.info("Sprinkler run complete")
```

## Cancel Scheduled Tasks

Save and cancel callback IDs:

```python
class CancellableTask(AppBase[TaskConfig]):
    callback_id: str | None = None

    async def initialize(self) -> None:
        self.callback_id = self.callbacks.run_every(
            Interval(minutes=1),
            self.periodic_task,
            "now",
        )

    async def stop_task(self) -> None:
        if self.callback_id:
            self.callbacks.cancel_callback(self.callback_id)
            self.callback_id = None
```

## Key Concepts

- **`run_daily(callback, time)`**: Daily at specific time
- **`run_daily_on_sun_event(callback, event, delta)`**: Relative to sun
- **`run_every(interval, callback, start)`**: Recurring intervals
- **`run_in(interval, callback)`**: One-time delayed execution
- **`run_at(callback, datetime)`**: Specific date/time
- **`Interval(hours=1, minutes=30)`**: Time duration helper
- **Sun events**: dawn, sunrise, noon, sunset, dusk
