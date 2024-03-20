"""Integration for synchronization with Google Keep."""

from __future__ import annotations

import logging
from functools import partial

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import as_timestamp, utcnow

from .api import GoogleKeepAPI
from .const import DOMAIN
from .coordinator import GoogleKeepSyncCoordinator

PLATFORMS: list[Platform] = [Platform.TODO]

_LOGGER = logging.getLogger(__name__)


async def async_service_request_sync(coordinator: GoogleKeepSyncCoordinator, call):
    """Handle the request_sync call."""
    sync_threshold = 55
    last_update_timestamp = as_timestamp(coordinator.last_update_success_time)
    seconds_since_update = as_timestamp(utcnow()) - last_update_timestamp

    if seconds_since_update > sync_threshold:
        _LOGGER.info("Requesting manual sync.")
        await coordinator.async_refresh()
    else:
        time_to_next_allowed_update = round(sync_threshold - seconds_since_update)
        _LOGGER.warning(
            "Requesting sync too soon after last update."
            f" Try again in {time_to_next_allowed_update} seconds."
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Keep Sync from a config entry."""
    # Create API instance
    api = GoogleKeepAPI(hass, entry.data["username"], entry.data["password"])

    # Authenticate with the API
    if not await api.authenticate():
        _LOGGER.error("Failed to authenticate Google Keep API")
        return False  # Exit early if authentication fails

    # Create the coordinator
    coordinator = GoogleKeepSyncCoordinator(hass, api, entry)

    # Start the data update coordinator
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator object in hass.data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register the request_sync service
    hass.services.async_register(
        DOMAIN, "request_sync", partial(async_service_request_sync, coordinator)
    )

    # Forward the setup to the todo platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
