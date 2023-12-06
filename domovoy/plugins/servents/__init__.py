import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any, Concatenate, ParamSpec

from domovoy.core.app_infra import AppWrapper
from domovoy.core.utils import strip_none_and_enums_from_containers
from domovoy.plugins import callbacks, hass, meta
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
from .enums import ButtonDeviceClass, EntityCategory, EntityType

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
            servent_device_id=self.__meta.get_app_name(),
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

    async def __reload_callback(self, _event_name: str, _data: dict[str, object]) -> None:
        # TODO: Add Logging
        await self.__meta.restart_app()

    async def _create_entity(
        self,
        entity_type: EntityType,
        entity_config: ServEntEntityConfig,
        device_config: ServEntDeviceConfig | None,
        *,
        wait_for_creation: bool,
    ) -> None:
        device_config = device_config or self.__default_device_for_app

        if entity_config.app_name is None:
            entity_config.app_name = self.__meta.get_app_name()

        if device_config.app_name is None:
            device_config.app_name = self.__meta.get_app_name()

        if device_config.is_global:
            entity_config.servent_id = f"global-{device_config.app_name}-{entity_config.servent_id}"

        else:
            entity_config.servent_id = f"{entity_config.app_name}-{entity_config.servent_id}"

        entity_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(asdict(entity_config))  # type: ignore
        device_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(asdict(device_config))  # type: ignore

        await self.__hass.services.servents.create_entity(
            type=entity_type,
            entity=entity_config_dict,
            device=device_config_dict,
        )

        if wait_for_creation:
            entities = self.__hass.get_entity_id_by_attribute(
                "servent_id",
                entity_config.servent_id,
            )

            count = 0
            while not any(entities) and count < 10:
                await asyncio.sleep(0.5)
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
            EntityType.SENSOR,
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
            EntityType.THRESHOLD_BINARY_SENSOR,
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
            EntityType.BINARY_SENSOR,
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
            EntityType.NUMBER,
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
            EntityType.SELECT,
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
            EntityType.BUTTON,
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
            EntityType.SWITCH,
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
        callback: Callable[Concatenate[str, dict[str, Any], P], None | Awaitable[None]],
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
                event_data=target_event_data,
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
                _event_name: str,
                extended_event_data: dict[str, object],
                *callback_args: P.args,
                **callback_kwargs: P.kwargs,
            ) -> None:
                self._wrapper.logger.debug(
                    "Calling Extended Button Press functionality for `{final_event}`",
                    final_event=final_event,
                )
                if extended_event_data["true_event"] != final_event:
                    self._wrapper.logger.debug(
                        "{true_event} != `{final_event}`",
                        true_event=extended_event_data["true_event"],
                        final_event=final_event,
                    )
                    return

                callback_result = callback(
                    event_name_to_fire,
                    event_data or {},
                    *callback_args,
                    **callback_kwargs,
                )
                if callback_result is not None:
                    await callback_result

            self.__callbacks.listen_event(
                f"servent.{target_event}",
                extended_callback,
            )

        else:
            self.__callbacks.listen_event(
                f"servent.{target_event}",
                callback,
            )

        return button
