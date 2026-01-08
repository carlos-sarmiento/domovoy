# Home Assistant Integration Guide

The hass plugin provides full integration with Home Assistant.

## Reading Entity State

### Get State Value

```python
from domovoy.plugins.hass.types import EntityID

# Get the current state value
state = self.hass.get_state(entity_id)
# Returns: "on", "off", "23.5", etc.
```

### Get Full State Object

```python
# Get complete state with attributes
entity_state = self.hass.get_full_state(entity_id)

# Access properties
state = entity_state.state           # "on"
brightness = entity_state.attributes.get("brightness")  # 255
last_changed = entity_state.last_changed  # datetime
last_updated = entity_state.last_updated  # datetime
```

### Get Typed State

```python
# For entities with typed state values
from domovoy.plugins.hass.domains import SensorEntity

sensor: SensorEntity = entities.sensor.temperature
typed_value = self.hass.get_typed_state(sensor)
# Returns appropriate type based on entity
```

## Calling Services

### Typed Service Calls (Recommended)

Use auto-generated typed service stubs for IDE autocomplete and type checking:

```python
# Light services
await self.hass.services.light.turn_on(
    entity_id=light,
    brightness=255,
    color_temp=300,
)
await self.hass.services.light.turn_off(entity_id=light)

# Switch services
await self.hass.services.switch.turn_on(entity_id=switch)
await self.hass.services.switch.toggle(entity_id=switch)

# Climate services
await self.hass.services.climate.set_temperature(
    entity_id=thermostat,
    temperature=72,
)

# Generic homeassistant domain
await self.hass.services.homeassistant.turn_on(entity_id=entity)
await self.hass.services.homeassistant.turn_off(entity_id=entity)
await self.hass.services.homeassistant.toggle(entity_id=entity)
```

### Generic Service Call

For services without typed stubs:

```python
# Basic call
await self.hass.call_service(
    "notify.mobile_app_phone",
    message="Hello World",
    title="Notification",
)

# With return response
response = await self.hass.call_service(
    "weather.get_forecasts",
    entity_id=weather_entity,
    type="hourly",
    return_response=True,
)
```

## Automation Triggers

Subscribe to Home Assistant automation triggers:

```python
async def initialize(self) -> None:
    trigger_config = {
        "platform": "state",
        "entity_id": "binary_sensor.motion",
        "to": "on",
        "for": {"seconds": 30},
    }

    self.callbacks.listen_trigger(trigger_config, self.on_motion)

async def on_motion(self) -> None:
    self.log.info("Motion detected for 30 seconds")
```

## Firing Events

Send custom events to the Home Assistant event bus:

```python
await self.hass.fire_event(
    "my_custom_event",
    {"action": "triggered", "source": "domovoy"},
)
```

## Waiting for State

Wait asynchronously for an entity to reach a specific state:

```python
from domovoy.applications.types import Interval

# Wait for light to turn on (with timeout)
await self.hass.wait_for_state_to_be(
    entity_id=light,
    states=["on"],
    timeout=Interval(seconds=30),
)

# Wait for light to be on for at least 5 seconds
await self.hass.wait_for_state_to_be(
    entity_id=light,
    states=["on"],
    duration=Interval(seconds=5),
    timeout=Interval(minutes=1),
)
```

## Finding Entities

### Get All Entities

```python
# Get all entity IDs
all_ids = self.hass.get_all_entity_ids()

# Get all entity state objects
all_entities = self.hass.get_all_entities()
```

### Search by Attribute

```python
# Find entities with a specific attribute value
lights = self.hass.get_entity_id_by_attribute("device_class", "light")

# Find entities that have an attribute (any value)
lockouts = self.hass.get_entity_id_by_attribute("is_pool_lockout_switch", None)
```

## Entity ID Typing

Entity IDs are typed objects for type safety:

```python
from domovoy.plugins.hass.types import EntityID
from domovoy.plugins.hass.domains import LightEntity, SwitchEntity

# In config
@dataclass
class MyAppConfig(AppConfigBase):
    light: LightEntity
    switch: SwitchEntity
    generic: EntityID  # Any entity type
```

When Domovoy connects to Home Assistant, it generates typed stubs for your specific entities:

```python
# Auto-generated entities module (synthetic)
from synthetic import entities

# Access entities with full typing
light = entities.light.living_room
sensor = entities.sensor.temperature
switch = entities.switch.pool_pump
```

## Development Helpers

### Validate Entity Exists

Check for typos during development:

```python
async def initialize(self) -> None:
    # Logs warning if entity doesn't exist
    self.hass.warn_if_entity_doesnt_exists(self.config.entity_id)
    self.hass.warn_if_entity_doesnt_exists([entity_a, entity_b])
```

### Search Related Entities

Find related entities/devices:

```python
# Find all entities related to a device
related = await self.hass.search_related("device", device_id)
```

## Advanced: Raw Commands

For unsupported operations, send raw WebSocket commands:

```python
result = await self.hass.send_raw_command(
    "config/entity_registry/update",
    {
        "entity_id": str(entity_id),
        "icon": "mdi:lightbulb",
    },
)
```

## Best Practices

### Always Use await for Service Calls

```python
# Good
await self.hass.services.light.turn_on(entity_id=light)

# Bad - fire and forget (may not complete)
self.hass.services.light.turn_on(entity_id=light)  # Missing await!
```

### Cache State Locally When Needed

```python
async def initialize(self) -> None:
    # State is cached by Domovoy and updated via WebSocket
    # Safe to call frequently
    state = self.hass.get_state(entity_id)
```

### Use Typed Entities in Config

```python
from domovoy.plugins.hass.domains import LightEntity, SwitchEntity

@dataclass
class MyAppConfig(AppConfigBase):
    # Type-safe entity references
    main_light: LightEntity
    backup_light: LightEntity
    power_switch: SwitchEntity
```
