# Advanced Patterns

These examples show complex patterns for sophisticated automations.

## Using Mixins

Share functionality across apps:

```python
from domovoy.applications import AppBase, AppBaseWithoutConfig, AppConfigBase

# Define a mixin
class AlertsMixin(AppBaseWithoutConfig):
    class AlertsImpl:
        def __init__(self, hass):
            self.hass = hass

        async def send_alert(self, title: str, message: str) -> None:
            await self.hass.fire_event(
                "domovoy_alert",
                {"title": title, "message": message},
            )

    alerts: AlertsImpl

    async def initialize(self) -> None:
        await super().initialize()
        self.alerts = AlertsMixin.AlertsImpl(self.hass)

# Use the mixin
class MyApp(AlertsMixin, AppBase[MyConfig]):
    async def initialize(self) -> None:
        await super().initialize()

        # Access mixin functionality
        await self.alerts.send_alert("Started", "App initialized")
```

## Mixin Composition

Mixins can inherit from other mixins:

```python
class NotificationMixin(PartyModeMixin, AppBaseWithoutConfig):
    """Notifications with party mode awareness."""

    async def initialize(self) -> None:
        await super().initialize()
        # PartyModeMixin is also initialized

    async def notify(self, message: str) -> None:
        if self.is_silent_mode_on():  # From PartyModeMixin
            return

        await self.hass.services.notify.mobile_app(
            message=message,
        )

# App gets both mixins
class MyApp(NotificationMixin, AppBase[Config]):
    async def initialize(self) -> None:
        await super().initialize()

        # From NotificationMixin
        await self.notify("Hello!")

        # From PartyModeMixin (via NotificationMixin)
        if self.is_party_mode_on():
            pass
```

## Concurrent Operations

Use asyncio for parallel operations:

```python
import asyncio

class MultiZoneController(AppBase[ZoneConfig]):
    async def initialize(self) -> None:
        # Create many entities in parallel
        self.zones = await asyncio.gather(*[
            self.create_zone(zone)
            for zone in self.config.zones
        ])

    async def create_zone(self, zone: ZoneInfo):
        sensor, switch, button = await asyncio.gather(
            self.servents.create_sensor(
                servent_id=f"{zone.id}_temp",
                name=f"{zone.name} Temperature",
            ),
            self.servents.create_switch(
                servent_id=f"{zone.id}_enabled",
                name=f"{zone.name} Enabled",
            ),
            self.servents.listen_button_press(
                self.on_zone_reset,
                button_name=f"{zone.name} Reset",
                event_name_to_fire=f"{zone.id}_reset",
                event_data={"zone_id": zone.id},
            ),
        )
        return {"sensor": sensor, "switch": switch, "button": button}
```

## State Machine Pattern

Manage complex states:

```python
from enum import Enum
from typing import Literal

class SystemState(Enum):
    IDLE = "idle"
    WARMING_UP = "warming_up"
    RUNNING = "running"
    COOLING_DOWN = "cooling_down"
    ERROR = "error"

class StateMachineApp(AppBase[StateMachineConfig]):
    state: SystemState = SystemState.IDLE

    async def initialize(self) -> None:
        self.state_sensor = await self.servents.create_sensor(
            servent_id="system_state",
            name="System State",
        )
        await self.update_state_sensor()

        # Start button
        await self.servents.listen_button_press(
            self.start_system,
            button_name="Start System",
            event_name_to_fire="system_start",
        )

    async def transition_to(self, new_state: SystemState) -> None:
        old_state = self.state
        self.state = new_state

        self.log.info(
            "State transition: {old} -> {new}",
            old=old_state.value,
            new=new_state.value,
        )

        await self.update_state_sensor()
        await self.on_state_enter(new_state)

    async def on_state_enter(self, state: SystemState) -> None:
        if state == SystemState.WARMING_UP:
            await self.time.sleep_for(Interval(minutes=5))
            await self.transition_to(SystemState.RUNNING)

        elif state == SystemState.COOLING_DOWN:
            await self.time.sleep_for(Interval(minutes=2))
            await self.transition_to(SystemState.IDLE)

    async def start_system(self) -> None:
        if self.state != SystemState.IDLE:
            self.log.warning("Cannot start, not idle")
            return

        await self.transition_to(SystemState.WARMING_UP)

    async def update_state_sensor(self) -> None:
        await self.state_sensor.set_to(self.state.value)
```

