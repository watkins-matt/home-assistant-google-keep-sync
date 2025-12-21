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
        "custom_components.google_keep_sync.api.GoogleKeepAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_create_todo_item = AsyncMock(return_value="new_item_id")
        mock_api.async_update_todo_item = AsyncMock()
        mock_api.async_delete_todo_item = AsyncMock()
        mock_api.async_move_todo_item = AsyncMock()

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
    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    with patch(
        "homeassistant.helpers.entity_platform.AddEntitiesCallback"
    ) as mock_add_entities:
        await async_setup_entry(hass, mock_config_entry, mock_add_entities)
        assert mock_add_entities.call_count == 1


async def test_create_todo_item(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test creating a todo item."""
    # Create a mock Google Keep list
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    grocery_list.items = []
    list_prefix = ""

    # Initialize the coordinator data
    mock_coordinator.api = mock_api
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": []}
    ]

    # Side effect to simulate adding item to Google Keep list
    # when mock_api.async_create_todo_item is called
    def async_create_todo_item_side_effect(list_id, text):
        if list_id == "grocery_list":
            new_item = MagicMock()
            new_item.text = text
            grocery_list.items.append(new_item)

    mock_api.async_create_todo_item.side_effect = async_create_todo_item_side_effect

    # Side effect to update coordinator data to reflect changes in the list
    def async_refresh_side_effect():
        mock_coordinator.data[0]["items"] = [
            {"text": item.text} for item in grocery_list.items
        ]

    mock_coordinator.async_refresh = AsyncMock(side_effect=async_refresh_side_effect)

    # Create the entity and add a new item
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    await entity.async_create_todo_item(TodoItem(summary="Milk"))

    # Ensure the proper methods were called
    mock_api.async_create_todo_item.assert_called_once_with("grocery_list", "Milk")
    mock_coordinator.async_refresh.assert_called_once()

    # Assertions to ensure the item is correctly added
    assert any(item.text == "Milk" for item in grocery_list.items)
    assert any(item.summary == "Milk" for item in entity.todo_items)
    assert any(item["text"] == "Milk" for item in mock_coordinator.data[0]["items"])


async def test_update_todo_item(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test updating a todo item."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""
    initial_item = {"id": "milk_item", "text": "Milk", "checked": False}
    grocery_list.items = [initial_item]

    mock_coordinator.api = mock_api
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": [initial_item]}
    ]

    # Side effect to simulate updating item to Google Keep list
    # when mock_api.async_update_todo_item is called
    def async_update_todo_item_side_effect(list_id, item_id, new_text, checked):
        if list_id == "grocery_list":
            if item_id == grocery_list.items[0]["id"]:
                grocery_list.items[0]["text"] = new_text
                grocery_list.items[0]["checked"] = checked

    mock_api.async_update_todo_item.side_effect = async_update_todo_item_side_effect

    # Side effect to update coordinator data to reflect changes in the list
    def async_refresh_side_effect():
        mock_coordinator.data[0]["items"] = grocery_list.items

    mock_coordinator.async_refresh = AsyncMock(side_effect=async_refresh_side_effect)

    # Create the entity
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    # update item
    updated_item = TodoItem(
        uid="milk_item", summary="Almond Milk", status=TodoItemStatus.COMPLETED
    )
    await entity.async_update_todo_item(updated_item)
    mock_api.async_update_todo_item.assert_called_once()
    mock_coordinator.async_refresh.assert_called_once()
    updated_list = mock_coordinator.data[0]

    assert "grocery_list" == updated_list["id"]
    assert len(updated_list["items"]) == 1
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
    grocery_list.items = initial_items
    mock_coordinator.api = mock_api
    mock_coordinator.data = [
        {"id": "grocery_list", "title": "Grocery List", "items": initial_items}
    ]

    # Side effect to simulate detele item from Google Keep list
    # when mock_api.async_delete_todo_item is called
    def async_delete_todo_item_side_effect(list_id, item_id):
        if list_id == "grocery_list" and item_id == "milk_item":
            grocery_list.items = [{"id": "eggs_item", "text": "Eggs", "checked": False}]

    mock_api.async_delete_todo_item.side_effect = async_delete_todo_item_side_effect

    # Side effect to update coordinator data to reflect changes in the list
    def async_refresh_side_effect():
        mock_coordinator.data[0]["items"] = grocery_list.items

    mock_coordinator.async_refresh = AsyncMock(side_effect=async_refresh_side_effect)

    # Create the entity
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    # Delete item
    await entity.async_delete_todo_items(["milk_item"])
    mock_api.async_delete_todo_item.assert_called_once_with("grocery_list", "milk_item")
    mock_coordinator.async_refresh.assert_called_once()
    updated_list = mock_coordinator.data[0]

    # Verify "milk_item" is deleted and "eggs_item" remains
    assert len(updated_list["items"]) == 1
    assert "milk_item" not in [item["id"] for item in updated_list["items"]]
    assert "eggs_item" in [item["id"] for item in updated_list["items"]]


async def test_default_list_prefix(hass, mock_api, mock_coordinator):
    """Test default list prefix setting (not set)."""
    list_prefix = ""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")

    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)

    # Test default prefix
    assert entity.name == "Grocery List"


async def test_custom_list_prefix(hass, mock_api, mock_coordinator):
    """Test custom list prefix setting ."""
    list_prefix = "Foo"
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")

    # Test custom prefix
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    assert entity.name == "Foo Grocery List"


async def test_handle_coordinator_update(hass, mock_api, mock_coordinator):
    """Test that _handle_coordinator_update updates entity name and list data."""
    # Create a dummy list with an initial title and no items
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Original Title"
    dummy_list.items = []

    # Set a list prefix in the coordinator configuration and assign hass to the entity
    mock_coordinator.config_entry = MagicMock()
    mock_coordinator.config_entry.data = {"list_prefix": "Prefix"}
    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "Prefix")
    entity.hass = hass

    # Simulate a coordinator update with an updated list title
    updated_list = MagicMock()
    updated_list.id = "test_list"
    updated_list.title = "Updated Title"
    updated_list.items = dummy_list.items
    mock_coordinator.data = [updated_list]

    # Process the coordinator update
    entity._handle_coordinator_update()

    # Verify that the entity's name is updated to include the new title
    assert entity._attr_name == "Prefix Updated Title"


async def test_todo_items_filtering(mock_api, mock_coordinator):
    """Test that todo_items property filters out empty or whitespace-only entries."""
    # Create items: one valid, one empty, and one with only whitespace
    valid_item = MagicMock(id="1", text="Buy Milk", checked=False)
    empty_item = MagicMock(id="2", text="", checked=False)
    whitespace_item = MagicMock(id="3", text="   ", checked=True)

    # Set up a dummy list containing all items
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [valid_item, empty_item, whitespace_item]

    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "")
    items = entity.todo_items

    # Only the valid item should be returned
    assert len(items) == 1
    assert items[0].summary == "Buy Milk"


async def test_async_create_todo_item_exception(mock_api, mock_coordinator):
    """Test async_create_todo_item calls async_refresh even if creation fails."""
    # Create a dummy list with no items
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = []

    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "")
    # Force an exception when creating a new todo item
    entity.api.async_create_todo_item = AsyncMock(side_effect=Exception("Error"))
    mock_coordinator.async_refresh = AsyncMock()

    item = TodoItem(
        summary="New Task", uid="new_item", status=TodoItemStatus.NEEDS_ACTION
    )
    await entity.async_create_todo_item(item)

    # Verify that a refresh is requested despite the error
    mock_coordinator.async_refresh.assert_called_once()


async def test_async_update_todo_item_exception(mock_api, mock_coordinator):
    """Test async_update_todo_item calls async_refresh even if update fails."""
    # Create a dummy list with an initial item
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [{"id": "item1", "text": "Old Task", "checked": False}]

    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "")
    # Force an exception during the update operation
    entity.api.async_update_todo_item = AsyncMock(side_effect=Exception("Update Error"))
    mock_coordinator.async_refresh = AsyncMock()

    item = TodoItem(
        summary="Updated Task", uid="item1", status=TodoItemStatus.COMPLETED
    )
    await entity.async_update_todo_item(item)

    # Confirm that a data refresh is still requested
    mock_coordinator.async_refresh.assert_called_once()


async def test_async_delete_todo_items_exception(mock_api, mock_coordinator):
    """Test async_delete_todo_items calls async_refresh even if deletion fails."""
    # Create a dummy list with a single item
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [{"id": "item1", "text": "Task", "checked": False}]

    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "")
    # Force an exception during the deletion process
    entity.api.async_delete_todo_item = AsyncMock(side_effect=Exception("Delete Error"))
    mock_coordinator.async_refresh = AsyncMock()

    await entity.async_delete_todo_items(["item1"])

    # Verify that async_refresh is called despite the deletion error
    mock_coordinator.async_refresh.assert_called_once()


async def test_move_todo_item(hass: HomeAssistant, mock_api, mock_coordinator):
    """Test moving a todo item to a new position."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""

    # Create mock items with IDs
    item1 = MagicMock(id="item_1", text="Item 1", checked=False)
    item2 = MagicMock(id="item_2", text="Item 2", checked=False)
    item3 = MagicMock(id="item_3", text="Item 3", checked=False)
    grocery_list.items = [item1, item2, item3]

    mock_coordinator.api = mock_api
    mock_coordinator.data = [
        {
            "id": "grocery_list",
            "title": "Grocery List",
            "items": [
                {"id": "item_1", "text": "Item 1", "checked": False},
                {"id": "item_2", "text": "Item 2", "checked": False},
                {"id": "item_3", "text": "Item 3", "checked": False},
            ],
        }
    ]

    # Mock the async_move_todo_item method
    mock_api.async_move_todo_item = AsyncMock()

    # Side effect to update coordinator data after move
    def async_refresh_side_effect():
        # Simulate reordered items
        mock_coordinator.data[0]["items"] = [
            {"id": "item_2", "text": "Item 2", "checked": False},
            {"id": "item_3", "text": "Item 3", "checked": False},
            {"id": "item_1", "text": "Item 1", "checked": False},
        ]

    mock_coordinator.async_refresh = AsyncMock(side_effect=async_refresh_side_effect)

    # Create the entity
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    # Move item_1 to after item_3
    await entity.async_move_todo_item("item_1", previous_uid="item_3")

    # Verify the API method was called correctly
    mock_api.async_move_todo_item.assert_called_once_with(
        "grocery_list", "item_1", "item_3"
    )
    mock_coordinator.async_refresh.assert_called_once()


async def test_move_todo_item_to_beginning(
    hass: HomeAssistant, mock_api, mock_coordinator
):
    """Test moving a todo item to the beginning of the list."""
    grocery_list = MagicMock(id="grocery_list", title="Grocery List")
    list_prefix = ""

    # Create mock items
    item1 = MagicMock(id="item_1", text="Item 1", checked=False)
    item2 = MagicMock(id="item_2", text="Item 2", checked=False)
    item3 = MagicMock(id="item_3", text="Item 3", checked=False)
    grocery_list.items = [item1, item2, item3]

    mock_coordinator.api = mock_api
    mock_coordinator.data = [
        {
            "id": "grocery_list",
            "title": "Grocery List",
            "items": [
                {"id": "item_1", "text": "Item 1", "checked": False},
                {"id": "item_2", "text": "Item 2", "checked": False},
                {"id": "item_3", "text": "Item 3", "checked": False},
            ],
        }
    ]

    # Mock the async_move_todo_item method
    mock_api.async_move_todo_item = AsyncMock()
    mock_coordinator.async_refresh = AsyncMock()

    # Create the entity
    entity = GoogleKeepTodoListEntity(mock_coordinator, grocery_list, list_prefix)
    entity.hass = hass

    # Move item_3 to the beginning (previous_uid=None)
    await entity.async_move_todo_item("item_3", previous_uid=None)

    # Verify the API method was called with None for previous_uid
    mock_api.async_move_todo_item.assert_called_once_with(
        "grocery_list", "item_3", None
    )
    mock_coordinator.async_refresh.assert_called_once()


async def test_move_todo_item_exception(mock_api, mock_coordinator):
    """Test async_move_todo_item calls async_refresh even if move fails."""
    # Create a dummy list with items
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    item1 = MagicMock(id="item_1", text="Item 1", checked=False)
    item2 = MagicMock(id="item_2", text="Item 2", checked=False)
    dummy_list.items = [item1, item2]

    entity = GoogleKeepTodoListEntity(mock_coordinator, dummy_list, "")
    # Force an exception during the move operation
    entity.api.async_move_todo_item = AsyncMock(side_effect=Exception("Move Error"))
    mock_coordinator.async_refresh = AsyncMock()

    await entity.async_move_todo_item("item_1", previous_uid="item_2")

    # Verify that async_refresh is called despite the move error
    mock_coordinator.async_refresh.assert_called_once()


async def test_todo_items_placeholder_enabled(mock_api, mock_coordinator):
    """Test that empty items show placeholder when feature is enabled."""
    # Create items: one valid, one empty, and one with only whitespace
    valid_item = MagicMock(id="1", text="Buy Milk", checked=False)
    empty_item = MagicMock(id="2", text="", checked=False)
    whitespace_item = MagicMock(id="3", text="   ", checked=False)

    # Set up a dummy list containing all items
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [valid_item, empty_item, whitespace_item]

    # Create entity with placeholder enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="---"
    )
    items = entity.todo_items

    # All items should be returned, with empty/whitespace items showing placeholder
    expected_item_count = 3
    assert len(items) == expected_item_count
    assert items[0].summary == "Buy Milk"
    assert items[1].summary == "---"
    assert items[2].summary == "---"


