
from __future__ import annotations

import datetime

from domovoy.core.logging import get_logger

_logcore = get_logger(__name__)

def local_get_type_for_domain(domain: str) -> type[EntityID]:
    from domovoy.plugins.hass.domains import get_type_for_domain
    global local_get_type_for_domain
    local_get_type_for_domain = get_type_for_domain
    return local_get_type_for_domain(domain)

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

        actual_type = local_get_type_for_domain(self._domain)

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

PrimitiveHassValue = int | float | str | bool | datetime.datetime | EntityID
