from __future__ import annotations

import asyncio
import datetime
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Concatenate, ParamSpec, TypeVar

from apscheduler.job import Job
from apscheduler.triggers.base import BaseTrigger

from domovoy.applications import AppBase, AppConfigBase, EmptyAppConfig
from domovoy.core.context import (
    context_callback_id,
    context_logger,
    inside_log_callback,
)
from domovoy.core.errors import (
    DomovoyException,
    DomovoyLogOnlyOnDebugWhenUncaughtException,
    DomovoyUnknownPluginException,
)
from domovoy.core.logging import get_logger
from domovoy.core.utils import get_callback_name, set_callback_true_information
from domovoy.plugins.plugins import AppPlugin

TConfig = TypeVar("TConfig", bound=AppConfigBase, contravariant=True)
P = ParamSpec("P")

T = TypeVar("T", bound=AppPlugin)
_logcore = get_logger(__name__)

TStrOrInt = TypeVar("TStrOrInt", bound=int | str)


class EmptyAppBase(AppBase[EmptyAppConfig]):
    def __init__(self) -> None:
        ...

    async def initialize(self) -> None:
        raise NotImplementedError("EmptyAppBase Cannot be used")

    async def finalize(self) -> None:
        raise NotImplementedError("EmptyAppBase Cannot be used")


@dataclass(kw_only=True)
class CallbackRegistration:
    id: str
    callback: Callable
    is_registered: bool
    times_called: int = 0
    last_call_datetime: datetime.datetime | None = None
    last_error_datetime: datetime.datetime | None = None


@dataclass(kw_only=True)
class SchedulerCallbackRegistration(CallbackRegistration):
    trigger: BaseTrigger | None
    start: datetime.datetime | None
    job: Job | None = None


@dataclass(kw_only=True)
class EventCallbackRegistration(CallbackRegistration):
    events: list[str]


class AppStatus(StrEnum):
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    FINALIZING = "finalizing"
    TERMINATED = "terminated"


