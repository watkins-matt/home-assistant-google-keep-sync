"""Unit tests for the todo component."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import EventOrigin
from homeassistant.helpers import entity_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    return mock_hass


@pytest.fixture
def mock_api():
    """Return a mocked GoogleKeepAPI."""
    api = MagicMock()
    api.async_create_todo_item = MagicMock()
    return api


async def test_async_update_data(
    mock_api: MagicMock, mock_hass: MagicMock, mock_config_entry: MockConfigEntry
):
    """Test update_data method with debugging."""
    with patch.object(mock_api, "async_sync_data", AsyncMock()):
        # Create MagicMock objects for the lists
        mock_list1 = MagicMock()
        mock_list1.id = "1"
        mock_list1.title = "list1"
        mock_list2 = MagicMock()
        mock_list2.id = "2"
        mock_list2.title = "list2"

        mock_lists = [mock_list1, mock_list2]
        mock_api.async_sync_data.return_value = (mock_lists, [])

        coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
        coordinator.config_entry = mock_config_entry
        coordinator.config_entry.data = {
            "list_prefix": "Test",
            "lists_to_sync": ["1", "2"],
        }

        # Mock the entity registry
        mock_entity_registry = MagicMock()

        # Use spec_set to define allowed attributes
        # Entities will be returned based on entity_id in side_effect
        mock_entity_registry.async_update_entity = AsyncMock()

        # Add debug logging
        logging.getLogger().setLevel(logging.DEBUG)

        with patch(
            "google_keep_sync.coordinator.async_get_entity_registry",
            return_value=mock_entity_registry,
        ), patch.object(
            coordinator, "_update_entity_names", wraps=coordinator._update_entity_names
        ) as mock_update_names:

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
                    mock_entity1 = MagicMock(spec_set=["entity_id", "name", "original_name"])
                    mock_entity1.entity_id = "todo.test_entity1"
                    mock_entity1.name = None  # Indicates no user-defined name
                    mock_entity1.original_name = "Old Name 1"
                    return mock_entity1
                elif entity_id == "todo.test_entity2":
                    mock_entity2 = MagicMock(spec_set=["entity_id", "name", "original_name"])
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

        # Debug output
        print(f"mock_entity1.name: {get_entity('todo.test_entity1').name}")
        print(f"mock_entity1.original_name: {get_entity('todo.test_entity1').original_name}")
        print(f"mock_entity2.name: {get_entity('todo.test_entity2').name}")
        print(f"mock_entity2.original_name: {get_entity('todo.test_entity2').original_name}")
        print(f"_update_entity_names called: {mock_update_names.called}")
        if mock_update_names.called:
            print(f"_update_entity_names args: {mock_update_names.call_args}")

        # Check if async_update_entity was called for each entity
        mock_entity_registry.async_update_entity.assert_any_call(
            "todo.test_entity1", original_name="Test list1"
        )
        mock_entity_registry.async_update_entity.assert_any_call(
            "todo.test_entity2", original_name="Test list2"
        )
        assert mock_entity_registry.async_update_entity.call_count == 2



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
