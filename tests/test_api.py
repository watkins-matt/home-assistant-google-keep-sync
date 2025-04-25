"""Tests for GoogleKeepAPI."""

from unittest.mock import AsyncMock, MagicMock, patch

import gkeepapi
import pytest

from custom_components.google_keep_sync.api import GoogleKeepAPI, ListCase

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
        api._keep.authenticate = AsyncMock()
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


async def test_authenticate_failed_resume(google_keep_api, mock_hass, mock_store):
    """Test authentication handling when resuming session fails."""
    mock_store.async_load.return_value = {
        "token": TEST_TOKEN,
        "state": TEST_STATE,
        "username": TEST_USERNAME,
    }
    google_keep_api._store = mock_store
    google_keep_api._keep.authenticate = AsyncMock(
        side_effect=gkeepapi.exception.LoginException
    )
    google_keep_api._keep.login = AsyncMock(
        side_effect=gkeepapi.exception.LoginException
    )

    result = await google_keep_api.authenticate()

    assert result is False
    assert google_keep_api._authenticated is False


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
    async def async_add_item(text, checked, _):
        mock_gkeep_list.items.append(
            MagicMock(id="milk_item_id", text=text, checked=checked)
        )

    mock_gkeep_list.add = AsyncMock(side_effect=async_add_item)

    # Adding a new item
    await google_keep_api.async_create_todo_item(list_id, item_text)

    # Assertions
    google_keep_api._keep.get.assert_called_with(list_id)
    mock_gkeep_list.add.assert_called_with(
        item_text, False, gkeepapi.node.NewListItemPlacementValue.Bottom
    )


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
    lists, _ = await google_keep_api.async_sync_data(["grocery_list_id"])
    lists: list[gkeepapi.node.List]

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


async def test_async_sync_data_sort_unchecked(google_keep_api, mock_hass):
    """Test synchronizing and sorting data with Google Keep."""
    google_keep_api._authenticated = True

    # Creating a mock list with unsorted unchecked items
    mock_list = MagicMock(spec=gkeepapi.node.List)
    mock_list.id = "todo_list_id"
    mock_list.title = "Todo List"
    mock_item1 = MagicMock(id="milk_item_id", text="Milk", checked=False)
    mock_item2 = MagicMock(id="apple_item_id", text="apple", checked=False)
    mock_list.items = [mock_item1, mock_item2]
    mock_list.unchecked = [mock_item1, mock_item2]

    # Mocking sort_items method
    mock_list.sort_items = AsyncMock()

    # Side effect to return the mock list
    google_keep_api._keep.get = AsyncMock(return_value=mock_list)

    # Mocking the is_list_sorted method
    google_keep_api.is_list_sorted = MagicMock(return_value=False)

    # Syncing data with sort_lists=True
    lists, _ = await google_keep_api.async_sync_data(["todo_list_id"], sort_lists=True)

    # Assertions to ensure sorting logic was called correctly
    google_keep_api.is_list_sorted.assert_called_once_with([mock_item1, mock_item2])
    mock_list.sort_items.assert_called_once()

    # Ensure the list is in the returned lists and has been sorted
    assert lists[0].id == "todo_list_id"
    assert lists[0].title == "Todo List"
    assert lists[0].items == [mock_item1, mock_item2]

    # Check if sync was called twice, once at the beginning and once after sorting
    expected_sync_call_count = 2
    assert google_keep_api._keep.sync.call_count == expected_sync_call_count


async def test_is_list_sorted(google_keep_api, mock_hass):
    """Tests whether is_list_sorted works as expected."""
    # Create mock items
    item1 = gkeepapi.node.ListItem()
    item1.text = "Apple"
    item2 = gkeepapi.node.ListItem()
    item2.text = "banana"
    item3 = gkeepapi.node.ListItem()
    item3.text = "Cherry"

    # List is sorted
    sorted_list = [item1, item2, item3]
    assert (
        google_keep_api.is_list_sorted(sorted_list) is True
    ), "The list should be identified as sorted"

    # List is not sorted
    not_sorted_list = [item3, item1, item2]
    assert (
        google_keep_api.is_list_sorted(not_sorted_list) is False
    ), "The list should be identified as not sorted"


