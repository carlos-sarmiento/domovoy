import asyncio

from aiohttp import web
from strawberry.aiohttp.views import GraphQLView

from domovoy.core.logging import get_logger
from domovoy.core.services.service import DomovoyService, DomovoyServiceResources

from .schema import build_schema

_logcore = get_logger(__name__)


class DomovoyWebApi(DomovoyService):
    __resources: DomovoyServiceResources

    def __init__(
        self,
        resources: DomovoyServiceResources,
    ) -> None:
        super().__init__(resources)
        self.__resources = resources

    def start(self) -> None:
        _logcore.info("Configuring webapi")
        routes = web.RouteTableDef()

        schema = build_schema(self.__resources.get_all_apps_by_name)

        app = web.Application()
        app.add_routes([web.route("*", "/graphql", GraphQLView(schema=schema))])
        app.add_routes(routes)

        # set up the web server
        self.__runner = web.AppRunner(app)

        async def app_run() -> None:
            address = self.__resources.config["address"]
            port = self.__resources.config["port"]

            _logcore.info(
                "Starting webapi on address: {address}:{port}",
                address=address,
                port=port,
            )
            await self.__runner.setup()
            await web.TCPSite(
                self.__runner,
                address,
                port,
            ).start()

        asyncio.get_event_loop().create_task(app_run(), name="webapi")

    async def stop(self) -> None:
        _logcore.info("Stopping webapi")

        await self.__runner.cleanup()
