"""Configure pytest for Home Assistant custom component testing."""

import os
import sys

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
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


@pytest.fixture
def mock_config_entry():
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
