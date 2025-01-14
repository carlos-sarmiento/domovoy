from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from domovoy.core.configuration import get_main_config
from domovoy.core.dependency_tracking.dependency_tracker import DependencyTracker
from domovoy.core.engine.active_engine import set_active_engine_for_app_registration
from domovoy.core.engine.engine import AppEngine
from domovoy.core.logging import get_logger
from domovoy.core.logging.http_json import JsonHtttpHandler
from domovoy.core.services.pip_dependencies import install_requirements

_logcore = get_logger(__name__)

_is_running = False


def stop_domovoy() -> None:
    global _is_running
    _logcore.info("Received Signal from App to stop Domovoy")
    _is_running = False


async def start(*, wait_for_all_tasks_before_exit: bool = True) -> None:
    global _is_running
    _is_running = True
    app_engine = None
    dependency_tracker = None

    try:
        _logcore.info("Starting Domovoy")

        _logcore.trace("Inserting App path into Python PATH")
        app_path = get_main_config().app_path
        app_path = Path(app_path).resolve()

        parent_app_path = (app_path / os.pardir).resolve()

        _logcore.trace(
            "Inserting Parent Path: `{parent_app_path}` of App Path: `{app_path}` to PYTHON_PATH",
            parent_app_path=parent_app_path,
            app_path=app_path,
        )
        sys.path.insert(0, str(parent_app_path))

        install_requirements()

        _logcore.trace("Initializing App Engine")
        app_engine = AppEngine()
        set_active_engine_for_app_registration(app_engine)

        await app_engine.start()

        _logcore.trace("Initializing Dependency Tracker")
        dependency_tracker = DependencyTracker(str(app_path), app_engine)

        dependency_tracker.start()

        await loop_until_exit()

    except Exception as e:
        _logcore.exception("{e}", e=e)
    finally:
        _logcore.info("Stopping Domovoy")

        if app_engine is not None:
            await app_engine.stop()

        if dependency_tracker is not None:
            dependency_tracker.stop()

        if wait_for_all_tasks_before_exit:
            pending_tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]

            _logcore.warning(
                "Cancelling remaining {pending_tasks} tasks",
                pending_tasks=len(pending_tasks),
            )

            for t in pending_tasks:
                _logcore.trace(t)
                t.cancel()

            await asyncio.gather(*pending_tasks, return_exceptions=True)

        _logcore.info("Stopping HttpLoggers")
        JsonHtttpHandler.shutdown()

        _logcore.info("Domovoy Terminated")


async def loop_until_exit() -> None:
    try:
        while _is_running:
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                _logcore.trace("Async Loop was Cancelled")
                raise

    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        _logcore.warning("Received termination signal")
        return
