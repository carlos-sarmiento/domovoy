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

    in_venv = __in_venv()
    _logcore.info("Running inside venv?: {result}", result=in_venv)

    __install_from_pyproject()

    __install_from_requirements_files()


def __install_from_requirements_files() -> None:
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

        if __in_venv():
            command = ["uv", "pip", "install", "-r", str(file)]
        else:
            command = ["uv", "pip", "install", "--system", "-r", str(file)]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            _logcore.info(f"{file} -- stdout:\n" + result.stdout + "\n" + result.stderr)

        if result.returncode != 0:
            _logcore.error(f"{file} -- stdout:\n" + result.stdout + "\n" + result.stderr)


def __install_from_pyproject() -> None:
    pyproject_file = Path("pyproject.toml")

    if not pyproject_file.exists():
        _logcore.info(
            "No pyproject.toml found in {path}, skipping uv sync",
            path=pyproject_file.parent.absolute(),
        )
        return

    _logcore.info("Found pyproject.toml, running uv sync --no-dev")

    if __in_venv():
        command = ["uv", "pip", "install", "-r", str(pyproject_file)]
    else:
        command = ["uv", "pip", "install", "--system", "-r", str(pyproject_file)]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        _logcore.info("uv pip install completed successfully:\n" + result.stdout + "\n" + result.stderr)
    else:
        _logcore.error("uv pip installfailed:\n" + result.stdout + "\n" + result.stderr)


def __in_venv() -> bool:
    return sys.prefix != sys.base_prefix
