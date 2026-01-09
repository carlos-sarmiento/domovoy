# Type Stubs Configuration

Domovoy supports auto-generated type stubs that provide IDE autocomplete and type checking for your Home Assistant entities and services. This guide explains how to configure the type system.

:::{warning}
The typed entity and service stubs **will not work** without configuring the `domovoy-typing` package and registering the stub updater apps as described below.
:::

## Overview

When configured, Domovoy generates Python stub files (`.pyi`) that contain type definitions for:

- **Entity stubs**: All entities from your Home Assistant instance (e.g., `entities.light.living_room`)
- **Service stubs**: All services with their parameters (e.g., `self.hass.services.light.turn_on()`)

These stubs enable:

- IDE autocomplete for entity names and service calls
- Type checking to catch errors before runtime
- Documentation hints for service parameters

## Installation

### 1. Install domovoy-typing

:::{note}
If you are using the starter template, this package is already included in the requirements
:::

Via pip/uv:

```bash
uv add domovoy-typing
```

### 2. Register Stub Updater Apps

Create an app file to register the stub updaters. These apps connect to Home Assistant and generate the stub files automatically.

Create `infra_apps.py` in your apps folder:

```python
from domovoy.applications.registration import register_app
from domovoy_typing.apps import (
    HassSyntheticEntitiesStubUpdater,
    HassSyntheticEntitiesStubUpdaterConfig,
    HassSyntheticServiceStubUpdater,
    HassSyntheticServiceStubUpdaterConfig,
)

# Register the service stub updater
register_app(
    app_class=HassSyntheticServiceStubUpdater,
    app_name="synthetic_services_stub",
    config=HassSyntheticServiceStubUpdaterConfig(
        stub_path=("./typings/domovoy_typing/services.pyi"),
    ),
)

# Register the entity stub updater
register_app(
    app_class=HassSyntheticEntitiesStubUpdater,
    app_name="synthetic_entities_stub",
    config=HassSyntheticEntitiesStubUpdaterConfig(
        stub_path=("./typings/domovoy_typing/entities.pyi"),
    ),
)
```

## Using the Generated Types

Once configured, import the generated types in your apps:

### Entity Types

```python
from domovoy_typing.entities import entities

class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        # Full autocomplete for entity names
        light = entities.light.living_room
        sensor = entities.sensor.outdoor_temperature
        switch = entities.switch.pool_pump

        # Use in state operations
        state = self.hass.get_state(light)

        # Use in callbacks
        self.callbacks.listen_state(sensor, self.on_temp_change)
```

### Service Types

```python
class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        # Full autocomplete for services and parameters
        await self.hass.services.light.turn_on(
            entity_id=entities.light.living_room,
            brightness=255,
            color_temp=300,
        )

        await self.hass.services.climate.set_temperature(
            entity_id=entities.climate.main_thermostat,
            temperature=72,
        )
```

## Stub Updater Configuration

### HassSyntheticServiceStubUpdater

Generates stubs for Home Assistant services.

```python
@dataclass
class HassSyntheticServiceStubUpdaterConfig(AppConfigBase):
    stub_path: str                    # Path to write the .pyi file
    dump_hass_services_json: bool = False  # Also dump raw JSON (for debugging)
```

The service stub updater regenerates when:

- Domovoy starts
- Home Assistant restarts (detected via `homeassistant_started` event)

### HassSyntheticEntitiesStubUpdater

Generates stubs for Home Assistant entities.

```python
@dataclass
class HassSyntheticEntitiesStubUpdaterConfig(AppConfigBase):
    stub_path: str                           # Path to write the .pyi file
    update_frequency: Interval = Interval(seconds=5)  # How often to check for new entities
```

The entity stub updater:

- Runs periodically (default: every 5 seconds)
- Only regenerates the file when entities change
- Includes sensor device classes and select options for better typing

## Troubleshooting

### Stubs Not Generated

1. Verify the stub updater apps are registered and running (check logs)
2. Ensure Domovoy is connected to Home Assistant
3. Check that the `typing` directory exists and is writable

### IDE Not Finding Types

1. Verify `pyproject.toml` has correct `stubPath`
2. Restart your IDE/language server after generating stubs
3. Check that the `.pyi` files exist in your typing directory

### Type Errors After HA Changes

When you add new entities or services to Home Assistant:

1. The stub updaters will automatically regenerate the files
2. Restart your IDE/language server to pick up the changes
3. For immediate updates, restart the stub updater apps

## Next Steps

- [Home Assistant Integration](hass.md) - Using typed services and entities
- [Configuration Reference](../getting-started/configuration.md) - Full configuration options
