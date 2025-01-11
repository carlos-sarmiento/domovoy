from __future__ import annotations

import base64
import concurrent.futures
import logging

import orjson as json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)


def default(obj: object) -> str:
    return str(obj)


def actual_emit(self: JsonHtttpHandler, record: logging.LogRecord) -> None:
    raw = record.__dict__
    application = self.application

    args = raw.get("_additionalArgs", {})

    data = {
        "application": application,
        "logger_name": record.name,
        "args": args,
        "level": record.levelname,
        "time": record.asctime,
        "message": record.message,
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


class JsonHtttpHandler(logging.Handler):
    def __init__(self, application: str, url: str, username: str, password: str) -> None:
        self.url = url
        self.application = application
        self.token = base64.b64encode(bytes(username + ":" + password, "utf-8")).decode("utf-8")

        # sets up a session with the server
        self.MAX_POOLSIZE = 100
        self.session = session = requests.Session()
        session.headers.update({"Content-Type": "application/json", "Authorization": f"Basic {self.token}"})

        self.session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(total=5, backoff_factor=0.5, status_forcelist=[403, 500]),
                pool_connections=self.MAX_POOLSIZE,
                pool_maxsize=self.MAX_POOLSIZE,
            ),
        )

        self.session.mount(
            "http://",
            HTTPAdapter(
                max_retries=Retry(total=5, backoff_factor=0.5, status_forcelist=[403, 500]),
                pool_connections=self.MAX_POOLSIZE,
                pool_maxsize=self.MAX_POOLSIZE,
            ),
        )
        super().__init__()

    def emit(self, record: logging.LogRecord) -> None:
        executor.submit(actual_emit, self, record)
