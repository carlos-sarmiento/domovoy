import datetime
from typing import Any, TypeVar

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
from servents.data_model.entity_types import EntityType

from domovoy.core.errors import DomovoyError
from domovoy.core.utils import parse_state
from domovoy.plugins.hass import HassPlugin
from domovoy.plugins.hass.core import EntityState
from domovoy.plugins.hass.domains import (
    BinarySensorEntity,
    ButtonEntity,
    NumberEntity,
    SelectEntity,
    SensorEntity,
    SwitchEntity,
)
from domovoy.plugins.hass.exceptions import HassApiInvalidValueError
from domovoy.plugins.hass.types import EntityID, HassData, HassValue, PrimitiveHassValue

from .exceptions import ServentMissingRegistrationError

T = TypeVar("T", bound=EntityID)


class ServEntEntity[T: EntityID]:
    def __init__(
        self,
        hass: HassPlugin,
        entity_type: EntityType,
        servent_id: str,
        config: EntityConfig,
        device_config: DeviceConfig,
        entity_id_type: type[T],
    ) -> None:
        self.name = "ServEntEntity"
        self.__hass = hass
        self.type = entity_type
        self.id = servent_id
        self.entity_config = config
        self.device_config = device_config
        self.entity_id_type = entity_id_type

    async def set_to(self, state: HassValue, attributes: dict[str, object] | None = None) -> None:
        if attributes is not None and not isinstance(attributes, dict):
            raise DomovoyError("Attributes is not a dict")

        await self.__hass.services.servents.update_state(
            servent_id=self.entity_config.servent_id,
            state=state,  # type: ignore
            attributes=attributes or {},  # type: ignore
        )

    def get_entity_id(self) -> T:
        entity_id = self.__hass.get_entity_id_by_attribute(
            "servent_id",
            self.entity_config.servent_id,
        )

        if entity_id:
            return self.entity_id_type(str(entity_id[0]))

        raise ServentMissingRegistrationError(
            "Servent Entity hasn't been registered in the system. Check if it has been disabled in HA",
        )

    def get_state(self) -> PrimitiveHassValue:
        return self.get_raw_state()

    def get_raw_state(self) -> PrimitiveHassValue:
        try:
            full_state = self.get_full_state()
            return full_state.state
        except ServentMissingRegistrationError:
            return "unknown"

    def get_state_attributes(self) -> HassData:
        full_state = self.get_full_state()
        return full_state.attributes

    def get_full_state(self) -> EntityState:
        entity_id: EntityID = self.get_entity_id()

        if entity_id:
            full_state = self.__hass.get_full_state(entity_id)

            if full_state is not None:
                return full_state

        raise ServentMissingRegistrationError(
            "The Servent Entity has not yet been registered in Home Assistant.",
        )


class ServEntSensor(ServEntEntity[SensorEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: SensorConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SENSOR, servent_id, config, device_config, SensorEntity)

    async def set_to(  # type: ignore
        self,
        state: float | str | datetime.datetime | None,
        attributes: dict | None = None,
    ) -> None:
        if isinstance(state, datetime.datetime):
            state = state.timestamp()

        return await super().set_to(state, attributes or {})

    def get_state(self) -> float | int | str | datetime.datetime:  # type: ignore
        state = super().get_state()

        if isinstance(state, str):
            state = parse_state(state)

        elif not isinstance(state, float | int | str | datetime.datetime):
            msg = f"State of type `{type(state)}` is not valid for a ServentSensor Entity"
            raise HassApiInvalidValueError(msg)

        return state


class ServEntThresholdBinarySensor(ServEntEntity[BinarySensorEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ThresholdBinarySensorConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(
            hass,
            EntityType.THRESHOLD_BINARY_SENSOR,
            servent_id,
            config,
            device_config,
            BinarySensorEntity,
        )

    async def set_to(self, _state: bool, _attributes: dict | None = None) -> None:  # type: ignore # noqa: FBT001
        raise NotImplementedError("Threshold sensors cannot have their state set")

    def get_state(self) -> bool | None:  # type: ignore
        state = super().get_state()
        if state == "on":
            return True

        if state == "off":
            return False

        return None


class ServEntBinarySensor(ServEntEntity[BinarySensorEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: BinarySensorConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(
            hass,
            EntityType.BINARY_SENSOR,
            servent_id,
            config,
            device_config,
            BinarySensorEntity,
        )

    async def set_on(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=True, attributes=attributes)

    async def set_off(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=False, attributes=attributes)

    async def set_to(self, state: bool, attributes: dict | None = None) -> None:  # type: ignore # noqa: FBT001
        return await super().set_to(state=state, attributes=attributes)

    async def get_state(self) -> bool | None:  # type: ignore
        state = super().get_state()
        if state == "on":
            return True

        if state == "off":
            return False

        return None


class ServEntSwitch(ServEntEntity[SwitchEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: SwitchConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SWITCH, servent_id, config, device_config, SwitchEntity)

    async def set_on(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=True, attributes=attributes)

    async def set_off(self, attributes: dict | None = None) -> None:
        return await super().set_to(state=False, attributes=attributes)

    async def set_to(self, state: bool, attributes: dict | None = None) -> None:  # type: ignore # noqa: FBT001
        return await super().set_to(state=state, attributes=attributes)

    def get_state(self) -> bool | None:  # type: ignore
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


class ServEntNumber(ServEntEntity[NumberEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: NumberConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.NUMBER, servent_id, config, device_config, NumberEntity)

    async def set_to(self, state: float, attributes: dict | None = None) -> None:  # type: ignore
        return await super().set_to(state, attributes)

    def get_state(self) -> float | int | None:  # type: ignore
        state = super().get_state()

        if isinstance(state, str):
            state = parse_state(state)

        if not isinstance(state, float | int):
            return None

        return state


class ServEntSelect(ServEntEntity[SelectEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: SelectConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.SELECT, servent_id, config, device_config, SelectEntity)

    async def set_to(  # type: ignore
        self,
        state: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        return await super().set_to(state, attributes)


class ServEntButton(ServEntEntity[ButtonEntity]):
    def __init__(
        self,
        hass: HassPlugin,
        servent_id: str,
        config: ButtonConfig,
        device_config: DeviceConfig,
    ) -> None:
        super().__init__(hass, EntityType.BUTTON, servent_id, config, device_config, ButtonEntity)
