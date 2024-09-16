from __future__ import annotations

import datetime
import hashlib
from typing import Union


class EntityID:
    def __init__(self, entity_id: str) -> None:
        if isinstance(entity_id, EntityID):
            entity_id = str(entity_id)

        self._entity_id: str = entity_id
        split = entity_id.split(".")

        self._platform = split[0]
        self._entity_name = split[1]

    def __str__(self) -> str:
        return self._entity_id

    def __repl__(self) -> str:
        return f"HassEntity('{self._entity_id}')"

    def __hash__(self) -> int:
        sha1 = hashlib.sha256(self._entity_id.encode())
        hash_as_hex = sha1.hexdigest()
        return int(hash_as_hex, 16)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityID) and self._entity_id == other._entity_id

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
