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
from .types import HassApiDataDict

_logcore = get_logger(__name__)
pattern = re.compile("^\\d{4}-\\d{2}-\\d{2}")


T = TypeVar("T")


def __decode_response(msg: T) -> T:
    if isinstance(msg, dict):
        for key, value in msg.items():
            msg[key] = __decode_response(value)
        return msg

    elif isinstance(msg, list):
        return [__decode_response(x) for x in msg]  # type: ignore

    elif isinstance(msg, str) and pattern.match(msg):
        try:
            return datetime.datetime.fromisoformat(msg)  # type: ignore
        except (ValueError, TypeError):
            return msg

    else:
        return msg


def parse_message(message: Data, parse_datetimes: bool) -> HassApiDataDict:
    if not isinstance(message, str):
        raise HassApiParseError("Invalid message received from Home Assistant")

    msg = json.loads(message)  # , cls=DomovoyHassApiJSONDecoder)

    if parse_datetimes:
        return __decode_response(msg)
    else:
        return msg


def encode_message(message: HassApiDataDict) -> bytes:
    try:
        return json.dumps(message)  # , cls=DomovoyHassApiJSONEncoder)
    except TypeError as e:
        raise HassApiParseError(e)
