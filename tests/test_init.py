"""Test the Google Keep Sync setup entry."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.google_keep_sync import async_setup_entry, async_unload_entry
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
        mock_api_instance.async_sync_data = AsyncMock(return_value=True)
        mock_api_instance._store = mock_store
        yield mock_api_instance


async def test_async_setup_entry_successful(
    hass: HomeAssistant, mock_api, mock_config_entry
):
    """Test a successful setup entry."""
    mock_config_entry.add_to_hass(hass)
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
    await async_setup_entry(hass, mock_config_entry)
    assert await async_unload_entry(hass, mock_config_entry)
    assert not hass.data[GOOGLE_KEEP_DOMAIN].get(mock_config_entry.entry_id)
    await hass.async_block_till_done()
