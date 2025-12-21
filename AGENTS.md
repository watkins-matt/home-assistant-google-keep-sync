# Architecture Overview

This is a Home Assistant custom integration that provides bidirectional synchronization between Google Keep lists and Home Assistant todo entities.

## Core Components

```
┌──────────────────────────────────────────────────────────┐
│                      HOME ASSISTANT                      │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Config Flow (config_flow.py)                      │  │
│  │  • User credentials & list selection               │  │
│  │  • Options flow for post-setup changes             │  │
│  └────────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Coordinator (coordinator.py)                      │  │
│  │  • Periodic sync with Google Keep                  │  │
│  │  • Detects remote changes, fires events            │  │
│  │  • Handles deleted lists & entity cleanup          │  │
│  └────────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Todo Entities (todo.py)                           │  │
│  │  • One entity per synced Google Keep list          │  │
│  │  • CRUD operations + optional reordering           │  │
│  └────────────────────────────────────────────────────┘  │
│                           ↓                              │
│  ┌────────────────────────────────────────────────────┐  │
│  │  API Layer (api.py)                                │  │
│  │  • Wraps gkeepapi library                          │  │
│  │  • Authentication & state persistence              │  │
│  │  • Auto-sort & case transformation                 │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────────────┬─────────────────────────────┘
                             ↓
                    ┌────────────────┐
                    │  GOOGLE KEEP   │
                    └────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `__init__.py` | Integration lifecycle, service registration, migrations |
| `api.py` | Google Keep API wrapper, authentication, CRUD operations |
| `coordinator.py` | Data sync orchestration, change detection |
| `todo.py` | Home Assistant TodoListEntity implementation |
| `config_flow.py` | Setup UI, options flow, validation |
| `exponential_backoff.py` | Retry decorator for API resilience |
| `const.py` | Domain name, scan interval constants |

## Data Flow

**Sync Cycle:**
1. Coordinator calls `api.async_sync_data()`
2. Compares before/after state to detect new remote items
3. Fires `add_item` events for items added in Google Keep
4. Updates entity registry if list names changed

**User Actions (HA → Google Keep):**
1. User modifies todo entity (create/update/delete/move)
2. Entity calls corresponding API method
3. API updates gkeepapi and syncs
4. Coordinator refreshes to ensure consistency

## Authentication

The integration uses a **master token** (starts with `aas_et/`, 223 characters) for authentication. Users can also provide an exchange token (starts with `oauth2_4/`) which is automatically converted to a master token.

Auth state is persisted to Home Assistant storage for fast re-authentication on restart.

## Key Patterns

- **Async/Executor**: Blocking gkeepapi calls wrapped in `async_add_executor_job()`
- **CoordinatorEntity**: Entities subscribe to coordinator for automatic updates
- **Exponential Backoff**: API sync retries with increasing delays
- **Dynamic Features**: `MOVE_TODO_ITEM` disabled when auto-sort enabled

---

# Coding Standards

This document outlines the coding standards and requirements for contributing to this project.

## Code Formatting

All code must be formatted with **Black**. No exceptions.

```bash
black .
```

## Linting

All code must pass **Ruff** with zero warnings. No `# noqa` comments to suppress warnings - fix the underlying issue instead.

```bash
ruff check .
```

## Test Coverage

Test coverage must remain above **95%**. All new code should include appropriate tests.

```bash
pytest --cov --cov-fail-under=95
```

## Pre-commit Hooks

Before committing, run pre-commit to verify all checks pass with no modifications:

```bash
pre-commit run --all-files
```

If pre-commit makes any changes, stage them and run again until all hooks pass without modifications.

## Python Version

This project targets Python 3.11+ to align with Home Assistant requirements.
