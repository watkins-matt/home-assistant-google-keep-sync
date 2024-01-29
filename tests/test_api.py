"""Tests for GoogleKeepAPI."""

from unittest.mock import AsyncMock, MagicMock, patch

import gkeepapi
import pytest

from custom_components.google_keep_sync.api import GoogleKeepAPI

# Constants for testing
TEST_USERNAME = "testuser@example.com"
TEST_PASSWORD = "testpassword"  # noqa: S105
TEST_TOKEN = "test_token"
TEST_STATE = "test_state"
TEST_LIST_ID = "test_list_id"
TEST_ITEM_ID = "test_item_id"
TEST_ITEM_TEXT = "Test Item"


@pytest.fixture
def mock_hass():
    """Fixture for mocking Home Assistant."""
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job.side_effect = lambda f, *args, **kwargs: f(
        *args, **kwargs
    )
    return mock_hass


@pytest.fixture
def google_keep_api(mock_hass):
    """Fixture for creating a GoogleKeepAPI instance with a mocked Keep."""
    with patch("gkeepapi.Keep", autospec=True) as mock_keep:
        api = GoogleKeepAPI(mock_hass, TEST_USERNAME, TEST_PASSWORD)
        api._keep = mock_keep.return_value
        api._keep.login = AsyncMock()
        api._keep.resume = AsyncMock()
        api._keep.sync = AsyncMock()
        api._keep.dump = AsyncMock(return_value=TEST_STATE)
        api._keep.getMasterToken = MagicMock(return_value=TEST_TOKEN)

        mock_list = MagicMock(spec=gkeepapi.node.List)
        mock_list.id = TEST_LIST_ID
        mock_item = MagicMock()
        mock_item.id = TEST_ITEM_ID
        mock_list.items = [mock_item]
        mock_keep.get.return_value = mock_list
        return api


@pytest.fixture
def mock_store():
    """Fixture for mocking storage."""
    store = MagicMock()
    store.async_load = AsyncMock()
    store.async_save = AsyncMock()
    return store


async def test_init(google_keep_api):
    """Test constructor of GoogleKeepAPI."""
    assert google_keep_api._username == TEST_USERNAME
    assert google_keep_api._password == TEST_PASSWORD
    assert google_keep_api._token is None
    assert google_keep_api._authenticated is False


@pytest.mark.asyncio
async def test_authenticate_new_login(google_keep_api, mock_hass, mock_store):
    """Test authentication with new login."""
    # Setting up mocks
    google_keep_api._store = mock_store
    mock_store.async_load.return_value = None
    google_keep_api._keep.getMasterToken.return_value = TEST_TOKEN

    # Patch _async_save_state_and_token
    with patch.object(google_keep_api, "_async_save_state_and_token", AsyncMock()):
        result = await google_keep_api.authenticate()

        # Assertions
        assert result is True
        assert google_keep_api._authenticated is True
        assert google_keep_api._token == TEST_TOKEN
        google_keep_api._keep.login.assert_called_once_with(
            TEST_USERNAME, TEST_PASSWORD
        )
        google_keep_api._keep.getMasterToken.assert_called_once()
        google_keep_api._async_save_state_and_token.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_resume(google_keep_api, mock_hass, mock_store):
    """Test resuming authentication with saved credentials."""
    # Setup mock store with saved credentials
    mock_store.async_load.return_value = {
        "token": TEST_TOKEN,
        "state": TEST_STATE,
        "username": TEST_USERNAME,
    }
    google_keep_api._store = mock_store

    # Patching token save method and authenticating
    with patch.object(google_keep_api, "_async_save_state_and_token", AsyncMock()):
        result = await google_keep_api.authenticate()

        # Assertions
        assert result is True
        assert google_keep_api._authenticated is True
        assert google_keep_api._token == TEST_TOKEN


@pytest.mark.asyncio
async def test_authenticate_failed_login(google_keep_api, mock_hass, mock_store):
    """Test authentication handling when login fails."""
    # Setup mock store with no saved credentials
    google_keep_api._store = mock_store
    mock_store.async_load.return_value = None
    google_keep_api._keep.login.side_effect = gkeepapi.exception.LoginException

    # Attempting authentication
    result = await google_keep_api.authenticate()

    # Assertions
    assert result is False
    assert google_keep_api._authenticated is False
    google_keep_api._keep.login.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_failed_resume(google_keep_api, mock_hass, mock_store):
    """Test authentication handling when resuming session fails."""
    mock_store.async_load.return_value = {
        "token": TEST_TOKEN,
        "state": TEST_STATE,
        "username": TEST_USERNAME,
    }
    google_keep_api._store = mock_store
    google_keep_api._keep.resume = AsyncMock(
        side_effect=gkeepapi.exception.LoginException
    )
    google_keep_api._keep.login = AsyncMock(
        side_effect=gkeepapi.exception.LoginException
    )

    result = await google_keep_api.authenticate()

    assert result is False
    assert google_keep_api._authenticated is False


