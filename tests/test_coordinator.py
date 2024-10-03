"""Unit tests for the todo component."""

import logging
from typing import List
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import EventOrigin
from homeassistant.helpers import entity_registry
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.google_keep_sync.api import GoogleKeepAPI
from custom_components.google_keep_sync.const import DOMAIN
from custom_components.google_keep_sync.coordinator import (
    GoogleKeepSyncCoordinator,
    TodoItem,
    TodoItemData,
    TodoList,
)


@pytest.fixture
def mock_hass():
    """Fixture for mocking Home Assistant."""
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job.side_effect = lambda f, *args, **kwargs: f(
        *args, **kwargs
    )
    mock_hass.config_entries = MagicMock()
    mock_hass.config_entries.async_update_entry = AsyncMock()
    return mock_hass


@pytest.fixture
def mock_api():
    """Fixture for a mocked GoogleKeepAPI."""
    api = MagicMock(spec=GoogleKeepAPI)
    api.async_create_todo_item = AsyncMock()
    return api


@pytest.fixture
def mock_config_entry():
    """Fixture for a mocked ConfigEntry."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.data = {
        "list_prefix": "Test",
        "lists_to_sync": ["list1", "list2", "list3"],
        "list_auto_sort": False,
        "list_item_case": "NO_CHANGE",
    }
    return config_entry


async def test_async_update_data(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test update_data method with debugging."""
    # Create MagicMock objects for the lists
    mock_list1 = MagicMock()
    mock_list1.id = "1"
    mock_list1.title = "list1"
    mock_list2 = MagicMock()
    mock_list2.id = "2"
    mock_list2.title = "list2"

    mock_lists = [mock_list1, mock_list2]

    # Directly assign an AsyncMock to async_sync_data
    mock_api.async_sync_data = AsyncMock(return_value=(mock_lists, []))

    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.config_entry = mock_config_entry
    coordinator.config_entry.data = {
        "list_prefix": "Test",
        "lists_to_sync": ["1", "2"],
    }

    # Mock the entity registry
    mock_entity_registry = MagicMock()
    mock_entity_registry.async_update_entity = AsyncMock()

    # Add debug logging
    logging.getLogger().setLevel(logging.DEBUG)

    with patch(
        "google_keep_sync.coordinator.async_get_entity_registry",
        return_value=mock_entity_registry,
    ), patch.object(
        coordinator, "_update_entity_names", wraps=coordinator._update_entity_names
    ):
        # Define side_effect for async_get_entity_id
        def get_entity_id(platform, domain, unique_id):
            if unique_id == "google_keep_sync.list.1":
                return "todo.test_entity1"
            elif unique_id == "google_keep_sync.list.2":
                return "todo.test_entity2"
            return None

        mock_entity_registry.async_get_entity_id.side_effect = get_entity_id

        # Define side_effect for async_get
        def get_entity(entity_id):
            if entity_id == "todo.test_entity1":
                mock_entity1 = MagicMock(
                    spec_set=["entity_id", "name", "original_name"]
                )
                mock_entity1.entity_id = "todo.test_entity1"
                mock_entity1.name = None  # Indicates no user-defined name
                mock_entity1.original_name = "Old Name 1"
                return mock_entity1
            elif entity_id == "todo.test_entity2":
                mock_entity2 = MagicMock(
                    spec_set=["entity_id", "name", "original_name"]
                )
                mock_entity2.entity_id = "todo.test_entity2"
                mock_entity2.name = None
                mock_entity2.original_name = "Old Name 2"
                return mock_entity2
            return None

        mock_entity_registry.async_get.side_effect = get_entity

        # Execute the method under test
        result = await coordinator._async_update_data()

    # Assertions
    assert result == mock_lists
    mock_api.async_sync_data.assert_called_once()


