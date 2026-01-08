from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domovoy.core.logging.logger_adapter_with_trace import LoggerAdapterWithTrace

context_logger: contextvars.ContextVar[LoggerAdapterWithTrace[logging.Logger]] = contextvars.ContextVar(
    "context_logger",
)

inside_log_callback: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "inside_log_callback",
    default=False,
)

context_callback_id: contextvars.ContextVar[str | int | None] = contextvars.ContextVar(
    "context_callback_id",
    default=None,
)
