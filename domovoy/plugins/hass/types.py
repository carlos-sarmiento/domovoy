from __future__ import annotations

import datetime
from typing import Union

from .entity_id import PrimitiveHassValue, EntityID


HassApiValue = PrimitiveHassValue | EntityID | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassData = dict[str, HassApiValue | None]

HassValue = HassApiValue | None

HassValueStrict = HassApiValue
