import datetime
from typing import Any

from domovoy.core.errors import DomovoyError
from domovoy.core.utils import parse_state
from domovoy.plugins.hass import HassPlugin
from domovoy.plugins.hass.core import EntityState
from domovoy.plugins.hass.types import HassApiDataDict, HassApiValue

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
from .enums import EntityType
from .exceptions import ServentMissingRegistrationError


class ServEntEntity:
    def __init__(
        self,
        hass: HassPlugin,
        entity_type: EntityType,
        servent_id: str,
        config: ServEntEntityConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        self.name = "ServEntEntity"
        self.__hass = hass
        self.type = entity_type
        self.id = servent_id
        self.entity_config = config
        self.device_config = device_config

    async def set_to(self, state: HassApiValue, attributes: dict[str, object] | None = None) -> None:
        if attributes is not None and not isinstance(attributes, dict):
            raise DomovoyError("Attributes is not a dict")

        await self.__hass.services.servents.update_state(
            servent_id=self.entity_config.servent_id,
            state=state,
            attributes=attributes or {},
        )

    def get_entity_id(self) -> str:
        entity_id = self.__hass.get_entity_id_by_attribute(
            "servent_id",
            self.entity_config.servent_id,
        )

        if entity_id:
            return entity_id[0]

        raise ServentMissingRegistrationError(
            "Servent Entity hasn't been registered in the system.",
        )

    def get_state(self) -> str:
        return self.get_raw_state()

    def get_raw_state(self) -> str:
        try:
            full_state = self.get_full_state()
            return full_state.state
        except ServentMissingRegistrationError:
            return "unknown"

    def get_state_attributes(self) -> HassApiDataDict:
        full_state = self.get_full_state()
        return full_state.attributes

    def get_full_state(self) -> EntityState:
        entity_id = self.get_entity_id()

        if entity_id:
            full_state = self.__hass.get_full_state(entity_id)

            if full_state is not None:
                return full_state

        raise ServentMissingRegistrationError(
            "The Servent Entity has not yet been registered in Home Assistant.",
        )


class ServEntSensor(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntSensorConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SENSOR, servent_id, config, device_config)

    async def set_to(
        self,
        state: float | str | datetime.datetime | None,
        attributes: dict | None = None,
    ) -> None:
        if state is None:
            state = "unknown"
        return await super().set_to(state, attributes or {})

    def get_state(self) -> float | int | str | datetime.datetime:
        return parse_state(super().get_state())


class ServEntThresholdBinarySensor(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntThresholdBinarySensorConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(
            hass,
            EntityType.THRESHOLD_BINARY_SENSOR,
            servent_id,
            config,
            device_config,
        )

    async def set_to(self, _state: bool, _attributes: dict | None = None) -> None:  # noqa: FBT001
        raise NotImplementedError("Threshold sensors cannot have their state set")

    def get_state(self) -> bool | None:
        state = super().get_state()
        if state == "on":
            return True

        if state == "off":
            return False

        return None


class ServEntBinarySensor(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntBinarySensorConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(
            hass,
            EntityType.BINARY_SENSOR,
            servent_id,
            config,
            device_config,
        )

    async def set_on(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=True, attributes=attributes)

    async def set_off(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=False, attributes=attributes)

    async def set_to(self, state: bool, attributes: dict | None = None) -> None:  # noqa: FBT001
        return await super().set_to(state=state, attributes=attributes)

    async def get_state(self) -> bool | None:
        state = super().get_state()
        if state == "on":
            return True

        if state == "off":
            return False

        return None


class ServEntSwitch(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntSwitchConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SWITCH, servent_id, config, device_config)

    async def set_on(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=True, attributes=attributes)

    async def set_off(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=False, attributes=attributes)

    async def set_to(self, state: bool, attributes: dict | None = None) -> None:  # noqa: FBT001
        return await super().set_to(state=state, attributes=attributes)

    def get_state(self) -> bool | None:
        state = super().get_state()
        if state == "on":
            return True
        if state == "off":
            return False

        return None

    def is_on(self) -> bool:
        return self.get_state() is True

    def is_off(self) -> bool:
        return self.get_state() is False


class ServEntNumber(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntNumberConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.NUMBER, servent_id, config, device_config)

    async def set_to(self, state: float, attributes: dict | None = None) -> None:
        return await super().set_to(state, attributes)

    def get_state(self) -> float | int | None:
        state = parse_state(super().get_state())

        if isinstance(state, str):
            return None

        return state


class ServEntSelect(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntSelectConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SELECT, servent_id, config, device_config)

    async def set_to(
        self,
        state: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        return await super().set_to(state, attributes)


class ServEntButton(ServEntEntity):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ServEntButtonConfig,
        device_config: ServEntDeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.BUTTON, servent_id, config, device_config)
