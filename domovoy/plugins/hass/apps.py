from domovoy.app import stop_domovoy
from domovoy.applications import AppBase, EmptyAppConfig


class HassTerminateDomovoy(AppBase[EmptyAppConfig]):
    async def initialize(self) -> None:
        await self.servents.listen_button_press(
            self.homeassistant_started_event_handler,
            button_name="Terminate Domovoy",
            event_name_to_fire="dangerous_terminate_domovoy_signal",
            device_class="restart",
            entity_category="diagnostic",
        )

    async def homeassistant_started_event_handler(
        self,
    ) -> None:
        stop_domovoy()