async def test_todo_items_placeholder_disabled_empty_str(mock_api, mock_coordinator):
    """Test that empty items are filtered when placeholder is empty string."""
    # Create items: one valid, one empty
    valid_item = MagicMock(id="1", text="Buy Milk", checked=False)
    empty_item = MagicMock(id="2", text="", checked=False)

    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [valid_item, empty_item]

    # Create entity with empty placeholder (disabled)
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder=""
    )
    items = entity.todo_items

    # Only valid item should be returned
    assert len(items) == 1
    assert items[0].summary == "Buy Milk"


async def test_todo_items_placeholder_disabled_whitespace(mock_api, mock_coordinator):
    """Test that empty items are filtered when placeholder is whitespace only."""
    # Create items: one valid, one empty
    valid_item = MagicMock(id="1", text="Buy Milk", checked=False)
    empty_item = MagicMock(id="2", text="", checked=False)

    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [valid_item, empty_item]

    # Create entity with whitespace-only placeholder (should be treated as disabled)
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="   "
    )
    items = entity.todo_items

    # Only valid item should be returned
    assert len(items) == 1
    assert items[0].summary == "Buy Milk"


async def test_create_placeholder_item_syncs_as_empty(mock_api, mock_coordinator):
    """Test creating item with placeholder text syncs as empty to Google Keep."""
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = []

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity with placeholder enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="---"
    )

    # Create item with placeholder text
    await entity.async_create_todo_item(TodoItem(summary="---"))

    # Verify API was called with empty string
    mock_api.async_create_todo_item.assert_called_once_with("test_list", "")


