from __future__ import annotations

import base64
import concurrent.futures
import datetime
import itertools
import logging
import queue

import orjson as json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


def default(obj: object) -> str:
    return str(obj)


class JsonHtttpHandler(logging.Handler):
    is_shutdown = False

    @classmethod
    def shutdown(cls) -> None:
        cls.is_shutdown = True

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
                    total=3,
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
                    total=3,
                    backoff_factor=0.5,
                    status_forcelist=[403, 500],
                ),
                pool_connections=self.MAX_POOLSIZE,
                pool_maxsize=self.MAX_POOLSIZE,
            ),
        )
        super().__init__()
        self.queue: queue.Queue[dict] = queue.Queue()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        self.executor.submit(self.actual_submit)

    def emit(self, record: logging.LogRecord) -> None:
        if JsonHtttpHandler.is_shutdown:
            return

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

        self.queue.put(data)

    last_exception: datetime.datetime | None = None
    exception_count: int = 0

    def get_item(self) -> dict | None:
        try:
            return self.queue.get(block=True, timeout=1)
        except queue.Empty:
            if JsonHtttpHandler.is_shutdown:
                raise queue.ShutDown from None

            return None

    def actual_submit(self) -> None:
        try:
            while True:
                iterator = iter(self.get_item, None)
                for chunk in iter(lambda iterator=iterator: list(itertools.islice(iterator, 100)), []):
                    data = json.dumps(chunk, default=default)

                    try:
                        self.session.post(self.url, data=data)
                    except requests.exceptions.ConnectionError as e:
                        now = datetime.datetime.now(datetime.UTC)
                        if self.last_exception is None or now - self.last_exception >= datetime.timedelta(minutes=1):
                            from domovoy.core.logging import logging_infra_logger

                            logging_infra_logger.critical(
                                "Failed to submit logs to: {destination}. There have been {additional_failures} additional failures since the last message",
                                destination=self.url,
                                additional_failures=self.exception_count,
                            )
                            self.last_exception = now
                            self.exception_count = 0
                        else:
                            self.exception_count += 1
        except queue.ShutDown:
            # Do nothing
            ...