@pytest.mark.asyncio
async def test_async_create_todo_item(google_keep_api, mock_hass):
    """Test creating a new todo item."""
    google_keep_api._authenticated = True
    list_id = "grocery_list_id"
    item_text = "Milk"

    # Setup mocked Google Keep list and item
    mock_gkeep_list = MagicMock(spec=gkeepapi.node.List)
    mock_new_item = MagicMock(id="milk_item_id", text=item_text, checked=False)
    mock_gkeep_list.items = [mock_new_item]
    google_keep_api._keep.get.return_value = mock_gkeep_list

    # Mock the 'add' method as an async function
    async def async_add_item(text, checked):
        mock_gkeep_list.items.append(
            MagicMock(id="milk_item_id", text=text, checked=checked)
        )

    mock_gkeep_list.add = AsyncMock(side_effect=async_add_item)

    # Adding a new item
    await google_keep_api.async_create_todo_item(list_id, item_text)

    # Assertions
    google_keep_api._keep.get.assert_called_with(list_id)
    mock_gkeep_list.add.assert_called_with(item_text, False)


@pytest.mark.asyncio
async def test_async_delete_todo_item(google_keep_api, mock_hass):
    """Test deleting a specific todo item."""
    google_keep_api._authenticated = True
    list_id = "grocery_list_id"
    item_id = "milk_item_id"

    # Setup mocked Google Keep list and item
    mock_gkeep_list = MagicMock(spec=gkeepapi.node.List)
    mock_target_item = MagicMock(id=item_id)
    mock_gkeep_list.items = [mock_target_item]
    google_keep_api._keep.get.return_value = mock_gkeep_list

    mock_target_item.delete = AsyncMock()

    # Deleting the item
    await google_keep_api.async_delete_todo_item(list_id, item_id)

    # Assertions
    mock_target_item.delete.assert_called_once()


@pytest.mark.asyncio
async def test_async_update_todo_item(google_keep_api, mock_hass):
    """Test updating an existing todo item."""
    google_keep_api._authenticated = True
    list_id = "grocery_list_id"
    item_id = "milk_item_id"
    new_text = "Milk"

    # Setup mocked Google Keep list and item
    mock_gkeep_list = MagicMock(spec=gkeepapi.node.List)
    mock_target_item = MagicMock(id=item_id)
    mock_gkeep_list.items = [mock_target_item]
    google_keep_api._keep.get.return_value = mock_gkeep_list

    # Updating the item
    await google_keep_api.async_update_todo_item(
        list_id, item_id, new_text=new_text, checked=True
    )

    # Assertions
    assert mock_target_item.text == new_text
    assert mock_target_item.checked is True


@pytest.mark.asyncio
async def test_fetch_all_lists(google_keep_api, mock_hass):
    """Test fetching all lists from Google Keep."""
    google_keep_api._authenticated = True
    mock_list = MagicMock(spec=gkeepapi.node.List)
    mock_list.id = "grocery_list_id"
    mock_list.title = "Grocery List"
    google_keep_api._keep.all.return_value = [mock_list]

    # Fetching lists
    lists = await google_keep_api.fetch_all_lists()

    # Assertions
    assert lists == [mock_list]
    google_keep_api._keep.all.assert_called_once()


@pytest.mark.asyncio
async def test_async_sync_data(google_keep_api, mock_hass):
    """Test synchronizing data with Google Keep."""
    google_keep_api._authenticated = True
    mock_list = MagicMock(spec=gkeepapi.node.List)
    mock_list.id = "grocery_list_id"
    mock_list.title = "Grocery List"
    mock_item = MagicMock(id="milk_item_id", text="Milk", checked=False)
    mock_list.items = [mock_item]

    # Side effect to return the mock list
    def get_side_effect(list_id):
        if list_id == "grocery_list_id":
            return mock_list

    google_keep_api._keep.get = AsyncMock(side_effect=get_side_effect)

    # Syncing data
    lists = await google_keep_api.async_sync_data(["grocery_list_id"])

    # Expected data structure
    expected_lists = [
        {
            "id": "grocery_list_id",
            "title": "Grocery List",
            "items": [{"id": "milk_item_id", "text": "Milk", "checked": False}],
        }
    ]
    # Assertions
    # assert lists == [expected_lists]
    assert lists[0].id == expected_lists[0]["id"]
    assert lists[0].title == expected_lists[0]["title"]
    assert lists[0].items[0].id == expected_lists[0]["items"][0]["id"]
    assert lists[0].items[0].text == expected_lists[0]["items"][0]["text"]
    assert lists[0].items[0].checked == expected_lists[0]["items"][0]["checked"]

    google_keep_api._keep.sync.assert_called_once()
    google_keep_api._keep.get.assert_called_once()