async def test_create_non_placeholder_item_syncs_normally(mock_api, mock_coordinator):
    """Test that creating a regular item syncs with its actual text."""
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = []

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity with placeholder enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="---"
    )

    # Create regular item (not placeholder)
    await entity.async_create_todo_item(TodoItem(summary="Buy Eggs"))

    # Verify API was called with actual text
    mock_api.async_create_todo_item.assert_called_once_with("test_list", "Buy Eggs")


async def test_update_to_placeholder_syncs_as_empty(mock_api, mock_coordinator):
    """Test that updating an item to placeholder text syncs as empty to Google Keep."""
    item = MagicMock(id="1", text="Old text", checked=False)
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [item]

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity with placeholder enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="---"
    )

    # Update item to placeholder text
    await entity.async_update_todo_item(
        TodoItem(uid="1", summary="---", status=TodoItemStatus.NEEDS_ACTION)
    )

    # Verify API was called with empty string
    mock_api.async_update_todo_item.assert_called_once_with("test_list", "1", "", False)


async def test_update_non_placeholder_item_syncs_normally(mock_api, mock_coordinator):
    """Test that updating an item with regular text syncs normally."""
    item = MagicMock(id="1", text="Old text", checked=False)
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [item]

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity with placeholder enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder="---"
    )

    # Update item with regular text
    await entity.async_update_todo_item(
        TodoItem(uid="1", summary="New text", status=TodoItemStatus.COMPLETED)
    )

    # Verify API was called with actual text
    mock_api.async_update_todo_item.assert_called_once_with(
        "test_list", "1", "New text", True
    )