async def test_parse_gkeep_data_dict_empty(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test _parse_gkeep_data_dict when empty."""
    test_input: dict = {}
    expected: dict = {}
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = test_input

    actual = await coordinator._parse_gkeep_data_dict()
    assert actual == expected


async def test_parse_gkeep_data_dict_normal(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test _parse_gkeep_data_dict with data."""
    mock_list = MagicMock(id="grocery_list_id", title="Grocery List")
    mock_item = MagicMock(id="milk_item_id", text="Milk", checked=False)
    mock_list.items = [mock_item]
    expected = {
        "grocery_list_id": TodoList(
            name="Grocery List",
            items={"milk_item_id": TodoItem(summary="Milk", checked=False)},
        )
    }

    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [mock_list]

    actual = await coordinator._parse_gkeep_data_dict()
    assert actual == expected


async def test_get_new_items_added(
    mock_api: MagicMock,
    mock_hass: MagicMock,
    mock_config_entry: MockConfigEntry,
):
    """Test handling new items added to a list."""
    # Set up coordinator and mock API
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)

    list1 = {
        "grocery_list_id": TodoList(
            name="Grocery List",
            items={"milk_item_id": TodoItem(summary="Milk", checked=False)},
        )
    }
    list2 = {
        "grocery_list_id": TodoList(
            name="Grocery List",
            items={
                "milk_item_id": TodoItem(summary="Milk", checked=False),
                "bread_item_id": TodoItem(summary="Bread", checked=False),
            },
        )
    }

    with patch.object(entity_registry, "async_get") as er:
        instance = er.return_value
        instance.async_get_entity_id.return_value = "list_entity_id"

        # Call method under test
        # callback = MagicMock()
        new_items = await coordinator._get_new_items_added(list1, list2)

        # Assertions
        expected = [
            TodoItemData(
                item="Bread",
                entity_id="list_entity_id",
            )
        ]
        assert new_items == expected


async def test_get_new_items_not_added(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test handling when no new items are added to a list."""
    # Set up coordinator and mock API
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)

    list1 = {
        "grocery_list_id": TodoList(
            name="Grocery List",
            items={"milk_item_id": TodoItem(summary="Milk", checked=False)},
        )
    }

    # Call method under test
    new_items = await coordinator._get_new_items_added(list1, list1)

    # Assertions
    assert new_items == []


async def test_notify_new_items(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test sending notifications of new items added to a list."""
    # Set up coordinator and mock API
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)

    new_items = [
        TodoItemData(
            item="Bread",
            entity_id="list_entity_id",
        )
    ]
    # Call method under test
    await coordinator._notify_new_items(new_items)

    expected = {
        "domain": "todo",
        "service": "add_item",
        "service_data": {
            "item": "Bread",
            "entity_id": ["list_entity_id"],
        },
    }

    # Assertions
    mock_hass.bus.async_fire.assert_called_once_with(
        EVENT_CALL_SERVICE, expected, origin=EventOrigin.remote
    )


async def test_no_deleted_lists(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that entities and config remain the same when lists are not deleted."""
    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_list2 = MagicMock(id="list2", title="List 2")
    mock_lists = [mock_list1, mock_list2]

    # Mock the API to return no deleted lists
    mock_api.async_sync_data = AsyncMock(return_value=(mock_lists, []))

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = mock_lists.copy()

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.return_value = {
            "list1": TodoList(name="List 1", items={}),
            "list2": TodoList(name="List 2", items={}),
        }

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ):
            # Execute the update
            await coordinator.async_refresh()

            # Assertions
            assert coordinator.data == mock_lists
            mock_api.async_sync_data.assert_called_once()

            # Ensure no entities were removed
            mock_entity_registry.async_remove.assert_not_called()

            # Ensure configuration was not updated
            mock_hass.config_entries.async_update_entry.assert_not_called()


async def test_some_deleted_lists(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that list deletion results in entity removal and config change."""
    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_list3 = MagicMock(id="list3", title="List 3")
    mock_synced_lists = [mock_list1, mock_list3]
    deleted_list_ids = ["list2"]

    # Mock the API to return some deleted lists
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [mock_list1, MagicMock(id="list2", title="List 2"), mock_list3]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
                "list2": TodoList(name="List 2", items={}),
                "list3": TodoList(name="List 3", items={}),
            },
            {
                "list1": TodoList(name="List 1", items={}),
                "list3": TodoList(name="List 3", items={}),
            },
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)
        # Assume list2 has an entity
        mock_entity_registry.async_get_entity_id.return_value = "todo.list.list2"
        mock_entity_registry.async_remove = AsyncMock()
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ):
            # Execute the update
            await coordinator.async_refresh()

            # Assertions
            assert coordinator.data == mock_synced_lists
            mock_api.async_sync_data.assert_called_once()

            # Ensure async_remove was called for list2
            mock_entity_registry.async_remove.assert_called_once_with("todo.list.list2")

            # Ensure configuration was updated to remove list2
            updated_lists = ["list1", "list3"]
            mock_hass.config_entries.async_update_entry.assert_called_once_with(
                mock_config_entry,
                data={**mock_config_entry.data, "lists_to_sync": updated_lists},
            )


