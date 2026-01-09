# Getting Started

This guide will help you get Domovoy up and running with Home Assistant.

## Prerequisites

- **Python 3.14.2+**: Domovoy requires Python 3.14.2 or later
- **Home Assistant**: A running Home Assistant instance with WebSocket API access
- **Long-Lived Access Token**: Generate one from your Home Assistant profile page
- **ServEnts (Optional)**: The [ServEnts](https://github.com/carlos-sarmiento/servents) custom component for creating entities from Python

## Installation

## Quickest Start

The fastest way to get started is with the [Domovoy Starter Template](https://github.com/carlos-sarmiento/domovoy-starter). This prebuilt template has most of the pieces already in place—just update the config file with your Home Assistant details and run the included docker command.

## Quick Start with Docker

The recommended way to run Domovoy is using Docker.

### 1. Create your configuration directory

```bash
mkdir -p ~/domovoy/apps
```

### 2. Create a configuration file

Create `~/domovoy/config.yml`:

```yaml
app_suffix: _apps
hass_access_token: YOUR_LONG_LIVED_ACCESS_TOKEN
hass_url: ws://homeassistant.local:8123/api/websocket
app_path: /config/apps
timezone: America/Chicago
install_pip_dependencies: true
```

Replace:

- `YOUR_LONG_LIVED_ACCESS_TOKEN` with a [Home Assistant long-lived access token](https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token)
- `hass_url` with your Home Assistant WebSocket URL
- `timezone` with your timezone

### 3. Install ServEnts Integration (Optional)

If you want to create Home Assistant entities directly from your Python code, install the [ServEnts custom component](https://github.com/carlos-sarmiento/servents) in Home Assistant. This allows Domovoy to dynamically create sensors, switches, buttons, and other entities.

### 4. Run with Docker

```bash
docker run -d \
  --name domovoy \
  --restart unless-stopped \
  -v ~/domovoy:/config \
  ghcr.io/carlos-sarmiento/domovoy:latest
```

### 5. Create your first app

Create `~/domovoy/apps/my_first_apps.py`:

```python
from domovoy.applications import AppBase, EmptyAppConfig
from domovoy.applications.registration import register_app


class MyFirstApp(AppBase[EmptyAppConfig]):
    async def initialize(self):
        self.log.info("Hello from Domovoy!")

        # Listen to state changes
        self.callbacks.listen_state(
            "light.living_room"
            self.on_light_change,
        )

    async def on_light_change(self, entity_id, old, new):
        self.log.info(f"Light changed from {old} to {new}")


register_app(
    app_class=MyFirstApp,
    app_name="my_first_app",
    config=EmptyAppConfig(),
)
```

### Running Without Docker

#### Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager that handles dependencies efficiently.

```bash
# Clone the repository
git clone https://github.com/your-repo/domovoy.git
cd domovoy

# Install dependencies
uv sync

# Run Domovoy
python domovoy/cli.py --config config.yml
```

## Next Steps

- [Creating Your First App](first-app.md) - Learn the app structure in detail
- [Configuration Reference](configuration.md) - Understand all configuration options
- [Callbacks Guide](../guides/callbacks.md) - Schedule tasks and listen to events
- [Home Assistant Integration](../guides/hass.md) - Interact with Home Assistant entities and services
