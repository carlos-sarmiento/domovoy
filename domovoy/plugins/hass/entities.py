import datetime
from pathlib import Path

from domovoy.core.configuration import get_main_config


class HassSyntheticPlatformEntities:
    __platform: str

    def __init__(self, platform: str) -> None:
        self.__platform = platform

    def __getattr__(self, entity: str) -> str:
        entity = entity.removeprefix("_")
        return f"{self.__platform}.{entity}"


class HassSyntheticPlatforms:
    __defined_domains: dict[str, HassSyntheticPlatformEntities]

    def __init__(self) -> None:
        self.__defined_domains = {}

    def __getattr__(self, name: str) -> HassSyntheticPlatformEntities:
        if name not in self.__defined_domains:
            self.__defined_domains[name] = HassSyntheticPlatformEntities(
                platform=name,
            )

        return self.__defined_domains[name]


entities = HassSyntheticPlatforms()


def generate_stub_file_for_synthetic_entities(
    platforms: dict[str, set[str]],
    destination: str,
) -> None:
    def __to_camel_case(snake_str: str) -> str:
        return "".join(x.capitalize() for x in snake_str.lower().split("_"))

    with Path(destination).open("w") as text_file:
        now = datetime.datetime.now(get_main_config().get_timezone())
        text_file.write(f"# Generated on {now.isoformat()}\n\n")
        # text_file.write("# ruff: noqa\n\n")

        text_file.write("class HassSyntheticPlatforms:\n")
        text_file.write(
            "    def __init__(self) -> None: ...\n\n",
        )

        text_file.write(
            "entities: HassSyntheticPlatforms = ...\n\n",
        )
        platform_to_class: dict[str, str] = {}

        for platform, _entities in sorted(platforms.items()):
            class_name = f"HassSynthetic{__to_camel_case(platform)}Platform"
            platform_to_class[platform] = class_name
            text_file.write(f"    {platform}: {class_name}\n")

        text_file.write("\n\n")

        for platform, entities in sorted(platforms.items()):
            text_file.write(
                f"class HassSynthetic{__to_camel_case(platform)}Platform:\n",
            )

            for entity_base in sorted(entities):
                field_name = entity_base
                if field_name[0] in "0123456789":
                    field_name = "_" + entity_base

                text_file.write(
                    f"    {field_name} : str = ...\n",
                )

            text_file.write("\n\n")
