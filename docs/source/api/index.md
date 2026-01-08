# API Reference

This section contains auto-generated API documentation from the Domovoy source code.

The API is organized into three main sections:

- **[Plugins](plugins.md)**: The plugin system that provides functionality to apps (hass, callbacks, servents, etc.)
- **[Applications](applications.md)**: Base classes for creating apps (`AppBase`, `AppConfigBase`, registration functions)
- **[Types](types.md)**: Common types used throughout Domovoy (`EntityID`, `Interval`, `HassValue`, etc.)

## Quick Links

### Most Used Plugins

- `hass` - Home Assistant integration (state access, service calls, triggers)
- `callbacks` - Event listening and scheduling
- `servents` - Create Home Assistant entities from Python
- `log` - Logging functionality

### Core Classes

- `AppBase[TConfig]` - Base class for all apps
- `AppConfigBase` - Base class for app configuration
- `register_app()` - Register an app with Domovoy
