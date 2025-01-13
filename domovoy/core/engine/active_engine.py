from domovoy.core.engine.engine import AppEngine
from domovoy.core.errors import DomovoyError
from domovoy.core.logging import get_logger

__active_engine = None
_logcore = get_logger(__name__)


def set_active_engine_for_app_registration(engine: AppEngine) -> None:
    global __active_engine
    _logcore.trace("Setting Active App Engine to: {engine}", engine=engine)
    __active_engine = engine


def get_active_engine() -> AppEngine:
    if __active_engine is None:
        raise DomovoyError(
            "Trying to fetch the active App Engine but none has been set yet.",
        )

    return __active_engine