async def test_async_login_with_saved_token(google_keep_api, mock_hass):
    """Test logging in to Google Keep using the saved token."""
    google_keep_api._authenticated = False
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = TEST_TOKEN

    # Patching token save method and logging in
    with patch.object(google_keep_api, "_async_save_state_and_token", AsyncMock()):
        result = await google_keep_api.async_login_with_saved_token()

        # Assertions
        assert result is True
        assert google_keep_api._authenticated is True
        assert google_keep_api._token == google_keep_api._keep.getMasterToken()
        google_keep_api._keep.resume.assert_called_once_with(
            TEST_USERNAME, TEST_TOKEN, None
        )
        google_keep_api._async_save_state_and_token.assert_called_once()


async def test_async_login_with_saved_token_no_username(google_keep_api, mock_hass):
    """Test logging in to Google Keep using the saved token without a username."""
    google_keep_api._authenticated = False
    google_keep_api._username = None
    google_keep_api._token = TEST_TOKEN

    result = await google_keep_api.async_login_with_saved_token()

    assert result is False
    assert google_keep_api._authenticated is False


async def test_async_login_with_saved_token_no_token(google_keep_api, mock_hass):
    """Test logging in to Google Keep using the saved token without a token."""
    google_keep_api._authenticated = False
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = None

    result = await google_keep_api.async_login_with_saved_token()

    assert result is False
    assert google_keep_api._authenticated is False


async def test_async_login_with_saved_token_failed_login(google_keep_api, mock_hass):
    """Test logging in to Google Keep using the saved token with a failed login."""
    google_keep_api._authenticated = False
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = TEST_TOKEN
    google_keep_api._keep.resume.side_effect = gkeepapi.exception.LoginException
    google_keep_api._async_save_state_and_token = AsyncMock()

    result = await google_keep_api.async_login_with_saved_token()

    assert result is False
    assert google_keep_api._authenticated is False
    google_keep_api._keep.resume.assert_called_once_with(
        TEST_USERNAME, TEST_TOKEN, None
    )
    google_keep_api._async_save_state_and_token.assert_not_called()


async def test_username(google_keep_api, mock_hass):
    """Test username."""
    google_keep_api._username = TEST_USERNAME
    assert google_keep_api.username == TEST_USERNAME


async def test_token(google_keep_api, mock_hass):
    """Test token."""
    google_keep_api._token = TEST_TOKEN
    assert google_keep_api.token == TEST_TOKEN


async def test_async_save_state_and_token(google_keep_api, mock_hass, mock_store):
    """Test saving the state, token, and username of Google Keep."""
    google_keep_api._authenticated = True
    google_keep_api._token = TEST_TOKEN
    google_keep_api._store = mock_store

    # Mock the dump method as an async function
    async def async_dump_state():
        return TEST_STATE

    google_keep_api._keep.dump = AsyncMock(side_effect=async_dump_state)

    # Saving the state and token
    await google_keep_api._async_save_state_and_token()

    # Assertions
    google_keep_api._keep.dump.assert_called_once()
    google_keep_api._keep.getMasterToken.assert_not_called()
    mock_store.async_save.assert_called_once_with(
        {"token": TEST_TOKEN, "state": TEST_STATE, "username": TEST_USERNAME}
    )


async def test_change_list_case(google_keep_api, mock_hass):
    """Test changing the case of list items."""
    # Create a list with items
    mock_list = MagicMock(spec=gkeepapi.node.List)
    mock_list.id = "todo_list_id"
    mock_list.title = "Todo List"
    mock_item1 = MagicMock(id="milk_item_id", text="Milk", checked=False)
    mock_item2 = MagicMock(id="apple_item_id", text="apple", checked=False)
    mock_list.items = [mock_item1, mock_item2]

    # Check upper case
    google_keep_api.change_list_case(mock_list.items, ListCase.UPPER)
    assert mock_item1.text == "MILK"
    assert mock_item2.text == "APPLE"

    # Check lower case
    google_keep_api.change_list_case(mock_list.items, ListCase.LOWER)
    assert mock_item1.text == "milk"
    assert mock_item2.text == "apple"

    # Check no change
    google_keep_api.change_list_case(mock_list.items, ListCase.NO_CHANGE)
    assert mock_item1.text == "milk"
    assert mock_item2.text == "apple"

    # Check title case
    google_keep_api.change_list_case(mock_list.items, ListCase.TITLE)
    assert mock_item1.text == "Milk"
    assert mock_item2.text == "Apple"

    # Check sentence case
    google_keep_api.change_list_case(mock_list.items, ListCase.SENTENCE)
    assert mock_item1.text == "Milk"
    assert mock_item2.text == "Apple"


