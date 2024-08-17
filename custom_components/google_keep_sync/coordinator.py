"""DataUpdateCoordinator for the Google Keep Sync component."""

import logging
from collections import namedtuple

from gkeepapi.node import List as GKeepList
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CALL_SERVICE, Platform
from homeassistant.core import EventOrigin, HomeAssistant
from homeassistant.helpers import entity_registry
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import GoogleKeepAPI, ListCase
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
TodoItem = namedtuple("TodoItem", ["summary", "checked"])
TodoList = namedtuple("TodoList", ["name", "items"])
TodoItemData = namedtuple("TodoItemData", ["item", "entity_id"])


class GoogleKeepSyncCoordinator(TimestampDataUpdateCoordinator[list[GKeepList]]):
    """Coordinator for updating task data from Google Keep."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: GoogleKeepAPI,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Google Keep Todo coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.config_entry = entry
        _LOGGER.debug("GoogleKeepSyncCoordinator initialized")

    # Define the update method for the coordinator
    async def _async_update_data(self) -> list[GKeepList]:
        """Fetch data from API."""
        try:
            _LOGGER.debug("Starting data update process")

            # Save lists prior to syncing
            original_lists = await self._parse_gkeep_data_dict()
            _LOGGER.debug("Parsed original lists: %d lists found", len(original_lists))

            # Sync data with Google Keep
            lists_to_sync = self.config_entry.data.get("lists_to_sync", [])
            auto_sort = self.config_entry.data.get("list_auto_sort", False)
            change_case = self.config_entry.data.get(
                "list_item_case", ListCase.NO_CHANGE
            )

            _LOGGER.debug(
                "Syncing data with Google Keep. Lists to sync: %d, Auto sort: %s, Change case: %s",
                len(lists_to_sync),
                auto_sort,
                change_case,
            )

            result = await self.api.async_sync_data(
                lists_to_sync, auto_sort, change_case
            )
            _LOGGER.debug("Data sync completed. Received %d lists", len(result))

            # save lists after syncing
            updated_lists = await self._parse_gkeep_data_dict()
            _LOGGER.debug("Parsed updated lists: %d lists found", len(updated_lists))

            # compare both list for changes, and fire event for changes
            new_items = await self._get_new_items_added(
                original_lists,
                updated_lists,
            )
            _LOGGER.debug("Found %d new items", len(new_items))

            await self._notify_new_items(new_items)

            return result
        except Exception as error:
            _LOGGER.error("Error communicating with API: %s", error, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {error}") from error

    async def _parse_gkeep_data_dict(self) -> dict[str, TodoList]:
        """Parse unchecked gkeep data to a dictionary, with the list id as the key."""
        _LOGGER.debug("Parsing Google Keep data")
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
            _LOGGER.debug(
                "Parsed list '%s': %d unchecked items", keep_list.title, len(items)
            )

        _LOGGER.debug(
            "Finished parsing Google Keep data: %d lists", len(all_keep_lists)
        )
        return all_keep_lists

    async def _get_new_items_added(
        self,
        original_lists: dict[str, TodoList],
        updated_lists: dict[str, TodoList],
    ) -> list[TodoItemData]:
        """Compare original and updated lists to find new TodoItems.

        For each new TodoItem found, call the provided on_new_item callback.

        :param original_lists: The original todo list data.
        :param updated_lists: The updated todo list data.
        # :param on_new_item: Callback function to execute for each new item found.
        """
        _LOGGER.debug("Comparing original and updated lists to find new items")
        new_items = []
        # for each list
        for updated_list_id, updated_list in updated_lists.items():
            if updated_list_id not in original_lists:
                _LOGGER.debug("Found new list not in original: %s", updated_list.name)
                continue

            # for each todo item in the list
            updated_list_item: TodoItem
            for (
                updated_list_item_id,
                updated_list_item,
            ) in updated_list.items.items():
                # get original list with updated_list_id
                original_list = original_lists[updated_list_id]

                # if todo is not in original list, then it is new
                if updated_list_item_id not in original_list.items:
                    # Get HA List entity_id for _gkeep_list_id
                    entity_reg = entity_registry.async_get(self.hass)
                    uuid = f"{DOMAIN}.list.{updated_list_id}"
                    list_entity_id = entity_reg.async_get_entity_id(
                        Platform.TODO, DOMAIN, uuid
                    )
                    new_items.append(
                        TodoItemData(
                            item=updated_list_item.summary, entity_id=list_entity_id
                        )
                    )

                    _LOGGER.debug(
                        "Found new TodoItem: '%s' in List entity_id: '%s'",
                        updated_list_item.summary,
                        list_entity_id,
                    )

        _LOGGER.debug("Finished comparing lists. Found %d new items", len(new_items))
        return new_items

    async def _notify_new_items(self, new_items: list[TodoItemData]) -> None:
        """Emit add_item service call event for new remote Todo items."""
        _LOGGER.debug("Notifying about %d new items", len(new_items))
        for new_item in new_items:
            event_data = {
                "domain": "todo",
                "service": "add_item",
                "service_data": {
                    "item": new_item.item,
                    "entity_id": [new_item.entity_id],
                },
            }
            self.hass.bus.async_fire(
                EVENT_CALL_SERVICE, event_data, origin=EventOrigin.remote
            )
            _LOGGER.debug(
                "Fired add_item event for item: '%s' in entity: '%s'",
                new_item.item,
                new_item.entity_id,
            )

        _LOGGER.debug("Finished notifying about new items")
