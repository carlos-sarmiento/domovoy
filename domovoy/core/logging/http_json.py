from __future__ import annotations

import base64
import datetime
import logging

import orjson as json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from domovoy.core.thread_pool import executor


def default(obj: object) -> str:
    return str(obj)


last_exception: datetime.datetime | None = None
exception_count: int = 0


def actual_emit(self: JsonHtttpHandler, record: logging.LogRecord) -> None:
    try:
        raw = record.__dict__

        args = raw.get("_additionalArgs", {})

        data = {
            "logger_name": record.name,
            "args": args,
            "level": record.levelname,
            "time": raw.get("asctime", raw.get("created", None)),
            "message": raw.get("message", raw.get("msg", "")),
        }

        if "app_name" in args:
            data["app_name"] = args["app_name"]

        if record.exc_info:
            tp, obj, trace = record.exc_info
            data["exception"] = {
                "message": str(obj),
                "type": tp.__name__ if tp else None,
                "trace": record.exc_text,
            }

        data = json.dumps([data], default=default)
        self.session.post(self.url, data=data)
    except requests.exceptions.ConnectionError as e:
        global last_exception
        global exception_count
        now = datetime.datetime.now(datetime.UTC)
        if last_exception is None or now - last_exception >= datetime.timedelta(minutes=1):
            from domovoy.core.logging import logging_infra_logger

            logging_infra_logger.critical(
                "Failed to submit logs to: {destination}. There have been {additional_failures} additional failures since the last message",
                destination=self.url,
                additional_failures=exception_count,
            )
            last_exception = now
            exception_count = 0
        else:
            exception_count += 1


class JsonHtttpHandler(logging.Handler):
    def __init__(self, url: str, username: str, password: str) -> None:
        self.url = url
        self.token = base64.b64encode(bytes(username + ":" + password, "utf-8")).decode("utf-8")

        # sets up a session with the server
        self.MAX_POOLSIZE = 100
        self.session = session = requests.Session()
        session.headers.update({"Content-Type": "application/json", "Authorization": f"Basic {self.token}"})

        self.session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=0.5,
                    status_forcelist=[403, 500],
                ),
                pool_connections=self.MAX_POOLSIZE,
                pool_maxsize=self.MAX_POOLSIZE,
            ),
        )

        self.session.mount(
            "http://",
            HTTPAdapter(
                max_retries=Retry(
                    total=5,
                    backoff_factor=0.5,
                    status_forcelist=[403, 500],
                ),
                pool_connections=self.MAX_POOLSIZE,
                pool_maxsize=self.MAX_POOLSIZE,
            ),
        )
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            executor.submit(actual_emit, self, record)
        except Exception as e:
            print(e, record.__dict__)

            actual_emit(self, record)
