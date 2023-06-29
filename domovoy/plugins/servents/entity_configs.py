from dataclasses import dataclass
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
    type: EntityType
    servent_id: str
    name: str
    default_state: str | bool | int | float | None = None
    fixed_attributes: dict[str, str | bool | int | float] | None = None
    entity_category: EntityCategory | None = None
    disabled_by_default: bool = False
    app_name: str | None = None


@dataclass(kw_only=True)
class ServEntSensorConfig(ServEntEntityConfig):
    type: EntityType = EntityType.SENSOR
    device_class: SensorDeviceClass | None = None
    unit_of_measurement: str | None = None
    state_class: SensorStateClass | None = None
    options: list[str] | None = None

    def __post_init__(self):
        if self.options is not None and self.device_class is None:
            self.device_class = SensorDeviceClass.ENUM

        elif self.options is not None and self.device_class != SensorDeviceClass.ENUM:
            raise ValueError(
                "If providing Options for a sensor, the device class should be ENUM"
            )
        else:
            self.device_class = self.device_class


@dataclass(kw_only=True)
class ServEntNumberConfig(ServEntEntityConfig):
    type: EntityType = EntityType.NUMBER
    device_class: NumberDeviceClass | None = None
    unit_of_measurement: str | None = None
    mode: NumberMode | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None


@dataclass(kw_only=True)
class ServEntBinarySensorConfig(ServEntEntityConfig):
    type: EntityType = EntityType.BINARY_SENSOR
    device_class: BinarySensorDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntThresholdBinarySensorConfig(ServEntEntityConfig):
    type: EntityType = EntityType.THRESHOLD_BINARY_SENSOR
    entity_id: str | None = None
    device_class: BinarySensorDeviceClass | None = None
    lower: float | None = None
    upper: float | None = None
    hysteresis: float = 0

    def __post_init__(self):
        if self.lower is None and self.upper is None:
            raise ValueError(
                "Threshold sensor must have at least a lower or an upper value set."
            )


@dataclass(kw_only=True)
class ServEntSelectConfig(ServEntEntityConfig):
    type: EntityType = EntityType.SELECT
    options: list[str] | None = None


@dataclass(kw_only=True)
class ServEntSwitchConfig(ServEntEntityConfig):
    type: EntityType = EntityType.SWITCH
    device_class: SwitchDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntButtonConfig(ServEntEntityConfig):
    type: EntityType = EntityType.BUTTON
    event: str | None = None
    event_data: dict | None = None
    device_class: ButtonDeviceClass | None = None


@dataclass(kw_only=True)
class ServEntDeviceConfig:
    servent_device_id: str | None = None
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    version: str | None = None
    app_name: str | None = None
    is_global: bool = False
