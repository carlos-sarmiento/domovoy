# Creating Your First App

This guide covers the fundamentals of creating Domovoy apps.

## App Structure

Every Domovoy app consists of three parts:

1. **Configuration class** - Defines the app's configurable parameters
2. **App class** - Contains the automation logic
3. **Registration** - Tells Domovoy to run the app

## Basic App Template

### With Configuration

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app

@dataclass
class MyAppConfig(AppConfigBase):
    # Define your configuration parameters here
    entity_id: str
    interval_minutes: int = 5

class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        # Setup code runs when the app starts
        self.log.info("App initialized with entity: {entity}", entity=self.config.entity_id)

    async def finalize(self) -> None:
        # Cleanup code runs when the app stops (optional)
        self.log.info("App shutting down")

# Register the app
register_app(
    app_class=MyApp,
    app_name="my_app",
    config=MyAppConfig(
        entity_id="light.living_room",
        interval_minutes=10,
    ),
)
```

### Without Configuration

For simple apps that don't need configuration:

```python
from domovoy.applications import AppBase, EmptyAppConfig
from domovoy.applications.registration import register_app

class SimpleApp(AppBase[EmptyAppConfig]):
    async def initialize(self) -> None:
        self.log.info("Simple app started")

register_app(
    app_class=SimpleApp,
    app_name="simple_app",
    config=EmptyAppConfig(),
)
```

## File Naming Convention

App files must end with the configured suffix (default: `_apps.py`).

```
apps/
├── lighting_apps.py      # Valid - will be loaded
├── climate_apps.py       # Valid - will be loaded
├── helpers.py            # Ignored - not an app file
└── utils/
    └── common.py         # Ignored - can be imported by apps
```

## Available Plugins

Every app has access to these plugins through `self`:

| Plugin | Purpose |
|--------|---------|
| `self.hass` | Home Assistant integration (states, services, triggers) |
| `self.callbacks` | Event listening and scheduling |
| `self.servents` | Create Home Assistant entities |
| `self.log` | Logging with trace/debug/info/warning/error levels |
| `self.meta` | App metadata and control (restart, get name) |
| `self.time` | Time utilities (now, parse dates, sleep) |
| `self.utils` | General utilities (parse numbers, run async) |
| `self.config` | Access to your app's configuration |

## A Complete Example

Here's a practical example that turns on a light at sunset:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app
from domovoy.plugins.hass.types import EntityID

@dataclass
class SunsetLightConfig(AppConfigBase):
    light_entity: EntityID

class SunsetLight(AppBase[SunsetLightConfig]):
    async def initialize(self) -> None:
        # Schedule the light to turn on at sunset every day
        self.callbacks.run_daily_on_sun_event(
            self.turn_on_light,
            "sunset",
        )
        self.log.info("Sunset light automation initialized")

    async def turn_on_light(self) -> None:
        self.log.info("Sunset! Turning on {light}", light=self.config.light_entity)
        await self.hass.services.light.turn_on(
            entity_id=self.config.light_entity,
            brightness=200,
        )

register_app(
    app_class=SunsetLight,
    app_name="sunset_light",
    config=SunsetLightConfig(
        light_entity="light.porch",  # type: ignore
    ),
)
```

## Registering Multiple Instances

To run the same app class with different configurations:

```python
from domovoy.applications.registration import register_app_multiple

configs = {
    "living_room_sunset": SunsetLightConfig(light_entity="light.living_room"),
    "porch_sunset": SunsetLightConfig(light_entity="light.porch"),
    "bedroom_sunset": SunsetLightConfig(light_entity="light.bedroom"),
}

register_app_multiple(
    app_class=SunsetLight,
    configs=configs,
)
```

## App Lifecycle

Apps go through these states:

1. **CREATED** - App instance created
2. **INITIALIZING** - `initialize()` is running
3. **RUNNING** - App is active and processing callbacks
4. **FINALIZING** - `finalize()` is running (on shutdown or reload)
5. **TERMINATED** - App has stopped

If `initialize()` raises an exception, the app enters the **FAILED** state.

## Best Practices

### Make `initialize()` Idempotent

Since apps can be reloaded (due to hot-reload), your `initialize()` should be safe to call multiple times:

```python
async def initialize(self) -> None:
    # Good: Creates new listeners each time (old ones are cleaned up)
    self.callbacks.listen_state(self.config.entity_id, self.on_state_change)
```

### Use `finalize()` for Cleanup

Clean up resources that shouldn't persist across reloads:

```python
async def finalize(self) -> None:
    # Close connections, cancel external tasks, etc.
    if hasattr(self, 'session'):
        await self.session.close()
```

### Keep Callbacks Async

All I/O operations should use `await`:

```python
async def on_state_change(self, new) -> None:
    # Good: Uses await for Home Assistant call
    await self.hass.services.light.turn_on(entity_id="light.hall")
```

## Next Steps

- [Configuration Reference](configuration.md) - All configuration options
- [Callbacks Guide](../guides/callbacks.md) - Scheduling and event listening
- [Examples](../examples/index.md) - Real-world app examples
