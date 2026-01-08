# Domovoy Documentation

Welcome to the Domovoy documentation! Domovoy is a Python-based automation framework for Home Assistant, built from the ground up with modern async/await patterns.

:::{note}
Domovoy is designed for users who prefer writing home automations in pure Python rather than YAML, Node Red, or n8n, providing a more flexible and developer-friendly approach.
:::

## Key Features

- **ServEnts Integration**: Create Home Assistant devices and entities directly from Python code
- **Type Safety**: Full typing support including type-checking for Home Assistant entities and services
- **Hot Reload**: Automatic file watching and module reloading during development
- **High Performance**: Leverages Python's async/await for efficient, non-blocking operations
- **Plugin Architecture**: Access functionality through well-designed plugins

## Contents

```{toctree}
:maxdepth: 2
:caption: Getting Started

getting-started/index
getting-started/first-app
getting-started/configuration
```

```{toctree}
:maxdepth: 2
:caption: Guides

guides/index
guides/callbacks
guides/hass
guides/servents
guides/state-management
guides/hot-reload
guides/mixins
```

```{toctree}
:maxdepth: 2
:caption: Examples

examples/index
examples/simple-toggle
examples/state-listeners
examples/scheduling
examples/entity-creation
examples/climate-control
examples/advanced
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api/index
api/plugins
api/applications
api/types
```

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
