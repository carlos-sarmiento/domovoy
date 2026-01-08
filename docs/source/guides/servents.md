# ServEnts Guide

ServEnts allows you to create Home Assistant entities directly from Python code.

:::{note}
ServEnts requires the [ServEnts custom component](https://github.com/carlos-sarmiento/servents) to be installed in Home Assistant.
:::

## Overview

Instead of manually creating helpers in Home Assistant, ServEnts lets you:

- Create sensors, switches, buttons, and other entities from Python
- Update entity states programmatically
- React to entity interactions (button presses, switch toggles)

## Creating Entities

### Sensors

Create a sensor to display values:

```python
async def initialize(self) -> None:
    self.temperature_sensor = await self.servents.create_sensor(
        servent_id="room_temperature",
        name="Room Temperature",
        device_class="temperature",
        unit_of_measurement="°F",
        state_class="measurement",
    )

    # Update the sensor value
    await self.temperature_sensor.set_to(72.5)
```

### Binary Sensors

Create on/off state sensors:

```python
async def initialize(self) -> None:
    self.door_sensor = await self.servents.create_binary_sensor(
        servent_id="door_open",
        name="Front Door",
        device_class="door",
    )

    # Set state
    await self.door_sensor.set_on()   # Set to "on"
    await self.door_sensor.set_off()  # Set to "off"
    await self.door_sensor.set_to(True)  # Using boolean
```

### Switches

Create toggleable switches:

```python
async def initialize(self) -> None:
    self.automation_switch = await self.servents.create_switch(
        servent_id="automation_enabled",
        name="Automation Enabled",
        device_class="switch",
    )

    # Check and control state
    if self.automation_switch.is_on():
        await self.automation_switch.set_off()
```

### Buttons

Create buttons that trigger callbacks:

```python
async def initialize(self) -> None:
    self.reset_button = await self.servents.listen_button_press(
        callback=self.on_reset_pressed,
        button_name="Reset Counter",
        event_name_to_fire="counter_reset",
    )

async def on_reset_pressed(self) -> None:
    self.log.info("Reset button pressed!")
    self.counter = 0
```

### Number Inputs

Create adjustable number inputs:

```python
async def initialize(self) -> None:
    self.threshold = await self.servents.create_number(
        servent_id="temperature_threshold",
        name="Temperature Threshold",
        mode="slider",  # or "box"
        min_value=60,
        max_value=90,
        step=1,
        unit_of_measurement="°F",
        default_state=75,
    )

    # Get current value
    current = self.threshold.get_state()
```

### Select Inputs

Create dropdown selectors:

```python
async def initialize(self) -> None:
    self.mode_select = await self.servents.create_select(
        servent_id="operating_mode",
        name="Operating Mode",
        options=["Auto", "Manual", "Off"],
        default_state="Auto",
    )

    # Set value
    await self.mode_select.set_to("Manual")
```

### Threshold Binary Sensors

Create binary sensors that automatically trigger based on another sensor's value:

```python
async def initialize(self) -> None:
    # Automatically turns on when pump pressure > 5
    self.pump_running = await self.servents.create_threshold_binary_sensor(
        servent_id="pump_is_running",
        name="Pump Running",
        entity_id=entities.sensor.pump_pressure,
        lower=5,  # Threshold value
        upper=100,
        hysteresis=0.5,
    )
```

## Entity State Management

### Getting State

```python
# Get current state value
state = self.sensor.get_state()  # Returns the state value

# Get full state with attributes
full_state = self.sensor.get_full_state()
attributes = full_state.attributes

# Get the Home Assistant entity ID
entity_id = self.sensor.get_entity_id()
```

### Setting State with Attributes

```python
# Set state with custom attributes
await self.sensor.set_to(
    72.5,  # State value
    {
        "last_updated": str(datetime.now()),
        "source": "local_sensor",
        "icon": "mdi:thermometer",
    },
)
```

## Device Configuration

Entities are grouped into devices. By default, each app gets its own device.

### Custom Device Name

```python
async def initialize(self) -> None:
    self.servents.update_default_device_name_for_app("Climate Controller")

    # All entities will be grouped under "Climate Controller"
    self.sensor = await self.servents.create_sensor(...)
```

### Custom Device Configuration

```python
from servents.data_model.entity_configs import DeviceConfig

device_config = DeviceConfig(
    device_id="my_custom_device",
    name="My Custom Device",
    manufacturer="Domovoy",
    model="Climate Controller v2",
)

self.servents.set_default_device_for_app(device_config)
```

### Global Entities

Create entities shared across apps:

```python
from servents.data_model.entity_configs import DeviceConfig
from domovoy.plugins.servents import ExtraConfig

device_config = DeviceConfig(
    device_id="global_controls",
    name="Global Controls",
    app_name="global_controls",
    is_global=True,  # Mark as global
)

self.global_switch = await self.servents.create_switch(
    servent_id="party_mode",
    name="Party Mode",
    creation_config=ExtraConfig(device_config=device_config),
)
```

## Concurrent Entity Creation

Create multiple entities in parallel for faster initialization:

```python
import asyncio

async def initialize(self) -> None:
    sensor, switch, button = await asyncio.gather(
        self.servents.create_sensor("temp", "Temperature"),
        self.servents.create_switch("enabled", "Enabled"),
        self.servents.listen_button_press(
            self.on_press,
            "Reset",
            "reset_event",
        ),
    )

    self.sensor = sensor
    self.switch = switch
    self.button = button
```

## Diagnostic Entities

Add a reload button for debugging:

```python
async def initialize(self) -> None:
    # Creates a "Restart App" button with diagnostic category
    await self.servents.enable_reload_button()
```

## Entity Categories

Control how entities appear in Home Assistant:

```python
# Config entities (shown in device config)
await self.servents.create_number(
    ...,
    entity_category="config",
)

# Diagnostic entities (shown in diagnostics)
await self.servents.create_sensor(
    ...,
    entity_category="diagnostic",
)
```

## Best Practices

### Wait for Entity Creation

By default, `wait_for_creation=True` ensures the entity exists in HA before continuing:

```python
# Waits for HA to register the entity
sensor = await self.servents.create_sensor(...)

# Skip waiting (for faster startup, but entity may not exist yet)
sensor = await self.servents.create_sensor(
    ...,
    creation_config=ExtraConfig(wait_for_creation=False),
)
```

### Use Descriptive IDs

```python
# Good - clear and descriptive
servent_id="hvac_temperature_setpoint"

# Bad - too generic
servent_id="temp"
```

### Listen to Your Own Entities

React when users change your entities in HA:

```python
async def initialize(self) -> None:
    self.mode_select = await self.servents.create_select(
        servent_id="mode",
        name="Mode",
        options=["Auto", "Manual", "Off"],
    )

    # Listen for changes from HA UI
    self.callbacks.listen_state(
        self.mode_select.get_entity_id(),
        self.on_mode_changed,
    )

async def on_mode_changed(self, new: HassValue) -> None:
    self.log.info("Mode changed to: {mode}", mode=new)
```