## External API Integration

Call external services:

```python
import aiohttp

class WeatherIntegration(AppBase[WeatherConfig]):
    session: aiohttp.ClientSession | None = None

    async def initialize(self) -> None:
        self.session = aiohttp.ClientSession()

        self.weather_sensor = await self.servents.create_sensor(
            servent_id="external_weather",
            name="External Weather",
        )

        self.callbacks.run_every(
            Interval(hours=1),
            self.fetch_weather,
            "now",
        )

    async def finalize(self) -> None:
        if self.session:
            await self.session.close()

    async def fetch_weather(self) -> None:
        if not self.session:
            return

        try:
            async with self.session.get(self.config.api_url) as resp:
                data = await resp.json()
                await self.weather_sensor.set_to(
                    data["temperature"],
                    {"humidity": data["humidity"]},
                )
        except Exception as e:
            self.log.error("Weather fetch failed: {err}", err=e)
```

## TypeGuard Validation

Type-safe runtime validation:

```python
from typing import Literal, get_args
from typing_extensions import TypeGuard

ValidMode = Literal["auto", "manual", "schedule", "off"]
VALID_MODES: list[str] = list(get_args(ValidMode))

def is_valid_mode(value: str) -> TypeGuard[ValidMode]:
    return value in VALID_MODES

class TypeSafeApp(AppBase[Config]):
    async def on_mode_change(self, new) -> None:
        if not isinstance(new, str):
            return

        if is_valid_mode(new):
            # new is now typed as ValidMode
            await self.apply_mode(new)
        else:
            self.log.warning("Invalid mode: {mode}", mode=new)

    async def apply_mode(self, mode: ValidMode) -> None:
        # Type-safe handling
        match mode:
            case "auto":
                pass
            case "manual":
                pass
            case "schedule":
                pass
            case "off":
                pass
```

## Persistent Storage

Save state across restarts:

```python
import json
from pathlib import Path

class PersistentApp(AppBase[PersistentConfig]):
    storage_path: Path

    async def initialize(self) -> None:
        self.storage_path = Path(f"storage/{self.meta.get_app_name()}.json")
        self.storage_path.parent.mkdir(exist_ok=True)

        # Load saved state
        self.data = self.load_data()

        self.counter_sensor = await self.servents.create_sensor(
            servent_id="counter",
            name="Counter",
            default_state=self.data.get("counter", 0),
        )

    def load_data(self) -> dict:
        if self.storage_path.exists():
            return json.loads(self.storage_path.read_text())
        return {}

    def save_data(self) -> None:
        self.storage_path.write_text(json.dumps(self.data))

    async def increment(self) -> None:
        self.data["counter"] = self.data.get("counter", 0) + 1
        self.save_data()
        await self.counter_sensor.set_to(self.data["counter"])
```

## Event-Driven Architecture

React to custom events:

```python
class EventDrivenApp(AppBase[EventConfig]):
    async def initialize(self) -> None:
        # Listen to custom events
        self.callbacks.listen_event(
            "domovoy_command",
            self.on_command,
        )

        # Create command button
        await self.servents.listen_button_press(
            self.send_command,
            button_name="Send Command",
            event_name_to_fire="domovoy_command",
            event_data={"action": "refresh"},
        )

    async def on_command(self, data: dict) -> None:
        action = data.get("action")
        self.log.info("Received command: {action}", action=action)

        if action == "refresh":
            await self.refresh_data()
        elif action == "reset":
            await self.reset_state()
```

## Key Concepts

- **Mixins**: Share functionality via multiple inheritance
- **asyncio.gather**: Parallel async operations
- **State machines**: Manage complex state transitions
- **External APIs**: aiohttp for HTTP requests
- **TypeGuard**: Runtime type validation
- **Persistence**: Save state to disk
- **Events**: Loosely coupled communication
