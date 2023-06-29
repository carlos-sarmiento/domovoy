from dataclasses import dataclass
import os
from typing import Any
from pathlib import Path
from domovoy.app import stop_domovoy

from domovoy.applications import AppBase, AppConfigBase, EmptyAppConfig
from domovoy.plugins.servents.enums import ButtonDeviceClass, EntityCategory
from .synthetic import (
    generate_stub_file_for_synthetic_services,
)


@dataclass
class HassSyntheticServiceStubUpdaterConfig(AppConfigBase):
    stub_path: str
    dump_hass_services_json: bool = False


class HassSyntheticServiceStubUpdater(AppBase[HassSyntheticServiceStubUpdaterConfig]):
    async def initialize(self) -> None:
        self.callbacks.listen_event(
            "homeassistant_started",
            self.homeassistant_started_event_handler,
        )
        self.log.info("HassSyntheticServiceStubUpdater is initializing")
        await self.update_stubs()

    async def homeassistant_started_event_handler(
        self, event_name: str, event_data: dict[str, Any]
    ) -> None:
        self.log.info("Home Assistant Started")
        await self.update_stubs()

    async def update_stubs(self):
        self.log.info("Updating Home Assitant Services Stub File")
        Path(os.path.dirname(self.config.stub_path)).mkdir(parents=True, exist_ok=True)

        services_definitions = await self.hass.get_service_definitions()
        generate_stub_file_for_synthetic_services(
            services_definitions,
            self.config.stub_path,
            self.config.dump_hass_services_json,
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
        self, event_name: str, event_data: dict[str, Any]
    ) -> None:
        stop_domovoy()
