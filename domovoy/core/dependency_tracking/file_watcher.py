from __future__ import annotations

import threading
from typing import Protocol

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEventHandler,
)

from domovoy.core.logging import get_logger

_logcore = get_logger(__name__)


class ReloadPythonFileWatcher(FileSystemEventHandler):
    class LoadOrReloadCallback(Protocol):
        def __call__(self, filepath: str, *, is_deletion: bool) -> None: ...

    __timer_per_file: dict[str, threading.Timer]

    def __init__(self, load_or_reload_callback: LoadOrReloadCallback) -> None:
        super().__init__()
        self.__timer_per_file = {}
        self.__module_load_callback = load_or_reload_callback

    def __process_event(self, path: str, *, is_deletion: bool) -> None:
        if not path.endswith(".py"):
            return

        if path in self.__timer_per_file:
            timer = self.__timer_per_file[path]

            if timer.is_alive():
                timer.cancel()

        timer = threading.Timer(
            interval=0.5,
            function=self.__notify,
            kwargs={"filepath": path, "is_deletion": is_deletion},
        )
        timer.start()
        self.__timer_per_file[path] = timer

    def __notify(self, filepath: str, *, is_deletion: bool) -> None:
        _logcore.trace("Detected File Change: {filepath}", filepath=filepath)
        self.__module_load_callback(filepath, is_deletion=is_deletion)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore
        super().on_moved(event)
        self.__process_event(str(event.src_path), is_deletion=True)
        self.__process_event(str(event.dest_path), is_deletion=False)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore
        super().on_created(event)
        self.__process_event(str(event.src_path), is_deletion=False)

    def on_deleted(self, event: FileDeletedEvent) -> None:  # type: ignore
        super().on_deleted(event)
        self.__process_event(str(event.src_path), is_deletion=True)

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore
        super().on_modified(event)
        self.__process_event(str(event.src_path), is_deletion=False)
