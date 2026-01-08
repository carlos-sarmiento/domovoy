# State Management Guide

This guide covers how Domovoy handles entity states and how to work with them effectively.

## State Caching

Domovoy maintains a local cache of all Home Assistant entity states:

- Cache is populated on startup via WebSocket
- Updates arrive in real-time via WebSocket events
- Reading state is fast (no network call)
- State is always current (within milliseconds)

```python
# Fast - reads from local cache
state = self.hass.get_state(entity_id)

# Also fast - cache is updated in real-time
full_state = self.hass.get_full_state(entity_id)
```

## State vs Attributes

Every entity has both a **state** and **attributes**:

```python
entity_state = self.hass.get_full_state(entity_id)

# State - the primary value ("on", "off", "23.5", etc.)
state = entity_state.state

# Attributes - additional data
brightness = entity_state.attributes.get("brightness")
color_temp = entity_state.attributes.get("color_temp")
friendly_name = entity_state.attributes.get("friendly_name")

# Timestamps
last_changed = entity_state.last_changed  # When state changed
last_updated = entity_state.last_updated  # When any update occurred
```

## State Types

### Primitive Values

State values can be strings, numbers, or None:

```python
from domovoy.plugins.hass.types import HassValue

state: HassValue = self.hass.get_state(entity_id)
# Returns: str | int | float | None
```

### Parsing Values

Use utilities to safely parse state values:

```python
# Parse as float (returns None if invalid)
temp = self.utils.parse_float(self.hass.get_state(sensor))

# Parse as int
count = self.utils.parse_int(self.hass.get_state(counter))

# Parse as either
value = self.utils.parse_int_or_float(self.hass.get_state(sensor))
```

## Checking State Duration

Check how long an entity has been in a specific state:

```python
entity_state = self.hass.get_full_state(entity_id)

# Check if entity has been "on" for at least 5 minutes
from domovoy.applications.types import Interval

if entity_state.has_been_in_state_for_at_least("on", Interval(minutes=5)):
    self.log.info("Entity has been on for 5+ minutes")
```

## Waiting for State

Wait asynchronously for an entity to reach a specific state:

```python
from domovoy.applications.types import Interval

# Wait for entity to turn on
await self.hass.wait_for_state_to_be(
    entity_id,
    states=["on"],
)

# Wait with timeout
try:
    await self.hass.wait_for_state_to_be(
        entity_id,
        states=["on", "home"],
        timeout=Interval(seconds=30),
    )
except asyncio.TimeoutError:
    self.log.warning("Timed out waiting for state")

# Wait for state to persist for a duration
await self.hass.wait_for_state_to_be(
    entity_id,
    states=["on"],
    duration=Interval(seconds=5),  # Must stay "on" for 5 seconds
    timeout=Interval(minutes=1),
)
```

## Listening to State Changes

### Basic State Listening

```python
async def initialize(self) -> None:
    self.callbacks.listen_state(
        entity_id,
        self.on_change,
    )

async def on_change(self, old: HassValue, new: HassValue) -> None:
    self.log.info("Changed from {old} to {new}", old=old, new=new)
```

### Immediate State Notification

Get the current state immediately on startup:

```python
self.callbacks.listen_state(
    entity_id,
    self.on_change,
    immediate=True,  # Calls callback with current state
)
```

### Listening to All Changes

Use `attribute="all"` to get notified on any update:

```python
self.callbacks.listen_attribute(
    entity_id,
    "all",  # All changes, not just state
    self.on_any_update,
)
```

## Entity Lookup

### Find by Attribute

```python
# Find all entities with a specific attribute value
motion_sensors = self.hass.get_entity_id_by_attribute(
    "device_class",
    "motion",
)

# Find entities that have an attribute (any value)
pool_switches = self.hass.get_entity_id_by_attribute(
    "is_pool_switch",
    None,  # Any value
)
```

### Check Entity Existence

```python
# Validate entities exist (logs warning if not)
self.hass.warn_if_entity_doesnt_exists(entity_id)
self.hass.warn_if_entity_doesnt_exists([entity_a, entity_b])
```

## Working with Typed States

For entities with known types, use typed access:

```python
from domovoy.plugins.hass.domains import SensorEntity

sensor: SensorEntity = entities.sensor.temperature

# Get typed state value
value = self.hass.get_typed_state(sensor)
```

## State Patterns

### Debouncing State Changes

Wait for state to stabilize before acting:

```python
async def on_motion_detected(self, new: HassValue) -> None:
    if new != "on":
        return

    # Wait 30 seconds to confirm motion continues
    await self.time.sleep_for(Interval(seconds=30))

    # Check if still on
    current = self.hass.get_state(self.config.motion_sensor)
    if current == "on":
        await self.turn_on_lights()
```

### Tracking State History

Store previous states for comparison:

```python
async def initialize(self) -> None:
    self.previous_states: dict[str, HassValue] = {}

    self.callbacks.listen_state(
        entity_id,
        self.on_change,
        immediate=True,
    )

async def on_change(self, entity_id: EntityID, new: HassValue) -> None:
    previous = self.previous_states.get(str(entity_id))

    if previous is not None and previous != new:
        self.log.info(
            "State transition: {prev} -> {new}",
            prev=previous,
            new=new,
        )

    self.previous_states[str(entity_id)] = new
```

### Aggregating Multiple Entities

Check multiple entities together:

```python
async def check_all_doors(self) -> None:
    door_entities = [
        entities.binary_sensor.front_door,
        entities.binary_sensor.back_door,
        entities.binary_sensor.garage_door,
    ]

    states = [self.hass.get_state(door) for door in door_entities]

    if all(state == "off" for state in states):
        self.log.info("All doors are closed")
    else:
        open_doors = [
            door for door, state in zip(door_entities, states)
            if state == "on"
        ]
        self.log.warning("Open doors: {doors}", doors=open_doors)
```

## Best Practices

### Check State Before Acting

```python
async def turn_on_if_needed(self, entity_id: EntityID) -> None:
    if self.hass.get_state(entity_id) != "on":
        await self.hass.services.homeassistant.turn_on(entity_id=entity_id)
```

### Handle Unknown States

```python
state = self.hass.get_state(entity_id)

if state in ("unavailable", "unknown", None):
    self.log.warning("Entity {id} is unavailable", id=entity_id)
    return

# Safe to process state
```

### Use Type Hints

```python
from domovoy.plugins.hass.types import HassValue, EntityID

async def process_state(
    self,
    entity_id: EntityID,
    state: HassValue,
) -> None:
    ...
```
