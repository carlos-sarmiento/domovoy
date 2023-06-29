from __future__ import annotations
import asyncio
from dataclasses import dataclass
from logging import DEBUG, WARNING
from typing import Any, Awaitable, Callable, ParamSpec

from domovoy.core.services.callback_register import CallbackRegister
from domovoy.core.services.service import DomovoyServiceResources
from domovoy.plugins.callbacks import (
    CallbacksPlugin,
)
from domovoy.core.services.webapi import DomovoyWebApi

from domovoy.applications import (
    AppBase,
    AppConfigBase,
)
from domovoy.plugins.utils import UtilsPlugin

from ..app_infra import (
    AppStatus,
    AppWrapper,
    EmptyAppConfig,
)
from domovoy.core.configuration import get_main_config
from domovoy.core.services.event_listener import EventListener
from ..context import context_logger

from domovoy.core.logging import (
    get_logger,
    get_logger_for_app,
)

from domovoy.plugins.hass.core import HassCore
from domovoy.plugins.hass import HassPlugin
from domovoy.plugins.logger import LoggerPlugin
from domovoy.plugins.meta import MetaPlugin
from domovoy.plugins.servents import ServentsPlugin

_logcore = get_logger(__name__)

P = ParamSpec("P")


@dataclass
class AppRegistration:
    app_class: type[AppBase[Any]]
    app_name: str
    app_path: str
    config: AppConfigBase
    logging_config_name: str


