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

User-facing text (the README and the config flow strings) describes only the OAuth token: the `oauth_token` cookie copied from `accounts.google.com/EmbeddedSetup`. The ways of getting a master token directly no longer work, so don't document them, even though the code still accepts both formats. A master token gives access to the whole Google account, not only Keep; say so wherever the token's reach comes up.

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

All code must also pass **mypy**. CI runs every hook in `.pre-commit-config.yaml` (Ruff, Black, mypy, codespell, pyupgrade and the file checks) at the versions pinned there, so run pre-commit locally to see the same result (see Pre-commit Hooks).

## Test Coverage

Test coverage must remain above **95%**. All new code should include appropriate tests.

```bash
pytest --cov --cov-fail-under=95
```

## Translations

`strings.json` and all the translation JSON files in `custom_components/google_keep_sync/translations/` must stay in sync. When you add, change or remove a user-facing string:

- Make the same change in `strings.json` and in all the translation JSON files in the same commit. Translate the new meaning; don't leave the old text or English in a translated file.
- Keep the set of keys identical across `strings.json` and all the translation JSON files, and keep placeholders such as `{invalid_auth_url}` unchanged.
- Remove keys the code no longer uses from all of them.

`tests/test_repository_consistency.py` checks the keys and placeholders.

## Pre-commit Hooks

Before committing, run pre-commit to verify all checks pass with no modifications:

```bash
pre-commit run --all-files
```

If pre-commit makes any changes, stage them and run again until all hooks pass without modifications.

The `commit-msg` hook stage must be installed once per clone so commit messages are checked (Conventional Commits format, and no attribution trailers):

```bash
pre-commit install --hook-type commit-msg
```

## Commit Messages

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org) spec. This is enforced by pre-commit, and release-please uses the prefixes to decide the next version.

Format:

```
<type>(<optional scope>): <description>

<optional body>

<optional footer>
```

Allowed types and their release effect:

| Type | Version bump | Use for |
|------|--------------|---------|
| `feat` | minor | New user-facing feature |
| `fix` | patch | Bug fix |
| `perf` | patch | Performance improvement |
| `refactor` | none | Code restructure with no behavior change |
| `docs` | none | Documentation only |
| `test` | none | Test-only changes |
| `build` | none | Build system / dependencies |
| `ci` | none | CI config changes |
| `chore` | none | Other maintenance |
| `revert` | context-dependent | Reverting a prior commit |

Breaking changes bump the major version. Mark them either by appending `!` to the type (`feat!: drop support for HA 2025.x`) or with a `BREAKING CHANGE:` footer.

Examples:

```
feat: add empty item placeholder option
fix(coordinator): avoid duplicate add_item events after rename
feat!: require master token instead of email/password
```

### No attribution trailers

Commit under your own name only. Don't add these lines to a commit message:

- A `Co-authored-by:` trailer, for an AI tool or for a person
- A line starting with "Generated with", such as "🤖 Generated with [Claude Code]"
- An AI session or log link (`Claude-Session:`, `Agent-Logs-Url:`)

If your tool adds these by default, turn that off in its settings. Squash merging copies a PR's co-authors onto `main`, so these would end up in the project history.

The `no-attribution-trailers` pre-commit hook rejects them when you commit, and the "No attribution trailers" CI check fails a PR whose commits contain them. Both use the same regex, and `tests/test_repository_consistency.py` checks that they match. To fix commits you've already pushed, reword them (`git commit --amend` for the last one, `git rebase -i` for older ones) and force-push.

## Python Version

The code targets Python 3.11+ (`pyupgrade --py311-plus`), matching the oldest Home Assistant version in `hacs.json`. The tools and CI run on Python 3.14, which current Home Assistant releases need.

## Dependencies

Dependabot opens one PR a month covering `requirements.test.txt`, the pre-commit hooks and the GitHub Actions. It leaves version ranges (`>=`) alone while the newest release fits them, and bumps exact pins (`==`). `gkeepapi` and `gpsoauth` are listed both in `manifest.json` (what Home Assistant installs for users) and in `requirements.test.txt` (what the tests use). They must name the same version: `tests/test_repository_consistency.py` fails otherwise. When a dependency PR bumps one of them, update `manifest.json` in the same PR and title it `fix(deps): ...` so the change is released.
