import datetime
from io import StringIO
from pathlib import Path

from domovoy.core.configuration import get_main_config
from domovoy.plugins.hass.domains import get_type_for_domain, get_typestr_for_domain
from domovoy.plugins.hass.types import EntityID


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
        return get_type_for_domain(EntityID(entity_id).get_platform())(entity_id)


entities = HassSyntheticDomains()


def __to_camel_case(snake_str: str) -> str:
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def generate_stub_file_for_synthetic_entities(
    domains: dict[str, set[str]],
    destination: str,
) -> None:
    with Path(destination).open("w") as text_file:
        now = datetime.datetime.now(get_main_config().get_timezone())
        text_file.write(f"# Generated on {now.isoformat()}\n\n")
        text_file.write("# ruff: noqa\n\n")

        text_file.write("from domovoy.plugins.hass.types import EntityID\n")
        text_file.write("from domovoy.plugins.hass.domains import *\n\n")

        text_file.write(__build_class_hierarchy(domains))

        text_file.write(
            "entities: HassSyntheticDomains = ...\n\n",
        )


def __build_class_hierarchy(
    domains: dict[str, set[str]],
) -> str:
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

            text_file.write(
                f"    {field_name} : {return_type_for_domain} = ...\n",
            )

        text_file.write("\n\n")

    return text_file.getvalue()
