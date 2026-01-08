from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import DEBUG, WARNING
from typing import Any, ParamSpec

from domovoy.applications import (
    AppBase,
    AppConfigBase,
)
from domovoy.core.app_infra import (
    AppStatus,
    AppWrapper,
    EmptyAppConfig,
)
from domovoy.core.configuration import get_main_config
from domovoy.core.context import context_logger
from domovoy.core.logging import get_logger
from domovoy.core.services.callback_register import CallbackRegister
from domovoy.core.services.event_listener import EventListener
from domovoy.core.services.service import DomovoyServiceResources
from domovoy.core.services.webapi import DomovoyWebApi
from domovoy.plugins.callbacks import (
    CallbacksPlugin,
)
from domovoy.plugins.hass import HassPlugin
from domovoy.plugins.hass.core import HassCore
from domovoy.plugins.logger import LoggerPlugin
from domovoy.plugins.meta import MetaPlugin
from domovoy.plugins.servents import ServentsPlugin
from domovoy.plugins.time import TimePlugin
from domovoy.plugins.utils import UtilsPlugin

_logcore = get_logger(__name__)

P = ParamSpec("P")


@dataclass
class AppRegistration:
    app_class: type[AppBase[Any]]
    app_name: str
    app_path: str
    config: AppConfigBase
    logging_config_name: str
    active_instance: AppWrapper | None

    def get_app_name_for_logs(self) -> str:
        return f"{self.app_class.__name__}.{self.app_name}"

    def __hash__(self) -> int:
        return self.app_name.__hash__()


@dataclass
class AppEngineStats:
    total_apps: int
    apps_per_status: dict[AppStatus, list[str]]


