"""Unit tests for the todo component."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.todo import TodoItem, TodoItemStatus
from homeassistant.core import HomeAssistant

from custom_components.google_keep_sync.const import DOMAIN
from custom_components.google_keep_sync.todo import (
    GoogleKeepTodoListEntity,
    async_setup_entry,
)


@pytest.fixture()
def mock_api():
    """Return a mocked Google Keep API."""
    with patch(
        "custom_components.google_keep_sync.todo.GoogleKeepAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_create_todo_item = AsyncMock(return_value="new_item_id")
        mock_api.async_update_todo_item = AsyncMock()
        mock_api.async_delete_todo_item = AsyncMock()

        # Mock fetch_all_lists to return a list of mock gkeepapi.node.List objects
        mock_lists = [
            MagicMock(id=f"list_id_{i}", title=f"list{i}") for i in range(1, 4)
        ]
        mock_api.fetch_all_lists = AsyncMock(return_value=mock_lists)

        yield mock_api


@pytest.fixture
def mock_coordinator():
    """Return a mocked update coordinator."""
    coordinator = AsyncMock()
    coordinator.data = [{"id": "grocery_list", "title": "Grocery List", "items": []}]
    return coordinator


async def test_async_setup_entry(
    hass: HomeAssistant, mock_api, mock_config_entry, mock_coordinator
):
    """Test platform setup of todo."""
    mock_config_entry.add_to_hass(hass)
    hass.data[DOMAIN] = {
        mock_config_entry.entry_id: {"api": mock_api, "coordinator": mock_coordinator}
    }

    with patch(
        "homeassistant.helpers.entity_platform.AddEntitiesCallback"
    ) as mock_add_entities:
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)
        assert mock_add_entities.call_count == 1


async def test_create_todo_item(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test creating a todo item."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": []}
    ]
    entity = GoogleKeepTodoListEntity(mock_api, mock_coordinator, grocery_list, list_prefix)

    await entity.async_create_todo_item(TodoItem(summary="Milk"))
    mock_api.async_create_todo_item.assert_called_once()
    assert any(item["text"] == "Milk" for item in mock_coordinator.data[0]["items"])


async def test_update_todo_item(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test updating a todo item."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""
    initial_item = {"id": "milk_item", "text": "Milk", "checked": False}
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": [initial_item]}
    ]
    entity = GoogleKeepTodoListEntity(mock_api, mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    updated_item = TodoItem(
        uid="milk_item", summary="Almond Milk", status=TodoItemStatus.COMPLETED
    )
    await entity.async_update_todo_item(updated_item)
    mock_api.async_update_todo_item.assert_called_once()
    updated_list = mock_coordinator.data[0]
    assert any(
        item["id"] == "milk_item" and item["text"] == "Almond Milk" and item["checked"]
        for item in updated_list["items"]
    )


async def test_delete_todo_items(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test deleting todo items."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""
    initial_items = [
        {"id": "milk_item", "text": "Milk", "checked": False},
        {"id": "eggs_item", "text": "Eggs", "checked": False},
    ]
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": initial_items}
    ]
    entity = GoogleKeepTodoListEntity(mock_api, mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    await entity.async_delete_todo_items(["milk_item"])
    mock_api.async_delete_todo_item.assert_called_once_with("grocery_list", "milk_item")
    updated_list = mock_coordinator.data[0]

    # Verify "milk_item" is deleted and "eggs_item" remains
    assert "milk_item" not in [item["id"] for item in updated_list["items"]]
    assert "eggs_item" in [item["id"] for item in updated_list["items"]]
