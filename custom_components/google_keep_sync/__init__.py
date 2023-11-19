"""Integration for synchronization with Google Keep."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoogleKeepAPI
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.TODO]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Keep Sync from a config entry."""
    # Create API instance
    api = GoogleKeepAPI(hass, entry.data["username"], entry.data["password"])

    # Authenticate with the API
    if not await api.authenticate():
        _LOGGER.error("Failed to authenticate Google Keep API")
        return False  # Exit early if authentication fails

    # Define the update method for the coordinator
    async def async_update_data():
        """Fetch data from API."""
        try:
            # Directly call the async_sync_data method
            return await api.async_sync_data()
        except Exception as error:
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    # Create the coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Google Keep",
        update_method=async_update_data,
        update_interval=timedelta(minutes=15),
    )

    # Start the data update coordinator
    await coordinator.async_refresh()

    # Store the API and coordinator objects in hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Forward the setup to the todo platform
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
