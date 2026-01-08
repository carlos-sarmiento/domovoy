# State Listener Examples

These examples show how to react to entity state changes.

## Basic State Listener

React when an entity's state changes:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app
from domovoy.plugins.hass.types import EntityID, HassValue

@dataclass
class MotionLightConfig(AppConfigBase):
    motion_sensor: EntityID
    light: EntityID

class MotionLight(AppBase[MotionLightConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.motion_sensor,
            self.on_motion,
        )

    async def on_motion(self, old: HassValue, new: HassValue) -> None:
        if new == "on":
            self.log.info("Motion detected, turning on light")
            await self.hass.services.light.turn_on(
                entity_id=self.config.light
            )
        elif old == "on" and new == "off":
            self.log.info("Motion cleared, turning off light")
            await self.hass.services.light.turn_off(
                entity_id=self.config.light
            )

register_app(
    app_class=MotionLight,
    app_name="hallway_motion",
    config=MotionLightConfig(
        motion_sensor="binary_sensor.hallway_motion",  # type: ignore
        light="light.hallway",  # type: ignore
    ),
)
```

## Alert When State Persists

Alert when an entity stays in a specific state for a duration:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.types import Interval
from domovoy.plugins.hass.types import EntityID, HassValue

@dataclass
class AlertWhenStateConfig(AppConfigBase):
    entity_id: EntityID
    alert_state: str  # State to alert on (e.g., "unavailable")
    min_duration: Interval  # How long before alerting

class AlertWhenState(AppBase[AlertWhenStateConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.entity_id,
            self.on_state_change,
            immediate=True,
        )

    async def on_state_change(self, new: HassValue) -> None:
        if new != self.config.alert_state:
            return

        # Wait to see if state persists
        await self.time.sleep_for(self.config.min_duration)

        # Check if still in alert state
        current = self.hass.get_state(self.config.entity_id)
        if current == self.config.alert_state:
            self.log.warning(
                "Entity {entity} has been {state} for {duration}",
                entity=self.config.entity_id,
                state=self.config.alert_state,
                duration=self.config.min_duration,
            )
            # Fire alert event
            await self.hass.fire_event(
                "domovoy_alert",
                {
                    "entity_id": str(self.config.entity_id),
                    "state": self.config.alert_state,
                },
            )
```

## Listen to Multiple Entities

Monitor several entities with one callback:

```python
@dataclass
class MultiSensorConfig(AppConfigBase):
    sensors: list[EntityID]

class MultiSensorMonitor(AppBase[MultiSensorConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.sensors,  # List of entities
            self.on_any_change,
            immediate=True,
        )

    async def on_any_change(
        self,
        entity_id: EntityID,
        old: HassValue,
        new: HassValue,
    ) -> None:
        self.log.info(
            "Sensor {entity} changed: {old} -> {new}",
            entity=entity_id,
            old=old,
            new=new,
        )
```

## Listen to Attributes

Monitor specific attributes instead of state:

```python
class BrightnessMonitor(AppBase[BrightnessConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_attribute(
            self.config.light,
            "brightness",  # Attribute name
            self.on_brightness_change,
        )

    async def on_brightness_change(
        self,
        entity_id: EntityID,
        attribute: str,
        old: HassValue,
        new: HassValue,
    ) -> None:
        self.log.info(
            "Brightness changed from {old} to {new}",
            old=old,
            new=new,
        )
```

## Conditional State Logic

React based on complex conditions:

```python
from collections.abc import Callable
from domovoy.plugins.hass.types import HassValue

@dataclass
class ConditionalAlertConfig(AppConfigBase):
    entity_id: EntityID
    condition: Callable[[HassValue], bool]  # Lambda function
    alert_message: str

class ConditionalAlert(AppBase[ConditionalAlertConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.entity_id,
            self.check_condition,
            immediate=True,
        )

    async def check_condition(self, new: HassValue) -> None:
        if self.config.condition(new):
            self.log.warning(self.config.alert_message)
            await self.hass.fire_event(
                "conditional_alert",
                {"message": self.config.alert_message},
            )

# Usage - alert when temperature exceeds 80
register_app(
    app_class=ConditionalAlert,
    app_name="temp_alert",
    config=ConditionalAlertConfig(
        entity_id="sensor.temperature",  # type: ignore
        condition=lambda x: float(x) > 80 if x not in (None, "unavailable") else False,
        alert_message="Temperature is too high!",
    ),
)
```

## One-Shot Listener

Listen only once, then stop:

```python
class DoorOpenNotifier(AppBase[DoorConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.door_sensor,
            self.on_first_open,
            oneshot=True,  # Only fires once
        )

    async def on_first_open(self, new: HassValue) -> None:
        if new == "on":
            self.log.info("Door opened for the first time")
            # This callback won't fire again
```

## Extended Callback with Extra Data

Pass additional data to callbacks:

```python
@dataclass
class ZoneConfig:
    name: str
    entity_id: EntityID

@dataclass
class MultiZoneConfig(AppConfigBase):
    zones: list[ZoneConfig]

class MultiZoneMonitor(AppBase[MultiZoneConfig]):
    async def initialize(self) -> None:
        for zone in self.config.zones:
            self.callbacks.listen_state_extended(
                zone.entity_id,
                self.on_zone_change,
                immediate=True,
                zone_name=zone.name,  # Extra data
            )

    async def on_zone_change(
        self,
        entity_id: EntityID,
        attribute: str,
        old: HassValue,
        new: HassValue,
        zone_name: str,  # Receives extra data
    ) -> None:
        self.log.info(
            "Zone '{zone}' changed to {state}",
            zone=zone_name,
            state=new,
        )
```

## Key Concepts

- **`listen_state(entity, callback)`**: Basic state monitoring
- **`listen_attribute(entity, attr, callback)`**: Monitor specific attributes
- **`immediate=True`**: Get current state on startup
- **`oneshot=True`**: Fire callback only once
- **`listen_state_extended`**: Pass extra arguments to callbacks
