# Entity Creation Examples

These examples show how to create Home Assistant entities from Python.

## Basic Sensor

Create a sensor to display values:

```python
from domovoy.applications import AppBase, EmptyAppConfig

class TemperatureTracker(AppBase[EmptyAppConfig]):
    async def initialize(self) -> None:
        self.temp_sensor = await self.servents.create_sensor(
            servent_id="current_temperature",
            name="Tracked Temperature",
            device_class="temperature",
            unit_of_measurement="°F",
            state_class="measurement",
        )

        # Set initial value
        await self.temp_sensor.set_to(72.5)

        # Listen to source sensor
        self.callbacks.listen_state(
            "sensor.external_temp",  # type: ignore
            self.on_temp_update,
        )

    async def on_temp_update(self, new) -> None:
        temp = self.utils.parse_float(new)
        if temp is not None:
            await self.temp_sensor.set_to(temp)
```

## Button with Callback

Create a button that triggers an action:

```python
class MaintenanceTracker(AppBase[MaintenanceConfig]):
    async def initialize(self) -> None:
        # Create reset button
        self.reset_button = await self.servents.listen_button_press(
            callback=self.on_reset,
            button_name="Reset Maintenance",
            event_name_to_fire="maintenance_reset",
            event_data={"source": "button"},
        )

        # Create due date sensor
        self.due_sensor = await self.servents.create_sensor(
            servent_id="maintenance_due",
            name="Next Maintenance Due",
            device_class="timestamp",
        )

    async def on_reset(self) -> None:
        self.log.info("Maintenance reset!")
        next_due = self.time.now() + timedelta(days=90)
        await self.due_sensor.set_to(next_due.timestamp())
```

## Switch for Automation Control

Create a switch to enable/disable automation:

```python
class ControllableAutomation(AppBase[AutomationConfig]):
    async def initialize(self) -> None:
        self.enabled_switch = await self.servents.create_switch(
            servent_id="automation_enabled",
            name="Automation Enabled",
            default_state=True,
        )

        self.callbacks.listen_state(
            self.config.trigger_entity,
            self.on_trigger,
        )

    async def on_trigger(self, new) -> None:
        # Check if automation is enabled
        if not self.enabled_switch.is_on():
            self.log.debug("Automation disabled, skipping")
            return

        # Run automation logic
        await self.do_automation()
```

## Binary Sensor

Create an on/off indicator:

```python
class ConnectionMonitor(AppBase[MonitorConfig]):
    async def initialize(self) -> None:
        self.status_sensor = await self.servents.create_binary_sensor(
            servent_id="connection_status",
            name="Connection Status",
            device_class="connectivity",
        )

        # Check connection periodically
        self.callbacks.run_every(
            Interval(minutes=1),
            self.check_connection,
            "now",
        )

    async def check_connection(self) -> None:
        is_connected = await self.test_connection()

        if is_connected:
            await self.status_sensor.set_on()
        else:
            await self.status_sensor.set_off()
```

## Select Input

Create a dropdown selector:

```python
class ModeController(AppBase[ModeConfig]):
    async def initialize(self) -> None:
        self.mode_select = await self.servents.create_select(
            servent_id="operating_mode",
            name="Operating Mode",
            options=["Auto", "Manual", "Off", "Schedule"],
            default_state="Auto",
        )

        # React to mode changes from HA UI
        self.callbacks.listen_state(
            self.mode_select.get_entity_id(),
            self.on_mode_change,
            immediate=True,
        )

    async def on_mode_change(self, new) -> None:
        self.log.info("Mode changed to: {mode}", mode=new)
        await self.apply_mode(new)
```

## Number Input

Create an adjustable number:

```python
class ThresholdController(AppBase[ThresholdConfig]):
    async def initialize(self) -> None:
        self.threshold = await self.servents.create_number(
            servent_id="temp_threshold",
            name="Temperature Threshold",
            mode="slider",
            min_value=60,
            max_value=90,
            step=1,
            unit_of_measurement="°F",
            default_state=75,
        )

        # Use threshold in automation
        self.callbacks.listen_state(
            "sensor.temperature",  # type: ignore
            self.check_threshold,
        )

    async def check_threshold(self, new) -> None:
        temp = self.utils.parse_float(new)
        threshold = self.utils.parse_float(self.threshold.get_state())

        if temp and threshold and temp > threshold:
            self.log.warning("Temperature exceeds threshold!")
```

## Concurrent Entity Creation

Create multiple entities in parallel:

```python
import asyncio

class MultiEntityApp(AppBase[MultiConfig]):
    async def initialize(self) -> None:
        # Create all entities concurrently
        (
            self.status_sensor,
            self.count_sensor,
            self.enabled_switch,
            self.reset_button,
        ) = await asyncio.gather(
            self.servents.create_binary_sensor(
                servent_id="status",
                name="Status",
            ),
            self.servents.create_sensor(
                servent_id="count",
                name="Count",
            ),
            self.servents.create_switch(
                servent_id="enabled",
                name="Enabled",
            ),
            self.servents.listen_button_press(
                self.on_reset,
                button_name="Reset",
                event_name_to_fire="reset",
            ),
        )
```

## Dynamic Entity Creation

Create entities based on runtime data:

```python
class DynamicRoomController(AppBase[RoomConfig]):
    room_switches: list

    async def initialize(self) -> None:
        # Get rooms from HA sensor
        rooms_data = self.hass.get_full_state(
            self.config.rooms_sensor
        ).attributes

        # Create switch for each room
        switch_tasks = [
            self.servents.create_switch(
                servent_id=f"clean_room_{room_id}",
                name=f"Clean {room_name}",
                fixed_attributes={"room_id": room_id},
            )
            for room_id, room_name in rooms_data.items()
        ]

        self.room_switches = await asyncio.gather(*switch_tasks)
```

## State with Attributes

Set state with custom attributes:

```python
async def update_sensor(self) -> None:
    await self.sensor.set_to(
        42,  # State value
        {
            "last_updated": str(self.time.now()),
            "source": "calculation",
            "icon": "mdi:calculator",
            "confidence": 0.95,
        },
    )
```

## Diagnostic Entities

Create entities for debugging:

```python
class DiagnosticApp(AppBase[DiagConfig]):
    async def initialize(self) -> None:
        # Reload button (built-in helper)
        await self.servents.enable_reload_button()

        # Custom diagnostic sensor
        self.debug_sensor = await self.servents.create_sensor(
            servent_id="debug_info",
            name="Debug Info",
            entity_category="diagnostic",
            disabled_by_default=True,
        )
```

## Key Concepts

- **`create_sensor`**: Display values (numbers, text, timestamps)
- **`create_binary_sensor`**: On/off state indicators
- **`create_switch`**: Toggleable controls
- **`create_button`**: Trigger actions
- **`create_number`**: Adjustable numeric inputs
- **`create_select`**: Dropdown selections
- **`listen_button_press`**: Button with automatic callback
- **`asyncio.gather`**: Create multiple entities concurrently
- **`get_entity_id()`**: Get HA entity ID for listeners
