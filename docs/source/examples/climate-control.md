# Climate Control Examples

These examples show HVAC and temperature management patterns.

## Basic Thermostat Control

Control a thermostat based on schedule:

```python
from dataclasses import dataclass
import datetime
from domovoy.applications import AppBase, AppConfigBase
from domovoy.plugins.hass.types import EntityID

@dataclass
class SchedulePoint:
    time: datetime.time
    temperature: float

@dataclass
class ThermostatConfig(AppConfigBase):
    thermostat: EntityID
    schedule: list[SchedulePoint]

class ScheduledThermostat(AppBase[ThermostatConfig]):
    async def initialize(self) -> None:
        for point in self.config.schedule:
            self.callbacks.run_daily(
                self.set_temperature,
                point.time,
                target_temp=point.temperature,
            )

    async def set_temperature(self, target_temp: float) -> None:
        await self.hass.services.climate.set_temperature(
            entity_id=self.config.thermostat,
            temperature=target_temp,
        )

# Usage
register_app(
    app_class=ScheduledThermostat,
    app_name="main_thermostat",
    config=ThermostatConfig(
        thermostat="climate.main_floor",  # type: ignore
        schedule=[
            SchedulePoint(datetime.time(6, 0), 72),   # Wake
            SchedulePoint(datetime.time(8, 0), 68),   # Away
            SchedulePoint(datetime.time(17, 0), 72),  # Home
            SchedulePoint(datetime.time(22, 0), 68),  # Sleep
        ],
    ),
)
```

## Smart HVAC with Priority Sensors

Use the best available temperature sensor:

```python
from dataclasses import dataclass
from domovoy.plugins.hass.domains import SensorEntity, BinarySensorEntity

@dataclass
class SmartHVACConfig(AppConfigBase):
    thermostat: EntityID
    default_sensor: SensorEntity
    presence_priority: dict[BinarySensorEntity, SensorEntity]
    target_temperature: float
    hysteresis: float = 0.5

class SmartHVAC(AppBase[SmartHVACConfig]):
    async def initialize(self) -> None:
        # Create sensor to show which temp sensor is active
        self.active_sensor = await self.servents.create_sensor(
            servent_id="active_temp_sensor",
            name="Active Temperature Sensor",
        )

        # Create control state sensor
        self.state_sensor = await self.servents.create_sensor(
            servent_id="hvac_state",
            name="HVAC Control State",
        )

        # Monitor presence sensors
        for presence in self.config.presence_priority.keys():
            self.callbacks.listen_state(
                presence,
                self.update_priority,
                immediate=True,
            )

        # Periodic control loop
        self.callbacks.run_every(
            Interval(minutes=5),
            self.control_loop,
            "now",
        )

    async def update_priority(self) -> None:
        """Select best temperature sensor based on presence."""
        for presence, temp_sensor in self.config.presence_priority.items():
            presence_state = self.hass.get_state(presence)
            sensor_state = self.hass.get_state(temp_sensor)

            if presence_state == "on" and sensor_state != "unavailable":
                await self.active_sensor.set_to(str(temp_sensor))
                return

        await self.active_sensor.set_to(str(self.config.default_sensor))

    async def control_loop(self) -> None:
        """Main HVAC control logic."""
        # Get active sensor
        active = self.active_sensor.get_state()
        current_temp = self.utils.parse_float(
            self.hass.get_state(active)  # type: ignore
        )

        if current_temp is None:
            return

        target = self.config.target_temperature
        diff = current_temp - target

        # Hysteresis-based control
        if diff < -self.config.hysteresis:
            mode = "heat"
        elif diff > self.config.hysteresis:
            mode = "cool"
        else:
            mode = "off"

        await self.state_sensor.set_to(
            mode,
            {
                "current_temp": current_temp,
                "target_temp": target,
                "differential": diff,
            },
        )

        await self.hass.services.climate.set_hvac_mode(
            entity_id=self.config.thermostat,
            hvac_mode=mode,
        )
```

## Pause HVAC When Windows Open

Stop heating/cooling when doors or windows are open:

