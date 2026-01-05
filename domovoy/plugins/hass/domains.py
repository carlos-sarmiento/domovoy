from __future__ import annotations

import datetime
import inspect
import sys
from typing import Literal, TypeVar

from .entity_id import EntityID

TSelectOptions = TypeVar(name="TSelectOptions", default=str)

TSensor = TypeVar(name="TSensor", default=str)


class AutomationEntity(EntityID): ...


class BinarySensorEntity(EntityID[bool]): ...


class ButtonEntity(EntityID[datetime.datetime]): ...


class CalendarEntity(EntityID[bool]): ...


class CameraEntity(EntityID[Literal["recording", "streaming", "idle"]]): ...


class ClimateEntity(EntityID[Literal["off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"]]): ...


class ConversationEntity(EntityID): ...


class CoverEntity(EntityID[Literal["closed", "closing", "opening", "open"]]): ...


class DeviceTrackerEntity(EntityID[str]): ...


class EventEntity(EntityID[datetime.datetime]): ...


class FanEntity(EntityID[bool]): ...


class ImageEntity(EntityID[datetime.datetime]): ...


class InputBooleanEntity(EntityID[bool]): ...


class InputDatetimeEntity(EntityID[datetime.datetime]): ...


class InputNumberEntity(EntityID[float | int]): ...


class InputSelectEntity(EntityID[str]): ...


class InputTextEntity(EntityID[str]): ...


class LightEntity(EntityID[bool]): ...


class LockEntity(EntityID[Literal["locked", "locking", "unlocking", "unlocked", "jammed", "opening", "open"]]): ...


class MediaPlayerEntity(EntityID[Literal["off", "on", "idle", "playing", "paused", "buffering"]]): ...


class NotifyEntity(EntityID[datetime.datetime]): ...


class NumberEntity(EntityID[float | int]): ...


class PersonEntity(EntityID): ...


class RemoteEntity(EntityID): ...


class SceneEntity(EntityID): ...


class ScheduleEntity(EntityID): ...


class ScriptEntity(EntityID): ...


class SelectEntity[TSelectOptions](EntityID[TSelectOptions]): ...


class SensorEntity[TSensor](EntityID[TSensor]): ...


class SirenEntity(EntityID[bool]): ...


class SttEntity(EntityID): ...


class SunEntity(EntityID[Literal["above_horizon", "below_horizon"]]): ...


class SwitchEntity(EntityID[bool]): ...


class TodoEntity(EntityID[int]): ...


class TextEntity(EntityID[str]): ...


class TimeEntity(EntityID[datetime.time]): ...


class TtsEntity(EntityID): ...


class UpdateEntity(EntityID[bool]): ...


class VacuumEntity(EntityID[Literal["cleaning", "docked", "idle", "paused", "returning", "error"]]): ...


class ValveEntity(EntityID[Literal["opening", "open", "closing", "closed"]]): ...


class WakeWordEntity(EntityID): ...


class WeatherEntity(
    EntityID[
        Literal[
            "clear-night",
            "cloudy",
            "exceptional",
            "fog",
            "hail",
            "lightning",
            "lightning-rainy",
            "partlycloudy",
            "pouring",
            "rainy",
            "snowy",
            "snowy-rainy",
            "sunny",
            "windy",
            "windy-variant",
        ]
    ],
): ...


class ZoneEntity(EntityID): ...


__defined_classes: dict[str, type[EntityID]] = {
    x[0]: x[1]
    for x in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member) and member.__module__ == __name__,
    )
}


def __to_camel_case(snake_str: str) -> str:
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def get_typestr_for_domain(domain: str) -> str:
    entity_class_name = f"{__to_camel_case(domain)}Entity"
    return entity_class_name if entity_class_name in __defined_classes else "EntityID"


def get_type_for_domain(domain: str) -> type[EntityID]:
    entity_class_name = f"{__to_camel_case(domain)}Entity"
    return __defined_classes.get(entity_class_name, EntityID)


__sensor_type_cache: dict[type, type[EntityID]] = {}


def get_type_for_sensor_domain(inner_type: type) -> type[EntityID]:
    if inner_type not in __sensor_type_cache:

        class SensorEntityTyped(SensorEntity[inner_type]): ...

        __sensor_type_cache[inner_type] = SensorEntityTyped

    return __sensor_type_cache[inner_type]


def get_type_instance_for_entity_id(entity_id: str | EntityID) -> EntityID:
    if isinstance(entity_id, EntityID):
        domain = entity_id.get_domain()
    else:
        split = entity_id.split(".")
        domain: str = split[0]

    return get_type_for_domain(domain)(entity_id)
