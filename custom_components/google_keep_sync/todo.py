"""Platform for creating to do list entries based on Google Keep lists."""

import logging

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

from .const import DOMAIN
from .coordinator import GoogleKeepSyncCoordinator

_LOGGER = logging.getLogger(__name__)


class GoogleKeepTodoListEntity(
    CoordinatorEntity[GoogleKeepSyncCoordinator], TodoListEntity
):
    """A To-do List representation of a Google Keep List."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        gkeep_list: gkeepapi.node.List,
        list_prefix: str,
    ):
        """Initialize the Google Keep Todo List Entity."""
        super().__init__(coordinator)
        self.api = coordinator.api
        self._gkeep_list = gkeep_list
        self._gkeep_list_id = gkeep_list.id
        self._attr_name = (
            f"{list_prefix} " if list_prefix else ""
        ) + f"{gkeep_list.title}"
        self._attr_unique_id = f"{DOMAIN}.list.{gkeep_list.id}"

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items from Google Keep."""
        list_id = self._gkeep_list_id

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
        await self.coordinator.async_refresh()
        _LOGGER.debug("Requested data refresh.")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item in Google Keep."""
        try:
            list_id = self._gkeep_list_id
            item_id = item.uid
            new_text = item.summary
            checked = item.status == TodoItemStatus.COMPLETED

            # Update Google Keep in the background
            await self.api.async_update_todo_item(list_id, item_id, new_text, checked)
            _LOGGER.debug("Successfully updated item in Google Keep.")

        except Exception as e:
            _LOGGER.error("Failed to update item in Google Keep: %s", e)

        finally:
            # Resync data with Google Keep
            await self.coordinator.async_refresh()
            _LOGGER.debug("Requested data refresh and updated Home Assistant UI.")

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new todo item in Google Keep."""
        list_id = self._gkeep_list_id
        text = item.summary

        try:
            # Create the new item in the specified list
            await self.api.async_create_todo_item(list_id, text)

            _LOGGER.debug(
                "Successfully created new item in Google Keep and updated locally."
            )

        except Exception as e:
            _LOGGER.error("Failed to create new item in Google Keep: %s", e)

        finally:
            # Request refresh to synchronize with Google Keep
            await self.coordinator.async_refresh()
            _LOGGER.debug("Requested data refresh and updated Home Assistant UI.")

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get the current set of To-do items."""
        # if self._gkeep_list.id not in self.coordinator.data:
        #     _LOGGER.warning(
        #     "Unable to load data for Google Keep list: %s", self._gkeep_list.summary
        #     )
        #     return []

        return [
            TodoItem(
                summary=item.text,
                uid=item.id,
                status=(
                    TodoItemStatus.COMPLETED
                    if item.checked
                    else TodoItemStatus.NEEDS_ACTION
                ),
            )
            for item in self._gkeep_list.items
        ]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Keep todo platform."""
    coordinator: GoogleKeepSyncCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Retrieve user-selected lists from the configuration
    selected_lists = entry.data.get("lists_to_sync", [])
    list_prefix = entry.data.get("list_prefix", "")

    # Filter Google Keep lists based on user selection
    all_lists = await coordinator.api.fetch_all_lists()
    lists_to_sync = [lst for lst in all_lists if lst.id in selected_lists]

    async_add_entities(
        [
            GoogleKeepTodoListEntity(coordinator, list, list_prefix)
            for list in lists_to_sync
        ]
    )
