from __future__ import annotations

from .entity_id import EntityID, PrimitiveHassValue

__PrimitiveHassValueWithEntityID = PrimitiveHassValue | EntityID


__HassApiValue = (
    __PrimitiveHassValueWithEntityID
    | list[__PrimitiveHassValueWithEntityID | dict[str, __PrimitiveHassValueWithEntityID | None]]
    | dict[str, __PrimitiveHassValueWithEntityID | list[__PrimitiveHassValueWithEntityID] | None]
)

HassData = dict[str, __HassApiValue | None]

HassValue = __HassApiValue | None

HassValueStrict = __HassApiValue
