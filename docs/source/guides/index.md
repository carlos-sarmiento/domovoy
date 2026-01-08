# Guides

This section provides in-depth guides for using Domovoy's features.

## Plugin Guides

| Guide                                   | Description                                  |
| --------------------------------------- | -------------------------------------------- |
| [Callbacks](callbacks.md)               | Scheduling tasks and listening to events     |
| [Home Assistant Integration](hass.md)   | Interacting with entities and services.      |
| [ServEnts](servents.md)                 | Creating Home Assistant entities from Python |
| [State Management](state-management.md) | Working with entity states                   |

## Development Guides

| Guide                       | Description                                   |
|-----------------------------|-----------------------------------------------|
| [Hot Reload](hot-reload.md) | Development workflow with automatic reloading |
| [Mixins](mixins.md)         | Sharing code between apps                     |

## Quick Reference

### Available Plugins

Every app has access to these plugins via `self`:

```python
class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        # Home Assistant integration
        state = self.hass.get_state(entity_id)
        await self.hass.services.light.turn_on(entity_id=light)

        # Scheduling and events
        self.callbacks.run_daily(self.my_callback, "08:00:00")
        self.callbacks.listen_state(entity_id, self.on_change)

        # Create HA entities
        sensor = await self.servents.create_sensor("my_sensor", "My Sensor")

        # Logging
        self.log.info("App initialized")

        # Utilities
        value = self.utils.parse_float(some_string)
        now = self.time.now()

        # App control
        app_name = self.meta.get_app_name()
```

### Callback Patterns

```python
# State changes
self.callbacks.listen_state(entity_id, callback)

# Events
self.callbacks.listen_event("my_event", callback)

# Scheduling
self.callbacks.run_daily(callback, "08:00:00")
self.callbacks.run_in(Interval(minutes=5), callback)
self.callbacks.run_daily_on_sun_event(callback, "sunset")
```

### Service Calls

```python
# Typed service calls (recommended)
await self.hass.services.light.turn_on(entity_id=light, brightness=255)
await self.hass.services.switch.turn_off(entity_id=switch)

# Generic service call
await self.hass.call_service("notify.mobile_app", message="Hello")
```