```python
@dataclass
class PauseConfig(AppConfigBase):
    thermostat: EntityID
    pause_sensors: list[EntityID]  # Doors/windows
    pause_delay: Interval  # How long open before pausing
    resume_delay: Interval  # How long closed before resuming

class PausableHVAC(AppBase[PauseConfig]):
    saved_mode: str | None = None

    async def initialize(self) -> None:
        for sensor in self.config.pause_sensors:
            self.callbacks.listen_state(sensor, self.check_pause)

    async def check_pause(self) -> None:
        # Check if any sensor is open
        any_open = any(
            self.hass.get_state(s) == "on"
            for s in self.config.pause_sensors
        )

        if any_open:
            await self.pause_hvac()
        else:
            await self.resume_hvac()

    async def pause_hvac(self) -> None:
        current_mode = self.hass.get_state(self.config.thermostat)

        if current_mode != "off" and self.saved_mode is None:
            self.saved_mode = current_mode
            self.log.info("Pausing HVAC, window/door open")

            await self.hass.services.climate.set_hvac_mode(
                entity_id=self.config.thermostat,
                hvac_mode="off",
            )

    async def resume_hvac(self) -> None:
        if self.saved_mode:
            self.log.info("Resuming HVAC mode: {mode}", mode=self.saved_mode)

            await self.hass.services.climate.set_hvac_mode(
                entity_id=self.config.thermostat,
                hvac_mode=self.saved_mode,
            )
            self.saved_mode = None
```

## Mode Selection with ServEnts

Create a mode selector for HVAC control:

```python
from typing import Literal

HVACMode = Literal["Auto", "Cool", "Heat", "Off", "Schedule"]

@dataclass
class HVACModeConfig(AppConfigBase):
    thermostat: EntityID
    modes: list[HVACMode]

class HVACModeController(AppBase[HVACModeConfig]):
    async def initialize(self) -> None:
        self.mode_select = await self.servents.create_select(
            servent_id="hvac_mode",
            name="HVAC Mode",
            options=list(self.config.modes),
            default_state="Auto",
        )

        self.callbacks.listen_state(
            self.mode_select.get_entity_id(),
            self.on_mode_change,
            immediate=True,
        )

    async def on_mode_change(self, new) -> None:
        self.log.info("HVAC mode changed to: {mode}", mode=new)

        if new == "Off":
            await self.hass.services.climate.set_hvac_mode(
                entity_id=self.config.thermostat,
                hvac_mode="off",
            )
        elif new == "Schedule":
            # Enable schedule-based control
            pass
        else:
            await self.hass.services.climate.set_hvac_mode(
                entity_id=self.config.thermostat,
                hvac_mode=new.lower(),
            )
```

## Freeze Protection

Automatically protect against freezing:

```python
@dataclass
class FreezeProtectionConfig(AppConfigBase):
    outdoor_temp_sensor: SensorEntity
    freeze_threshold: float = 35.0  # °F
    protection_temp: float = 55.0

class FreezeProtection(AppBase[FreezeProtectionConfig]):
    protection_active: bool = False

    async def initialize(self) -> None:
        self.callbacks.listen_state(
            self.config.outdoor_temp_sensor,
            self.check_freeze,
            immediate=True,
        )

    async def check_freeze(self, new) -> None:
        temp = self.utils.parse_float(new)
        if temp is None:
            return

        if temp <= self.config.freeze_threshold and not self.protection_active:
            await self.activate_protection()
        elif temp > self.config.freeze_threshold + 5 and self.protection_active:
            await self.deactivate_protection()

    async def activate_protection(self) -> None:
        self.protection_active = True
        self.log.warning("Freeze protection activated!")

        await self.hass.services.climate.set_temperature(
            entity_id=self.config.thermostat,
            temperature=self.config.protection_temp,
        )

    async def deactivate_protection(self) -> None:
        self.protection_active = False
        self.log.info("Freeze protection deactivated")
```

## Key Concepts

- **Hysteresis**: Prevent rapid on/off cycling
- **Priority sensors**: Use best available data source
- **Pause conditions**: Stop HVAC when inappropriate
- **Mode selection**: User-controllable operation modes
- **Freeze protection**: Safety overrides
- **ServEnts**: Create control UI in Home Assistant
