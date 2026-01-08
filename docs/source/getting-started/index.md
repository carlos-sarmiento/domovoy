# Getting Started

This guide will help you get Domovoy up and running with Home Assistant.

## Prerequisites

- **Python 3.14.2+**: Domovoy requires Python 3.14.2 or later
- **Home Assistant**: A running Home Assistant instance with WebSocket API access
- **Long-Lived Access Token**: Generate one from your Home Assistant profile page
- **ServEnts (Optional)**: The [ServEnts](https://github.com/carlos-sarmiento/servents) custom component for creating entities from Python

## Installation

### Using uv (Recommended)

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

### Using pip

```bash
# Clone the repository
git clone https://github.com/your-repo/domovoy.git
cd domovoy

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Run Domovoy
python domovoy/cli.py --config config.yml
```

### Using Docker

```bash
# Build the Docker image
docker build -t domovoy .

# Run with your config directory mounted
docker run -v /path/to/your/config:/config domovoy
```

## Quick Start

### 1. Create a Configuration File

Create a `config.yml` file with your Home Assistant connection details:

```yaml
app_suffix: _apps
hass_url: "wss://your-home-assistant:8123/api/websocket"
hass_access_token: "your-long-lived-access-token"
app_path: ./apps
timezone: America/New_York
install_pip_dependencies: true

logs:
  _base:
    handlers:
      - StreamLoggingHandler:
          log_level: info
          stream: "stdout"
```

### 2. Create Your Apps Directory

```bash
mkdir apps
```

### 3. Create Your First App

Create a file `apps/my_first_apps.py`:

```python
from dataclasses import dataclass
from domovoy.applications import AppBase, AppConfigBase
from domovoy.applications.registration import register_app

@dataclass
class HelloWorldConfig(AppConfigBase):
    message: str

class HelloWorld(AppBase[HelloWorldConfig]):
    async def initialize(self) -> None:
        self.log.info("Hello from Domovoy! Message: {msg}", msg=self.config.message)

register_app(
    app_class=HelloWorld,
    app_name="hello_world",
    config=HelloWorldConfig(message="My first app is running!"),
)
```

### 4. Run Domovoy

```bash
python domovoy/cli.py --config config.yml
```

You should see your "Hello from Domovoy!" message in the logs.

## Next Steps

- [Creating Your First App](first-app.md) - Learn the app structure in detail
- [Configuration Reference](configuration.md) - Understand all configuration options
- [Callbacks Guide](../guides/callbacks.md) - Schedule tasks and listen to events
- [Home Assistant Integration](../guides/hass.md) - Interact with Home Assistant entities and services
