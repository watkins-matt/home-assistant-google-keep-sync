"""DataUpdateCoordinator for the Google Keep Sync component."""

import logging
from datetime import timedelta

from gkeepapi.node import List as GKeepList
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoogleKeepAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GoogleKeepSyncCoordinator(DataUpdateCoordinator[list[GKeepList]]):
    """Coordinator for updating task data from Google Keep."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: GoogleKeepAPI,
    ) -> None:
        """Initialize the Google Keep Todo coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )
        self.api = api

    # Define the update method for the coordinator
    async def _async_update_data(self) -> list[GKeepList]:
        """Fetch data from API."""
        try:
            # save lists prior to syncing
            original_lists = await self._parse_gkeep_data_dict()
            # Directly call the async_sync_data method
            lists_to_sync = self.config_entry.data.get("lists_to_sync", [])
            result = await self.api.async_sync_data(lists_to_sync)
            # save lists after syncing
            updated_lists = await self._parse_gkeep_data_dict()
            # compare both list for changes
            await self._check_gkeep_lists_changes(original_lists, updated_lists)

            return result
        except Exception as error:
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    async def _parse_gkeep_data_dict(self) -> dict[str, dict[str, dict[str, str]]]:
        """Parse unchecked gkeep api data to a dictionary."""
        todo_lists = {}

        # for each list
        for glist in self.data or []:
            # get all the unchecked items only
            items = {
                item.id: {"summary": item.text, "checked": item.checked}
                for item in glist.items
                if not item.checked
            }
            todo_lists[glist.id] = {"name": glist.title, "items": items}
        return todo_lists

    async def _check_gkeep_lists_changes(self, original_lists, updated_lists) -> None:
        """Compare original_lists and updated_lists lists.

        Report on any new TodoItem's that have been added to any
        lists in updated_lists that are not in original_lists.
        """
        # for each list
        for updated_list_id, upldated_list in updated_lists.items():
            if updated_list_id not in original_lists:
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
                    not in original_lists[updated_list_id]["items"]
                ):
                    list_prefix = self.config_entry.data.get("list_prefix", "")
                    data = {
                        "item_name": upldated_list_item["summary"],
                        "item_id": upldated_list_item_id,
                        "item_checked": upldated_list_item["checked"],
                        "list_name": (f"{list_prefix} " if list_prefix else "")
                        + upldated_list["name"],
                        "list_id": updated_list_id,
                    }

                    _LOGGER.debug("Found new TodoItem: %s", data)
                    self.hass.bus.async_fire("google_keep_sync_new_item", data)
