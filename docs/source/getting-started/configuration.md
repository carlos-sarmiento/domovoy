# Configuration Reference

Domovoy is configured through a YAML file (default: `config.yml`).

## Required Settings

```yaml
# File suffix for app files (apps must end with this + .py)
app_suffix: _apps

# Path to directory containing app files
app_path: ./apps

# Home Assistant WebSocket URL
hass_url: "wss://your-home-assistant:8123/api/websocket"

# Home Assistant Long-Lived Access Token
hass_access_token: "your-token-here"

# Timezone for scheduling operations
timezone: America/New_York
```

## Optional Settings

```yaml
# Auto-install pip dependencies from app files (default: false)
install_pip_dependencies: true
```

## Astral Configuration

For sunrise/sunset scheduling, configure your location:

```yaml
astral:
  name: My Home
  region: My Region
  timezone: America/New_York
  latitude: 40.7128
  longitude: -74.0060
```

## Logging Configuration

Domovoy uses a hierarchical logging system with multiple handlers.

### Basic Example

```yaml
logs:
  _base:
    handlers:
      - StreamLoggingHandler:
          log_level: info
          stream: "stdout"
```

### Full Example

```yaml
logs:
  # Base configuration applied to all loggers
  _base:
    handlers:
      - StreamLoggingHandler:
          log_level: info
          stream: "stdout"

  # Default configuration for apps (overrides _base for apps)
  _default:
    handlers:
      - FileLoggingHandler:
          filename: "apps.log"
          log_level: debug

  # Per-app configuration (by app name)
  my_specific_app:
    handlers:
      - StreamLoggingHandler:
          log_level: debug
          stream: "stderr"
      - FileLoggingHandler:
          filename: "my_app.log"
          log_level: trace
```

### Available Handlers

#### StreamLoggingHandler

Outputs to console (stdout or stderr):

```yaml
- StreamLoggingHandler:
    log_level: info       # trace, debug, info, warning, error
    stream: "stdout"      # stdout or stderr
```

#### FileLoggingHandler

Outputs to a file:

```yaml
- FileLoggingHandler:
    filename: "app.log"
    log_level: debug
```

#### OpenObserveLoggingHandler

Sends logs to OpenObserve (remote logging service):

```yaml
- OpenObserveLoggingHandler:
    log_level: info
    endpoint: "https://your-openobserve-instance"
    organization: "your-org"
    stream: "your-stream"
    username: "your-username"
    password: "your-password"
```

### Log Levels

From most to least verbose:

1. `trace` - Very detailed debugging
2. `debug` - Debugging information
3. `info` - General information
4. `warning` - Warning messages
5. `error` - Error messages

## Complete Example

```yaml
app_suffix: _apps
app_path: ./apps
hass_url: "wss://homeassistant.local:8123/api/websocket"
hass_access_token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
timezone: America/Chicago
install_pip_dependencies: true

astral:
  name: Home
  region: Texas
  timezone: America/Chicago
  latitude: 29.7604
  longitude: -95.3698

logs:
  _base:
    handlers:
      - StreamLoggingHandler:
          log_level: info
          stream: "stdout"

  _default:
    handlers:
      - FileLoggingHandler:
          filename: "main.log"
          log_level: debug

  # Verbose logging for a specific app
  hvac_control:
    handlers:
      - StreamLoggingHandler:
          log_level: debug
          stream: "stdout"
      - FileLoggingHandler:
          filename: "hvac.log"
          log_level: trace
```

## Environment Variables

You can use environment variables in your config:

```yaml
hass_access_token: ${HASS_TOKEN}
hass_url: ${HASS_URL}
```

## Command Line Options

```bash
python domovoy/cli.py --config /path/to/config.yml
```

| Option | Description |
|--------|-------------|
| `--config` | Path to configuration file (required) |

## Next Steps

- [Creating Your First App](first-app.md) - App development guide
- [Callbacks Guide](../guides/callbacks.md) - Scheduling and events
- [Hot Reload](../guides/hot-reload.md) - Development workflow
