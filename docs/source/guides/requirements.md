# Installing Additional Dependencies

Domovoy can automatically install Python packages required by your apps using `requirements.txt` files or a `pyproject.toml` file. This allows each app or group of apps to declare their own dependencies without modifying the core Domovoy installation.

## Enabling Dependency Installation

To enable automatic dependency installation, set `install_pip_dependencies: true` in your `config.yml`:

```yaml
app_suffix: _apps
app_path: ./apps
hass_url: "wss://homeassistant.local:8123/api/websocket"
hass_access_token: "your-token-here"
timezone: America/Chicago
install_pip_dependencies: true  # Enable this
```

When enabled, Domovoy scans your apps directory for `requirements.txt` files at startup and installs all listed packages. It also checks for a `pyproject.toml` file at the root of your project directory.

### pyproject.toml File

Domovoy also supports installing dependencies from a `pyproject.toml` file located at the root of your project directory (the same directory as your `config.yml`). This is useful if you prefer the modern Python packaging standard.

When a `pyproject.toml` exists, Domovoy runs `uv sync` to install all dependencies defined in the project.

Example `pyproject.toml`:

```toml
[project]
name = "my-domovoy-apps"
version = "0.1.0"
dependencies = [
    "httpx>=0.25.2",
    "pydantic>=2.5.0",
    "qrcode>=7.4.2",
]
```

## Creating Requirements Files

### requirements.txt Files

Place a `requirements.txt` file in any directory within your apps folder. Domovoy uses the glob pattern `**/requirements*.txt`, so files can be:

- `requirements.txt`
- `requirements-dev.txt`
- `requirements_extra.txt`
- Any file matching `requirements*.txt`

### Directory Structure

You can organize requirements files alongside related apps:

```text
apps/
├── lights/
│   ├── living_room_light_apps.py
│   └── requirements.txt
├── printing/
│   ├── printer_apps.py
│   └── requirements.txt
├── mixins/
│   ├── common_mixins.py
│   └── requirements.txt
└── home_apps.py
```

### File Format

Requirements files use the standard pip format. Pin versions for reproducibility:

```txt
# printing/requirements.txt
qrcode==7.4.2
python-barcode==0.15.1
pillow==10.4.0
```

## How It Works

At startup, when `install_pip_dependencies` is enabled:

1. Domovoy checks for a `pyproject.toml` at the project root and runs `uv pip install -r <file>` if found
2. Domovoy scans the app directory recursively for files matching `**/requirements*.txt`
3. Each discovered requirements file is processed using `uv pip install --system -r <file>`
4. Installation output is logged (info level for success, error level for failures)
5. After all dependencies are installed, apps are loaded and initialized

## Best Practices

### Pin Your Versions

Always specify exact versions to ensure reproducible installations:

```txt
# Good - predictable behavior
httpx==0.25.2
pydantic==2.5.0

# Avoid - may break on restart
httpx
pydantic>=2.0
```

### Group Related Dependencies

Keep requirements files close to the apps that use them:

```text
apps/
├── telegram/
│   ├── telegram_apps.py
│   └── requirements.txt    # Only telegram-related packages
└── weather/
    ├── weather_apps.py
    └── requirements.txt    # Only weather-related packages
```

### Shared Dependencies

For packages used by multiple apps, create a shared requirements file:

```text
apps/
├── mixins/
│   ├── http_mixin.py       # Shared HTTP utilities
│   └── requirements.txt    # httpx, used by multiple apps
├── telegram/
│   └── ...
└── weather/
    └── ...
```

## Troubleshooting

### Dependencies Not Installing

1. Verify `install_pip_dependencies: true` is set in your config
2. Check that your requirements file matches the pattern `requirements*.txt`
3. Look for error messages in the Domovoy startup logs

### Installation Errors

Check the logs for pip installation output:

```text
INFO: Processing package dependencies from: /config/apps/telegram/requirements.txt
ERROR: /config/apps/telegram/requirements.txt -- stdout:
...
```

Common issues:

- Package name typos
- Version conflicts with existing packages
- Network connectivity problems

### Package Not Available at Runtime

Dependencies are installed at Domovoy startup. If you add a new requirements file:

1. Restart Domovoy to trigger dependency installation
2. Hot reload does not reinstall dependencies

## Docker Considerations

When running Domovoy in Docker, dependencies are installed inside the container at startup. The packages persist until the container is recreated. When updating the image, first boot might take some time.

## Next Steps

- [Hot Reload](hot-reload.md) - Note that hot reload doesn't reinstall dependencies
- [Configuration Reference](../getting-started/configuration.md) - Full configuration options