async def test_change_case(google_keep_api, mock_hass):
    """Test changing the case of individual strings."""
    assert google_keep_api.change_case("milk", ListCase.UPPER) == "MILK"
    assert google_keep_api.change_case("milk", ListCase.LOWER) == "milk"
    assert google_keep_api.change_case("milk", ListCase.NO_CHANGE) == "milk"
    assert (
        google_keep_api.change_case("chocolate milk", ListCase.TITLE)
        == "Chocolate Milk"
    )
    assert (
        google_keep_api.change_case("chocolate milk", ListCase.SENTENCE)
        == "Chocolate milk"
    )


@pytest.mark.parametrize(
    "input_username,expected",
    [
        ("", "Unknown"),
        ("username", "u*******"),
        ("username@example.com", "u*******@.com"),
        ("username@localhost", "u*******@"),
        ("username@sub.example.com", "u*******@.com"),
        ("username@example.net", "u*******@.net"),
    ],
)
def test_redact_username(google_keep_api, input_username: str, expected) -> None:
    """Test _redact_username returns correct redaction."""
    result = google_keep_api.redact_username(input_username)
    assert result == expected


async def test_api_caching_on_failure(mock_hass):
    """Test that the API caches and returns last known data on failure."""
    api = GoogleKeepAPI(mock_hass, "test@example.com", "password")
    api._authenticated = True

    # Create mock list
    mock_list = AsyncMock()
    mock_list.id = "list1"
    mock_list.title = "Shopping"
    mock_list.items = []

    # Mock Keep API to succeed first then fail
    api._keep.sync = AsyncMock(
        side_effect=[
            None,  # First sync succeeds
            Exception("Sync failed"),  # Second sync fails
        ]
    )

    api._sync_with_google_keep = AsyncMock()
    api._keep.get = AsyncMock(return_value=mock_list)

    # First sync - should succeed and cache data
    lists, deleted = await api.async_sync_data(["list1"])
    assert len(lists) == 1
    assert lists[0].id == "list1"
    assert deleted == []

    # Second sync - should fail but return cached data
    lists, deleted = await api.async_sync_data(["list1"])
    assert len(lists) == 1
    assert lists[0].id == "list1"
    assert deleted == []


async def test_is_oauth_token(google_keep_api):
    """Test the is_oauth_token method correctly identifies different token types."""
    # Test empty token
    assert google_keep_api.is_oauth_token("") is False
    assert google_keep_api.is_oauth_token(None) is False

    # Test master token (starts with "aas_et/" and is 223 chars)
    master_token = "aas_et/" + "x" * 216  # 223 chars total
    assert google_keep_api.is_oauth_token(master_token) is False

    # Test OAuth token (doesn't start with "aas_et/" or not 223 chars)
    oauth_token = "ya29.some_oauth_token"
    assert google_keep_api.is_oauth_token(oauth_token) is True

    # Test token with "aas_et/" prefix but wrong length
    wrong_length_token = "aas_et/too_short"
    assert google_keep_api.is_oauth_token(wrong_length_token) is True


async def test_async_login_with_oauth_token_success(google_keep_api, mock_hass):
    """Test successful OAuth token login."""
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = "ya29.oauth_token"

    # Need to properly mock the executor job to return a master token
    def executor_mock(*args, **kwargs):
        # This is the function that gets called when self._hass.async_add_executor_job is executed
        # It should return a master token
        return "master_token_123"

    # Replace the entire mock_hass.async_add_executor_job with our own mock
    mock_hass.async_add_executor_job = AsyncMock(side_effect=executor_mock)

    # Patch _async_save_state_and_token method and ensure resume is properly mocked
    with patch.object(google_keep_api, "_async_save_state_and_token", AsyncMock()):
        # Call the method we're testing
        result = await google_keep_api.async_login_with_oauth_token()

        # Assertions
        assert result is True
        assert google_keep_api._authenticated is True
        assert google_keep_api._token == "master_token_123"
        google_keep_api._keep.resume.assert_called_once_with(
            TEST_USERNAME, "master_token_123", None
        )


