import datetime
from io import StringIO
from pathlib import Path

from domovoy.core.configuration import get_main_config
from domovoy.plugins.hass.domains import get_type_for_domain, get_type_instance_for_entity_id, get_typestr_for_domain
from domovoy.plugins.hass.types import EntityID

SensorInfo = dict[str, tuple[str, list[str] | None]]

SelectInfo = dict[str, list[str]]


class HassSyntheticDomain:
    __domain: str

    def __init__(self, *, domain: str) -> None:
        self.__domain = domain

    def __getattr__(self, entity: str) -> EntityID:
        entity = entity.removeprefix("_")
        entity_id = f"{self.__domain}.{entity}"

        return get_type_for_domain(self.__domain)(entity_id)


class HassSyntheticDomains:
    __defined_domains: dict[str, HassSyntheticDomain]

    def __init__(self) -> None:
        self.__defined_domains = {}

    def __getattr__(self, name: str) -> HassSyntheticDomain:
        if name not in self.__defined_domains:
            self.__defined_domains[name] = HassSyntheticDomain(
                domain=name,
            )

        return self.__defined_domains[name]

    def __call__(self, entity_id: str) -> EntityID:
        return get_type_instance_for_entity_id(entity_id)


entities = HassSyntheticDomains()


def __to_camel_case(snake_str: str) -> str:
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def generate_stub_file_for_synthetic_entities(
    domains: dict[str, set[str]],
    destination: str,
    sensor_info: SensorInfo,
    select_info: SelectInfo,
) -> None:
    with Path(destination).open("w") as text_file:
        now = datetime.datetime.now(get_main_config().get_timezone())
        text_file.write(f"# Generated on {now.isoformat()}\n\n")
        text_file.write("# ruff: noqa\n\n")

        text_file.write("import datetime\n\n")
        text_file.write("from typing import Literal\n\n")
        text_file.write("from domovoy.plugins.hass.types import EntityID\n")
        text_file.write("from domovoy.plugins.hass.domains import *\n\n")

        text_file.write(__build_class_hierarchy(domains, sensor_info, select_info))

        text_file.write(
            "entities: HassSyntheticDomains = ...\n\n",
        )


def __build_class_hierarchy(domains: dict[str, set[str]], sensor_info: SensorInfo, select_info: SelectInfo) -> str:
    return_type = "EntityID"

    text_file = StringIO()

    text_file.write("class HassSyntheticDomains:\n")
    text_file.write(
        "    def __init__(self) -> None: ...\n\n",
    )
    text_file.write(
        f"    def __call__(self, entity_id : str) -> {return_type}: ...\n\n",
    )
    domain_to_class: dict[str, str] = {}

    for domain, _entities in sorted(domains.items()):
        class_name = f"HassSynthetic{__to_camel_case(domain)}Domain"
        domain_to_class[domain] = class_name
        text_file.write(f"    {domain}: {class_name}\n")

    text_file.write("\n\n")

    for domain, entities in sorted(domains.items()):
        text_file.write(
            f"class HassSynthetic{__to_camel_case(domain)}Domain:\n",
        )

        return_type_for_domain = get_typestr_for_domain(domain)

        for entity_base in sorted(entities):
            field_name = entity_base
            if field_name[0] in "0123456789":
                field_name = "_" + entity_base

            if domain == "sensor":
                device_class, options = sensor_info.get(entity_base, (None, None))
                return_type_for_domain = get_typestr_for_sensor_domain(device_class, options)

            if domain == "select":
                options = select_info.get(entity_base, [])
                return_type_for_domain = get_typestr_for_select_domain(options)

            text_file.write(
                f"    {field_name} : {return_type_for_domain} = ...\n",
            )

        text_file.write("\n\n")

    return text_file.getvalue()


def get_typestr_for_sensor_domain(device_class: str | None, options: list[str] | None) -> str:
    sensor_type = "float | int"

    if device_class is None or device_class == "None":
        sensor_type = "str"

    if device_class == "enum":
        if options:
            values = ", ".join(f'"{option}"' for option in options)
            sensor_type = f"Literal[{values}]"
        else:
            sensor_type = "str"

    if device_class == "date":
        sensor_type = "datetime.date"

    if device_class == "timestamp":
        sensor_type = "datetime.datetime"

    return f"SensorEntity[{sensor_type}]"


def get_typestr_for_select_domain(options: list[str] | None) -> str:
    if options:
        values = ", ".join(f'"{option}"' for option in options)
        sensor_type = f"Literal[{values}]"
    else:
        sensor_type = "str"

    return f"SelectEntity[{sensor_type}]"
