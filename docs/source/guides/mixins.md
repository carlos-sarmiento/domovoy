# Mixins Guide

Mixins allow you to share functionality across multiple apps without code duplication.

## What Are Mixins?

Mixins are classes that provide reusable functionality that can be "mixed in" to your apps through multiple inheritance.

```python
class MyApp(AlertsMixin, NotificationMixin, AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        # Access mixin functionality
        await self.alerts.add_alert(...)
        await self.notify_house_tts("Hello!")
```

## Creating a Mixin

### Basic Mixin Structure

```python
from domovoy.applications import AppBaseWithoutConfig

class MyMixin(AppBaseWithoutConfig):
    async def initialize(self) -> None:
        # Always call super() to chain initialization
        await super().initialize()

        # Your mixin setup code
        self.my_data = {}

    def my_helper_method(self) -> str:
        return "Hello from mixin!"
```

### Using the Mixin

```python
class MyApp(MyMixin, AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        await super().initialize()  # Initializes mixin too

        result = self.my_helper_method()
        self.log.info("Mixin says: {msg}", msg=result)
```

## Mixin Patterns

### Inner Implementation Class

Encapsulate mixin logic in an inner class for clean separation:

```python
class AlertsMixin(AppBaseWithoutConfig):
    class AlertsMixinImpl:
        def __init__(self, hass, callbacks, logger):
            self.__hass = hass
            self.__callbacks = callbacks
            self.__log = logger

        async def add_alert(self, config: AlertConfiguration) -> None:
            await self.__hass.fire_event("add_alert", asdict(config))

        async def clear_alert(self, alert_id: str) -> None:
            await self.__hass.fire_event("clear_alert", {"id": alert_id})

    alerts: AlertsMixinImpl

    async def initialize(self) -> None:
        await super().initialize()
        self.alerts = AlertsMixin.AlertsMixinImpl(
            self.hass,
            self.callbacks,
            self.log,
        )
```

Usage:

```python
class MyApp(AlertsMixin, AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        await super().initialize()

        # Clean, namespaced API
        await self.alerts.add_alert(AlertConfiguration(
            id="my_alert",
            title="Something happened",
        ))
```

### Mixin Composition

Mixins can inherit from other mixins:

```python
class NotificationMixin(PartyModeMixin, AppBaseWithoutConfig):
    """NotificationMixin includes PartyModeMixin functionality."""

    async def notify_house_tts(self, message: str) -> None:
        # Check party mode from inherited mixin
        if self.is_silent_mode_on():
            return  # Don't announce during silent mode

        await self.hass.services.tts.speak(
            entity_id=self.tts_entity,
            message=message,
        )
```

Apps using `NotificationMixin` automatically get `PartyModeMixin` too:

```python
class MyApp(NotificationMixin, AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        await super().initialize()

        # From NotificationMixin
        await self.notify_house_tts("Hello!")

        # From PartyModeMixin (via NotificationMixin)
        if self.is_party_mode_on(backyard=True):
            self.log.info("Party time!")
```

### Global Entities in Mixins

Create shared entities that persist across apps:

```python
from servents.data_model.entity_configs import DeviceConfig

class PartyModeMixin(AppBaseWithoutConfig):
    async def initialize(self) -> None:
        await super().initialize()

        device_config = DeviceConfig(
            device_id="global_party_control",
            name="Global Party Controls",
            app_name="global_party_controls",
            is_global=True,  # Shared across all apps
        )

        # This entity is created once, shared by all apps using this mixin
        self.party_mode_select = await self.servents.create_select(
            servent_id="party_mode",
            name="Party Mode",
            options=["None", "Backyard", "Inside", "Full House"],
            creation_config=ExtraConfig(device_config=device_config),
        )

    def is_party_mode_on(self, *, inside: bool = False, backyard: bool = False) -> bool:
        state = self.party_mode_select.get_state()
        return (
            (state == "Full House" and (inside or backyard))
            or (inside and state == "Inside")
            or (backyard and state == "Backyard")
        )
```

### Storage Mixin

Persist data across app restarts:

```python
import json
from pathlib import Path

class StorageMixin(AppBaseWithoutConfig):
    class StorageMixinImpl:
        def __init__(self, app_name: str):
            self.storage_path = Path(f"storage/{app_name}.json")
            self.storage_path.parent.mkdir(exist_ok=True)

        def load(self, key: str = "__default") -> dict | None:
            if not self.storage_path.exists():
                return None
            data = json.loads(self.storage_path.read_text())
            return data.get(key)

        def save(self, data: dict, key: str = "__default") -> None:
            existing = {}
            if self.storage_path.exists():
                existing = json.loads(self.storage_path.read_text())
            existing[key] = data
            self.storage_path.write_text(json.dumps(existing))

    storage: StorageMixinImpl

    async def initialize(self) -> None:
        await super().initialize()
        self.storage = StorageMixin.StorageMixinImpl(self.meta.get_app_name())
```

### Generic Mixins with TypeVar

Create type-safe mixins that work with specific config types:

```python
from typing import TypeVar

TConfig = TypeVar("TConfig", bound=BaseZWaveSwitchConfig)

class AbstractZWaveSwitch(AppBase[TConfig]):
    """Abstract base for Z-Wave switch handlers."""

    async def initialize(self) -> None:
        await super().initialize()

        self.callbacks.listen_event(
            "zwave_js_value_notification",
            self.on_zwave_event,
        )

    async def on_zwave_event(self, data: dict) -> None:
        # Parse button press
        button = self._parse_button(data)
        action = self._parse_action(data)

        # Dispatch to specific handler
        if action == "KeyPressed":
            await self.on_key_press(button)
        elif action == "KeyPressed2x":
            await self.on_2x_key_press(button)

    # Override these in subclass
    async def on_key_press(self, button: str) -> None:
        pass

    async def on_2x_key_press(self, button: str) -> None:
        pass
```

## Best Practices

### Always Call super().initialize()

```python
async def initialize(self) -> None:
    await super().initialize()  # Required!
    # Your code here
```

### Keep Mixins Focused

Each mixin should do one thing well:

```python
# Good: Single responsibility
class AlertsMixin(AppBaseWithoutConfig):
    # Only alert-related functionality
    pass

class NotificationMixin(AppBaseWithoutConfig):
    # Only notification-related functionality
    pass

# Bad: Too many responsibilities
class KitchenSinkMixin(AppBaseWithoutConfig):
    # Alerts, notifications, storage, logging, etc.
    pass
```

### Document Mixin Requirements

```python
class MyMixin(AppBaseWithoutConfig):
    """
    Provides X functionality.

    Requires: hass, callbacks plugins
    Creates entities: sensor.mixin_status
    """
```

### Order Matters

Mixins are processed left-to-right:

```python
class MyApp(FirstMixin, SecondMixin, AppBase[Config]):
    # FirstMixin's initialize() runs before SecondMixin's
    pass
```

### Use Type Hints

```python
class AlertsMixin(AppBaseWithoutConfig):
    alerts: AlertsMixinImpl  # Type hint for IDE support

    async def initialize(self) -> None:
        await super().initialize()
        self.alerts = AlertsMixin.AlertsMixinImpl(...)
```

## Common Mixins

Here are examples of useful mixins:

| Mixin               | Purpose                          |
|---------------------|----------------------------------|
| `AlertsMixin`       | Fire and manage alerts           |
| `NotificationMixin` | Send notifications (mobile, TTS) |
| `PartyModeMixin`    | Check/control party mode state   |
| `StorageMixin`      | Persist data to disk             |
| `SwitchMixin`       | Idempotent switch helpers        |
| `TimingMixin`       | State duration checks            |
