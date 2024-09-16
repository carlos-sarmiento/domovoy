from collections.abc import Sequence
from dataclasses import dataclass, field

from domovoy.plugins.hass.types import EntityID

from .enums import (
    BinarySensorDeviceClass,
    ButtonDeviceClass,
    EntityCategory,
    EntityType,
    NumberDeviceClass,
    NumberMode,
    SensorDeviceClass,
    SensorStateClass,
    SwitchDeviceClass,
)


@dataclass(kw_only=True)
class ServEntEntityConfig:
    entity_type: EntityType
    servent_id: str
    name: str
    default_state: str | bool | int | float | None = None
    fixed_attributes: dict[str, str | bool | int | float] = field(default_factory=dict)
    entity_category: EntityCategory | None = None
    disabled_by_default: bool = False
    app_name: str | None = None


@dataclass(kw_only=True)
class ServEntSensorConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.SENSOR
    device_class: SensorDeviceClass | None = None
    unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    options: Sequence[str] | None = None

    def __post_init__(self) -> None:
        if self.options is not None and self.device_class is None:
            self.device_class = SensorDeviceClass.ENUM

        elif self.options is not None and self.device_class != SensorDeviceClass.ENUM:
            raise ValueError(
                "If providing Options for a sensor, the device class should be ENUM",
            )
        else:
            self.device_class = self.device_class


@dataclass(kw_only=True)
class ServEntNumberConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.NUMBER
    device_class: NumberDeviceClass | None = None
    unit_of_measurement: str | None = None
    mode: NumberMode
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None


@dataclass(kw_only=True)
class ServEntBinarySensorConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.BINARY_SENSOR
    device_class: BinarySensorDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntThresholdBinarySensorConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.THRESHOLD_BINARY_SENSOR
    entity_id: EntityID
    device_class: BinarySensorDeviceClass | None = None
    lower: float | None = None
    upper: float | None = None
    hysteresis: float = 0

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            raise ValueError(
                "Threshold sensor must have at least a lower or an upper value set.",
            )


@dataclass(kw_only=True)
class ServEntSelectConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.SELECT
    options: Sequence[str]


@dataclass(kw_only=True)
class ServEntSwitchConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.SWITCH
    device_class: SwitchDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntButtonConfig(ServEntEntityConfig):
    entity_type: EntityType = EntityType.BUTTON
    event: str
    event_data: dict = field(default_factory=dict)
    device_class: ButtonDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntDeviceConfig:
    device_id: str
    name: str
    manufacturer: str | None = None
    model: str | None = None
    version: str | None = None
    app_name: str | None = None
    is_global: bool = False
