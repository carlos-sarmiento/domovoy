from __future__ import annotations

import datetime
from typing import Union


class EntityID:
    def __init__(self, entity_id: str) -> None:
        self._entity_id: str = entity_id
        split = entity_id.split(".")

        self._platform = split[0]
        self._entity_name = split[1]

    def __str__(self) -> str:
        return self._entity_id

    def __repl__(self) -> str:
        return f"HassEntity('{self._entity_id}')"

    def __hash__(self) -> int:
        return self._entity_id.__hash__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityID) and self.__hash__() == other.__hash__()

    def get_platform(self) -> str:
        return self._platform

    def get_entity_name(self) -> str:
        return self._entity_name


EntityIDOrStr = EntityID | str

PrimitiveHassValue = int | float | str | bool | datetime.datetime | EntityID

HassApiValue = PrimitiveHassValue | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassData = dict[str, HassApiValue | None]

HassValue = HassApiValue | None

HassValueStrict = HassApiValue