class AppEngine:
    __active_apps: dict[str, list[AppWrapper]] = {}
    __active_app_by_name: dict[str, AppWrapper] = {}
    __app_registrations: dict[str, AppRegistration] = {}

    __event_listener: EventListener
    __hass_core: HassCore
    __webapi: DomovoyWebApi

    def __init__(self):
        self.__event_listener = EventListener(
            DomovoyServiceResources(
                start_dependent_apps_callback=self.__build_start_apps_using_service_callback(),
                stop_dependent_apps_callback=self.__build_terminate_apps_using_service_callback(),
                get_all_apps_by_name=self.__get_all_apps_by_name,
                config={},
            )
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
                config={"address": "0.0.0.0", "port": 8080},
            ),
        )

    async def start(self):
        """Starts the App Engine and its dependent services."""
        _logcore.info("Starting Scheduling Engine")
        self.__event_listener.start()
        self.__callback_register.start()
        self.__webapi.start()
        await self.__hass_core.start()

    async def stop(self):
        await self.terminate_all_apps_before_engine_stop()
        await self.__webapi.stop()
        self.__callback_register.stop()
        self.__event_listener.stop()
        await self.__hass_core.stop()

    async def __get_all_apps_by_name(self) -> dict[str, AppWrapper]:
        return self.__active_app_by_name

    async def register_app(
        self,
        app_class: type[AppBase[Any]],
        app_name: str,
        app_path: str,
        config: AppConfigBase | None,
        logging_config_name: str | None,
    ) -> None:
        _logcore.info("Registering app: {app_name} in AppEngine", app_name=app_name)

        if app_name in self.__active_app_by_name:
            _logcore.error(
                "{app_name} is already registered. Choose a different name.",
                app_name=app_name,
            )
            return

        if config is None:
            config = EmptyAppConfig()

        app_registration = AppRegistration(
            app_class=app_class,
            app_name=app_name,
            app_path=app_path,
            config=config,
            logging_config_name=logging_config_name or "apps",
        )

        self.__app_registrations[app_name] = app_registration
        await self.__start_app(app_name)

    async def __start_app(self, app_name: str):
        # Needs Validation
        try:
            app_registration = self.__app_registrations[app_name]
            wrapper = self.__build_app_instance(app_registration)
            await self.__initialize_app(wrapper)
        except Exception as e:
            _logcore.exception(
                "Error when initializing app: {app_name}", e, app_name=app_name
            )

    def __build_app_instance(self, app_registration: AppRegistration) -> AppWrapper:
        if app_registration.app_path not in self.__active_apps:
            self.__active_apps[app_registration.app_path] = []

        _logcore.debug(
            "Initializing AppWrapper for {app_name}", app_name=app_registration.app_name
        )
        wrapper = AppWrapper(
            config=app_registration.config,
            app_name=app_registration.app_name,
            class_name=app_registration.app_class.__name__,
            module_name=app_registration.app_class.__module__,
            filepath=app_registration.app_path,
            status=AppStatus.CREATED,
            logger=get_logger_for_app(
                app_registration.logging_config_name,
                f"{app_registration.app_class.__name__}.{app_registration.app_name}",
            ),
        )

        _logcore.debug(
            "Initializing Modules for {app_name}", app_name=app_registration.app_name
        )

        logmodule = LoggerPlugin("log", wrapper)
        wrapper.register_plugin(logmodule, logmodule.name)

        meta = MetaPlugin(
            "meta", wrapper, lambda: self.__reload_app(app_registration.app_name)
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

        _logcore.debug(
            "Preparing all plugins for app {app_name}",
            app_name=app_registration.app_name,
        )
        wrapper.prepare_all_plugins()

        _logcore.debug(
            "Creating instance of class {class_name} for app {app_name}",
            app_name=app_registration.app_name,
            class_name=app_registration.app_class.__name__,
        )
        wrapper.app = app_registration.app_class(
            app_registration.config,
            meta,
            logmodule,
            callbacks,
            hass,
            servents,
            utils,
        )

        self.__active_apps[app_registration.app_path].append(wrapper)
        self.__active_app_by_name[app_registration.app_name] = wrapper

        return wrapper

    async def __initialize_app(self, wrapper: AppWrapper) -> None:
        context_logger.set(wrapper.logger)
        _logcore.info(
            "Calling initialize() for {app_name}",
            app_name=wrapper.app_name,
        )
        wrapper.status = AppStatus.INITIALIZING
        await super(wrapper.app.__class__, wrapper.app).initialize()
        await wrapper.app.initialize()
        wrapper.status = AppStatus.RUNNING
        self.__callback_register.register_all_callbacks(wrapper)
        _logcore.debug(
            "Initialization complete for {app_name}",
            app_name=wrapper.app_name,
        )

    async def __finalize_app(self, wrapper: AppWrapper) -> None:
        _logcore.info(
            "Calling finalize() for {app_name}",
            app_name=wrapper.app_name,
        )
        try:
            await wrapper.app.finalize()
        except Exception as e:
            _logcore.exception(
                "Error while calling finalize() for app {app_name}",
                e,
                app_name=wrapper.app_name,
            )

    async def __terminate_app(self, app_name: str) -> None:
        # Needs Validation
        _logcore.debug(
            "Terminating {app_name}",
            app_name=app_name,
        )

        if app_name not in self.__active_app_by_name:
            _logcore.warning(
                "Tried to terminate {app_name} but it is not running", app_name=app_name
            )
            return

        wrapper = self.__active_app_by_name[app_name]
        context_logger.set(wrapper.logger)

        wrapper.status = AppStatus.FINALIZING
        self.__callback_register.cancel_all_callbacks(wrapper)
        await self.__finalize_app(wrapper)
        wrapper.status = AppStatus.TERMINATED
        self.__clear_app_instance(wrapper)
        _logcore.debug(
            "Terminated {app_name}",
            app_name=app_name,
        )

    async def __reload_app(self, app_name: str) -> None:
        _logcore.info(
            "Reloading app: {app_name}",
            app_name=app_name,
        )
        await self.__terminate_app(app_name)
        await self.__start_app(app_name)

    def __clear_app_instance(self, wrapper: AppWrapper) -> None:
        _logcore.debug(
            "Clearing registrations for {app_name}",
            app_name=wrapper.app_name,
        )
        self.__active_app_by_name.pop(wrapper.app_name)
        self.__active_apps[wrapper.filepath].remove(wrapper)

    async def terminate_app_from_files(
        self, paths: list[str], remove_from_registry: bool = True
    ) -> None:
        _logcore.debug(
            "Building list of apps for termination from path(s): {paths}", paths=paths
        )

        app_names_to_terminate: list[str] = []
        for path in paths:
            if path not in self.__active_apps:
                continue

            app_names_to_terminate += [x.app_name for x in self.__active_apps[path]]

        await self.__terminate_multiple_apps(
            app_names_to_terminate, remove_from_registry
        )

    async def terminate_all_apps_before_engine_stop(self) -> None:
        await self.__terminate_multiple_apps(
            list(self.__active_app_by_name.keys()), True
        )

    def __build_terminate_apps_using_service_callback(
        self,
    ) -> Callable[[], Awaitable[None]]:
        async def app_termination_callback() -> None:
            apps_to_terminate = [
                app_name
                for app_name in self.__app_registrations.keys()
                if app_name in self.__active_app_by_name
            ]

            _logcore.log(
                WARNING if len(apps_to_terminate) > 0 else DEBUG,
                "Terminating {apps_to_terminate} Apps",
                apps_to_terminate=len(apps_to_terminate),
            )

            app_terminations = [
                self.__terminate_app(app_name) for app_name in apps_to_terminate
            ]
            await asyncio.gather(*app_terminations)

        return app_termination_callback

    def __build_start_apps_using_service_callback(
        self,
    ) -> Callable[[], Awaitable[None]]:
        async def app_start_callback() -> None:
            apps_to_start = [
                app_name
                for app_name in self.__app_registrations.keys()
                if app_name not in self.__active_app_by_name
            ]

            _logcore.warning(
                "Starting {reload_app_count} Apps",
                reload_app_count=len(apps_to_start),
            )
            app_reloads = [self.__start_app(app_name) for app_name in apps_to_start]
            await asyncio.gather(*app_reloads)

        return app_start_callback

    async def __terminate_multiple_apps(
        self, app_names_to_terminate: list[str], remove_from_app_registry: bool
    ) -> None:
        if not app_names_to_terminate:
            _logcore.warning("Called termination on an empty app list")

        for app_name in app_names_to_terminate:
            await self.__terminate_app(app_name)

            if remove_from_app_registry:
                _logcore.debug(
                    "Removing app {app_name} from registrations", app_name=app_name
                )
                if app_name not in self.__app_registrations:
                    _logcore.debug(
                        "Attempted to remove non-existing app registration for `{app_name}`",
                        app_name=app_name,
                    )
                    continue

                self.__app_registrations.pop(app_name)