async def test_placeholder_disabled_create_does_not_convert(mock_api, mock_coordinator):
    """Test that placeholder text is not converted when feature is disabled."""
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = []

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity without placeholder (disabled)
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=False, empty_item_placeholder=""
    )

    # Create item with what would be placeholder text
    await entity.async_create_todo_item(TodoItem(summary="---"))

    # Verify API was called with the literal text (not converted to empty)
    mock_api.async_create_todo_item.assert_called_once_with("test_list", "---")


async def test_placeholder_disabled_when_auto_sort_enabled(mock_api, mock_coordinator):
    """Test that placeholder is disabled when auto_sort is enabled."""
    # Create items: one valid, one empty
    valid_item = MagicMock(id="1", text="Buy Milk", checked=False)
    empty_item = MagicMock(id="2", text="", checked=False)

    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = [valid_item, empty_item]

    # Create entity with placeholder set BUT auto_sort enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=True, empty_item_placeholder="---"
    )
    items = entity.todo_items

    # Empty items should be filtered out (placeholder disabled due to auto_sort)
    assert len(items) == 1
    assert items[0].summary == "Buy Milk"


async def test_create_with_auto_sort_does_not_convert_placeholder(
    mock_api, mock_coordinator
):
    """Test that placeholder is not converted to empty when auto_sort is enabled."""
    dummy_list = MagicMock()
    dummy_list.id = "test_list"
    dummy_list.title = "Test List"
    dummy_list.items = []

    mock_coordinator.api = mock_api
    mock_coordinator.async_refresh = AsyncMock()

    # Create entity with placeholder set BUT auto_sort enabled
    entity = GoogleKeepTodoListEntity(
        mock_coordinator, dummy_list, "", auto_sort=True, empty_item_placeholder="---"
    )

    # Create item with placeholder text
    await entity.async_create_todo_item(TodoItem(summary="---"))

    # Verify API was called with literal text (not converted due to auto_sort)
    mock_api.async_create_todo_item.assert_called_once_with("test_list", "---")
