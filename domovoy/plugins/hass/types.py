from __future__ import annotations

import datetime
from typing import Union

PrimitiveHassApiValue = int | float | str | bool | datetime.datetime

HassApiValue = PrimitiveHassApiValue | list["HassApiValue"] | dict[str, Union["HassApiValue", None]]

HassApiDataDict = dict[str, HassApiValue | None]
