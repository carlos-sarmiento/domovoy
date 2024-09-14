from __future__ import annotations

import datetime
from typing import Union

PrimitiveHassValue = int | float | str | bool | datetime.datetime

HassApiValue = PrimitiveHassValue | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassData = dict[str, HassApiValue | None]

HassValue = HassApiValue | None

HassValueStrict = HassApiValue


class HassEntity:
    def __init__(self, entity_id: str) -> None:
        self._entity_id: str = entity_id

    def __str__(self) -> str:
        return self.value()

    def __repl__(self) -> str:
        return f"HassEntity('{self._entity_id}')"

    def value(self) -> str:
        return self._entity_id


EntityID = HassEntity | str
