from __future__ import annotations

import datetime
import re
from typing import TypeVar

import orjson as json
from websockets.typing import Data

from domovoy.core.logging import get_logger

from .exceptions import (
    HassApiParseError,
)
from .types import EntityID, HassData

pattern = re.compile("^\\d{4}-\\d{2}-\\d{2}")


T = TypeVar("T")

_logcore = get_logger("hass_parsing")


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


def parse_message(message: Data, *, parse_datetimes: bool) -> HassData:
    if not isinstance(message, str):
        raise HassApiParseError("Invalid message received from Home Assistant")

    msg = json.loads(message)

    if isinstance(msg, list):
        _logcore.error("Received a message from Hass which is a list")

    if parse_datetimes:
        return __decode_response(msg)  # type: ignore

    return msg  # type: ignore


def default(obj: object) -> str:
    if isinstance(obj, EntityID):
        return str(obj)

    raise TypeError


def encode_message(message: HassData) -> bytes:
    try:
        return json.dumps(message, default=default)
    except TypeError as e:
        raise HassApiParseError(e) from e
