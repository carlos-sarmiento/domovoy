import datetime
from io import StringIO
from pathlib import Path
from typing import Literal

from domovoy.core.configuration import get_main_config
from domovoy.plugins.hass.types import EntityID


class HassSyntheticPlatformEntities:
    __platform: str

    def __init__(self, *, platform: str, return_entity_cls: bool) -> None:
        self.__platform = platform
        self.__return_entity_cls = return_entity_cls

    def __getattr__(self, entity: str) -> EntityID | str:
        entity = entity.removeprefix("_")
        entity_id = f"{self.__platform}.{entity}"

        if self.__return_entity_cls:
            return EntityID(entity_id)

        return entity_id


class HassSyntheticPlatforms:
    __defined_domains: dict[str, HassSyntheticPlatformEntities]

    def __init__(self, *, return_entity_cls: bool) -> None:
        self.__defined_domains = {}
        self.__return_entity_cls = return_entity_cls

    def __getattr__(self, name: str) -> HassSyntheticPlatformEntities:
        if name not in self.__defined_domains:
            self.__defined_domains[name] = HassSyntheticPlatformEntities(
                platform=name,
                return_entity_cls=self.__return_entity_cls,
            )

        return self.__defined_domains[name]

    def __call__(self, entity_id: str) -> EntityID | str:
        if self.__return_entity_cls:
            return EntityID(entity_id)

        return entity_id


entities = HassSyntheticPlatforms(return_entity_cls=True)


def __to_camel_case(snake_str: str) -> str:
    return "".join(x.capitalize() for x in snake_str.lower().split("_"))


def generate_stub_file_for_synthetic_entities(
    platforms: dict[str, set[str]],
    destination: str,
) -> None:
    with Path(destination).open("w") as text_file:
        now = datetime.datetime.now(get_main_config().get_timezone())
        text_file.write(f"# Generated on {now.isoformat()}\n\n")
        text_file.write("# ruff: noqa\n\n")

        text_file.write("from domovoy.plugins.hass.types import EntityID\n\n")

        text_file.write(__build_class_hierarchy(platforms, "Entity", "EntityID"))

        text_file.write(
            "entities: HassSyntheticPlatformsEntity = ...\n\n",
        )


def __build_class_hierarchy(
    platforms: dict[str, set[str]],
    postfix: str,
    return_type: Literal["EntityID", "str"],
) -> str:
    text_file = StringIO()

    postfix = postfix.capitalize()

    text_file.write(f"class HassSyntheticPlatforms{postfix}:\n")
    text_file.write(
        "    def __init__(self) -> None: ...\n\n",
    )
    text_file.write(
        f"    def __call__(self, entity_id : str) -> {return_type}: ...\n\n",
    )
    platform_to_class: dict[str, str] = {}

    for platform, _entities in sorted(platforms.items()):
        class_name = f"HassSynthetic{__to_camel_case(platform)}Platform{postfix}"
        platform_to_class[platform] = class_name
        text_file.write(f"    {platform}: {class_name}\n")

    text_file.write("\n\n")

    for platform, entities in sorted(platforms.items()):
        text_file.write(
            f"class HassSynthetic{__to_camel_case(platform)}Platform{postfix}:\n",
        )

        for entity_base in sorted(entities):
            field_name = entity_base
            if field_name[0] in "0123456789":
                field_name = "_" + entity_base

            text_file.write(
                f"    {field_name} : {return_type} = ...\n",
            )

        text_file.write("\n\n")

    return text_file.getvalue()
