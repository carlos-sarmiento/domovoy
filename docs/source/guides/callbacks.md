# Callbacks Plugin Guide

The callbacks plugin provides event listening and scheduling functionality.

## Event Listening

### Listen to State Changes

React when an entity's state changes:

```python
from domovoy.plugins.hass.types import HassValue

async def initialize(self) -> None:
    self.callbacks.listen_state(
        self.config.entity_id,
        self.on_state_change,
        immediate=True,  # Call immediately with current state
    )

async def on_state_change(self, new: HassValue) -> None:
    self.log.info("State changed to: {state}", state=new)
```

### Flexible Callback Signatures

Callbacks only receive the parameters they declare:

```python
# Minimal - just the new value
async def on_change(self, new: HassValue) -> None:
    pass

# Include old value
async def on_change(self, old: HassValue, new: HassValue) -> None:
    pass

# Full signature
async def on_change(self, entity_id: EntityID, attribute: str, old: HassValue, new: HassValue) -> None:
    pass
```

### Listen to Attributes

Monitor specific attributes instead of state:

```python
self.callbacks.listen_attribute(
    entity_id,
    "brightness",  # attribute name
    self.on_brightness_change,
)
```

### Listen to Events

Subscribe to Home Assistant events:

```python
async def initialize(self) -> None:
    self.callbacks.listen_event(
        "zwave_js_value_notification",
        self.on_zwave_event,
    )

async def on_zwave_event(self, event_name: str, data: dict) -> None:
    self.log.info("Received event: {name}", name=event_name)
```

### One-Shot Callbacks

Use `oneshot=True` to automatically unsubscribe after first trigger:

```python
self.callbacks.listen_state(
    entity_id,
    self.on_first_change,
    oneshot=True,
)
```

## Scheduling

### Run at Specific Time

```python
import datetime

# Run at 8:00 AM every day
self.callbacks.run_daily(self.morning_routine, "08:00:00")

# Using datetime.time
self.callbacks.run_daily(self.morning_routine, datetime.time(8, 0, 0))
```

### Run After Delay

```python
from domovoy.applications.types import Interval

# Run once after 5 minutes
self.callbacks.run_in(Interval(minutes=5), self.delayed_task)

# Using multiple units
self.callbacks.run_in(Interval(hours=1, minutes=30), self.delayed_task)
```

### Run at Specific DateTime

```python
import datetime

run_time = datetime.datetime(2024, 12, 25, 8, 0, 0)
self.callbacks.run_at(self.christmas_morning, run_time)
```

### Recurring Intervals

```python
# Run every 10 minutes starting now
self.callbacks.run_every(
    Interval(minutes=10),
    self.periodic_check,
    "now",  # start immediately
)

# Run every hour starting at next hour
self.callbacks.run_every(
    Interval(hours=1),
    self.hourly_task,
    datetime.time(0, 0, 0),
)
```

### Sun Events

Schedule based on sunrise/sunset:

```python
from domovoy.applications.types import Interval

# Run at sunset
self.callbacks.run_daily_on_sun_event(
    self.sunset_routine,
    "sunset",
)

# Run 30 minutes before sunrise
self.callbacks.run_daily_on_sun_event(
    self.pre_dawn_routine,
    "sunrise",
    Interval(minutes=-30),  # negative = before
)

# Run 1 hour after sunset
self.callbacks.run_daily_on_sun_event(
    self.evening_routine,
    "sunset",
    Interval(hours=1),
)
```

Available sun events:
- `dawn` - Civil dawn
- `sunrise` - Sunrise
- `noon` - Solar noon
- `sunset` - Sunset
- `dusk` - Civil dusk

## Canceling Callbacks

All callback registration methods return a callback ID:

```python
async def initialize(self) -> None:
    self.callback_id = self.callbacks.run_every(
        Interval(minutes=5),
        self.check_status,
        "now",
    )

async def stop_checking(self) -> None:
    self.callbacks.cancel_callback(self.callback_id)
```

## Extended Callbacks

For advanced use cases, use `_extended` variants to pass extra arguments:

```python
async def initialize(self) -> None:
    for zone in self.config.zones:
        self.callbacks.listen_state_extended(
            zone.entity_id,
            self.on_zone_change,
            immediate=True,
            zone_name=zone.name,  # Extra kwarg passed to callback
        )

async def on_zone_change(
    self,
    entity_id: EntityID,
    attribute: str,
    old: HassValue,
    new: HassValue,
    zone_name: str,  # Receives the extra kwarg
) -> None:
    self.log.info("Zone {zone} changed", zone=zone_name)
```

## Best Practices

### Use Interval for Time Durations

```python
from domovoy.applications.types import Interval

# Good
Interval(hours=1, minutes=30)
Interval(seconds=90)

# Also supported
Interval(days=1)
```

### Handle Multiple Entities

```python
# Listen to multiple entities with one callback
self.callbacks.listen_state(
    [entity_a, entity_b, entity_c],
    self.on_any_change,
)
```

### Immediate Execution

Use `immediate=True` to get the current state on startup:

```python
self.callbacks.listen_state(
    entity_id,
    self.on_state_change,
    immediate=True,  # Calls callback with current state immediately
)
```
