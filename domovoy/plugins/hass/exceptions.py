from typing import Any

from domovoy.core.errors import DomovoyLogOnlyOnDebugWhenUncaughtException


class HassError(Exception):
    ...


class HassApiAuthenticationError(HassError):
    def __init__(self) -> None:
        super().__init__(
            "Failed to authenticate to Home Assistant Websocket API. Please check your access_token",
        )


class HassApiParseError(HassError):
    ...


class HassApiConnectionError(HassError, DomovoyLogOnlyOnDebugWhenUncaughtException):
    ...


class HassApiConnectionResetError(HassApiConnectionError):
    ...


class HassUnknownEntityError(HassError):
    def __init__(self, entity_id: str) -> None:
        super().__init__(f"Entity ID: {entity_id} was not found.")


class HassApiCommandError(HassError):
    command_id: int
    code: int

    def __init__(
        self,
        *,
        command_id: int,
        code: int,
        message: str,
        full_response: dict[str, Any],
        original_command: dict[str, Any],
    ) -> None:
        super().__init__(
            "Received Error from HASS:"
            + f"{message}. Code: {code}. Command ID: {command_id}. "
            + f"Full response: {full_response}. Original Command: {original_command}",
        )

        self.command_id = command_id
        self.code = code
