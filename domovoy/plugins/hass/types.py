from __future__ import annotations

import datetime
from typing import Union
from warnings import deprecated

from domovoy.core.logging import get_logger
from domovoy.plugins.hass.domains import get_type_for_domain

_logcore = get_logger(__name__)


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

        if self.__class__ != get_type_for_domain(self._domain):
            _logcore.warning("Created an Entity instance with the wrong domain: {entity}", entity=self)

    def __str__(self) -> str:
        return self._entity_id

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self._entity_id}')"

    def __hash__(self) -> int:
        return self._entity_id.__hash__()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, EntityID) and self.__hash__() == other.__hash__()

    @deprecated("use get_domain instead")
    def get_platform(self) -> str:
        return self._domain

    def get_domain(self) -> str:
        return self._domain

    def get_entity_name(self) -> str:
        return self._entity_name


EntityIDOrStr = EntityID | str

PrimitiveHassValue = int | float | str | bool | datetime.datetime | EntityID

HassApiValue = PrimitiveHassValue | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassData = dict[str, HassApiValue | None]

HassValue = HassApiValue | None

HassValueStrict = HassApiValue
