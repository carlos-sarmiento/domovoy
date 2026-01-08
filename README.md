# Domovoy

Domovoy is a powerful application framework designed to drive automations for Home Assistant using Python. If you prefer writing your automations in pure Python rather than YAML, Node Red, or n8n, Domovoy provides a more flexible and developer-friendly approach to home automation.

Inspired by AppDaemon, Domovoy is a completely new codebase built from the ground up with Python's async/await throughout, resulting in significantly improved resource efficiency and performance.

## Key Features

- **ServEnts Integration**: When paired with ServEnts (a Home Assistant custom component), Domovoy can create devices and entities directly from Python code, eliminating the need for manually configuring helpers in HA.

- **Type Safety**: Full support for Python typing, including typechecking for entities and services on the Home Assistant instance it connects to, catching errors before they happen.

- **Python-First Approach**: Write all your automations in Python with full IDE support, and the ability to leverage Python's rich ecosystem of libraries.

- **High Performance**: Leverages Python's async/await for efficient, non-blocking operations that make the most of your system resources.

- **Hot Reload**: Automatic file watching and module reloading during development - make changes to your apps and see them take effect immediately without restarting.

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

### 3. Run with Docker

```bash
docker run -d \
  --name domovoy \
  --restart unless-stopped \
  -v ~/domovoy:/config \
  ghcr.io/YOUR_REGISTRY/domovoy:latest
```

### 4. Create your first app

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

## Documentation

For comprehensive documentation, guides, and examples:

- [Getting Started Guide](docs/source/getting-started/index.md) - Installation and first steps
- [Configuration Reference](docs/source/getting-started/configuration.md) - Detailed configuration options
- [Writing Your First App](docs/source/getting-started/first-app.md) - Step-by-step tutorial
- [Guides](docs/source/guides/index.md) - In-depth guides on callbacks, state management, ServEnts, and more
- [Examples](docs/source/examples/index.md) - Real-world automation examples
- [API Reference](docs/source/api/index.md) - Complete API documentation

## License

This project is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](https://www.gnu.org/licenses/agpl-3.0.html).
