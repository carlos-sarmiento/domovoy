from __future__ import annotations

import datetime
from types import UnionType
from typing import TYPE_CHECKING, Any, Literal, TypeVar, get_args, get_origin

from dateutil.parser import parse

from domovoy.core.logging import get_logger
from domovoy.core.utils import as_float, as_int

if TYPE_CHECKING:
    from domovoy.plugins.hass.core import EntityState

_logcore = get_logger(__name__)

T = TypeVar(name="T", default=int | float | str | bool | datetime.datetime)


class EntityID[T]:
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

        from domovoy.plugins.hass.domains import get_type_for_domain  # noqa: PLC0415

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

    def parse_state(self, state: PrimitiveHassValue) -> PrimitiveHassValue:
        return state

    def parse_state_typed(self, full_state: EntityState) -> T | None:
        if full_state.entity_id.get_domain() == "sensor":
            return self.__parse_state_for_sensor(full_state)

        target_type = self.get_target_type()

        return self.__parse_state_for_type(target_type, full_state.state)

    def __parse_state_for_sensor(self, full_state: EntityState) -> Any | None:  # noqa: ANN401
        device_class = full_state.attributes.get("device_class")
        state_class = full_state.attributes.get("state_class")

        target_type = int | float

        if (device_class is None and state_class is None) or device_class == "enum":
            target_type = str
        if device_class in ["date"]:
            target_type = datetime.date
        elif device_class in ["timestamp"]:
            target_type = datetime.datetime

        return self.__parse_state_for_type(target_type, full_state.state)

    def __parse_state_for_union_type(self, target_type: type[UnionType], state: PrimitiveHassValue) -> T | None:
        types = get_args(target_type)

        for t in types:
            result = self.__parse_state_for_type(t, state)
            if result is not None:
                return result

        return None

    def __parse_state_for_type(self, target_type: type | UnionType, state: PrimitiveHassValue) -> T | None:  # noqa: PLR0911
        if target_type is UnionType:
            return self.__parse_state_for_union_type(target_type, state)

        if state in ["unknown", "unavailable"]:
            return None

        if get_origin(target_type) is Literal and state in get_args(target_type):
            return state  # type: ignore

        if target_type is bool:
            if state == "on":
                return True  # type: ignore
            if state == "off":
                return False  # type: ignore

        if target_type is float:
            return as_float(state)  # type: ignore

        if target_type is int:
            return as_int(state)  # type: ignore

        if target_type is str:
            return str(state)  # type: ignore

        if target_type is datetime.datetime:
            if isinstance(state, datetime.datetime):
                return state  # type: ignore
            if isinstance(state, str):
                return parse(state)  # type: ignore

        return None

    def get_target_type(self) -> type[T] | UnionType:
        try:
            orig_base = self.__orig_bases__[0]  # type: ignore
            type_args = get_args(orig_base)
            return type_args[0]
        except Exception as e:
            _logcore.error(e)
            return int | float | str | bool | datetime.datetime  # type: ignore


PrimitiveHassValue = int | float | str | bool | datetime.datetime | EntityID
