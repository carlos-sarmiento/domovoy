import glob
import subprocess
import sys

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
    path = f"{app_folder}/**/requirements.txt"
    files = glob.glob(path, recursive=True)

    if not files:
        _logcore.info(
            "No requirements.txt files discovered inside {app_folder}",
            app_folder=app_folder,
        )
        return

    for file in files:
        _logcore.info("Processing package dependencies from: {file}", file=file)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", file],
            capture_output=True,
            text=True,
        )

        if result.stdout:
            _logcore.info(f"{file}\n" + result.stdout)

        if result.returncode != 0 or result.stderr:
            _logcore.error(f"{file}\n" + result.stderr)
