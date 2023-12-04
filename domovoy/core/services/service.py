from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from domovoy.core.app_infra import AppWrapper


@dataclass(kw_only=True)
class DomovoyServiceResources:
    start_dependent_apps_callback: Callable[[], Awaitable[None]]
    stop_dependent_apps_callback: Callable[[], Awaitable[None]]
    get_all_apps_by_name: Callable[[], Awaitable[dict[str, AppWrapper]]]
    config: dict[str, Any] = field(default_factory=dict)


class DomovoyService:
    __resources: DomovoyServiceResources

    def __init__(self, resources: DomovoyServiceResources) -> None:
        self.__resources = resources

    async def _stop_related_apps(self) -> None:
        await self.__resources.stop_dependent_apps_callback()

    async def start_dependent_apps(self) -> None:
        await self.__resources.start_dependent_apps_callback()
