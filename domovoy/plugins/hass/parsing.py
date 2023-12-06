from __future__ import annotations

import datetime
import re
from typing import TypeVar

import orjson as json
from websockets.typing import Data

from .exceptions import (
    HassApiParseError,
)
from .types import HassApiDataDict

pattern = re.compile("^\\d{4}-\\d{2}-\\d{2}")


T = TypeVar("T")


def __decode_response(msg: T) -> T:
    if isinstance(msg, dict):
        for key, value in msg.items():
            msg[key] = __decode_response(value)
        return msg

    if isinstance(msg, list):
        return [__decode_response(x) for x in msg]  # type: ignore

    if isinstance(msg, str) and pattern.match(msg):
        try:
            return datetime.datetime.fromisoformat(msg)  # type: ignore
        except (ValueError, TypeError):
            return msg

    return msg


def parse_message(message: Data, *, parse_datetimes: bool) -> HassApiDataDict:
    if not isinstance(message, str):
        raise HassApiParseError("Invalid message received from Home Assistant")

    msg = json.loads(message)

    if parse_datetimes:
        return __decode_response(msg)

    return msg


def encode_message(message: HassApiDataDict) -> bytes:
    try:
        return json.dumps(message)
    except TypeError as e:
        raise HassApiParseError(e) from e
