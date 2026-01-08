# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Domovoy is a Python-based automation framework for Home Assistant, built from the ground up with async/await throughout. It allows users to write home automations in pure Python instead of YAML, Node Red, or n8n.

Key distinguishing features:

- **ServEnts Integration**: Creates Home Assistant devices and entities directly from Python code
- **Type Safety**: Full typing support including type-checking for Home Assistant entities and services
- **Hot Reload**: Automatic file watching and module reloading during development
- **Plugin Architecture**: Apps access functionality through plugins (hass, callbacks, servents, servents_v2, log, utils, time, meta)

## Development Commands

### Running the Application

```bash
# Install dependencies
uv sync

# Run locally with default config
python domovoy/cli.py --config config.yml

# Run with custom config
python domovoy/cli.py --config /path/to/config.yml

# Run in Docker
docker build -t domovoy .
docker run -v /path/to/config:/config domovoy
```

### Linting and Type Checking

```bash
# Run ruff linter
uv run ruff check .

# Run ruff formatter
uv run ruff format .

# Run pyright type checker
uv run pyright
```

### Documentation

```bash
# Install docs dependencies
uv sync --group docs

# Build HTML documentation
uv run --group docs sphinx-build -b html docs/source docs/build/html

# View documentation locally
python -m http.server -d docs/build/html 8000
```

### Configuration

The `config.yml` file requires:

- `app_suffix`: Suffix for app files (default: `_apps`)
- `hass_access_token`: Home Assistant long-lived access token
- `hass_url`: WebSocket URL to Home Assistant instance
- `app_path`: Path to directory containing app files
- `timezone`: Timezone for scheduling operations
- `install_pip_dependencies`: Whether to auto-install requirements from app files

## Architecture

### Core Engine Flow

1. **App Engine** (`domovoy/core/engine/engine.py`): Central orchestrator
   - Manages app lifecycle (registration, initialization, termination)
   - Maintains app registry and tracks app status
   - Coordinates with all services (HassCore, CallbackRegister, EventListener, WebApi)

2. **Dependency Tracker** (`domovoy/core/dependency_tracking/`): Hot-reload system
   - Watches app directory for file changes
   - Tracks module dependencies using importlab
   - Triggers app reloads when dependencies change
   - Uses deep reload to properly unload and reload modules

3. **App Lifecycle States** (`domovoy/core/app_infra.py`):
   - CREATED → INITIALIZING → RUNNING → FINALIZING → TERMINATED
   - FAILED state if initialization throws

### App Structure

Apps inherit from `AppBase[TConfig]` where TConfig is a config class inheriting from `AppConfigBase`:

```python
@dataclass
class MyAppConfig(AppConfigBase):
    some_param: str

class MyApp(AppBase[MyAppConfig]):
    async def initialize(self):
        # Setup listeners, create entities, etc.
        pass

    async def finalize(self):
        # Cleanup (called on app termination)
        pass
```

Apps must be registered in files ending with the configured `app_suffix` (default: `_apps.py`):

```python
from domovoy.applications.registration import register_app

register_app(
    app_class=MyApp,
    app_name="unique_app_name",
    config=MyAppConfig(some_param="value"),
)
```

### Plugin System

Each app instance receives plugin instances injected during construction:

- **hass**: Home Assistant integration
  - `get_state(entity_id)`: Get entity state
  - `call_service(service_name, **kwargs)`: Call HA services
  - `listen_trigger(trigger, callback)`: Subscribe to HA triggers
  - `wait_for_state_to_be(entity_id, states, duration, timeout)`: Async wait for state
  - `services`: Auto-generated service call stubs from HA API

- **callbacks**: Scheduling and event listening
  - `listen_event(events, callback)`: Listen to HA events
  - `listen_state(entity_id, callback, immediate, oneshot)`: Listen to state changes
  - `listen_attribute(entity_id, attribute, callback)`: Listen to attribute changes
  - `run_at(callback, datetime)`: Schedule for specific time
  - `run_in(interval, callback)`: Schedule after interval
  - `run_daily(callback, time)`: Daily scheduling
  - `run_every(interval, callback, start)`: Recurring scheduling
  - `run_daily_on_sun_event(callback, sun_event, delta)`: Schedule based on sunrise/sunset

