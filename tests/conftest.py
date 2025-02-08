"""Configure pytest for Home Assistant custom component testing."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Callable, List, Mapping, Tuple
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery_flow import DiscoveryKey
from pytest_socket import enable_socket, socket_allow_hosts

from custom_components.google_keep_sync.const import DOMAIN

# Ensure custom components are in Python Path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../custom_components"))
)


# Ensure custom integrations are loaded
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable custom integrations in all tests."""
    yield


@pytest.fixture(scope="function", autouse=True)
def workaround_for_windows_socket_issues():
    """Workaround to allow testing on Windows with VS Code."""
    enable_socket()
    socket_allow_hosts(["127.0.0.1", "localhost", "::1"], allow_unix_socket=True)
    yield


class MockConfigEntry(MagicMock):
    """A mock config entry for testing the Google Keep Sync integration."""

    def __init__(  # noqa
        self,
        *,
        created_at: datetime | None = None,
        data: Mapping[str, Any] = MappingProxyType({}),
        disabled_by: ConfigEntryDisabler | None = None,
        discovery_keys: MappingProxyType[
            str, Tuple[DiscoveryKey, ...]
        ] = MappingProxyType({}),
        domain: str = "",
        entry_id: str | None = None,
        minor_version: int = 1,
        modified_at: datetime | None = None,
        options: Mapping[str, Any] | None = None,
        pref_disable_new_entities: bool | None = False,
        pref_disable_polling: bool | None = False,
        source: str = "",
        state: ConfigEntryState = ConfigEntryState.NOT_LOADED,
        title: str = "",
        unique_id: str | None = None,
        version: int = 1,
        **kwargs: Any,
    ) -> None:
        """Initialize the fake config entry with the given parameters."""
        super().__init__()
        self.created_at: datetime = created_at or datetime.now(UTC)
        self.data: Mapping[str, Any] = data
        self.disabled_by: ConfigEntryDisabler | None = disabled_by
        self.discovery_keys: MappingProxyType[str, Tuple[DiscoveryKey, ...]] = (
            discovery_keys
        )
        self.domain: str = domain
        self.entry_id: str = entry_id if entry_id is not None else "test_entry"
        self.minor_version: int = minor_version
        self.modified_at: datetime = modified_at or datetime.now(UTC)
        self.options: Mapping[str, Any] = options or {}
        self.pref_disable_new_entities: bool = pref_disable_new_entities or False
        self.pref_disable_polling: bool = pref_disable_polling or False
        self.source: str = source
        self.state: ConfigEntryState = state
        self.title: str = title
        self.unique_id: str | None = unique_id
        self.version: int = version

        self.setup_lock: asyncio.Lock = asyncio.Lock()
        self.update_listeners: List[Callable[[], None]] = []

        self.clear_state_cache: Callable[[], None] = lambda: None
        self.clear_storage_cache: Callable[[], None] = lambda: None
        self.async_cancel_retry_setup: Callable[[], None] = lambda: None

    async def async_setup(self, hass: HomeAssistant, **kwargs: Any) -> bool:
        """Simulate setting up the config entry."""
        return True

    async def async_unload(self, hass: HomeAssistant, **kwargs: Any) -> bool:
        """Simulate unloading the config entry."""
        return True

    async def async_shutdown(self, hass: HomeAssistant) -> None:
        """Simulate shutting down the config entry."""
        return

    async def async_setup_locked(
        self, hass: HomeAssistant, *, integration: Any
    ) -> bool:
        """Simulate setting up the entry while holding the setup lock.

        This method calls the async_setup method (an AsyncMock) and returns its result.
        """
        return await self.async_setup(hass, integration=integration)

    def add_to_hass(self, hass: HomeAssistant) -> None:
        """Simulate adding the config entry to Home Assistant.

        This adds the entry to hass.config_entries._entries so that the core
        can locate it.
        """
        hass.config_entries._entries[self.entry_id] = self


@pytest.fixture(scope="function")
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry for Google Keep Sync integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "testuser@example.com",
            "password": "testpassword",
            "lists_to_sync": [],
            "list_prefix": "",
        },
        unique_id="google_keep_sync.testuser@example.com",
    )
    return entry
