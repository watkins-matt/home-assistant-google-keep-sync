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
    api = GoogleKeepAPI(
        hass,
        entry.data["username"],
        entry.data.get("token"),
    )

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to new format."""
    version = entry.version
    data = dict(entry.data)
    unique_id = entry.unique_id
    updated = False

    # Migration 1: unique_id format
    if version == 1:
        if unique_id and not unique_id.startswith(f"{DOMAIN}."):
            new_unique_id = f"{DOMAIN}.{data['username'].lower()}"
            hass.config_entries.async_update_entry(entry, unique_id=new_unique_id)
            updated = True
        version = 2

    # Migration 2: Remove password, enforce token
    migration_version_token_required = 2
    migration_version_latest = 3
    if version == migration_version_token_required:
        if "password" in data:
            data.pop("password")
            updated = True
        token = data.get("token")
        if not token:
            # No token present, migration cannot continue
            _LOGGER.error(
                "Google Keep Sync config entry migration failed: token is required. "
                "Please update your integration to use a token."
            )
            return False
        version = migration_version_latest

    if updated or entry.version != version:
        hass.config_entries.async_update_entry(entry, data=data, version=version)
        _LOGGER.info("Migrated Google Keep Sync config entry to version %d", version)
    return True
