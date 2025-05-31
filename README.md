# Domovoy

Domovoy is a powerful application framework designed to drive automations for Home Assistant using Python. If you prefer writing your automations in pure Python rather than YAML, Node Red, or n8n, providing a more flexible and developer-friendly approach to home automation.

Inspired by AppDaemon, Domovoy is a completely new codebase built from the ground up with Python's async/await throughout, resulting in significantly improved resource efficiency and performance.

## Key Features

- **ServEnts Integration**: When paired with ServEnts (a Home Assistant custom component), Domovoy can create devices and entities directly from Python code, eliminating the need for manually configuring helpers in HA.

- **Type Safety**: Full support for Python typing, including typechecking for entities and services on the Home Assistant instance it connects to, catching errors before they happen.

- **Python-First Approach**: Write all your automations in Python with full IDE support, and the ability to leverage Python's rich ecosystem of libraries.

- **High Performance**: Leverages Python's async/await for efficient, non-blocking operations that make the most of your system resources.

## How to run

We prefer to use docker to execut

```bash
uv sync
python domovoy/cli.py --config config.yml
```

Missing Docs

## Basic App Template with Config

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase

# If the App uses a per-instance configuration
@dataclass
class AppNameConfig(AppConfigBase):
    ...


class AppName(AppBase[AppNameConfig]):
    async def initialize(self):
        ...
```

## Basic App Template without Config

```python
from domovoy.applications import AppBase, EmptyAppConfig

# If the App takes no configuration
class AppName(AppBase[EmptyAppConfig]):
    async def initialize(self):
        ...
```

## How to register an app

```python
from domovoy.applications.registration import register_app


register_app(
    app_class=AppName,
    app_name="app_name",
    config=AppNameConfig(

    ),
)
```

## Register multiple instances of the same AppType

```python
from domovoy.applications.registration import register_app_multiple


apps_to_register = {
    "some_app_name_a": SomeConfig(
        ...
    ),
    "some_app_name_b": SomeConfig(
        ...
    ),
    "some_app_name_c": SomeConfig(
        ...
    ),
    ...
}


register_app_multiple(
    app_class=AppName,
    configs=apps_to_register,
)
```