async def test_all_deleted_lists(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that all entities and config are removed when all lists are deleted."""
    # Initialize mock_config_entry.data
    mock_config_entry.data = {
        "list_prefix": "Test",
        "lists_to_sync": ["list1", "list2", "list3"],
        "list_auto_sort": False,
        "list_item_case": "NO_CHANGE",
    }

    # Setup mock lists
    mock_synced_lists: List[MagicMock] = []
    deleted_list_ids = ["list1", "list2", "list3"]

    # Mock the API to return all lists as deleted
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [
        MagicMock(id="list1", title="List 1"),
        MagicMock(id="list2", title="List 2"),
        MagicMock(id="list3", title="List 3"),
    ]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
                "list2": TodoList(name="List 2", items={}),
                "list3": TodoList(name="List 3", items={}),
            },
            {},  # After deletion
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)

        # Assume all lists have entities
        def get_entity_id(platform, domain, unique_id):
            return f"todo.list.{unique_id.split('.')[-1]}"

        mock_entity_registry.async_get_entity_id.side_effect = get_entity_id
        mock_entity_registry.async_remove = AsyncMock()
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ):
            # Execute the update
            await coordinator.async_refresh()

            # Assertions
            assert coordinator.data == mock_synced_lists
            mock_api.async_sync_data.assert_called_once()

            # Ensure async_remove was called for all deleted lists
            expected_calls = [
                call("todo.list.list1"),
                call("todo.list.list2"),
                call("todo.list.list3"),
            ]
            actual_calls = mock_entity_registry.async_remove.call_args_list
            assert actual_calls == expected_calls

            # Ensure configuration was updated to remove all lists
            updated_lists: List[str] = []
            mock_hass.config_entries.async_update_entry.assert_called_once_with(
                mock_config_entry,
                data={**mock_config_entry.data, "lists_to_sync": updated_lists},
            )


async def test_deleted_lists_without_entities(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that coordinator deletes lists without corresponding entities."""
    # Initialize mock_config_entry.data
    mock_config_entry.data = {
        "list_prefix": "Test",
        "lists_to_sync": ["list1", "list2", "list3"],
        "list_auto_sort": False,
        "list_item_case": "NO_CHANGE",
    }

    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_list3 = MagicMock(
        id="list3", title="List 3"
    )  # Assuming list3 is part of the data
    mock_synced_lists = [mock_list1, mock_list3]
    deleted_list_ids = ["list2"]  # Assume list2 exists but has no entity

    # Mock the API to return some deleted lists
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [
        mock_list1,
        MagicMock(id="list2", title="List 2"),
        mock_list3,
    ]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
                "list2": TodoList(name="List 2", items={}),
                "list3": TodoList(name="List 3", items={}),
            },
            {
                "list1": TodoList(name="List 1", items={}),
                "list3": TodoList(name="List 3", items={}),
            },
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)

        # Assume list2 does not have an entity
        def get_entity_id(platform, domain, unique_id):
            if unique_id.endswith("list2"):
                return None
            return f"todo.list.{unique_id.split('.')[-1]}"

        mock_entity_registry.async_get_entity_id.side_effect = get_entity_id
        mock_entity_registry.async_remove = AsyncMock()
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ):
            # Execute the update
            await coordinator.async_refresh()

            # Assertions
            assert coordinator.data == mock_synced_lists
            mock_api.async_sync_data.assert_called_once()

            # Ensure async_remove was not called since list2 has no entity
            mock_entity_registry.async_remove.assert_not_called()

            # Ensure configuration was updated to remove list2
            updated_lists = ["list1", "list3"]
            mock_hass.config_entries.async_update_entry.assert_called_once_with(
                mock_config_entry,
                data={**mock_config_entry.data, "lists_to_sync": updated_lists},
            )


