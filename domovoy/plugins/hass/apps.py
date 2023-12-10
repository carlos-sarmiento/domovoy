from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domovoy.app import stop_domovoy
from domovoy.applications import AppBase, AppConfigBase, EmptyAppConfig
from domovoy.plugins.servents.enums import ButtonDeviceClass, EntityCategory

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
