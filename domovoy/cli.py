from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from domovoy.core.configuration import load_main_config_from_yaml

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        prog="Domovoy",
        description="Powerful asyncio automation platform.",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=argparse.FileType("r"),
        help="Configuration file for Domovoy",
        default="config.yml",
    )
    parser.add_argument(
        "--dont-wait-on-all-tasks",
        dest="wait_on_all_tasks",
        help="When stopping Domovoy, do not wait for all tasks to finish before terminating the main process",
        action="store_false",
    )

    args = parser.parse_args()
    config = args.config.read()

    load_main_config_from_yaml(config, str(Path(args.config.name).resolve()))

    from domovoy.app import start

    logging.getLogger("asyncio").setLevel(logging.DEBUG)

    asyncio.run(
        start(wait_for_all_tasks_before_exit=args.wait_on_all_tasks),
    )
