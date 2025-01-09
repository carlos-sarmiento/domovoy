from typing import Any

from domovoy.core.errors import DomovoyLogOnlyOnDebugWhenUncaughtError
from domovoy.plugins.hass.types import EntityID


class HassError(Exception): ...


class HassApiAuthenticationError(HassError):
    def __init__(self) -> None:
        super().__init__(
            "Failed to authenticate to Home Assistant Websocket API. Please check your access_token",
        )


class HassApiParseError(HassError): ...


class HassApiConnectionError(HassError, DomovoyLogOnlyOnDebugWhenUncaughtError): ...


class HassApiConnectionResetError(HassApiConnectionError): ...


class HassApiInvalidValueError(HassError): ...


class HassUnknownEntityError(HassError):
    def __init__(self, entity_id: EntityID) -> None:
        super().__init__(f"Entity ID: {entity_id} was not found.")


class HassApiCommandError(HassError):
    command_id: int
    code: int
    message: str
    full_response: dict[str, Any]

    def __init__(
        self,
        *,
        command_id: int,
        code: int,
        message: str,
        full_response: dict[str, Any],
        original_command: dict[str, Any],
    ) -> None:
        message = full_response.get("message", message)
        super().__init__(
            "Received Error from HASS:"
            f"{message}. Code: {code}. Command ID: {command_id}. "
            f"Full response: {full_response}. Original Command: {original_command}",
        )

        self.message = message
        self.full_response = full_response
        self.command_id = command_id
        self.code = code