class AppEngine:
    __apps_by_path: dict[str, set[AppRegistration]]
    __app_registrations: dict[str, AppRegistration]

    __event_listener: EventListener
    __hass_core: HassCore
    __webapi: DomovoyWebApi

    def __init__(self) -> None:
        self.__apps_by_path = {}
        self.__app_registrations = {}

        self.__event_listener = EventListener(
            DomovoyServiceResources(
                start_dependent_apps_callback=self.__build_start_apps_using_service_callback(),
                stop_dependent_apps_callback=self.__build_terminate_apps_using_service_callback(),
                get_all_apps_by_name=self.__get_all_apps_by_name,
                config={},
            ),
        )
        self.__callback_register = CallbackRegister(
            DomovoyServiceResources(
                start_dependent_apps_callback=self.__build_start_apps_using_service_callback(),
                stop_dependent_apps_callback=self.__build_terminate_apps_using_service_callback(),
                get_all_apps_by_name=self.__get_all_apps_by_name,
                config={},
            ),
            self.__event_listener,
        )
        self.__hass_core = HassCore(
            DomovoyServiceResources(
                start_dependent_apps_callback=self.__build_start_apps_using_service_callback(),
                stop_dependent_apps_callback=self.__build_terminate_apps_using_service_callback(),
                get_all_apps_by_name=self.__get_all_apps_by_name,
                config={
                    "hass_url": get_main_config().hass_url,
                    "hass_access_token": get_main_config().hass_access_token,
                },
            ),
            self.__event_listener,
        )
        self.__webapi = DomovoyWebApi(
            DomovoyServiceResources(
                start_dependent_apps_callback=self.__build_start_apps_using_service_callback(),
                stop_dependent_apps_callback=self.__build_terminate_apps_using_service_callback(),
                get_all_apps_by_name=self.__get_all_apps_by_name,
                config={"address": "0.0.0.0", "port": 8081},  # noqa: S104 We bind to all interfaces because Domovoy is intended to run inside a docker container
            ),
        )

    async def start(self) -> None:
        """Start the App Engine and its dependent services."""
        _logcore.info("Starting Scheduling Engine")
        self.__event_listener.start()
        self.__callback_register.start()
        self.__webapi.start()
        await self.__hass_core.start()

    async def stop(self) -> None:
        await self.terminate_all_apps_before_engine_stop()
        await self.__webapi.stop()
        self.__callback_register.stop()
        self.__event_listener.stop()
        await self.__hass_core.stop()

    async def __get_all_apps_by_name(self) -> dict[str, AppWrapper]:
        return {
            name: registration.active_instance
            for name, registration in self.__app_registrations.items()
            if registration.active_instance is not None
        }

    async def register_app(
        self,
        app_class: type[AppBase[Any]],
        app_name: str,
        app_path: str,
        config: AppConfigBase | None,
        logging_config_name: str | None,
    ) -> None:
        app_name_for_log = f"{app_class.__name__}.{app_name}"
        _logcore.info("Registering app: {app_name} in AppEngine", app_name=app_name_for_log)

        if app_name in self.__app_registrations:
            registration = self.__app_registrations[app_name]
            if registration.active_instance is not None:
                _logcore.error(
                    "{app_name} is already registered and running. Choose a different name.",
                    app_name=app_name_for_log,
                )
                return

            _logcore.warning(
                "{app_name} is already registered but not running. Registration will be replaced.",
                app_name=app_name_for_log,
            )

        if config is None:
            config = EmptyAppConfig()

        app_registration = AppRegistration(
            app_class=app_class,
            app_name=app_name,
            app_path=app_path,
            config=config,
            logging_config_name=logging_config_name or "apps",
            active_instance=None,
        )

        if app_registration.app_path not in self.__apps_by_path:
            self.__apps_by_path[app_registration.app_path] = set()

        self.__apps_by_path[app_registration.app_path].add(app_registration)
        self.__app_registrations[app_name] = app_registration

        await self.__start_app(app_registration)

    async def __start_app(self, app_registration: AppRegistration) -> None:
        # Needs Validation
        try:
            wrapper = self.__build_app_instance(app_registration)
            await self.__initialize_app(wrapper)
        except Exception as e:
            _logcore.exception(
                "Error when initializing app: {app_name}",
                e,
                app_name=app_registration.get_app_name_for_logs(),
            )
            await self.__terminate_app(app_registration)

    def __build_app_instance(self, app_registration: AppRegistration) -> AppWrapper:
        _logcore.trace(
            "Initializing AppWrapper for {app_name}",
            app_name=app_registration.get_app_name_for_logs(),
        )
        wrapper = AppWrapper(
            config=app_registration.config,
            app_name=app_registration.app_name,
            class_name=app_registration.app_class.__name__,
            module_name=app_registration.app_class.__module__,
            filepath=app_registration.app_path,
            status=AppStatus.CREATED,
            logging_config_name=app_registration.logging_config_name,
            app_name_for_logs=app_registration.get_app_name_for_logs(),
        )

        _logcore.trace(
            "Initializing Modules for {app_name}",
            app_name=app_registration.get_app_name_for_logs(),
        )

        logmodule = LoggerPlugin("log", wrapper)
        wrapper.register_plugin(logmodule, logmodule.name)

        meta = MetaPlugin(
            "meta",
            wrapper,
            lambda: self.__reload_app(app_registration),
        )
        wrapper.register_plugin(meta, meta.name)

        hass = HassPlugin("hass", wrapper, self.__hass_core)
        wrapper.register_plugin(hass, hass.name)

        callbacks = CallbacksPlugin(
            "callbacks",
            wrapper,
            self.__callback_register,
        )
        wrapper.register_plugin(callbacks, callbacks.name)

        servents = ServentsPlugin("servents", wrapper)
        wrapper.register_plugin(servents, servents.name)

        utils = UtilsPlugin("utils", wrapper)
        wrapper.register_plugin(utils, utils.name)

        time = TimePlugin("time", wrapper)
        wrapper.register_plugin(time, time.name)

        _logcore.trace(
            "Preparing all plugins for app {app_name}",
            app_name=app_registration.get_app_name_for_logs(),
        )
        wrapper.prepare_all_plugins()

        _logcore.trace(
            "Creating instance of class {class_name} for app {app_name}",
            app_name=app_registration.get_app_name_for_logs(),
            class_name=app_registration.app_class.__name__,
        )
        wrapper.app = app_registration.app_class(
            app_registration.config,
            meta,
            logmodule,
            callbacks,
            hass,
            servents,
            servents,
            utils,
            time,
        )

        self.__app_registrations[app_registration.app_name].active_instance = wrapper

        return wrapper

    async def __initialize_app(self, wrapper: AppWrapper) -> None:
        context_logger.set(wrapper.logger)
        _logcore.info(
            "Calling initialize() for {app_name}",
            app_name=wrapper.get_app_name_for_logs(),
        )
        wrapper.status = AppStatus.INITIALIZING
        try:
            await super(wrapper.app.__class__, wrapper.app).initialize()
            await wrapper.app.initialize()
        except:
            wrapper.status = AppStatus.FAILED
            raise
        wrapper.status = AppStatus.RUNNING
        self.__callback_register.register_all_callbacks(wrapper)
        _logcore.trace(
            "Initialization complete for {app_name}",
            app_name=wrapper.get_app_name_for_logs(),
        )

    async def __finalize_app(self, app_registration: AppRegistration) -> None:
        wrapper = app_registration.active_instance

        if wrapper is None:
            _logcore.error(
                "Tried to finalize app {app_name} which is not running",
                app_name=app_registration.get_app_name_for_logs(),
            )
            return

        _logcore.info(
            "Calling finalize() for {app_name}",
            app_name=wrapper.get_app_name_for_logs(),
        )
        try:
            await wrapper.app.finalize()
        except Exception as e:
            _logcore.exception(
                "Error while calling finalize() for app {app_name}",
                e,
                app_name=wrapper.get_app_name_for_logs(),
            )

    async def __terminate_app(self, app_registration: AppRegistration) -> None:
        # Needs Validation
        app_name_for_logs = app_registration.get_app_name_for_logs()

        _logcore.trace(
            "Terminating {app_name}",
            app_name=app_name_for_logs,
        )

        wrapper: AppWrapper | None = app_registration.active_instance

        if wrapper is None:
            _logcore.warning(
                "Tried to terminate {app_name} but it is not running",
                app_name=app_name_for_logs,
            )
            return

        context_logger.set(wrapper.logger)

        self.__callback_register.cancel_all_callbacks(wrapper)
        wrapper.status = AppStatus.FINALIZING
        await self.__finalize_app(app_registration)
        wrapper.status = AppStatus.TERMINATED
        app_name_for_logs = wrapper.get_app_name_for_logs()
        self.__clear_app_instance(app_registration)
        _logcore.trace(
            "Terminated {app_name}",
            app_name=app_name_for_logs,
        )

    async def __reload_app(self, registration: AppRegistration) -> None:
        app_name_for_logs = registration.get_app_name_for_logs()

        _logcore.info(
            "Reloading app: {app_name}",
            app_name=app_name_for_logs,
        )
        await self.__terminate_app(registration)
        await self.__start_app(registration)

    def __clear_app_instance(self, registration: AppRegistration) -> None:
        _logcore.trace(
            "Clearing active instance for {app_name}",
            app_name=registration.get_app_name_for_logs(),
        )
        self.__app_registrations[registration.app_name].active_instance = None

    async def terminate_app_from_files(
        self,
        paths: list[str],
        *,
        remove_from_registry: bool = True,
    ) -> None:
        _logcore.trace(
            "Building list of apps for termination from path(s): {paths}",
            paths=paths,
        )

        app_names_to_terminate: list[AppRegistration] = []
        for path in paths:
            if path not in self.__apps_by_path:
                continue

            app_names_to_terminate += self.__apps_by_path[path]

        await self.__terminate_multiple_apps(
            app_names_to_terminate,
            remove_from_app_registry=remove_from_registry,
        )

    async def terminate_all_apps_before_engine_stop(self) -> None:
        await self.__terminate_multiple_apps(
            list(self.__app_registrations.values()),
            remove_from_app_registry=True,
        )

    def __build_terminate_apps_using_service_callback(
        self,
    ) -> Callable[[], Awaitable[None]]:
        async def app_termination_callback() -> None:
            apps_to_terminate = [
                registration
                for registration in self.__app_registrations.values()
                if registration.active_instance is not None
            ]

            _logcore.log(
                WARNING if len(apps_to_terminate) > 0 else DEBUG,
                "Terminating {apps_to_terminate} Apps",
                apps_to_terminate=len(apps_to_terminate),
            )

            app_terminations = [self.__terminate_app(app_name) for app_name in apps_to_terminate]
            await asyncio.gather(*app_terminations)

        return app_termination_callback

    def __build_start_apps_using_service_callback(
        self,
    ) -> Callable[[], Awaitable[None]]:
        async def app_start_callback() -> None:
            apps_to_start = [
                registration
                for registration in self.__app_registrations.values()
                if registration.active_instance is None
            ]

            _logcore.warning(
                "Starting {reload_app_count} Apps",
                reload_app_count=len(apps_to_start),
            )
            app_reloads = [self.__start_app(app_registration) for app_registration in apps_to_start]
            await asyncio.gather(*app_reloads)

        return app_start_callback

    async def __terminate_multiple_apps(
        self,
        app_names_to_terminate: list[AppRegistration],
        *,
        remove_from_app_registry: bool,
    ) -> None:
        if not app_names_to_terminate:
            _logcore.warning("Called termination on an empty app list")

        for app_registration in app_names_to_terminate:
            app_name_for_logs = app_registration.get_app_name_for_logs()

            await self.__terminate_app(app_registration)

            if remove_from_app_registry:
                _logcore.trace(
                    "Removing app {app_name} from registrations",
                    app_name=app_name_for_logs,
                )

                if app_registration.app_name in self.__app_registrations:
                    self.__app_registrations.pop(app_registration.app_name)
                else:
                    _logcore.warning(
                        "Tried to remove app {app_name} from registrations, but it was not found",
                        app_name=app_name_for_logs,
                    )

                self.__apps_by_path[app_registration.app_path].remove(app_registration)

    def get_stats(self) -> AppEngineStats:
        total_apps = len(self.__app_registrations.values())
        apps_per_status = {
            status: [
                r.app_name
                for r in self.__app_registrations.values()
                if (r.active_instance is not None and r.active_instance.status == status)
                or (r.active_instance is None and status == AppStatus.TERMINATED)
            ]
            for status in AppStatus
        }

        return AppEngineStats(
            total_apps=total_apps,
            apps_per_status=apps_per_status,
        )
