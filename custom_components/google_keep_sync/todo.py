"""Platform for creating to do list entries based on Google Keep lists."""
import logging
from datetime import timedelta

import gkeepapi
from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .api import GoogleKeepAPI
from .const import DOMAIN

SCAN_INTERVAL = timedelta(minutes=15)

_LOGGER = logging.getLogger(__name__)


class GoogleKeepTodoListEntity(CoordinatorEntity, TodoListEntity):
    """A To-do List representation of a Google Keep List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self,
        api: GoogleKeepAPI,
        coordinator: DataUpdateCoordinator,
        gkeep_list: gkeepapi.node.List,
        list_prefix: str,
    ):
        """Initialize the Google Keep Todo List Entity."""
        super().__init__(coordinator)
        self.api = api
        self._gkeep_list = gkeep_list
        self._gkeep_list_id = gkeep_list.id
        self._attr_name = (
            f"{list_prefix} " if list_prefix else ""
        ) + f"{gkeep_list.title}"
        self._attr_unique_id = f"{DOMAIN}.list.{gkeep_list.id}"
        self.entity_id = self._get_entity_id(gkeep_list.title)

    def _get_entity_id(self, title: str) -> str:
        """Return the entity ID for the given title."""
        return f"todo.google_keep_{title.lower().replace(' ', '_')}"

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items from Google Keep."""
        list_id = self._gkeep_list_id

        # Update local state first
        for list_data in self.coordinator.data:
            if list_data["id"] == list_id:
                list_data["items"] = [
                    item for item in list_data["items"] if item["id"] not in uids
                ]
                break

        # Update Home Assistant UI immediately after local state update
        self.async_write_ha_state()

        # Perform deletion in Google Keep API for each item
        for item_id in uids:
            try:
                await self.api.async_delete_todo_item(list_id, item_id)
                _LOGGER.debug("Item %s deleted from Google Keep", item_id)
            except Exception as e:
                _LOGGER.error(
                    "Failed to delete item %s from Google Keep: %s", item_id, e
                )

        # Resync data with Google Keep
        await self.coordinator.async_request_refresh()
        _LOGGER.debug("Requested data refresh.")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item in Google Keep."""
        try:
            list_id = self._gkeep_list_id
            item_id = item.uid
            new_text = item.summary
            checked = item.status == TodoItemStatus.COMPLETED

            # Update local state first
            for list_data in self.coordinator.data:
                if list_data["id"] == list_id:
                    for list_item in list_data["items"]:
                        if list_item["id"] == item_id:
                            list_item["text"] = new_text
                            list_item["checked"] = checked
                            break
                    break

            # Update Home Assistant UI immediately after local state update
            self.async_write_ha_state()

            # Update Google Keep in the background
            await self.api.async_update_todo_item(list_id, item_id, new_text, checked)
            _LOGGER.debug("Successfully updated item in Google Keep.")

        except Exception as e:
            _LOGGER.error("Failed to update item in Google Keep: %s", e)

        finally:
            # Resync data with Google Keep
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Requested data refresh and updated Home Assistant UI.")

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new todo item in Google Keep."""
        list_id = self._gkeep_list_id
        text = item.summary

        try:
            # Create item in Google Keep and get the item ID
            new_item_id = await self.api.async_create_todo_item(list_id, text)

            # Update local state
            for list_data in self.coordinator.data:
                if list_data["id"] == list_id:
                    # Add the new item to the local list data
                    new_item = {
                        "id": new_item_id,
                        "text": text,
                        "checked": False,
                    }
                    list_data["items"].append(new_item)
                    break

            # Update Home Assistant UI
            self.async_write_ha_state()

            _LOGGER.debug(
                "Successfully created new item in Google Keep and updated locally."
            )

        except Exception as e:
            _LOGGER.error("Failed to create new item in Google Keep: %s", e)

        finally:
            # Request refresh to synchronize with Google Keep
            await self.coordinator.async_request_refresh()
            _LOGGER.debug("Requested data refresh and updated Home Assistant UI.")

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get the current set of To-do items."""
        # Use the coordinator's data to ensure we have the latest updates.
        updated_list = next(
            (
                list_data
                for list_data in self.coordinator.data
                if list_data["id"] == self._gkeep_list.id
            ),
            None,
        )

        if not updated_list:
            _LOGGER.warning(
                "Unable to load data for Google Keep list: %s", self._gkeep_list.id
            )
            return []

        return [
            TodoItem(
                summary=item["text"],
                uid=item["id"],
                status=TodoItemStatus.COMPLETED
                if item["checked"]
                else TodoItemStatus.NEEDS_ACTION,
            )
            for item in updated_list["items"]
        ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Keep todo platform."""
    api: GoogleKeepAPI = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    # Retrieve user-selected lists from the configuration
    selected_lists = entry.data.get("lists_to_sync", [])
    list_prefix = entry.data.get("list_prefix", "")

    # Filter Google Keep lists based on user selection
    all_lists = await api.fetch_all_lists()
    lists_to_sync = [lst for lst in all_lists if lst.id in selected_lists]

    async_add_entities(
        [
            GoogleKeepTodoListEntity(api, coordinator, list, list_prefix)
            for list in lists_to_sync
        ]
    )
