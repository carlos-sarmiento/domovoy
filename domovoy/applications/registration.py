from __future__ import annotations

import inspect
from pathlib import Path
from typing import Literal, TypeVar

from domovoy.applications import AppBase, AppConfigBase
from domovoy.core.configuration import get_main_config
from domovoy.core.engine.active_engine import get_active_engine
from domovoy.core.logging import get_logger
from domovoy.core.task_utils import run_and_forget_task

_logcore = get_logger(__name__)

TConfig = TypeVar("TConfig", bound=AppConfigBase)


def __actual_registration[TConfig: AppConfigBase](
    *,
    app_class: type[AppBase[TConfig]],
    app_name: str,
    module_name: str,
    app_file_path: str,
    config: AppConfigBase | None,
    logging_config_name: str | None,
    ignore: Literal[True, False],
) -> None:
    if ignore:
        get_logger(module_name).warning(
            "App Registration for {app_name} in module: {path} is set to be ignored. App wasn't registered",
            app_name=app_name,
            path=app_file_path,
        )
        return

    run_and_forget_task(
        get_active_engine().register_app(
            app_class=app_class,
            app_name=app_name,
            app_path=app_file_path,
            config=config,
            logging_config_name=logging_config_name,
        ),
        name=f"app_{app_name}_registration",
    )


def register_app(
    *,
    app_class: type[AppBase[TConfig]],
    app_name: str,
    config: TConfig | None = None,
    logging_config_name: str | None = None,
    ignore: bool = False,
) -> None:
    """Register an app in the current running instance of the Domovy App Engine.

    Args:
    ----
        app_class (type[AppBase[TConfig]]): The class defining the App to instantiate
        app_name (str): The name/id for the app. Needs to be unique across all apps.
        config (TConfig | None, optional): An instance of the configuration for the App. Will throw if app takes a
          config and one is not provided. Defaults to None.
        logging_config_name (str | None, optional): The name of the logging config to use for this app. If not
          explicitly defined in config, a new config using this name will be created, using the _app_default logging
          config. Defaults to None.
        ignore (bool, optional): Whether this registration should be ignored and not actually ran into the system. Can
          be used to avoid an instance running without removing or commenting the code out. Defaults to False.

    """
    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])

    if mod is None:
        _logcore.error(
            "Error when trying to retrieve the module which called register_app for app {app_name}."
            " App wasn't registered",
            app_name=app_name,
        )
        return

    app_file_path = mod.__file__ or ""

    if not app_file_path.endswith(f"{get_main_config().app_suffix}.py"):
        get_logger(mod.__name__).error(
            "Attempting to register an app from a regular python file {path}."
            " Apps should be registered only in files that end in {suffix}.py",
            path=app_file_path,
            suffix=get_main_config().app_suffix,
        )
        return

    if logging_config_name is None:
        logging_config_name = Path(app_file_path).name.removesuffix(f"{get_main_config().app_suffix}.py")

    __actual_registration(
        app_class=app_class,
        app_name=app_name,
        module_name=mod.__name__,
        app_file_path=app_file_path,
        config=config,
        logging_config_name=logging_config_name,
        ignore=ignore,
    )


def register_app_multiple(
    *,
    app_class: type[AppBase[TConfig]],
    configs: dict[str, TConfig],
    logging_config_name: str | None = None,
    ignore: Literal[True, False] = False,
) -> None:
    """Register a group of apps in the current running instance of the Domovy App Engine, each one using its own config.

    Args:
    ----
        app_class (type[AppBase[TConfig]]): The class defining the App to instantiate
        configs (dict[str, TConfig]): Dictionary in which keys are the names of each app instance. The value of each
          key is an instance of the configuration for the App. Will throw if app takes a config and one is not provided
        logging_config_name (str | None, optional): The name of the logging config to use for this app. If not
          explicitly defined in config, a new config using this name will be created, using the _app_default logging
          config. Defaults to None.
        ignore (bool, optional): Whether this registration should be ignored and not actually ran into the system. Can
          be used to avoid an instance running without removing or commenting the code out. Defaults to False.

    """
    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])

    if mod is None:
        _logcore.error(
            "Error when trying to retrieve the module which called register_app for apps {app_names}."
            " Apps weren't registered",
            app_name=configs.keys(),
        )
        return

    app_file_path = mod.__file__ or ""

    if not app_file_path.endswith(f"{get_main_config().app_suffix}.py"):
        get_logger(mod.__name__).error(
            "Attempting to register apps from a regular python file {path}."
            " Apps should be registered only in files that end in {suffix}.py",
            path=app_file_path,
            suffix=get_main_config().app_suffix,
        )
        return

    for app_name, config in configs.items():
        __actual_registration(
            app_class=app_class,
            app_name=app_name,
            module_name=mod.__name__,
            app_file_path=app_file_path,
            config=config,
            logging_config_name=logging_config_name,
            ignore=ignore,
        )
