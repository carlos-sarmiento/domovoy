from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from domovoy.app import stop_domovoy
from domovoy.applications import AppBase, AppConfigBase, EmptyAppConfig
from domovoy.applications.types import Interval
from domovoy.plugins.hass.domains import get_type_instance_for_entity_id
from domovoy.plugins.hass.types import EntityID
from domovoy.plugins.servents.enums import ButtonDeviceClass, EntityCategory

from .entities import generate_stub_file_for_synthetic_entities  # type: ignore
from .synthetic import (
    generate_stub_file_for_synthetic_services,  # type: ignore
)


@dataclass
class HassSyntheticServiceStubUpdaterConfig(AppConfigBase):
    stub_path: str
    dump_hass_services_json: bool = False


class HassSyntheticServiceStubUpdater(AppBase[HassSyntheticServiceStubUpdaterConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_event_extended(
            "homeassistant_started",
            self.homeassistant_started_event_handler,
        )
        self.log.info("HassSyntheticServiceStubUpdater is initializing")
        await self.update_stubs()

    async def homeassistant_started_event_handler(
        self,
        _event_name: str,
        _event_data: dict[str, Any],
    ) -> None:
        self.log.info("Home Assistant Started")
        await self.update_stubs()

    async def update_stubs(self) -> None:
        self.log.info("Updating Home Assitant Services Stub File")
        Path(self.config.stub_path).parent.mkdir(parents=True, exist_ok=True)

        services_definitions = await self.hass.get_service_definitions()
        generate_stub_file_for_synthetic_services(
            services_definitions,
            self.config.stub_path,
            save_domains_as_json=self.config.dump_hass_services_json,
        )


@dataclass
class HassSyntheticEntitiesStubUpdaterConfig(AppConfigBase):
    stub_path: str
    update_frequency: Interval = field(default_factory=lambda: Interval(seconds=5))


class HassSyntheticEntitiesStubUpdater(AppBase[HassSyntheticEntitiesStubUpdaterConfig]):
    __registered_entities: frozenset[EntityID] = frozenset()

    async def initialize(self) -> None:
        self.__registered_entities: frozenset[EntityID] = frozenset()
        self.log.info("HassSyntheticEntitiesStubUpdater is initializing")
        self.callbacks.run_every(self.config.update_frequency, self.update_stubs, "now")

    async def update_stubs(self) -> None:
        entity_ids = self.hass.get_all_entity_ids()

        if entity_ids == self.__registered_entities:
            self.log.trace("No updates to registered entities")
            return

        self.log.info("Updating Home Assitant Entities Stub File")
        Path(self.config.stub_path).parent.mkdir(parents=True, exist_ok=True)

        domains: dict[str, set[str]] = {}

        for entity_id in entity_ids:
            if isinstance(entity_id, str):
                self.log.warning(
                    "Detected an string in a list that should only contain EntityIDs: '{entity_id}'",
                    entity_id=entity_id,
                )
                entity_id = get_type_instance_for_entity_id(entity_id)  # noqa: PLW2901

            domain = entity_id.get_domain()
            entity = entity_id.get_entity_name()

            if domain not in domains:
                domains[domain] = set()

            domains[domain].add(entity)

        self.__registered_entities = entity_ids

        generate_stub_file_for_synthetic_entities(
            domains,
            self.config.stub_path,
        )


class HassTerminateDomovoy(AppBase[EmptyAppConfig]):
    async def initialize(self) -> None:
        await self.servents.listen_button_press(
            self.homeassistant_started_event_handler,
            button_name="Terminate Domovoy",
            event_name_to_fire="dangerous_terminate_domovoy_signal",
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

    async def homeassistant_started_event_handler(
        self,
    ) -> None:
        stop_domovoy()
