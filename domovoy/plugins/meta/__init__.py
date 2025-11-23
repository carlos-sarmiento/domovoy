import datetime
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from domovoy.core.app_infra import AppPlugin
from domovoy.core.configuration import get_main_config

if TYPE_CHECKING:
    from domovoy.core.app_infra import AppStatus, AppWrapper
    from domovoy.core.engine.engine import AppEngineStats

T = TypeVar("T", bound=AppPlugin)


class MetaPlugin(AppPlugin):
    _wrapper: "AppWrapper"
    __app_restart_callback: Callable[[], Awaitable[None]]

    def __init__(
        self,
        name: str,
        wrapper: "AppWrapper",
        app_restart_callback: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(name, wrapper)
        self.__app_restart_callback = app_restart_callback

    def get_app_name(self) -> str:
        return self._wrapper.app_name

    def get_filepath(self) -> str:
        return self._wrapper.filepath

    def get_module_name(self) -> str:
        return self._wrapper.module_name

    def get_class_name(self) -> str:
        return self._wrapper.class_name

    def get_status(self) -> "AppStatus":
        return self._wrapper.status

    def get_config_tz(self) -> datetime.tzinfo:
        return get_main_config().get_timezone()

    async def restart_app(self) -> None:
        await self.__app_restart_callback()

    def get_plugin(self, plugin_type: type[T], name: str | None = None) -> T | None:
        self._wrapper.get_plugin(plugin_type, name)

    def get_app_engine_stats(self) -> "AppEngineStats":
        from domovoy.core.engine.active_engine import get_active_engine

        engine = get_active_engine()
        return engine.get_stats()
