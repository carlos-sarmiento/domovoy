import subprocess
import sys
from pathlib import Path

from domovoy.core.configuration import get_main_config
from domovoy.core.logging import get_logger

_logcore = get_logger(__name__)


def install_requirements() -> None:
    main_config = get_main_config()

    if not main_config.install_pip_dependencies:
        _logcore.critical("Installing Packages from Apps Folder is disabled on Config")
        return

    _logcore.info("Installing Packages from Apps Folder")
    app_folder = get_main_config().app_path
    files = Path(app_folder).glob("**/requirements*.txt")

    if not files:
        _logcore.info(
            "No requirements.txt files discovered inside {app_folder}",
            app_folder=app_folder,
        )
        return

    for file in files:
        _logcore.info("Processing package dependencies from: {file}", file=file)
        result = subprocess.run(
            ["uv", "pip", "install", "--system", "-r", str(file)],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            _logcore.info(f"{file} -- stdout:\n" + result.stdout + "\n" + result.stderr)

        if result.returncode != 0:
            _logcore.error(f"{file} -- stdout:\n" + result.stdout + "\n" + result.stderr)
