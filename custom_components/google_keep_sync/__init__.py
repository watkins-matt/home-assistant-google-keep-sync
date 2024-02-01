"""Integration for synchronization with Google Keep."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import GoogleKeepAPI
from .const import DOMAIN
from .coordinator import GoogleKeepSyncCoordinator

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

    # Create the coordinator
    coordinator = GoogleKeepSyncCoordinator(hass, api)

    # Start the data update coordinator
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator object in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward the setup to the todo platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