async def test_exception_during_entity_removal(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test coordinator's behavior when an exception occurs during entity removal."""
    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_synced_lists: List[MagicMock] = []
    deleted_list_ids = ["list1"]

    # Mock the API to return some deleted lists
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [mock_list1]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
            },
            {},  # After deletion
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)
        # Assume list1 has an entity
        mock_entity_registry.async_get_entity_id.return_value = "todo.list.list1"
        # Mock async_remove to raise an exception
        mock_entity_registry.async_remove.side_effect = Exception("Removal failed")
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ), patch(
            "custom_components.google_keep_sync.coordinator._LOGGER",
            new_callable=MagicMock,
        ) as mock_logger:
            # Execute the update and expect an UpdateFailed exception
            with pytest.raises(
                UpdateFailed,
                match="Error communicating with API: Removal failed",
            ):
                await coordinator._async_update_data()

            # Assertions
            mock_api.async_sync_data.assert_called_once()

            # Ensure async_remove was called
            mock_entity_registry.async_remove.assert_called_once_with("todo.list.list1")

            # Ensure configuration was not updated due to the exception
            mock_hass.config_entries.async_update_entry.assert_not_called()

            # Ensure the error was logged
            mock_logger.error.assert_called_with(
                "Error communicating with API: %s",
                mock_entity_registry.async_remove.side_effect,
                exc_info=True,
            )


async def test_notify_new_items_deleted_lists(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that notifications are not sent when handling deleted lists."""
    # This test ensures that when lists are deleted,
    # no new item notifications are triggered.

    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_synced_lists = [mock_list1]
    deleted_list_ids = ["list2"]

    # Mock the API to return some deleted lists
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [mock_list1, MagicMock(id="list2", title="List 2")]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
                "list2": TodoList(name="List 2", items={}),
            },
            {
                "list1": TodoList(name="List 1", items={}),
            },
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)
        mock_entity_registry.async_get_entity_id.return_value = "todo.list.list2"
        mock_entity_registry.async_remove = AsyncMock()
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ):
            # Execute the update
            await coordinator.async_refresh()

            # Ensure that no new item notifications were sent
            mock_hass.bus.async_fire.assert_not_called()


async def test_handle_deleted_lists_logging(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test that appropriate logs are generated when handling deleted lists."""
    # Setup mock lists
    mock_list1 = MagicMock(id="list1", title="List 1")
    mock_synced_lists: List[MagicMock] = []
    deleted_list_ids = ["list1"]

    # Mock the API to return some deleted lists
    mock_api.async_sync_data = AsyncMock(
        return_value=(mock_synced_lists, deleted_list_ids)
    )

    # Initialize the coordinator
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
    coordinator.data = [mock_list1]

    # Mock parsing of Google Keep data
    with patch.object(
        coordinator, "_parse_gkeep_data_dict", new_callable=AsyncMock
    ) as mock_parse:
        mock_parse.side_effect = [
            {
                "list1": TodoList(name="List 1", items={}),
            },
            {},  # After deletion
        ]

        # Mock entity registry
        mock_entity_registry = MagicMock(spec=entity_registry.EntityRegistry)
        mock_entity_registry.async_get_entity_id.return_value = "todo.list.list1"
        mock_entity_registry.async_remove = AsyncMock()
        with patch(
            "custom_components.google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ), patch(
            "custom_components.google_keep_sync.coordinator._LOGGER",
            new_callable=MagicMock,
        ) as mock_logger:
            # Execute the update
            await coordinator.async_refresh()

            # Assertions
            mock_api.async_sync_data.assert_called_once()
            mock_entity_registry.async_remove.assert_called_once_with("todo.list.list1")
            mock_logger.warning.assert_called_with(
                f"The following lists were deleted: {deleted_list_ids}"
            )
            mock_logger.info.assert_called_with(
                "Updated configuration entry to remove deleted lists: "
                f"{deleted_list_ids}"
            )
