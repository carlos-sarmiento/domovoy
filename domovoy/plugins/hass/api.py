from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from enum import StrEnum

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from domovoy.core.logging import get_logger

from .exceptions import (
    HassApiAuthenticationError,
    HassApiCommandError,
    HassApiConnectionError,
    HassApiParseError,
)
from .parsing import encode_message, parse_message
from .types import EntityID, HassData

_logcore = get_logger(__name__)
_messages_logcore = get_logger(f"{__name__}.messages")

EventListenerCallable = Callable[[str, HassData], Awaitable[None]]
TriggerListenerCallable = Callable[[int, HassData], Awaitable[None]]


class HassApiConnectionState(StrEnum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class HassWebsocketApi:
    __cmd_queue: deque[HassData]
    __in_flight_ops: dict[
        int,
        tuple[HassData, asyncio.Future[HassData]],
    ]
    __event_callbacks: dict[int, EventListenerCallable | TriggerListenerCallable]
    __current_op_id = 2
    __msg_receive_task: asyncio.Task[None] | None = None
    __msg_send_task: asyncio.Task[None] | None = None
    __is_running: bool = False
    __uri: str = ""
    __access_token: str
    __parse_datetimes: bool
    __connection_state_callback: Callable[[HassApiConnectionState], Awaitable[None]]
    __connection_state_task: list[asyncio.Task[None]]

    async def __dummy_callback(*_args: object, **_kwargs: object) -> None: ...

    def __init__(
        self,
        uri: str,
        access_token: str,
        connection_state_callback: Callable[[HassApiConnectionState], Awaitable[None]] | None = None,
        *,
        parse_datetimes: bool = True,
    ) -> None:
        self.__in_flight_ops = {}
        self.__event_callbacks = {}
        self.__connection_state_task = []
        self.__cmd_queue = deque([])
        self.__uri = uri
        self.__access_token = access_token
        self.__connection_state_callback = connection_state_callback or self.__dummy_callback
        self.__parse_datetimes = parse_datetimes

    def start(self) -> asyncio.Future[None]:
        _logcore.info("Starting Home Assistant API")
        future: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        asyncio.get_event_loop().create_task(
            self.__connect_and_listen(future),
            name="hass_api_connect_and_listen",
        )
        return future

    def __notify_connection_state_update(
        self,
        connection_state: HassApiConnectionState,
    ) -> None:
        _logcore.trace(
            "Notifying connection state update: `{state}`",
            state=connection_state,
        )
        task = asyncio.get_event_loop().create_task(
            self.__connection_state_callback(connection_state),  # type: ignore
            name="hass_api_connection_state_callback",
        )
        self.__connection_state_task.append(task)
        task.add_done_callback(self.__connection_state_task.remove)

    async def __connect_and_listen(self, future: asyncio.Future[None]) -> None:
        self.__is_running = True

        while True:
            try:
                websocket = await self.__connect_to_ha()
                break
            except Exception:
                await asyncio.sleep(1)

        try:
            self.__notify_connection_state_update(HassApiConnectionState.CONNECTING)
            self.__prep_for_connection()

            await self.__authenticate(
                websocket=websocket,
                access_token=self.__access_token,
            )

            future.set_result(None)

            self.__msg_receive_task = asyncio.create_task(
                self.hass_message_receiver(websocket),
                name="hass_websocket_message_receiver",
            )
            self.__msg_send_task = asyncio.create_task(
                self.producer_handler(websocket),
                name="hass_websocket_message_sender",
            )

            self.__notify_connection_state_update(HassApiConnectionState.CONNECTED)

            completed, pending = await asyncio.wait(
                [self.__msg_receive_task, self.__msg_send_task],
                return_when=asyncio.FIRST_COMPLETED,
            )  # type: ignore

            for task in completed:
                _logcore.trace("Task `{task}` completed", task=task)

            for task in pending:
                task.cancel()
                _logcore.trace("Task `{task}` is cancelled", task=task)

            _logcore.trace("Hass API Tasks have been cancelled.")

            for op_id in list(self.__in_flight_ops.keys()):
                _logcore.trace("Cancelling Pending Future with ID `{id}`", id=op_id)

                _, in_flight_future = self.__in_flight_ops[op_id]

                self.__in_flight_ops.pop(op_id)
                if not in_flight_future.done():
                    in_flight_future.set_exception(HassApiConnectionError())

        except HassApiAuthenticationError as e:
            _logcore.info("Authentication to Home Assistant Failed")

            self.__is_running = False

            if not future.done():
                future.set_exception(e)

        except ConnectionClosed as e:
            _logcore.critical(e)
            _logcore.info("Disconnected from Home Assistant Websocket API")

            if not self.__is_running:
                if not future.done():
                    future.set_result(None)

            elif not future.done():
                future.set_exception(e)

        except Exception as e:
            _logcore.exception("Unhandled Exception in HassAPI Connection Loop")

            if not self.__is_running:
                if not future.done():
                    future.set_result(None)

            elif not future.done():
                future.set_exception(e)

        finally:
            self.__notify_connection_state_update(HassApiConnectionState.DISCONNECTED)

    def stop(self) -> None:
        if not self.__is_running:
            return

        _logcore.info("Stopping Home Assistant API")

        self.__is_running = False
        if self.__msg_receive_task and not self.__msg_receive_task.cancelled():
            self.__msg_receive_task.cancel()

        if self.__msg_send_task and not self.__msg_send_task.cancelled():
            self.__msg_send_task.cancel()

    async def hass_message_receiver(self, websocket: ClientConnection) -> None:
        try:
            async for message_raw in websocket:
                message = parse_message(message_raw, parse_datetimes=self.__parse_datetimes)

                message_id: int = message["id"]  # type: ignore
                message_type = message["type"]
                _messages_logcore.trace(
                    "Received Message from Hass. ID: {id} Type: {type}: Message: {message}",
                    id=message_id,
                    type=message_type,
                    message=message_raw,
                )

                if message_type == "event":
                    if message_id not in self.__event_callbacks:
                        _logcore.warning(
                            "Received an Event without a registered Callback. Callback ID: `{id}`",
                            id=message_id,
                        )
                        continue

                    event_callback = self.__event_callbacks[message_id]

                    event: HassData = message["event"]  # type: ignore

                    if "event_type" in event:
                        event_type_or_subscription_id: str = event["event_type"]  # type: ignore
                        data: HassData = event["data"]  # type: ignore

                        _messages_logcore.trace(
                            "Calling Callback for event {event_type} with data {event_data}",
                            event_type=event_type_or_subscription_id,
                            event_data=data,
                        )

                        entity_id = data.get("entity_id", None)

                        _messages_logcore.trace(
                            f"Received from listener with id: {message_id} "
                            f"a `{event_type_or_subscription_id}` event for {entity_id}. {data}",
                        )

                    elif "variables" in event:
                        event_type_or_subscription_id: int = message_id
                        data = event["variables"].get("trigger", {})  # type: ignore

                        _messages_logcore.trace(
                            "Calling Callback for trigger with data {trigger_data}",
                            trigger_data=data,
                        )

                    try:
                        await asyncio.wait_for(
                            event_callback(event_type_or_subscription_id, data),  # type: ignore
                            timeout=5,
                        )
                    except asyncio.exceptions.CancelledError:
                        _logcore.trace(
                            "Cancelled Error for callback to Message ID: `{id}`",
                            id=message_id,
                        )

                    except TimeoutError:
                        _logcore.trace(
                            "Timeout Error for callback to Message ID: `{id}`",
                            id=message_id,
                        )

                    except Exception as e:
                        _logcore.exception(
                            f"{event_callback.__name__} {event_callback.__class__}",
                            e,
                        )
                        raise

                    continue

                if message_id not in self.__in_flight_ops:
                    _logcore.warning(
                        "Received a response for ID {id} that does not have an in-flight command. Ignoring...",
                        id=message_id,
                    )
                    continue

                (cmd, future) = self.__in_flight_ops[message_id]
                self.__in_flight_ops.pop(message_id)

                if future.done():
                    if self.__is_running:
                        _logcore.warning(
                            "Received a response for a finished future. ID: `{id}`. Future: `{future}`",
                            id=message_id,
                            future=future,
                        )

                    continue

                if "error" in message:
                    error = message["error"]
                    future.set_exception(
                        HassApiCommandError(
                            command_id=message["id"],  # type: ignore
                            code=error["code"],  # type: ignore
                            message=error["message"],  # type: ignore
                            full_response=message,
                            original_command=cmd,
                        ),
                    )
                    continue

                if "success" in message and message["success"] is False:
                    future.set_exception(
                        HassApiCommandError(
                            command_id=message["id"],  # type: ignore
                            code=-1,
                            message="Command Failed but Home Assistant did not send an specific error message",
                            full_response=message,
                            original_command=cmd,
                        ),
                    )

                future.set_result(message)

        except asyncio.CancelledError:
            _logcore.trace("hass_message_receiver() was cancelled")
            return

        except Exception as e:
            _logcore.exception("Failure on Hass API Receiver:", e)
            return

    async def producer_handler(self, websocket: ClientConnection) -> None:
        try:
            while True:
                while len(self.__cmd_queue) > 0:
                    message = self.__cmd_queue.popleft()
                    message_id: int = message["id"]  # type: ignore
                    try:
                        encoded_message = encode_message(message)
                        _logcore.trace("Sending message to hass")
                        await websocket.send(encoded_message, text=True)
                    except HassApiParseError as e:
                        (cmd, future) = self.__in_flight_ops[message_id]
                        self.__in_flight_ops.pop(message_id)
                        future.set_exception(e)

                # We do this to make sure this function yields
                # the event loop after it attemps to send messages.
                # If not, the code will get stuck on the while True:
                # loop until websocket.send yields.
                await asyncio.sleep(0.25)

        except asyncio.CancelledError:
            return

        except ConnectionClosedError as e:
            _logcore.trace("Failure on Hass API Sender:", e)
            return

        except Exception as e:
            _logcore.exception("Failure on Hass API Sender:", e)
            return

    async def __authenticate(
        self,
        websocket: ClientConnection,
        access_token: str,
    ) -> None:
        _logcore.info("Authenticating with Home Assistant")
        initial_message = await websocket.recv()
        initial_message = parse_message(initial_message, parse_datetimes=self.__parse_datetimes)

        if initial_message["type"] != "auth_required":
            raise HassApiCommandError(
                command_id=0,
                code=-1,
                message="Did not receive auth_required_message from Home Assistant API",
                full_response=initial_message,
                original_command={},
            )

        await websocket.send(
            encode_message({"type": "auth", "access_token": access_token}),
            text=True,
        )

        auth_response = await websocket.recv()
        auth_response = parse_message(auth_response, parse_datetimes=self.__parse_datetimes)

        if auth_response["type"] == "auth_ok":
            _logcore.info("Authenticated with Home Assistant")
        else:
            raise HassApiAuthenticationError

    def __connect_to_ha(
        self,
    ) -> connect:
        uri = f"{self.__uri.removesuffix('/')}/api/websocket"
        _logcore.info("Connecting to Home Assistant Websocket API {uri}", uri=uri)
        return connect(
            uri=uri,
            max_size=1_000_000_000,
            ping_timeout=None,
        )

    def __prep_for_connection(self) -> None:
        self.__cmd_queue = deque()
        self.__in_flight_ops = {}
        self.__event_callbacks = {}

    # Home Assistant API Below

    def __send_command(
        self,
        command: HassData,
    ) -> asyncio.Future[HassData]:
        _logcore.trace("Queueing Command to HA: {command}", command=command)

        # create Future
        future = asyncio.get_event_loop().create_future()

        # this might need a lock to make the operation atomic
        command["id"] = self.__current_op_id
        self.__in_flight_ops[command["id"]] = (command, future)
        self.__current_op_id += 1

        self.__cmd_queue.append(command)

        return future

    async def ping(self) -> bool:
        response = await self.__send_command({"type": "ping"})
        return response["type"] == "pong"

    async def subscribe_events(
        self,
        callback: Callable[[str, HassData], Awaitable[None]],
        event_type: str | None = None,
    ) -> int:
        _logcore.trace(
            "Calling subscribe_event with event: {event_type}",
            event_type=event_type,
        )

        cmd: HassData = {"type": "subscribe_events"}

        if event_type is not None:
            cmd["event_type"] = event_type

        response = await self.__send_command(cmd)

        subscription_id: int = response["id"]  # type: ignore

        self.__event_callbacks[subscription_id] = callback

        _logcore.trace(
            "Received Response for subscribe_event call for event: {event_type}. Response: {response}",
            event_type=event_type,
            response=response,
        )
        return response["id"]  # type: ignore

    async def subscribe_trigger(
        self,
        callback: Callable[[int, HassData], Awaitable[None]],
        trigger: HassData,
    ) -> int:
        _logcore.trace(
            "Calling subscribe_trigger with trigger: {trigger}",
            trigger=trigger,
        )

        cmd: HassData = {"type": "subscribe_trigger", "trigger": trigger}

        response = await self.__send_command(cmd)

        subscription_id: int = response["id"]  # type: ignore

        self.__event_callbacks[subscription_id] = callback

        _logcore.trace(
            "Received Response for subscribe_trigger call for event: {trigger}. Response: {response}",
            trigger=trigger,
            response=response,
        )
        return response["id"]  # type: ignore

    async def unsubscribe_events(self, subscription_id: int) -> bool:
        _logcore.trace(
            "Calling unsubscribe_events with subscription_id: {subscription_id}",
            subscription_id=subscription_id,
        )
        response = await self.__send_command(
            {"type": "unsubscribe_events", "subscription": subscription_id},
        )

        _logcore.trace(
            "Received Response for unsubscribe_events call for subscription_id: {subscription_id}."
            " Response: {response}",
            subscription_id=subscription_id,
            response=response,
        )

        if response["success"] is True:
            self.__event_callbacks.pop(subscription_id, None)
            return True

        return False

    async def fire_event(
        self,
        event_type: str,
        event_data: HassData | None = None,
    ) -> HassData:
        _logcore.trace(
            "Calling fire_event with event: {event_type} and data: {event_data}",
            event_type=event_type,
            event_data=event_data,
        )

        cmd: HassData = {"type": "fire_event", "event_type": event_type}

        if event_data is not None:
            cmd["event_data"] = event_data

        response = await self.__send_command(cmd)

        _logcore.trace(
            "Received Response for fire_event call for event: {event_type} and data: {event_data}."
            " Response: {response}",
            event_type=event_type,
            event_data=event_data,
            response=response,
        )

        return response["result"]  # type: ignore

    async def call_service(
        self,
        *,
        domain: str,
        service: str,
        service_data: HassData | None = None,
        entity_id: EntityID | list[EntityID] | None = None,
        return_response: bool = False,
    ) -> HassData | None:
        _logcore.trace(
            f"Calling call_service for {domain}.{service}",
            domain=domain,
            service=service,
        )

        cmd: HassData = {
            "type": "call_service",
            "domain": domain,
            "service": service,
            "return_response": return_response,
        }

        if service_data is not None:
            cmd["service_data"] = service_data

        if entity_id is not None:
            cmd["target"] = {"entity_id": entity_id}  # type: ignore

        response = await self.__send_command(cmd)

        _logcore.trace(
            "Received Response for call_service call for {domain}.{service}: {response}",
            domain=domain,
            service=service,
            response=response,
        )
        return response["result"]  # type: ignore

    async def get_states(
        self,
    ) -> list[HassData]:
        response = await self.__send_command(
            {
                "type": "get_states",
            },
        )

        return response["result"]  # type: ignore

    async def get_services(
        self,
    ) -> HassData:
        response = await self.__send_command(
            {
                "type": "get_services",
            },
        )

        return response["result"]  # type: ignore

    async def search_related(
        self,
        item_type: str,
        item_id: str,
    ) -> HassData:
        response = await self.__send_command(
            {
                "type": "search/related",
                "item_type": item_type,
                "item_id": item_id,
            },
        )

        return response["result"]  # type: ignore

    async def send_command(self, command_type: str, command_args: HassData) -> HassData | list[HassData]:
        command = command_args | {"type": command_type}

        response = await self.__send_command(
            command,
        )

        return response["result"]  # type: ignore
