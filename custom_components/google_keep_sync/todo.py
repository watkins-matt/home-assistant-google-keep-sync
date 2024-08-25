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

        # Set the default entity ID based on the list title.
        # We use a prefix to avoid conflicts with todo entities from other
        # integrations, and so the entities specific to this integration
        # can be filtered easily in developer tools.
        self.entity_id = self._get_default_entity_id(gkeep_list.title)

        _LOGGER.debug(
            "Initialized GoogleKeepTodoListEntity: name='%s', unique_id='%s', "
            "entity_id='%s'",
            self._attr_name,
            self._attr_unique_id,
            self.entity_id,
        )

    def _get_default_entity_id(self, title: str) -> str:
        """Return the entity ID for the given title."""
        entity_id = f"todo.google_keep_{title.lower().replace(' ', '_')}"
        _LOGGER.debug("Generated entity ID: '%s' for title: '%s'", entity_id, title)
        return entity_id

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Delete todo items from Google Keep."""
        _LOGGER.debug(
            "Deleting todo items: %s from list: %s", uids, self._gkeep_list_id
        )
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
        _LOGGER.debug("Requested data refresh after deletions.")

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update a todo item in Google Keep."""
        _LOGGER.debug(
            "Updating todo item: %s in list: %s", item.uid, self._gkeep_list_id
        )
        try:
            list_id = self._gkeep_list_id
            item_id = item.uid
            new_text = item.summary
            checked = item.status == TodoItemStatus.COMPLETED

            # Update Google Keep in the background
            await self.api.async_update_todo_item(list_id, item_id, new_text, checked)
            _LOGGER.debug("Successfully updated item %s in Google Keep.", item_id)

        except Exception as e:
            _LOGGER.error("Failed to update item %s in Google Keep: %s", item.uid, e)

        finally:
            # Resync data with Google Keep
            await self.coordinator.async_refresh()
            _LOGGER.debug("Requested data refresh after update.")

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new todo item in Google Keep."""
        _LOGGER.debug("Creating new todo item in list: %s", self._gkeep_list_id)
        list_id = self._gkeep_list_id
        text = item.summary

        try:
            # Create the new item in the specified list
            await self.api.async_create_todo_item(list_id, text)
            _LOGGER.debug("Successfully created new item '%s' in Google Keep.", text)

        except Exception as e:
            _LOGGER.error("Failed to create new item '%s' in Google Keep: %s", text, e)

        finally:
            # Request refresh to synchronize with Google Keep
            await self.coordinator.async_refresh()
            _LOGGER.debug("Requested data refresh after item creation.")

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for gkeep_list in self.coordinator.data:
            if gkeep_list.id == self._gkeep_list_id:
                self._gkeep_list = gkeep_list
                list_prefix = self.coordinator.config_entry.data.get("list_prefix", "")
                new_name = f"{list_prefix} {gkeep_list.title}".strip()
                if self._attr_name != new_name:
                    self._attr_name = new_name
                break
        super()._handle_coordinator_update()

    @property
    def todo_items(self) -> list[TodoItem]:
        """Get the current set of To-do items, filtering out empty entries."""
        items = [
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
            if item.text
            and len(item.text.strip())
            > 0  # Filter out empty or whitespace-only entries
        ]
        total_items = len(self._gkeep_list.items)
        filtered_items = len(items)
        _LOGGER.debug(
            "Retrieved %d todo items for list: %s",
            filtered_items,
            self._gkeep_list_id,
        )
        if filtered_items < total_items:
            _LOGGER.warning(
                "Filtered out %d empty items from list: %s",
                total_items - filtered_items,
                self._gkeep_list_id,
            )
        return items


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Google Keep todo platform."""
    _LOGGER.debug("Setting up Google Keep todo platform for entry: %s", entry.entry_id)
    coordinator: GoogleKeepSyncCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Retrieve user-selected lists from the configuration
    selected_lists = entry.data.get("lists_to_sync", [])
    list_prefix = entry.data.get("list_prefix", "")
    _LOGGER.debug(
        "User selected %d lists to sync with prefix: '%s'",
        len(selected_lists),
        list_prefix,
    )

    # Filter Google Keep lists based on user selection
    all_lists = await coordinator.api.fetch_all_lists()
    _LOGGER.debug("Fetched %d total lists from Google Keep", len(all_lists))

    lists_to_sync = [lst for lst in all_lists if lst.id in selected_lists]
    _LOGGER.debug("Filtered %d lists for syncing", len(lists_to_sync))

    entities = [
        GoogleKeepTodoListEntity(coordinator, list, list_prefix)
        for list in lists_to_sync
    ]
    _LOGGER.debug("Created %d GoogleKeepTodoListEntity instances", len(entities))

    async_add_entities(entities)
    _LOGGER.debug("Added %d entities to Home Assistant", len(entities))
