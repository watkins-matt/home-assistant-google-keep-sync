"""Test the Google Keep Sync setup entry."""

import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from custom_components.google_keep_sync import (
    _LOGGER as INTEGRATION_LOGGER,
)
from custom_components.google_keep_sync import (
    _filter_unknown_node_type_warning,
    async_migrate_entry,
    async_service_request_sync,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.google_keep_sync.const import DOMAIN as GOOGLE_KEEP_DOMAIN


@pytest.fixture
def mock_store():
    """Fixture for mocking storage."""
    store = MagicMock()
    store.async_load = AsyncMock()
    store.async_save = AsyncMock()
    return store


@pytest.fixture()
def mock_api(mock_store):
    """Return a mocked Google Keep API."""
    with patch(
        "custom_components.google_keep_sync.GoogleKeepAPI", autospec=True
    ) as mock_api_class:
        mock_api_instance = mock_api_class.return_value
        mock_api_instance.authenticate = AsyncMock(return_value=True)
        mock_api_instance.async_sync_data = AsyncMock(return_value=([], []))
        mock_api_instance._store = mock_store
        yield mock_api_instance


async def test_async_setup_entry_successful(
    hass: HomeAssistant, mock_api, mock_config_entry
):
    """Test a successful setup entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
    with (
        patch(
            "custom_components.google_keep_sync.GoogleKeepSyncCoordinator."
            "async_config_entry_first_refresh",
            AsyncMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await async_setup_entry(hass, mock_config_entry)
    assert hass.data[GOOGLE_KEEP_DOMAIN]
    await hass.async_block_till_done()


async def test_async_setup_entry_failed(
    hass: HomeAssistant, mock_api, mock_config_entry
):
    """Test a failed setup entry due to authentication error."""
    mock_api.authenticate = AsyncMock(return_value=False)
    mock_config_entry.add_to_hass(hass)
    assert not await async_setup_entry(hass, mock_config_entry)
    assert GOOGLE_KEEP_DOMAIN not in hass.data
    await hass.async_block_till_done()


async def test_async_unload_entry(hass: HomeAssistant, mock_api, mock_config_entry):
    """Test unloading a Google Keep Sync config entry."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.state = ConfigEntryState.SETUP_IN_PROGRESS
    with (
        patch(
            "custom_components.google_keep_sync.GoogleKeepSyncCoordinator."
            "async_config_entry_first_refresh",
            AsyncMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(
            hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)
        assert await async_unload_entry(hass, mock_config_entry)
    assert not hass.data[GOOGLE_KEEP_DOMAIN].get(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_async_service_request_sync_refresh_called(hass: HomeAssistant, mock_api):
    """Test that async_refresh is called when the sync threshold is exceeded."""
    coordinator = AsyncMock()
    coordinator.last_update_success_time = utcnow()
    coordinator.async_refresh = AsyncMock()

    with (
        patch(
            "custom_components.google_keep_sync.utcnow",
            return_value=coordinator.last_update_success_time + timedelta(seconds=60),
        ),
        patch("custom_components.google_keep_sync._LOGGER") as mock_logger,
    ):
        # Simulate the service call
        await async_service_request_sync(coordinator, None)
        assert coordinator.async_refresh.called
        mock_logger.info.assert_called_with("Requesting manual sync.")


async def test_async_service_request_sync_too_soon_warning(
    hass: HomeAssistant, mock_api
):
    """Test that a warning is logged if a sync is requested too soon."""
    coordinator = AsyncMock()
    coordinator.last_update_success_time = utcnow()
    coordinator.async_refresh = AsyncMock()

    with (
        patch(
            "custom_components.google_keep_sync.utcnow",
            return_value=coordinator.last_update_success_time + timedelta(seconds=50),
        ),
        patch("custom_components.google_keep_sync._LOGGER") as mock_logger,
    ):
        # Simulate the service call
        await async_service_request_sync(coordinator, None)
        assert not coordinator.async_refresh.called
        mock_logger.warning.assert_called()


@pytest.mark.parametrize(
    "test_case",
    [
        # Migration 1: unique_id update (should also remove password and
        # go to version 3)
        {
            "version": 1,
            "unique_id": "oldid",
            "username": "UserA",
            "token": "tok",
            "password": "pw",
            "expected_version": 3,
            "expected_unique_id": "google_keep_sync.usera",
            "expected_data": {"username": "UserA", "token": "tok"},
            "should_fail": False,
        },
        # Migration 2: remove password, token present
        {
            "version": 2,
            "unique_id": "google_keep_sync.userb",
            "username": "UserB",
            "token": "tok2",
            "password": "pw2",
            "expected_version": 3,
            "expected_unique_id": "google_keep_sync.userb",
            "expected_data": {"username": "UserB", "token": "tok2"},
            "should_fail": False,
        },
        # Migration 2: remove password, token missing (should fail)
        {
            "version": 2,
            "unique_id": "google_keep_sync.userc",
            "username": "UserC",
            "token": None,
            "password": "pw3",
            "expected_version": 2,
            "expected_unique_id": "google_keep_sync.userc",
            "expected_data": {"username": "UserC"},
            "should_fail": True,
        },
    ],
)
async def test_async_migrate_entry(hass, test_case):
    """Test config entry migrations for Google Keep Sync."""
    data = {"username": test_case["username"]}
    if test_case["token"] is not None:
        data["token"] = test_case["token"]
    if test_case["password"] is not None:
        data["password"] = test_case["password"]
    entry = MagicMock()
    entry.version = test_case["version"]
    entry.data = data.copy()
    entry.unique_id = test_case["unique_id"]

    def update_entry(e, **kwargs):
        if "data" in kwargs:
            e.data = kwargs["data"]
        if "version" in kwargs:
            e.version = kwargs["version"]
        if "unique_id" in kwargs:
            e.unique_id = kwargs["unique_id"]

    hass.config_entries.async_update_entry = update_entry
    result = await async_migrate_entry(hass, entry)
    if test_case["should_fail"]:
        assert result is False
        assert entry.version == test_case["version"]  # Should not update version
    else:
        assert result is True
        assert entry.version == test_case["expected_version"]
        assert entry.unique_id == test_case["expected_unique_id"]
        for k, v in test_case["expected_data"].items():
            assert entry.data[k] == v
        if "password" not in test_case["expected_data"]:
            assert "password" not in entry.data


def _make_record(msg: str, level: int = logging.WARNING) -> logging.LogRecord:
    return logging.LogRecord(
        name="gkeepapi.node",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


def test_unknown_node_type_filter_drops_target_warning_at_default_level():
    """The 'Unknown node type' warning is dropped when our logger is not at DEBUG."""
    INTEGRATION_LOGGER.setLevel(logging.WARNING)
    assert (
        _filter_unknown_node_type_warning(_make_record("Unknown node type: None"))
        is False
    )


def test_unknown_node_type_filter_preserves_other_warnings():
    """Unrelated gkeepapi warnings pass through."""
    assert _filter_unknown_node_type_warning(_make_record("Some other warning")) is True


def test_unknown_node_type_filter_reroutes_to_debug_when_enabled():
    """At DEBUG, the record is rewritten onto our logger with stack info."""
    INTEGRATION_LOGGER.setLevel(logging.DEBUG)
    try:
        record = _make_record("Unknown node type: None")
        assert _filter_unknown_node_type_warning(record) is True
        assert record.name == INTEGRATION_LOGGER.name
        assert record.levelno == logging.DEBUG
        assert "Unknown node type: None" in record.getMessage()
        assert "Stack:" in record.getMessage()
    finally:
        INTEGRATION_LOGGER.setLevel(logging.NOTSET)