async def test_async_login_with_oauth_token_no_credentials(google_keep_api):
    """Test OAuth token login with no credentials."""
    google_keep_api._username = ""
    google_keep_api._token = None

    result = await google_keep_api.async_login_with_oauth_token()

    assert result is False
    assert google_keep_api._authenticated is False


async def test_async_login_with_oauth_token_exchange_failed(google_keep_api, mock_hass):
    """Test OAuth token login with failed token exchange."""
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = "ya29.oauth_token"

    # Mock gpsoauth.exchange_token to return error
    with patch("gpsoauth.exchange_token", return_value={"Error": "Invalid token"}):
        result = await google_keep_api.async_login_with_oauth_token()

        assert result is False
        assert google_keep_api._authenticated is False


async def test_async_login_with_oauth_token_exception(google_keep_api, mock_hass):
    """Test OAuth token login handling exceptions."""
    google_keep_api._username = TEST_USERNAME
    google_keep_api._token = "ya29.oauth_token"

    # Mock gpsoauth.exchange_token to raise exception
    with patch("gpsoauth.exchange_token", side_effect=Exception("Connection error")):
        result = await google_keep_api.async_login_with_oauth_token()

        assert result is False
        assert google_keep_api._authenticated is False


async def test_sync_with_google_keep_retry(google_keep_api, mock_hass):
    """Test the _sync_with_google_keep method with retries."""
    # Set up mocks
    google_keep_api._authenticated = True

    # First call raises exception, second succeeds
    google_keep_api._keep.sync.side_effect = [
        Exception("Network error"),
        None,  # Success on retry
    ]

    # Call the method
    await google_keep_api._sync_with_google_keep()

    # Verify sync was called twice (initial attempt + retry)
    assert google_keep_api._keep.sync.call_count == 2


async def test_sync_with_google_keep_resync_required(google_keep_api, mock_hass):
    """Test the _sync_with_google_keep method with ResyncRequiredException."""
    google_keep_api._authenticated = True

    # First call raises ResyncRequiredException
    google_keep_api._keep.sync.side_effect = [
        gkeepapi.exception.ResyncRequiredException(),
        None,  # Success on full resync
    ]

    # Call the method
    await google_keep_api._sync_with_google_keep()

    # Verify sync was called twice (first attempt + full resync)
    assert google_keep_api._keep.sync.call_count == 2
    # Verify the second call was a full resync
    google_keep_api._keep.sync.assert_called_with(True)


async def test_async_sync_data_with_deleted_lists(google_keep_api, mock_hass):
    """Test synchronizing data with deleted lists."""
    google_keep_api._authenticated = True

    # First list exists
    mock_list1 = MagicMock(spec=gkeepapi.node.List)
    mock_list1.id = "list1_id"
    mock_list1.title = "List 1"

    # Define a get_side_effect that returns None for list2_id (deleted list)
    def get_side_effect(list_id):
        if list_id == "list1_id":
            return mock_list1
        return None  # list2_id not found

    # Mock _sync_with_google_keep properly
    with patch.object(google_keep_api, "_sync_with_google_keep", AsyncMock()):
        # Mock the _keep.get method
        def async_get(list_id):
            return get_side_effect(list_id)

        # We need to properly configure the side effect as an async method
        google_keep_api._keep.get = AsyncMock(side_effect=async_get)

        # Set the last_synced property so we have something to return on error
        google_keep_api._last_synced = [mock_list1]

        # Call with both lists
        lists, deleted = await google_keep_api.async_sync_data(["list1_id", "list2_id"])

        # Verify results
        assert len(lists) == 1
        assert lists[0].id == "list1_id"
        assert "list2_id" in deleted


async def test_async_clear_token(google_keep_api, mock_hass, mock_store):
    """Test clearing the saved token."""
    google_keep_api._store = mock_store
    google_keep_api._username = TEST_USERNAME

    await google_keep_api._async_clear_token()

    mock_store.async_save.assert_called_once_with({"token": None, "username": None})


async def test_authenticated_required_decorator(google_keep_api, mock_hass):
    """Test the authenticated_required decorator."""
    google_keep_api._authenticated = False

    # Try to call a method with the decorator when not authenticated
    with pytest.raises(Exception, match="Not authenticated with Google Keep"):
        await google_keep_api.async_create_todo_item("list_id", "test item")
