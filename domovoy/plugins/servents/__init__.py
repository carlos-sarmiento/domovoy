import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, ParamSpec

from serde import to_dict
from servents.data_model.derived_consts import (
    BinarySensorDeviceClass,
    ButtonDeviceClass,
    EntityCategory,
    NumberDeviceClass,
    NumberMode,
    SensorDeviceClass,
    SensorStateClass,
    SwitchDeviceClass,
)
from servents.data_model.entity_configs import (
    BinarySensorConfig,
    ButtonConfig,
    DeviceConfig,
    EntityConfig,
    NumberConfig,
    SelectConfig,
    SensorConfig,
    SwitchConfig,
    ThresholdBinarySensorConfig,
)

from domovoy.core.app_infra import AppWrapper
from domovoy.core.logging import get_logger
from domovoy.core.utils import strip_none_and_enums_from_containers
from domovoy.plugins import callbacks, hass, meta
from domovoy.plugins.callbacks.event_listener_callbacks import EventListenerCallback
from domovoy.plugins.hass.entity_id import EntityID
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
from .exceptions import ServentInvalidConfigurationError

_logger = get_logger("servents")
P = ParamSpec("P")


@dataclass(kw_only=True)
class ExtraConfig:
    device_config: DeviceConfig | None = None
    wait_for_creation: bool = True


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
        self.__default_device_for_app = DeviceConfig(
            device_id=self.__meta.get_app_name(),
            name=self.__meta.get_app_name(),
            model=self.__meta.get_app_name(),
            manufacturer=f"{self.__meta.get_module_name()}/{self.__meta.get_class_name()}",
            version="Domovoy",
        )

    def get_default_device_for_app(self) -> DeviceConfig:
        return self.__default_device_for_app

    def set_default_device_for_app(self, device_config: DeviceConfig) -> None:
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
            device_class="restart",
            entity_category="diagnostic",
            disabled_by_default=True,
        )

    async def __reload_callback(self) -> None:
        self._wrapper.logger.info("Restarting App from Servent Button")
        await self.__meta.restart_app()

    async def _create_entity(
        self,
        entity_config: EntityConfig,
        device_config: DeviceConfig | None,
        *,
        wait_for_creation: bool,
    ) -> None:
        device_config = device_config or self.__default_device_for_app

        if device_config.app_name is None:
            if not device_config.is_global:
                device_config.app_name = self.__meta.get_app_name()
            else:
                raise ServentInvalidConfigurationError(
                    "Device Config must include app_name if 'is_global' is set to true",
                )

        if device_config.is_global:
            entity_config.app_name = device_config.app_name
        elif entity_config.app_name is None:
            entity_config.app_name = self.__meta.get_app_name()

        if device_config.is_global:
            entity_config.servent_id = f"global-{device_config.app_name}-{entity_config.servent_id}"

        else:
            entity_config.servent_id = f"{entity_config.app_name}-{entity_config.servent_id}"

        entity_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(to_dict(entity_config))  # type: ignore
        device_config_dict: dict[str, Any] = strip_none_and_enums_from_containers(to_dict(device_config))  # type: ignore

        entity_config_dict["device_definition"] = device_config_dict

        await self.__hass.services.servents.create_entity(
            entities=[entity_config_dict],
        )

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

    def _breakout_creation_config(self, creation_config: ExtraConfig | None) -> tuple[DeviceConfig, bool]:
        device_config = creation_config.device_config if creation_config else None
        wait_for_creation = creation_config.wait_for_creation if creation_config else True
        device_config = device_config or self.__default_device_for_app

        return device_config, wait_for_creation

    async def create_sensor(
        self,
        servent_id: str,
        name: str,
        *,
        default_state: str | bool | float | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: SensorDeviceClass | None = None,
        unit_of_measurement: str | None = None,
        state_class: SensorStateClass | None = None,
        options: list[str] | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntSensor:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = SensorConfig(
            servent_id=servent_id,
            name=name,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
            unit_of_measurement=unit_of_measurement,
            state_class=state_class,
            options=options,
        )

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
        servent_id: str,
        name: str,
        entity_id: EntityID,
        *,
        lower: float | None = None,
        upper: float | None = None,
        hysteresis: float = 0.0,
        default_state: bool | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: BinarySensorDeviceClass | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntThresholdBinarySensor:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = ThresholdBinarySensorConfig(
            servent_id=servent_id,
            name=name,
            entity_id=str(entity_id),
            lower=lower,
            upper=upper,
            hysteresis=hysteresis,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
        )

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
        servent_id: str,
        name: str,
        *,
        default_state: bool | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: BinarySensorDeviceClass | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntBinarySensor:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = BinarySensorConfig(
            servent_id=servent_id,
            name=name,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
        )

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
        servent_id: str,
        name: str,
        mode: NumberMode,
        *,
        default_state: float | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: NumberDeviceClass | None = None,
        unit_of_measurement: str | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntNumber:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = NumberConfig(
            servent_id=servent_id,
            name=name,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
            unit_of_measurement=unit_of_measurement,
            mode=mode,
            min_value=min_value,
            max_value=max_value,
            step=step,
        )

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
        servent_id: str,
        name: str,
        options: list[str],
        *,
        default_state: str | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntSelect:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = SelectConfig(
            servent_id=servent_id,
            name=name,
            options=options,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
        )

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

    async def _create_button(
        self,
        servent_id: str,
        name: str,
        event: str,
        *,
        event_data: dict[str, Any] | None = None,
        default_state: str | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: ButtonDeviceClass | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntButton:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = ButtonConfig(
            servent_id=servent_id,
            name=name,
            event=event,
            event_data=event_data or {},
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
        )

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
        servent_id: str,
        name: str,
        *,
        default_state: bool | None = None,
        fixed_attributes: dict[str, str | bool | float] | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        app_name: str | None = None,
        device_class: SwitchDeviceClass | None = None,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntSwitch:
        device_config, wait_for_creation = self._breakout_creation_config(creation_config)

        entity_config = SwitchConfig(
            servent_id=servent_id,
            name=name,
            default_state=default_state,
            fixed_attributes=fixed_attributes or {},
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            app_name=app_name,
            device_class=device_class,
        )

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
        *,
        event_data: dict[str, Any] | None = None,
        device_class: ButtonDeviceClass | None = None,
        entity_category: EntityCategory | None = None,
        disabled_by_default: bool = False,
        creation_config: ExtraConfig | None = None,
    ) -> ServEntButton:
        final_event = f"{self.__meta.get_app_name()}.{event_name_to_fire}"

        self._wrapper.logger.trace(
            "Creating Button with final_event name `{final_event}`. Length: ``",
            final_event=final_event,
        )

        target_event = final_event
        target_event_data = event_data

        if len(final_event) > 50:
            self._wrapper.logger.trace(
                "Using Extended Button Press functionality for `{final_event}`",
                final_event=final_event,
            )
            target_event = self._SERVENT_EXTENDED_BUTTON_PRESS_EVENT
            target_event_data = {
                "true_event": final_event,
            }

        button = await self._create_button(
            servent_id=final_event,
            name=button_name,
            event=target_event,
            event_data=target_event_data or {},
            device_class=device_class,
            entity_category=entity_category,
            disabled_by_default=disabled_by_default,
            creation_config=creation_config,
        )

        if target_event == self._SERVENT_EXTENDED_BUTTON_PRESS_EVENT:
            self._wrapper.logger.trace(
                "Configuring Callback using Extended Button Press functionality for `{final_event}`",
                final_event=final_event,
            )

            async def extended_callback(
                data: dict[str, Any],
            ) -> None:
                self._wrapper.logger.trace(
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
            self._wrapper.logger.trace(
                "Adding simple button press listener for {target_event}",
                target_event=target_event,
            )
            self.__callbacks.listen_event(
                f"servent.{target_event}",
                callback,
            )

        return button
