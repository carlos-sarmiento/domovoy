import contextvars
import logging

context_logger: contextvars.ContextVar[
    logging.LoggerAdapter[logging.Logger]
] = contextvars.ContextVar("context_logger")

inside_log_callback: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "inside_log_callback", default=False
)

context_callback_id: contextvars.ContextVar[str | int | None] = contextvars.ContextVar(
    "context_callback_id", default=None
)