- **servents_v2**: Create and manage Home Assistant entities from Python
  - `create_sensor(servent_id, name, **config)`: Create sensor entity
  - `create_binary_sensor(servent_id, name, **config)`: Create binary sensor
  - `create_switch(servent_id, name, **config)`: Create switch entity
  - `create_button(servent_id, name, **config)`: Create button entity
  - `create_number(servent_id, name, mode, **config)`: Create number entity
  - `create_select(servent_id, name, options, **config)`: Create select entity
  - `listen_button_press(callback, button_name, event_name_to_fire)`: Create button with callback
  - Returns entity objects with methods like `set_state()`, `get_entity_id()`

- **servents**: Legacy V1 API (deprecated, use servents_v2)

- **log**: Logger instance scoped to the app with trace/debug/info/warning/error methods

- **meta**: App metadata and control
  - `get_app_name()`: Get app's unique name
  - `restart_app()`: Programmatically restart the app

- **utils**: Utility functions

- **time**: Time-related utilities

### Entity IDs and Type Safety

Entity IDs are typed objects, not strings:

```python
from domovoy.plugins.hass.entity_id import EntityID
from domovoy.plugins.hass.domains import Light, Switch

# Get typed entity instance
light = self.hass.entities.light.living_room
state = self.hass.get_state(light)  # Returns typed state

# Service calls are also typed
await self.hass.services.light.turn_on(
    entity_id=light,
    brightness=255
)
```

The type system is generated from the actual Home Assistant instance via synthetic stub files.

### Callback Signatures

Callbacks have flexible signatures - only include parameters you need:

```python
# State callback - include only what you use
async def on_state(entity_id, new):
    pass

async def on_state_full(entity_id, attribute, old, new):
    pass

# Event callback
async def on_event(event_name, data):
    pass

async def on_event_minimal():
    pass
```

### Configuration and Logging

Logging configuration is hierarchical in `config.yml`:

- `_base`: Default for all loggers
- `_default`: Default for apps
- Custom per-app configs by app name or filename

Available log handlers:

- `StreamLoggingHandler`: Console output (stdout/stderr)
- `FileLoggingHandler`: File output
- `OpenObserveLoggingHandler`: Remote logging service

## Code Style

This project uses:

- **ruff** for linting with comprehensive rule set (see pyproject.toml)
- **pyright** for type checking (Python 3.13+)
- Line length: 120 characters
- Requires Python >=3.13.2

Notable ignored ruff rules:

- Documentation rules (D100-D107) - docstrings not required
- Many complexity rules (PLR*) - allowed for domain logic
- Type annotation placement (TCH*) - types stay in runtime

When adding dependencies, add to `pyproject.toml` dependencies array.

## Important Implementation Details

### App Registration Validation

- Apps MUST be registered from files ending in `{app_suffix}.py` (e.g., `_apps.py`)
- App names must be unique across all running apps
- If an app with the same name is already running, registration is rejected

### Hot Reload Behavior

- File changes trigger automatic app reloads
- Reload process: terminate app → reload modules → start app
- Apps should be idempotent in `initialize()` since they may reload multiple times
- Use `finalize()` to clean up resources that shouldn't leak across reloads

### Async Context

- All app code runs in async context
- Callbacks can be sync or async - framework handles both
- Use `await` for all I/O operations (HA service calls, delays, etc.)
- Don't use `asyncio.create_task()` directly - let the framework manage tasks

### Entity State Caching

- HassCore maintains a local cache of all entity states
- Cache is updated via WebSocket events from Home Assistant
- Use `warn_if_entity_doesnt_exists()` during development to catch typos

### ServEnts Entity Creation

- Entity creation is async and takes time for HA to process
- Use `wait_for_creation=True` (default) to wait for entity to appear
- Entity IDs are auto-prefixed with app name unless marked as global
- Created entities persist in HA until manually deleted

### Error Handling

- Exceptions in `initialize()` mark app as FAILED
- Exceptions in callbacks are logged but don't crash the app
- App engine isolates apps - one app crashing doesn't affect others
