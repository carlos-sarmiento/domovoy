from __future__ import annotations

import inspect
import sys
from logging import Logger, LoggerAdapter

from domovoy.core.logging import get_logger

_logcore: LoggerAdapter[Logger] = get_logger(__name__)


class EntityID:
    def __init__(self, entity_id: str | EntityID) -> None:
        if isinstance(entity_id, EntityID):
            self._entity_id = entity_id._entity_id  # noqa: SLF001
            self._domain = entity_id._domain  # noqa: SLF001
            self._entity_name: str = entity_id._entity_name  # noqa: SLF001
        else:
            self._entity_id: str = entity_id
            split = entity_id.split(".")

            self._domain = split[0]
            self._entity_name = split[1]

        if self.__class__ == EntityID:
            return

        actual_type = get_type_for_domain(self._domain)

        if self.__class__ != actual_type:
            _logcore.warning("Created an Entity instance with the wrong domain: {entity}", entity=self)

    def __str__(self) -> str:
        return self._entity_id

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self._entity_id}')"

    def __hash__(self) -> int:
        return self._entity_id.__hash__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityID) and self.__hash__() == other.__hash__()

    def get_domain(self) -> str:
        return self._domain

    def get_entity_name(self) -> str:
        return self._entity_name


class AutomationEntity(EntityID): ...


class BinarySensorEntity(EntityID): ...


class ButtonEntity(EntityID): ...


class CalendarEntity(EntityID): ...


class CameraEntity(EntityID): ...


class ClimateEntity(EntityID): ...


class ConversationEntity(EntityID): ...


class CoverEntity(EntityID): ...


class DeviceTrackerEntity(EntityID): ...


class EventEntity(EntityID): ...


class FanEntity(EntityID): ...


class ImageEntity(EntityID): ...


class InputBooleanEntity(EntityID): ...


class InputDatetimeEntity(EntityID): ...


class InputNumberEntity(EntityID): ...


class InputSelectEntity(EntityID): ...


class InputTextEntity(EntityID): ...


class LightEntity(EntityID): ...


class LockEntity(EntityID): ...


class MediaPlayerEntity(EntityID): ...


class NotifyEntity(EntityID): ...


class NumberEntity(EntityID): ...


class PersonEntity(EntityID): ...


class RemoteEntity(EntityID): ...


class SceneEntity(EntityID): ...


class ScheduleEntity(EntityID): ...


class ScriptEntity(EntityID): ...


class SelectEntity(EntityID): ...


class SensorEntity(EntityID): ...


class SirenEntity(EntityID): ...


class SttEntity(EntityID): ...


class SunEntity(EntityID): ...


class SwitchEntity(EntityID): ...


class TodoEntity(EntityID): ...


class TtsEntity(EntityID): ...


class UpdateEntity(EntityID): ...


class VacuumEntity(EntityID): ...


class WakeWordEntity(EntityID): ...


class WeatherEntity(EntityID): ...


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


def get_type_instance_for_entity_id(entity_id: str | EntityID) -> EntityID:
    if isinstance(entity_id, EntityID):
        domain = entity_id.get_domain()
    else:
        split = entity_id.split(".")
        domain: str = split[0]

    return get_type_for_domain(domain)(entity_id)
