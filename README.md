# Domovoy

## How to run

```bash
poetry install
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
