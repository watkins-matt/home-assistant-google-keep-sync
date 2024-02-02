"""Unit tests for the todo component."""

from unittest.mock import MagicMock

import pytest
from homeassistant.components.todo import TodoItem

from custom_components.google_keep_sync.coordinator import (
    GoogleKeepSyncCoordinator,
    TodoItem,  # noqa: F811
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


async def test_parse_gkeep_data_dict_empty(mock_api: MagicMock, mock_hass: MagicMock):
    """Test _parse_gkeep_data_dict when empty."""
    test_input: dict = {}
    expected: dict = {}
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api)
    coordinator.data = test_input

    actual = await coordinator._parse_gkeep_data_dict()
    assert actual == expected


async def test_parse_gkeep_data_dict_normal(mock_api: MagicMock, mock_hass: MagicMock):
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

    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api)
    coordinator.data = [mock_list]

    actual = await coordinator._parse_gkeep_data_dict()
    assert actual == expected


async def test_handle_new_items_added(mock_api: MagicMock, mock_hass: MagicMock):
    """Test handling new items added to a list."""
    # Set up coordinator and mock API
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api)

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

    # Call method under test
    callback = MagicMock()
    await coordinator._handle_new_items_added(list1, list2, "", callback)

    # Assertions
    expected = TodoItemData(
        item_name="Bread",
        item_id="bread_item_id",
        item_checked=False,
        list_name="Grocery List",
        list_id="grocery_list_id",
    )
    callback.assert_called_with(expected)
    callback.assert_called_once()


async def test_handle_new_items_not_added(mock_api: MagicMock, mock_hass: MagicMock):
    """Test handling when no new items are added to a list."""
    # Set up coordinator and mock API
    coordinator = GoogleKeepSyncCoordinator(mock_hass, mock_api)

    list1 = {
        "grocery_list_id": TodoList(
            name="Grocery List",
            items={"milk_item_id": TodoItem(summary="Milk", checked=False)},
        )
    }

    # Call method under test
    callback = MagicMock()
    await coordinator._handle_new_items_added(list1, list1, "", callback)

    # Assertions
    callback.assert_not_called()
