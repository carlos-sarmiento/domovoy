import asyncio
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ParamSpec

from domovoy.core.app_infra import AppPlugin
from domovoy.core.context import inside_log_callback

if TYPE_CHECKING:
    from domovoy.core.app_infra import AppWrapper


class LogLevels(Enum):
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0


P = ParamSpec("P")


@dataclass
class LoggerCallbackRegistration:
    id: str
    callback: Callable[[str], Awaitable[None]]
    minimum_log_level: LogLevels


class LoggerPlugin(AppPlugin):
    _wrapper: "AppWrapper"
    __log_callbacks: dict[str, LoggerCallbackRegistration]
    __running_callbacks: set[asyncio.Task[None]]

    def __init__(
        self,
        name: str,
        wrapper: "AppWrapper",
    ) -> None:
        super().__init__(name, wrapper)
        self.__log_callbacks = {}
        self.__running_callbacks = set()

    def listen_log(
        self,
        minimim_log_level: LogLevels,
        callback: Callable[P, None | Awaitable[None]],
        *callback_args: P.args,
        **callback_kwargs: P.kwargs,
    ) -> str:
        instrumented_callback = self._wrapper.instrument_app_callback(callback)

        @self._wrapper.handle_exception_and_logging(callback)
        async def log_callback(callback_id: str) -> None:
            inside_log_callback.set(True)  # noqa: FBT003
            try:
                self._wrapper.logger.trace(
                    "Calling Timer Callback: {cls_name}.{func_name}",
                    cls_name=callback.__self__.__class__.__name__,  # type: ignore
                    func_name=callback.__name__,
                )

                await instrumented_callback(
                    callback_id,
                    *callback_args,
                    **callback_kwargs,
                )

            finally:
                inside_log_callback.set(False)  # noqa: FBT003

        callback_id = f"logs-{uuid.uuid4().hex}"

        self.__log_callbacks[callback_id] = LoggerCallbackRegistration(
            id=callback_id,
            callback=log_callback,
            minimum_log_level=minimim_log_level,
        )

        return callback_id

    def cancel_callback(self, callback_id: str) -> None:
        if callback_id in self.__log_callbacks:
            self.__log_callbacks.pop(callback_id)

    def set_level(self, level: LogLevels) -> None:
        self._wrapper.logger.setLevel(level.value)

    def __run_callbacks(self, log_level: LogLevels) -> None:
        if inside_log_callback.get() is True:
            return

        for callback_registration in self.__log_callbacks.values():
            if log_level.value < callback_registration.minimum_log_level.value:
                continue

            task = asyncio.create_task(
                callback_registration.callback(callback_registration.id),  # type: ignore
            )
            self.__running_callbacks.add(task)
            task.add_done_callback(lambda t: self.__running_callbacks.remove(t))

    def trace(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.trace(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def debug(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.debug(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def info(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.info(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def warning(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.warning(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def error(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.error(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def exception(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.exception(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def critical(
        self,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.critical(
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )

    def log(
        self,
        level: int,
        msg: object,
        *args: object,
        exc_info: Any = None,  # noqa: ANN401
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> None:
        self._wrapper.logger.log(
            level,
            msg,
            *args,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            extra=extra,
            **kwargs,
        )