@dataclass
class AppWrapper:
    config: AppConfigBase
    app_name: str
    filepath: str
    module_name: str
    class_name: str
    status: AppStatus
    logger: logging.LoggerAdapter[Any]
    app: AppBase[Any] = EmptyAppBase()
    scheduler_callbacks: dict[str, SchedulerCallbackRegistration] = field(
        default_factory=dict,
    )
    event_callbacks: dict[str, EventCallbackRegistration] = field(default_factory=dict)
    plugins: dict[type, dict[str, AppPlugin]] = field(default_factory=dict)

    def get_pluginx(self, plugin_type: type[T], name: str | None = None) -> T:
        plugin = self.get_plugin(plugin_type, name)

        if plugin is None:
            raise DomovoyUnknownPluginException(
                f"Unknown plugin of type: {plugin_type}",
            )

        return plugin

    def get_plugin(self, plugin_type: type[T], name: str | None = None) -> T | None:
        if plugin_type not in self.plugins:
            return None

        plugins = self.plugins[plugin_type]

        if name is not None:
            if name not in plugins:
                return None
            else:
                return plugins[name]  # type: ignore

        total_plugins = len(plugins)

        if total_plugins == 0:
            raise DomovoyException(
                f"There are no plugins registered for type {plugin_type.__name__}",
            )
        elif total_plugins >= 2:
            raise DomovoyException(
                f"There are multiple plugins registered for type {plugin_type.__name__}."
                + " You need to include the name of the plugin instance you require",
            )
        else:
            return next(iter(plugins.values()))  # type: ignore

    def register_plugin(self, plugin: AppPlugin, name: str) -> None:
        plugin_type = type(plugin)
        _logcore.debug(
            "Registering plugin of type {plugin_type} with name {name}",
            plugin_type=plugin_type,
            name=name,
        )
        if plugin_type not in self.plugins:
            self.plugins[plugin_type] = {}

        self.plugins[plugin_type][name] = plugin
        _logcore.debug(f"{self.plugins}")

    def prepare_all_plugins(self) -> None:
        for plugin_group in self.plugins.values():
            for p in plugin_group.values():
                p.prepare()

        for plugin_group in self.plugins.values():
            for p in plugin_group.values():
                p.post_prepare()

    def handle_exception_and_logging(
        self, true_callback: Callable,
    ) -> Callable[
        [Callable[Concatenate[TStrOrInt, P], Awaitable[None]]],
        Callable[Concatenate[TStrOrInt, P], Awaitable[None]],
    ]:
        def inner_handle_exception_and_logging(
            func: Callable[Concatenate[TStrOrInt, P], Awaitable[None]],
        ) -> Callable[Concatenate[TStrOrInt, P], Awaitable[None]]:
            async def wrapper(
                callback_id: TStrOrInt, *args: P.args, **kwargs: P.kwargs,
            ) -> None:
                if inside_log_callback.get():
                    logger = _logcore
                else:
                    logger = self.logger

                if self.status != AppStatus.RUNNING:
                    _logcore.warning(
                        "Tried to call {function_name} on app `{app_name}` when app's status was `{status}`."
                        + " -- args: {pargs} -- kwargs: {pkwargs}",
                        app_name=self.app_name,
                        status=self.status,
                        function_name=func.__name__,
                        pargs=args,
                        pkwargs=kwargs,
                    )
                    return

                context_logger.set(logger)
                context_callback_id.set(callback_id)

                _logcore.debug(
                    "Calling {function_name} -- args: {pargs} -- kwargs: {pkwargs}",
                    function_name=func.__name__,
                    pargs=args,
                    pkwargs=kwargs,
                )

                try:
                    self.scheduler_callbacks
                    await asyncio.create_task(
                        func(callback_id, *args, **kwargs), name=get_callback_name(true_callback),  # type: ignore
                    )

                except asyncio.exceptions.CancelledError as e:
                    logger.debug(
                        "Cancelled Loop error for {app_name}",
                        e,
                        app_name=self.app_name,
                    )

                except DomovoyLogOnlyOnDebugWhenUncaughtException as e:
                    logger.debug(
                        "Debug Log only Uncaught Exception",
                        e,
                        exc_info=True,
                    )

                except BaseException as e:
                    logger.exception(
                        "Uncaught Exception in: {app_name}",
                        e,
                        app_name=self.app_name,
                    )

            set_callback_true_information(wrapper, true_callback)

            return wrapper

        set_callback_true_information(inner_handle_exception_and_logging, true_callback)
        return inner_handle_exception_and_logging

    def __get_callback_registration(
        self, callback_id: str | int,
    ) -> CallbackRegistration | None:
        if isinstance(callback_id, int):
            return None

        if callback_id.startswith("event-"):
            return self.event_callbacks.get(callback_id, None)
        elif callback_id.startswith("scheduler-"):
            return self.scheduler_callbacks.get(callback_id, None)
        elif callback_id.startswith("ephemeral_callback"):
            return None
        else:
            self.logger.error(
                "Tried to load invalid callback_id `{callback_id}` from callback registrations",
                callback_id=callback_id,
            )
            return None

    TReturn = TypeVar("TReturn")

    def instrument_app_callback(
        self, callback: Callable[P, None | Awaitable[None]],
    ) -> Callable[Concatenate[str | int, P], Awaitable[None]]:
        async def instrumented_call(
            callback_id: str | int, *args: P.args, **kwargs: P.kwargs,
        ) -> None:
            try:
                self.__callback_called(callback_id)
                if inspect.iscoroutinefunction(callback):
                    await callback(*args, **kwargs)
                else:
                    callback(*args, **kwargs)
            except Exception:
                self.__callback_failed(callback_id)
                raise

        return instrumented_call

    def __callback_called(self, callback_id: str | int) -> None:
        registration = self.__get_callback_registration(callback_id)

        if registration:
            registration.times_called += 1
            registration.last_call_datetime = datetime.datetime.now()

    def __callback_failed(self, callback_id: str | int) -> None:
        registration = self.__get_callback_registration(callback_id)

        if registration:
            registration.last_error_datetime = datetime.datetime.now()
