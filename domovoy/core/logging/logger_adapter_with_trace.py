import logging
from typing import Any, TypeVar

T = TypeVar("T", bound=logging.Logger | logging.LoggerAdapter[Any])


class LoggerAdapterWithTrace(logging.LoggerAdapter[T]):
    def trace(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        self.log(5, *args, **kwargs)  # type: ignore
