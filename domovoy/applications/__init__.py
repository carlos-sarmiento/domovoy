from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from domovoy.plugins.callbacks import CallbacksPlugin
    from domovoy.plugins.hass import HassPlugin
    from domovoy.plugins.logger import LoggerPlugin
    from domovoy.plugins.meta import MetaPlugin
    from domovoy.plugins.servents import ServentsPlugin
    from domovoy.plugins.time import TimePlugin
    from domovoy.plugins.utils import UtilsPlugin


class AppConfigBase:
    """The base implementation for App configuration classes."""


class EmptyAppConfig(AppConfigBase):
    """A configuration class with no fields. Used when an app doesn't need config."""


TConfig = TypeVar("TConfig", bound=AppConfigBase)  # , contravariant=True)


class AppBaseWithoutConfig:
    meta: MetaPlugin
    hass: HassPlugin
    callbacks: CallbacksPlugin
    servents: ServentsPlugin
    log: LoggerPlugin
    utils: UtilsPlugin
    time: TimePlugin

    def __init__(
        self,
        meta: MetaPlugin,
        log: LoggerPlugin,
        scheduler: CallbacksPlugin,
        hass: HassPlugin,
        servents: ServentsPlugin,
        utils: UtilsPlugin,
        time: TimePlugin,
    ) -> None:
        self.hass = hass
        self.callbacks = scheduler
        self.servents = servents
        self.meta = meta
        self.log = log
        self.utils = utils
        self.time = time

    async def initialize(self) -> None:
        """Initialize the App when it is started.

        The initialize function is called when an app is first started. It can be used to
        setup listeners and other parameters needed during operations.
        """

    async def finalize(self) -> None:
        """Clean up resources when the app is being terminated.

        This function is called when the app is being terminated. It can be used to cleanup
        any resources created or used by the app which are not handled by Domovoy
        """


class AppBase[TConfig: AppConfigBase](AppBaseWithoutConfig):
    config: TConfig

    def __init__(
        self,
        config: TConfig,
        meta: MetaPlugin,
        log: LoggerPlugin,
        scheduler: CallbacksPlugin,
        hass: HassPlugin,
        servents: ServentsPlugin,
        utils: UtilsPlugin,
        time: TimePlugin,
    ) -> None:
        super().__init__(meta, log, scheduler, hass, servents, utils, time)
        self.config = config

    async def initialize(self) -> None:
        await super().initialize()

    async def finalize(self) -> None:
        await super().finalize()
