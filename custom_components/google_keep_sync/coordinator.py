"""DataUpdateCoordinator for the Google Keep Sync component."""

import logging
from collections import namedtuple
from collections.abc import Callable
from datetime import timedelta

from gkeepapi.node import List as GKeepList
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoogleKeepAPI
from .const import DOMAIN, EVENT_NEW_ITEM

_LOGGER = logging.getLogger(__name__)
TodoItem = namedtuple("TodoItem", ["summary", "checked"])
TodoList = namedtuple("TodoList", ["name", "items"])
TodoItemData = namedtuple(
    "TodoItemData", ["item_name", "item_id", "item_checked", "list_name", "list_id"]
)


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

            # Sync data with Google Keep
            lists_to_sync = self.config_entry.data.get("lists_to_sync", [])
            auto_sort = self.config_entry.data.get("list_auto_sort", False)
            result = await self.api.async_sync_data(lists_to_sync, auto_sort)

            # save lists after syncing
            updated_lists = await self._parse_gkeep_data_dict()
            # compare both list for changes, and fire event for changes
            await self._handle_new_items_added(
                original_lists,
                updated_lists,
                self.config_entry.data.get("list_prefix", ""),
                lambda item_data: self.hass.bus.async_fire(EVENT_NEW_ITEM, item_data),
            )

            return result
        except Exception as error:
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    async def _parse_gkeep_data_dict(self) -> dict[str, TodoList]:
        """Parse unchecked gkeep data to a dictionary, with the list id as the key."""
        all_keep_lists = {}

        # for each list
        for keep_list in self.data or []:
            # get all the unchecked items only
            items = {
                item.id: TodoItem(summary=item.text, checked=item.checked)
                for item in keep_list.items
                if not item.checked
            }
            all_keep_lists[keep_list.id] = TodoList(name=keep_list.title, items=items)
        return all_keep_lists

    async def _handle_new_items_added(
        self,
        original_lists: dict[str, TodoList],
        updated_lists: dict[str, TodoList],
        list_prefix: str,
        on_new_item: Callable[[TodoItemData], None],
    ) -> None:
        """Compare original and updated lists to find new TodoItems.

        For each new TodoItem found, call the provided on_new_item callback.

        :param original_lists: The original todo list data.
        :param updated_lists: The updated todo list data.
        # :param on_new_item: Callback function to execute for each new item found.
        """
        # for each list
        for updated_list_id, upldated_list in updated_lists.items():
            if updated_list_id not in original_lists:
                _LOGGER.debug("Found new list not in original: %s", upldated_list.name)
                continue

            # for each todo item in the list
            upldated_list_item: TodoItem
            for (
                upldated_list_item_id,
                upldated_list_item,
            ) in upldated_list.items.items():
                # get original list with updated_list_id
                original_list = original_lists[updated_list_id]

                # if todo is not in original list, then it is new
                if upldated_list_item_id not in original_list.items:
                    item_data = TodoItemData(
                        item_name=upldated_list_item.summary,
                        item_id=upldated_list_item_id,
                        item_checked=upldated_list_item.checked,
                        list_name=(f"{list_prefix} " if list_prefix else "")
                        + upldated_list.name,
                        list_id=updated_list_id,
                    )

                    _LOGGER.debug("Found new TodoItem: %s", item_data)
                    on_new_item(item_data)
