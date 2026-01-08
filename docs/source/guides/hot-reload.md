# Hot Reload Guide

Domovoy automatically reloads apps when their source files change, enabling rapid development without restarts.

## How Hot Reload Works

1. **File Watcher**: Domovoy monitors your app directory for changes
2. **Dependency Tracking**: Tracks which modules each app imports
3. **Deep Reload**: When a file changes, reloads all affected modules
4. **App Restart**: Terminates and reinitializes affected apps

## Development Workflow

### Start Domovoy

```bash
python domovoy/cli.py --config config.yml
```

### Edit Your Apps

Save changes to any app file, and Domovoy will:

1. Detect the file change
2. Call `finalize()` on affected apps
3. Reload the modified modules
4. Call `initialize()` on restarted apps

### Watch the Logs

```
INFO: File changed: /apps/lighting_apps.py
INFO: Reloading app: sunset_light
INFO: App sunset_light terminated
INFO: App sunset_light initialized
```

## Making Apps Reload-Safe

### Idempotent Initialization

Your `initialize()` method may be called multiple times due to reloads:

```python
async def initialize(self) -> None:
    # Good: Each reload creates fresh listeners
    # Old listeners are automatically cleaned up
    self.callbacks.listen_state(
        self.config.entity_id,
        self.on_change,
    )

    # Good: ServEnts entities are deduplicated by ID
    self.sensor = await self.servents.create_sensor(
        servent_id="my_sensor",  # Same ID = same entity
        name="My Sensor",
    )
```

### Cleanup in finalize()

Use `finalize()` to clean up resources that shouldn't persist:

```python
async def initialize(self) -> None:
    self.session = aiohttp.ClientSession()

async def finalize(self) -> None:
    # Clean up external resources
    if hasattr(self, 'session'):
        await self.session.close()
```

### Avoid Global State

```python
# Bad: Global state persists across reloads
_global_counter = 0

class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        global _global_counter
        _global_counter += 1  # Keeps incrementing on reload!

# Good: Instance state is reset on reload
class MyApp(AppBase[MyAppConfig]):
    async def initialize(self) -> None:
        self.counter = 0  # Fresh on each reload
```

## Dependency Tracking

Domovoy tracks module dependencies automatically:

```
apps/
├── lighting_apps.py      # App file
├── climate_apps.py       # App file
└── utils/
    └── helpers.py        # Shared module
```

If `helpers.py` changes:

- Apps that import `helpers` will be reloaded
- Apps that don't import it are unaffected

## Reload Triggers

Hot reload triggers when:

- App file (ending with `_apps.py`) is modified
- Any Python module imported by an app is modified
- Configuration changes that require a restart

Hot reload does NOT trigger when:

- Non-Python files change
- Files outside the app directory change
- Config file changes (requires manual restart)

## Debugging Reloads

### Check App Status

Use the meta plugin to check current status:

```python
status = self.meta.get_status()
self.log.info("App status: {status}", status=status)
```

### Manual Restart

Create a reload button for manual restarts:

```python
async def initialize(self) -> None:
    await self.servents.enable_reload_button()
```

Or programmatically:

```python
await self.meta.restart_app()
```

### Logging on Lifecycle Events

```python
async def initialize(self) -> None:
    self.log.info("App initializing...")
    # Setup code
    self.log.info("App initialized successfully")

async def finalize(self) -> None:
    self.log.info("App finalizing...")
    # Cleanup code
    self.log.info("App finalized")
```

## Common Issues

### State Lost on Reload

Use ServEnts to persist state in Home Assistant:

```python
async def initialize(self) -> None:
    self.counter_sensor = await self.servents.create_sensor(
        servent_id="counter",
        name="Counter",
        default_state=0,
    )

    # State persists in HA across reloads
    current = self.counter_sensor.get_state()
```

### Callbacks Not Firing After Reload

Callbacks are automatically cleaned up and recreated. If callbacks aren't firing:

1. Check for errors in `initialize()`
2. Verify entity IDs are correct
3. Check Home Assistant connection

### Module Import Errors

If a syntax error prevents loading:

```
ERROR: Failed to reload module: my_apps
ERROR: SyntaxError on line 42
```

Fix the error and save - Domovoy will retry automatically.

## Best Practices

### Keep Apps Small

Smaller apps reload faster and are easier to debug:

```python
# Good: One responsibility per app
class LightController(AppBase[LightConfig]):
    ...

class MotionHandler(AppBase[MotionConfig]):
    ...

# Avoid: One giant app doing everything
class EverythingApp(AppBase[HugeConfig]):
    ...
```

### Use Typed Configuration

Catch errors at reload time:

```python
@dataclass
class MyAppConfig(AppConfigBase):
    entity_id: EntityID  # Type checked
    threshold: float     # Type checked
```

### Test Incrementally

1. Make a small change
2. Save and watch logs
3. Verify behavior
4. Repeat

## Production Considerations

In production:

- Hot reload continues to work
- Consider logging reload events
- Monitor for reload loops (continuous errors)
- Use `finalize()` to ensure clean shutdown

```python
async def finalize(self) -> None:
    self.log.info("App shutting down - cleaning up resources")
    # Ensure all cleanup happens
```
