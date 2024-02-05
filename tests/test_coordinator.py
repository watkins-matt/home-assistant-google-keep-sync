"""Unit tests for the todo component."""

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
    """Test update_data method."""
    with patch.object(mock_api, "async_sync_data", AsyncMock()):
        mock_api.async_sync_data.return_value = ["list1", "list2"]

        coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api, mock_config_entry)
        coordinator.config_entry = mock_config_entry

        result = await coordinator._async_update_data()

        assert result == ["list1", "list2"]


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


async def test_handle_new_items_added(
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
        new_items = await coordinator._handle_new_items_added(list1, list2)

        # Assertions
        expected = [
            TodoItemData(
                item="Bread",
                entity_id="list_entity_id",
            )
        ]
        assert new_items == expected


async def test_handle_new_items_not_added(
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
    new_items = await coordinator._handle_new_items_added(list1, list1)

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
