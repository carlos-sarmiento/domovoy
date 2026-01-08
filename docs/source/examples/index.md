# Examples

This section contains real-world examples extracted from production Domovoy apps.

## Example Categories

| Example                               | Description                                           |
|---------------------------------------|-------------------------------------------------------|
| [Simple Toggle](simple-toggle.md)     | Basic on/off automations at specific times            |
| [State Listeners](state-listeners.md) | Reacting to entity state changes                      |
| [Scheduling](scheduling.md)           | Time-based automations (daily, sun events, intervals) |
| [Entity Creation](entity-creation.md) | Creating sensors, switches, and buttons               |
| [Climate Control](climate-control.md) | HVAC and temperature management patterns              |
| [Advanced Patterns](advanced.md)      | Mixins, concurrent operations, state machines         |

## Quick Reference

### Minimal App

```python
from domovoy.applications import AppBase, EmptyAppConfig
from domovoy.applications.registration import register_app

class MinimalApp(AppBase[EmptyAppConfig]):
    async def initialize(self) -> None:
        self.log.info("App started!")

register_app(
    app_class=MinimalApp,
    app_name="minimal_app",
    config=EmptyAppConfig(),
)
```

### App with Configuration

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app

@dataclass
class MyConfig(AppConfigBase):
    entity_id: str
    threshold: float = 75.0

class MyApp(AppBase[MyConfig]):
    async def initialize(self) -> None:
        self.log.info(
            "Monitoring {entity} with threshold {thresh}",
            entity=self.config.entity_id,
            thresh=self.config.threshold,
        )

register_app(
    app_class=MyApp,
    app_name="my_app",
    config=MyConfig(entity_id="sensor.temperature", threshold=80.0),
)
```

### Common Patterns

```python
# State listener
self.callbacks.listen_state(entity_id, self.on_change)

# Daily schedule
self.callbacks.run_daily(self.task, "08:00:00")

# Sun event
self.callbacks.run_daily_on_sun_event(self.task, "sunset")

# Service call
await self.hass.services.light.turn_on(entity_id=light, brightness=255)

# Create entity
sensor = await self.servents.create_sensor("id", "Name")
```

## Source Code

These examples are based on production apps. See the full source files for complete implementations with error handling and edge cases.
