from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domovoy.core.app_infra import AppWrapper


class AppPlugin:
    name: str
    _wrapper: AppWrapper

    def __init__(self, name: str, app_wrapper: AppWrapper) -> None:
        self.name = name
        self._wrapper = app_wrapper

    def prepare(self) -> None:
        pass

    def post_prepare(self) -> None:
        pass
