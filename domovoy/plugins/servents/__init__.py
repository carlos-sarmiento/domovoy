import asyncio
import inspect
from dataclasses import asdict
from typing import Any, ParamSpec

from domovoy.core.app_infra import AppWrapper
from domovoy.core.utils import strip_none_and_enums_from_containers
from domovoy.plugins import callbacks, hass, meta
from domovoy.plugins.callbacks.event_listener_callbacks import EventListenerCallback
from domovoy.plugins.plugins import AppPlugin

from .entities import (
    ServEntBinarySensor,
    ServEntButton,
    ServEntNumber,
    ServEntSelect,
    ServEntSensor,
    ServEntSwitch,
    ServEntThresholdBinarySensor,
)
from .entity_configs import (
    ServEntBinarySensorConfig,
    ServEntButtonConfig,
    ServEntDeviceConfig,
    ServEntEntityConfig,
    ServEntNumberConfig,
    ServEntSelectConfig,
    ServEntSensorConfig,
    ServEntSwitchConfig,
    ServEntThresholdBinarySensorConfig,
)
from .enums import ButtonDeviceClass, EntityCategory
from .exceptions import ServentInvalidConfigurationError

P = ParamSpec("P")


class ServentsPlugin(AppPlugin):
    __hass: hass.HassPlugin
    __callbacks: callbacks.CallbacksPlugin
    __meta: meta.MetaPlugin

    def __init__(
        self,
        name: str,
        wrapper: AppWrapper,
    ) -> None:
        super().__init__(name, wrapper)

    def prepare(self) -> None:
        super().prepare()
        self.__callbacks = self._wrapper.get_pluginx(callbacks.CallbacksPlugin)
        self.__hass = self._wrapper.get_pluginx(hass.HassPlugin)
        self.__meta = self._wrapper.get_pluginx(meta.MetaPlugin)

    def post_prepare(self) -> None:
        self.__default_device_for_app = ServEntDeviceConfig(
            device_id=self.__meta.get_app_name(),
            name=self.__meta.get_app_name(),
            model=self.__meta.get_app_name(),
            manufacturer=f"{self.__meta.get_module_name()}/{self.__meta.get_class_name()}",
            version="Domovoy",
        )

    def get_default_device_for_app(self) -> ServEntDeviceConfig:
        return self.__default_device_for_app

    def set_default_device_for_app(self, device_config: ServEntDeviceConfig) -> None:
        self.__default_device_for_app = device_config

    def update_default_device_name_for_app(
        self,
        name: str,
    ) -> None:
        self.__default_device_for_app.name = name

    async def enable_reload_button(self) -> ServEntButton:
        return await self.listen_button_press(
            self.__reload_callback,
            button_name="Restart App",
            event_name_to_fire="AppRestartRequested",
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.DIAGNOSTIC,
            disabled_by_default=True,
        )

    async def __reload_callback(self) -> None:
        self._wrapper.logger.info("Restarting App from Servent Button")
        await self.__meta.restart_app()

    async def _create_entity(
        self,
        entity_config: ServEntEntityConfig,
        device_config: ServEntDeviceConfig | None,
        *,
        wait_for_creation: bool,
    ) -> None:
        device_config = device_config or self.__default_device_for_app

        if device_config.app_name is None:
            if not device_config.is_global:
                device_config.app_name = self.__meta.get_app_name()
            else:
                raise ServentInvalidConfigurationError(
                    "Device Config must include app_name if 'is_global' is set to true"
                )

        if device_config.is_global:
            entity_config.app_name = device_config.app_name
        elif entity_config.app_name is None:
            entity_config.app_name = self.__meta.get_app_name()

        if device_config.is_global:
            entity_config.servent_id = f"global-{device_config.app_name}-{entity_config.servent_id}"

        else:
            entity_config.servent_id = f"{entity_config.app_name}-{entity_config.servent_id}"

        entity_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(asdict(entity_config))  # type: ignore
        device_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(asdict(device_config))  # type: ignore

        entity_config_dict["device_config"] = device_config_dict

        await self.__hass.services.servents.create_entity(
            entities=[entity_config_dict],
        )  # type: ignore

        if wait_for_creation:
            entities = self.__hass.get_entity_id_by_attribute(
                "servent_id",
                entity_config.servent_id,
            )

            count = 0
            while not any(entities) and count < 50:
                await asyncio.sleep(0.1)
                entities = self.__hass.get_entity_id_by_attribute(
                    "servent_id",
                    entity_config.servent_id,
                )
                count += 1

    async def create_sensor(
        self,
        entity_config: ServEntSensorConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntSensor:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntSensor(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_threshold_binary_sensor(
        self,
        entity_config: ServEntThresholdBinarySensorConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntThresholdBinarySensor:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntThresholdBinarySensor(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_binary_sensor(
        self,
        entity_config: ServEntBinarySensorConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntBinarySensor:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntBinarySensor(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_number(
        self,
        entity_config: ServEntNumberConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntNumber:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntNumber(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_select(
        self,
        entity_config: ServEntSelectConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntSelect:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntSelect(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_button(
        self,
        entity_config: ServEntButtonConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntButton:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntButton(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    async def create_switch(
        self,
        entity_config: ServEntSwitchConfig,
        device_config: ServEntDeviceConfig | None = None,
        *,
        wait_for_creation: bool = True,
    ) -> ServEntSwitch:
        device_config = device_config or self.__default_device_for_app

        await self._create_entity(
            entity_config,
            device_config,
            wait_for_creation=wait_for_creation,
        )
        return ServEntSwitch(
            self.__hass,
            entity_config.servent_id,
            entity_config,
            device_config,
        )

    _SERVENT_EXTENDED_BUTTON_PRESS_EVENT = "servent_extended_button_press"

    async def listen_button_press(
        self,
        callback: EventListenerCallback,
        button_name: str,
        event_name_to_fire: str,
        event_data: dict[str, Any] | None = None,
        device_class: ButtonDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        device_config: ServEntDeviceConfig | None = None,
        *,
        disabled_by_default: bool = False,
        wait_for_creation: bool = True,
    ) -> ServEntButton:
        final_event = f"{self.__meta.get_app_name()}.{event_name_to_fire}"

        self._wrapper.logger.debug(
            "Creating Button with final_event name `{final_event}`. Length: ``",
            final_event=final_event,
        )

        target_event = final_event
        target_event_data = event_data

        if len(final_event) > 50:
            self._wrapper.logger.debug(
                "Using Extended Button Press functionality for `{final_event}`",
                final_event=final_event,
            )
            target_event = self._SERVENT_EXTENDED_BUTTON_PRESS_EVENT
            target_event_data = {
                "true_event": final_event,
            }

        button = await self.create_button(
            ServEntButtonConfig(
                servent_id=final_event,
                name=button_name,
                event=target_event,
                event_data=target_event_data or {},
                device_class=device_class,
                entity_category=entity_category,
                disabled_by_default=disabled_by_default,
            ),
            device_config=device_config,
            wait_for_creation=wait_for_creation,
        )

        if target_event == self._SERVENT_EXTENDED_BUTTON_PRESS_EVENT:
            self._wrapper.logger.debug(
                "Configuring Callback using Extended Button Press functionality for `{final_event}`",
                final_event=final_event,
            )

            async def extended_callback(
                data: dict[str, Any],
            ) -> None:
                self._wrapper.logger.debug(
                    "Received Extended Button Press with event: `{final_event}`",
                    final_event=final_event,
                )
                if data["true_event"] != final_event:
                    # This event is not related to this button
                    return

                signature = inspect.signature(callback)
                valid_params = set(signature.parameters.keys())

                call_args = {}
                if "event_name" in valid_params:
                    call_args["event_name"] = event_name_to_fire
                if "data" in valid_params:
                    call_args["data"] = event_data or {}

                callback_result = callback(**call_args)
                if callback_result is not None:
                    await callback_result

            self.__callbacks.listen_event(
                f"servent.{target_event}",
                extended_callback,
            )

        else:
            self._wrapper.logger.debug(
                "Adding simple button press listener for {target_event}",
                target_event=target_event,
            )
            self.__callbacks.listen_event(
                f"servent.{target_event}",
                callback,
            )

        return button
