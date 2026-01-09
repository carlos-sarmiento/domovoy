import datetime
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from domovoy.core.configuration import get_main_config
from domovoy.plugins.hass.domains import get_typestr_for_domain
from domovoy.plugins.hass.parsing import encode_message
from domovoy.plugins.hass.types import HassValueStrict

if TYPE_CHECKING:
    from domovoy.plugins.hass import HassPlugin


class HassServiceCall(Protocol):
    async def __call__(self, **kwargs: HassValueStrict) -> dict[str, Any] | None: ...


class HassSyntheticServiceCall:
    __domain: str
    __hass: HassPlugin

    def __init__(self, hass_plugin: HassPlugin, domain: str) -> None:
        self.__domain = domain
        self.__hass = hass_plugin

    def __getattr__(self, service: str) -> HassServiceCall:
        async def synthetic_service_call(**kwargs: HassValueStrict) -> dict[str, Any] | None:
            full_name = f"{self.__domain}.{service}"
            service_definitions = await self.__hass._get_cached_service_definitions()  # noqa: SLF001

            if full_name not in service_definitions:
                service_definitions = await self.__hass._get_cached_service_definitions(reset=True)  # noqa: SLF001

            throw_on_error: bool = kwargs.pop("domovoy_throw_on_error", False)  # type: ignore

            if full_name in service_definitions and service_definitions[full_name].has_response:
                response: dict[str, Any] = await self.__hass.call_service(
                    full_name,
                    return_response=True,
                    throw_on_error=throw_on_error,
                    **kwargs,
                )  # type: ignore
                return response["response"]

            return await self.__hass.call_service(
                full_name,
                return_response=False,
                throw_on_error=throw_on_error,
                **kwargs,
            )

        return synthetic_service_call


class HassSyntheticDomainsServiceCalls:
    __hass: HassPlugin
    __defined_domains: dict[str, HassSyntheticServiceCall]

    def __init__(self, hass_pluging: HassPlugin) -> None:
        self.__hass = hass_pluging
        self.__defined_domains = {}

    def __getattr__(self, name: str) -> HassSyntheticServiceCall:
        if name not in self.__defined_domains:
            self.__defined_domains[name] = HassSyntheticServiceCall(
                hass_plugin=self.__hass,
                domain=name,
            )

        return self.__defined_domains[name]


def __generate_type_for_target(entity_details: list | dict) -> str:
    if isinstance(entity_details, list):
        entity_details = entity_details[0] if entity_details else {}

    elif not isinstance(entity_details, dict):
        entity_details = {}

    domains: list[str] = entity_details.get("domain")  # type: ignore

    final_type = "EntityID"

    if domains:
        final_type = " | ".join([get_typestr_for_domain(x) for x in domains])

    return f"{final_type} | Sequence[{final_type}]"


def __generate_type_for_entity_selector(selector_details: dict | None) -> str:
    internal_type = "EntityID"
    multiple = True

    if selector_details:
        multiple: bool = selector_details.get("multiple", False)
        domains = set()

        for x in selector_details.get("filter", []):
            if isinstance(x, dict):
                domain_list_or_str = x.get("domain")
                if isinstance(domain_list_or_str, str):
                    domains.add(get_typestr_for_domain(domain_list_or_str))
                elif isinstance(domain_list_or_str, list):
                    for d in domain_list_or_str:
                        domains.add(get_typestr_for_domain(d))

        if domains:
            internal_type = " | ".join(domains)

    typing = internal_type

    if multiple:
        typing += f" | Sequence[{internal_type}]"

    return typing


