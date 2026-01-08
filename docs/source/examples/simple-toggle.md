# Simple Toggle Examples

These examples show basic on/off automations.

## Toggle at Specific Times

Turn entities on/off at scheduled times:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app
from domovoy.plugins.hass.types import EntityID

@dataclass
class ToggleAtTimeConfig(AppConfigBase):
    start: str  # Time to turn on (e.g., "08:00:00")
    stop: str   # Time to turn off (e.g., "22:00:00")
    entity_id: EntityID | list[EntityID]

class ToggleAtTime(AppBase[ToggleAtTimeConfig]):
    async def initialize(self) -> None:
        self.callbacks.run_daily(self.activate, self.config.start)
        self.callbacks.run_daily(self.deactivate, self.config.stop)

    async def activate(self) -> None:
        await self.hass.services.homeassistant.turn_on(
            entity_id=self.config.entity_id
        )

    async def deactivate(self) -> None:
        await self.hass.services.homeassistant.turn_off(
            entity_id=self.config.entity_id
        )

# Usage
register_app(
    app_class=ToggleAtTime,
    app_name="porch_light_schedule",
    config=ToggleAtTimeConfig(
        start="18:00:00",
        stop="23:00:00",
        entity_id="light.porch",  # type: ignore
    ),
)
```

## Toggle Based on Schedule Entity

Follow a Home Assistant schedule helper:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app
from domovoy.plugins.hass.types import EntityID, HassValue

@dataclass
class ToggleAtScheduleConfig(AppConfigBase):
    schedule_id: EntityID  # schedule.my_schedule
    entity_id: EntityID | list[EntityID]

class ToggleAtSchedule(AppBase[ToggleAtScheduleConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.schedule_id,
            self.on_schedule_change,
            immediate=True,  # Apply current state on startup
        )

    async def on_schedule_change(self, new: HassValue) -> None:
        if new == "on":
            await self.hass.services.homeassistant.turn_on(
                entity_id=self.config.entity_id
            )
        else:
            await self.hass.services.homeassistant.turn_off(
                entity_id=self.config.entity_id
            )

# Usage
register_app(
    app_class=ToggleAtSchedule,
    app_name="living_room_schedule",
    config=ToggleAtScheduleConfig(
        schedule_id="schedule.living_room",  # type: ignore
        entity_id="light.living_room",  # type: ignore
    ),
)
```

## Toggle with Button Press

React to Z-Wave or Zigbee button presses:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app
from domovoy.plugins.hass.domains import SensorEntity, SwitchEntity, LightEntity
from domovoy.plugins.hass.types import HassValue

@dataclass
class ToggleWithButtonConfig(AppConfigBase):
    entity_id: SwitchEntity | LightEntity | list[SwitchEntity | LightEntity]
    trigger_entity_id: SensorEntity  # Button/action sensor
    trigger_states: str | list[str]  # States that trigger toggle

class ToggleWithButton(AppBase[ToggleWithButtonConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.trigger_entity_id,
            self.on_button_press,
        )

        self.trigger_states = (
            self.config.trigger_states
            if isinstance(self.config.trigger_states, list)
            else [self.config.trigger_states]
        )

    async def on_button_press(self, new: HassValue) -> None:
        if new in self.trigger_states:
            await self.hass.services.homeassistant.toggle(
                entity_id=self.config.entity_id
            )

# Usage - toggle lights on double-tap
register_app(
    app_class=ToggleWithButton,
    app_name="bedroom_button",
    config=ToggleWithButtonConfig(
        entity_id="light.bedroom",  # type: ignore
        trigger_entity_id="sensor.bedroom_switch_action",  # type: ignore
        trigger_states=["double_tap"],
    ),
)
```

## Multiple Instances

Register multiple toggles at once:

```python
from domovoy.applications.registration import register_app_multiple

configs = {
    "porch_light": ToggleAtTimeConfig(
        start="18:00:00",
        stop="23:00:00",
        entity_id="light.porch",  # type: ignore
    ),
    "garage_light": ToggleAtTimeConfig(
        start="06:00:00",
        stop="08:00:00",
        entity_id="light.garage",  # type: ignore
    ),
    "backyard_lights": ToggleAtTimeConfig(
        start="19:00:00",
        stop="22:00:00",
        entity_id=[
            "light.backyard_1",  # type: ignore
            "light.backyard_2",  # type: ignore
        ],
    ),
}

register_app_multiple(
    app_class=ToggleAtTime,
    configs=configs,
)
```

## Key Concepts

- **`run_daily(callback, time)`**: Schedule a daily callback
- **`listen_state(entity, callback, immediate=True)`**: React to state changes
- **`homeassistant.turn_on/turn_off/toggle`**: Generic entity control
- **`register_app_multiple`**: Multiple instances of the same app
