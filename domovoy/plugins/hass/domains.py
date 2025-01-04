import inspect
import sys

from .types import EntityID


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
