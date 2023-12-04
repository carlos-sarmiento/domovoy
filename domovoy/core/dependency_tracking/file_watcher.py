from __future__ import annotations

import threading
from collections.abc import Callable

from watchdog.events import FileSystemEventHandler

from domovoy.core.logging import get_logger

_logcore = get_logger(__name__)


class ReloadPythonFileWatcher(FileSystemEventHandler):
    __timer_per_file: dict[str, threading.Timer] = {}

    def __init__(self, load_or_reload_callback: Callable[[str, bool], None]) -> None:
        super().__init__()
        self.__module_load_callback = load_or_reload_callback

    def __process_event(self, path: str, is_deletion: bool) -> None:
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

    def __notify(self, filepath: str, is_deletion: bool) -> None:
        _logcore.debug("Detected File Change: {filepath}", filepath=filepath)
        self.__module_load_callback(filepath, is_deletion)

    def on_moved(self, event):
        super().on_moved(event)
        self.__process_event(event.src_path, True)
        self.__process_event(event.dest_path, False)

    def on_created(self, event):
        super().on_created(event)
        self.__process_event(event.src_path, False)

    def on_deleted(self, event):
        super().on_deleted(event)
        self.__process_event(event.src_path, True)

    def on_modified(self, event):
        super().on_modified(event)
        self.__process_event(event.src_path, False)
