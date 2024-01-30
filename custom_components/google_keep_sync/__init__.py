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


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Google Keep Sync from a config entry."""
    # Create API instance
    api = GoogleKeepAPI(hass, entry.data["username"], entry.data["password"])

    # Authenticate with the API
    if not await api.authenticate():
        _LOGGER.error("Failed to authenticate Google Keep API")
        return False  # Exit early if authentication fails

    async def _parse_gkeep_data_dict() -> dict[str, dict[str, dict[str, str]]]:
        """Parse unchecked gkeep api data to a dictionary."""
        todo_lists = {}

        # for each list
        for glist in coordinator.data or []:
            # get all the unchecked items only
            items = {
                item.id: {"summary": item.text, "checked": item.checked}
                for item in glist.items
                if not item.checked
            }
            todo_lists[glist.id] = {"name": glist.title, "items": items}
        return todo_lists

    async def _check_gkeep_lists_changes(original_lists, updated_lists) -> None:
        """Compare original_lists and updated_lists lists.

        Report on any new TodoItem's that have been added to any
        lists in updated_lists that are not in original_lists.
        """
        # for each list
        for upldated_list_id, upldated_list in updated_lists.items():
            if upldated_list_id not in original_lists:
                _LOGGER.debug(
                    "Found new list not in original: %s", upldated_list["name"]
                )
                continue

            # for each todo item in the list
            for upldated_list_item_id, upldated_list_item in upldated_list[
                "items"
            ].items():
                # if todo is not in original list, then it is new
                if (
                    upldated_list_item_id
                    not in original_lists[upldated_list_id]["items"]
                ):
                    list_prefix = entry.data.get("list_prefix", "")
                    data = {
                        "item_name": upldated_list_item["summary"],
                        "item_id": upldated_list_item_id,
                        "item_checked": upldated_list_item["checked"],
                        "list_name": (f"{list_prefix} " if list_prefix else "")
                        + upldated_list["name"],
                        "list_id": upldated_list_id,
                    }

                    _LOGGER.debug("Found new TodoItem: %s", data)
                    hass.bus.async_fire("google_keep_sync_new_item", data)

    # Define the update method for the coordinator
    async def async_update_data():
        """Fetch data from API."""
        try:
            # save lists prior to syncing
            original_lists = await _parse_gkeep_data_dict()
            # Directly call the async_sync_data method
            lists_to_sync = entry.data.get("lists_to_sync", [])
            result = await api.async_sync_data(lists_to_sync)
            # save lists after syncing
            updated_lists = await _parse_gkeep_data_dict()
            # compare both list for changes
            await _check_gkeep_lists_changes(original_lists, updated_lists)

            return result
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