def generate_stub_file_for_synthetic_services(
    domains: dict[str, Any],
    destination: str,
    *,
    save_domains_as_json: bool = False,
) -> None:
    def __to_camel_case(snake_str: str) -> str:
        return "".join(x.capitalize() for x in snake_str.lower().split("_"))

    def __clean_function_name(name: str, domain: str) -> str:
        if name == "import":
            return f"import_{domain}"

        return re.sub(r"[^a-zA-Z0-9]+", "_", name)

    domain_to_class: dict[str, str] = {}

    if save_domains_as_json:
        with Path(f"{destination}.json").open("wb") as services_file:
            services_file.write(encode_message(domains))

    with Path(destination).open("w") as text_file:
        now = datetime.datetime.now(get_main_config().get_timezone())
        text_file.write(f"# Generated on {now.isoformat()}\n\n")
        text_file.write("# ruff: noqa\n\n")

        text_file.write("from __future__ import annotations\n")
        text_file.write("from typing import Any\n")
        text_file.write("from datetime import datetime\n")
        text_file.write("from collections.abc import Sequence\n\n")

        text_file.write("from domovoy.plugins.hass import HassPlugin\n")
        text_file.write("from domovoy.plugins.hass.types import EntityID\n")
        text_file.write("from domovoy.plugins.hass.domains import *\n\n")

        text_file.write("class HassSyntheticDomainsServiceCalls:\n")
        text_file.write(
            "    def __init__(self, hass_pluging: HassPlugin) -> None: ...\n\n",
        )

        for domain, _services in sorted(domains.items()):
            class_name = f"HassSyntheticService{__to_camel_case(domain)}Domain"
            domain_to_class[domain] = class_name
            text_file.write(f"    {domain}: {class_name}\n")

        text_file.write("\n\n")

        for domain, services in sorted(domains.items()):
            text_file.write(
                f"class HassSyntheticService{__to_camel_case(domain)}Domain:\n",
            )

            for service, details in sorted(services.items()):
                args = ""

                arguments: dict[str, str] = {}

                if "target" in details and "entity" in details["target"]:
                    arguments["entity_id"] = __generate_type_for_target(details["target"]["entity"])

                if "fields" in details:
                    for field, field_params in details["fields"].items():
                        typing = "Any"

                        if field == "entity_id":
                            field = "service_data_entity_id"  # noqa: PLW2901

                        if "selector" in field_params:
                            if "boolean" in field_params["selector"]:
                                typing += " | bool"
                            if "text" in field_params["selector"]:
                                typing += " | str"
                            if "number" in field_params["selector"]:
                                if field_params["selector"]["number"] and "step" in field_params["selector"]["number"]:
                                    step = field_params["selector"]["number"]["step"]
                                    if step == "any":
                                        typing += " | str | int | float"

                                    elif isinstance(step, int) or (isinstance(step, float) and float.is_integer(step)):
                                        typing += " | int"
                                    else:
                                        typing += " | float"
                                else:
                                    typing += " | int | float"

                            if "datetime" in field_params["selector"]:
                                typing += " | datetime"
                            if "entity" in field_params["selector"]:
                                typing += (
                                    f" | {__generate_type_for_entity_selector(field_params['selector']['entity'])}"
                                )

                            if "select" in field_params["selector"]:
                                typing += " | str"

                        elif field.endswith("_id"):
                            typing = "EntityID | Sequence[EntityID] | str | Sequence[str]"

                        if "required" not in field_params or not field_params["required"]:
                            typing += " | None = None"

                        arguments[field] = typing.replace("Any | None", "Any").replace(
                            "Any | ",
                            "",
                        )

                for arg, typing in sorted(arguments.items()):
                    if arg == "in":
                        arg = "in_"  # noqa: PLW2901
                    args += f"{arg}: {typing}, "

                if len(args) > 0:
                    args = "*, " + args

                if "response" not in details:
                    return_type = "None"
                else:
                    return_type = "dict[str, Any]"
                    if details["response"].get("optional", True):
                        return_type += " | None"

                text_file.write(
                    "    async def "
                    f"{__clean_function_name(service, domain)}(self, {args}**kwargs) -> {return_type}: ...\n",
                )

            text_file.write("\n\n")
