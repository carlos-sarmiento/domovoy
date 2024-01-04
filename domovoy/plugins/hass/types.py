from __future__ import annotations

import datetime
from typing import Union

PrimitiveHassValue = int | float | str | bool | datetime.datetime

HassApiValue = PrimitiveHassValue | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassData = dict[str, HassApiValue | None]

HassValue = HassApiValue | None

HassValueStrict = HassApiValue
