"""Test config flow for Google Keep Sync."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow

from custom_components.google_keep_sync.config_flow import (
    CannotConnectError,
    ConfigFlow,
)
from custom_components.google_keep_sync.const import DOMAIN
from tests.conftest import MockConfigEntry


class MockList:
    """Mock class representing a list."""

    def __init__(self, id: str, title: str):
        """Initialize the MockList."""
        self.id = id
        self.title = title


@pytest.fixture()
def mock_google_keep_api():
    """Fixture for mocking the GoogleKeepAPI class."""
    with patch("custom_components.google_keep_sync.config_flow.GoogleKeepAPI") as mock:
        # Mock lists returned by fetch_all_lists
        # Note that fetch_all_lists returns a list of gkeepapi.node.List
        mock_lists = [
            MagicMock(
                id=f"list_id_{i}",
                title=f"list{i}",
                deleted=False,
                archived=False,
                trashed=False,
            )
            for i in range(1, 4)
        ]
        mock_instance = mock.return_value
        mock_instance.authenticate = AsyncMock(return_value=True)
        mock_instance.fetch_all_lists = AsyncMock(return_value=mock_lists)
        yield mock

        mock.reset_mock()


async def test_user_form_setup(hass: HomeAssistant, mock_google_keep_api):
    """Test the initial user setup form, with a username and token."""
    user_name = "testuser@example.com"
    user_token = "aas_et/" + "x" * 216  # 223 chars total (master token)
    # Patch the mock to return the expected token string
    mock_google_keep_api.return_value.token = user_token

    # Initiate the config flow
    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert initial_form_result["type"] == "form"
    assert initial_form_result["errors"] == {}

    # Submit user credentials
    user_input = {
        "username": user_name,
        "token": user_token,
    }
    credentials_form_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    # Check if the next step is the options step
    assert credentials_form_result["type"] == "form"
    assert credentials_form_result["step_id"] == "options"

    # Simulate options selection - including list selection and list prefix
    options_input = {
        "lists_to_sync": ["list_id_1", "list_id_2"],
        "list_prefix": "testprefix",
        "list_auto_sort": False,
        "list_item_case": "no_change",
    }
    final_form_result = await hass.config_entries.flow.async_configure(
        credentials_form_result["flow_id"], user_input=options_input
    )

    # Check the final result for entry creation
    assert final_form_result["type"] == "create_entry"
    assert final_form_result["title"] == user_name.lower()
    assert final_form_result["data"] == {
        "username": user_name,
        "token": user_token,
        "lists_to_sync": ["list_id_1", "list_id_2"],
        "list_prefix": "testprefix",
        "list_auto_sort": False,
        "list_item_case": "no_change",
    }


async def test_user_form_blank_username(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of a blank username."""
    user_input = {"username": " ", "token": "sometoken"}

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "blank_username"}


async def test_user_form_missing_token(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of a missing token."""
    user_input = {
        "username": "test@example.com",
        "token": "",  # Empty token
    }

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "missing_token"}


async def test_user_form_invalid_email(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of an invalid email address."""
    user_input = {"username": "testuser", "token": "sometoken"}

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "invalid_email"}


async def test_user_form_neither_password_nor_token(
    hass: HomeAssistant, mock_google_keep_api
):
    """Test handling of a missing token."""
    user_input = {"username": "test@example.com", "token": ""}

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "missing_token"}


async def test_invalid_auth_handling(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of invalid authentication."""
    user_input = {"username": "testuser@example.com", "token": "aas_et/" + "x" * 216}

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "invalid_auth"}


async def test_invalid_token(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of an invalid token."""
    user_input = {
        "username": "testuser@example.com",
        "token": "",  # Empty token
    }

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    auth_fail_result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert auth_fail_result["type"] == "form"
    assert auth_fail_result["errors"] == {"base": "missing_token"}


async def test_user_input_handling(hass: HomeAssistant, mock_google_keep_api):
    """Test user input handling."""
    user_input = {"username": "validuser@example.com", "token": "validtoken"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )
    # The next step after user input should be the options step
    assert result["type"] == "form"
    assert result["step_id"] == "options"


async def test_unexpected_exception_handling(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of unexpected exceptions."""
    # Access the mocked GoogleKeepAPI instance and set authenticate
    # to raise an exception
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.side_effect = Exception("Test Exception")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={"username": "user@example.com", "token": "some_token"},
    )

    # Assert that an unknown error is handled
    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_flow(hass: HomeAssistant, mock_google_keep_api):
    """Test reauthentication flow."""
    # Create a mock entry to simulate existing config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"username": "user@example.com", "token": "old_token"},
    )
    mock_entry.add_to_hass(hass)

    # Patch the mock to return the new token after reauth
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = True
    mock_instance.token = "new_token"

    # Initiate the reauthentication flow
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Assert that we are on the reauth_confirm step
    assert init_flow_result["type"] == "form"
    assert init_flow_result["step_id"] == "reauth_confirm"

    # Provide the new token
    new_token_input = {"token": "new_token"}
    config_flow_result = await hass.config_entries.flow.async_configure(
        init_flow_result["flow_id"], new_token_input
    )

    # Assert that reauthentication is successful and the flow is aborted
    assert config_flow_result["type"] == "abort"

    # Verify the entry data is updated with the new token
    updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
    assert updated_entry.data["token"] == "new_token"


async def test_options_flow(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Update user_input to include 'list_prefix'
    user_input = {
        "lists_to_sync": ["list_id_1", "list_id_3"],
        "list_prefix": "TestPrefix",
    }

    # Initialize the options flow
    init_form_response = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert init_form_response["type"] == "form"
    assert init_form_response["step_id"] == "init"

    # Fetch lists for dynamic options
    mock_google_keep_api.fetch_all_lists.return_value = [
        # Mock some lists for testing
        MockList(id="list_id_1", title="List One"),
        MockList(id="list_id_2", title="List Two"),
        MockList(id="list_id_3", title="List Three"),
    ]

    # Assert the initial form includes the 'list_prefix' field
    assert "list_prefix" in init_form_response["data_schema"].schema

    # Submit user input and get the response
    submission_response = await hass.config_entries.options.async_configure(
        init_form_response["flow_id"], user_input=user_input
    )
    assert submission_response["type"] == "create_entry"
    # Ensure the submitted 'list_prefix' is correctly handled
    assert submission_response["data"]["list_prefix"] == "TestPrefix"


async def test_reauth_flow_invalid_credentials(
    hass: HomeAssistant, mock_google_keep_api
):
    """Test reauthentication flow with invalid credentials."""
    # Create a mock entry to simulate existing config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"username": "user@example.com", "token": "old_token"},
    )
    mock_entry.add_to_hass(hass)

    # Modify the behavior of authenticate to simulate failed reauthentication
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    # Initiate the reauthentication flow
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Provide the incorrect new token
    incorrect_token_input = {"token": "wrong_token"}
    config_flow_result = await hass.config_entries.flow.async_configure(
        init_flow_result["flow_id"], incorrect_token_input
    )

    # Assert that reauthentication fails
    assert config_flow_result["type"] == "form"
    assert config_flow_result["errors"] == {"base": "invalid_auth"}


async def test_options_flow_fetch_list_failure(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow when list fetch fails."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Simulate fetch_all_lists raising an exception
    mock_instance = mock_google_keep_api.return_value
    mock_instance.fetch_all_lists.side_effect = Exception("Fetch Failed")

    # Initialize the options flow
    init_form_response = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert init_form_response["type"] == "form"
    assert init_form_response["errors"] == {"base": "list_fetch_error"}


async def test_empty_username_or_token(hass: HomeAssistant):
    """Test that empty username or token is handled."""
    # Test with empty username
    user_input = {"username": "", "token": "sometoken"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )
    assert result["errors"] == {"base": "blank_username"}

    # Test with empty token
    user_input = {"username": "username@example.com", "token": ""}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )
    assert result["errors"] == {"base": "missing_token"}


async def test_authentication_network_issue(hass: HomeAssistant, mock_google_keep_api):
    """Test network issues during authentication."""
    user_input = {"username": "testuser@example.com", "token": "testtoken"}

    # Simulate network issue
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.side_effect = CannotConnectError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )

    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_config_entry(hass: HomeAssistant, mock_google_keep_api):
    """Test that creating a duplicate configuration entry is handled."""
    user_name = "duplicateuser@example.com"
    user_token = "testtoken"

    unique_id = f"{DOMAIN}.{user_name.lower()}"

    # Create a mock entry to simulate existing config entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={"username": user_name, "token": user_token},
    )
    existing_entry.add_to_hass(hass)

    # Attempt to create a new entry with the same unique_id
    user_input = {"username": user_name, "token": "newtoken"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )

    assert result["errors"] == {"base": "already_configured"}


async def test_reauth_flow_success(hass: HomeAssistant, mock_google_keep_api):
    """Test reauthentication flow is aborted on success."""
    user_name = "testuser@example.com"
    old_token = "old_token"
    new_token = "new_token"

    # Create a mock entry to simulate existing config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=user_name.lower(),
        data={"username": user_name, "token": old_token},
    )
    mock_entry.add_to_hass(hass)

    # Modify the behavior of authenticate to simulate successful reauthentication
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = True
    mock_instance.token = new_token

    # Initiate the reauthentication flow
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Provide the new token
    new_token_input = {"token": new_token}
    config_flow_result = await hass.config_entries.flow.async_configure(
        init_flow_result["flow_id"], new_token_input
    )

    # Assert that reauthentication is successful and the flow is aborted
    assert config_flow_result["type"] == "abort"
    assert config_flow_result["reason"] in ("reauth_successful", "unique_id_mismatch")


async def test_options_flow_update_data(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test that options flow updates the configuration entry data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # New user input that changes the existing configuration
    user_input = {
        "lists_to_sync": ["list_id_1", "list_id_3"],
        "list_prefix": "TestPrefix",
    }

    # Assert that the entry data is not updated yet
    initial_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert initial_entry.data["lists_to_sync"] != user_input["lists_to_sync"]
    assert initial_entry.data["list_prefix"] != user_input["list_prefix"]

    # Initialize the options flow and capture the flow ID
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    flow_id = init_result["flow_id"]

    # Submit new user input and update the configuration entry

    await hass.config_entries.options.async_configure(flow_id, user_input=user_input)

    # Assert that the entry data is updated and reflects the changes
    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data["lists_to_sync"] == ["list_id_1", "list_id_3"]
    assert updated_entry.data["list_prefix"] == "TestPrefix"


async def test_options_flow_create_entry(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow creates an entry correctly."""
    mock_config_entry.add_to_hass(hass)

    # Initialize the options flow
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    user_input = {
        "lists_to_sync": ["list_id_1", "list_id_2"],
        "list_prefix": "Test",
        "list_auto_sort": False,
        "list_item_case": "no_change",
    }

    # Submit user input
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "create_entry"
    assert result["data"] == user_input


async def test_options_flow_reauth_required(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow aborts when reauthentication is required."""
    mock_config_entry.add_to_hass(hass)

    # Mock authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.return_value = False

    # Initialize the options flow
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    assert init_result["type"] == "abort"
    assert init_result["reason"] == "reauth_required"


async def test_user_form_cannot_connect(hass: HomeAssistant, mock_google_keep_api):
    """Test the user setup form handles connection issues."""
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.side_effect = CannotConnectError()

    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    user_input = {"username": "testuser@example.com", "token": "testtoken"}
    result = await hass.config_entries.flow.async_configure(
        initial_form_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_confirm_cannot_connect(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of network issues during reauthentication."""
    # Create a mock entry to simulate existing config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"username": "user@example.com", "token": "old_token"},
    )
    mock_entry.add_to_hass(hass)

    # Modify the behavior of authenticate to simulate a network connection issue
    mock_instance = mock_google_keep_api.return_value
    mock_instance.authenticate.side_effect = CannotConnectError()

    # Initiate the reauthentication flow
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Provide the new token input
    new_token_input = {"token": "new_token"}
    config_flow_result = await hass.config_entries.flow.async_configure(
        init_flow_result["flow_id"], new_token_input
    )

    # Assert that a network issue error is returned
    assert config_flow_result["type"] == "form"
    assert config_flow_result["errors"] == {"base": "cannot_connect"}


async def test_reauth_confirm_entry_not_found(
    hass: HomeAssistant, mock_google_keep_api
):
    """Test handling when the configuration entry is not found."""
    # Create a mock entry to simulate existing config entry,
    # but don't add it to Home Assistant
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"username": "user@example.com", "token": "old_token"},
    )

    # Initiate the reauthentication flow with the non-existent entry's ID
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Assert that the flow is aborted due to the missing config entry
    assert init_flow_result["type"] == "abort"
    assert init_flow_result["reason"] == "config_entry_not_found"

    # Provide the new token input
    new_token_input = {"token": "new_token"}

    with pytest.raises(UnknownFlow):
        await hass.config_entries.flow.async_configure(
            init_flow_result["flow_id"], user_input=new_token_input
        )


async def test_user_form_setup_with_oauth_token(
    hass: HomeAssistant, mock_google_keep_api
):
    """Test the initial user setup form with an OAuth token."""
    user_name = "testuser@example.com"
    user_token = "oauth2_4/valid_oauth_token"  # Example OAuth token
    # Patch the mock to return the expected token string
    mock_google_keep_api.return_value.token = user_token

    # Configure the mock to support OAuth tokens
    with patch(
        "custom_components.google_keep_sync.api.GoogleKeepAPI.is_oauth_token"
    ) as mock_is_oauth:
        mock_is_oauth.return_value = True  # Simulate an OAuth token

        # Initiate the config flow
        initial_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert initial_form_result["type"] == "form"
        assert initial_form_result["errors"] == {}

        # Submit user credentials with OAuth token
        user_input = {
            "username": user_name,
            "token": user_token,
        }
        credentials_form_result = await hass.config_entries.flow.async_configure(
            initial_form_result["flow_id"], user_input=user_input
        )

        # Check if the next step is the options step
        assert credentials_form_result["type"] == "form"
        assert credentials_form_result["step_id"] == "options"

        # Simulate options selection
        options_input = {
            "lists_to_sync": ["list_id_1", "list_id_2"],
            "list_prefix": "testprefix",
            "list_auto_sort": False,
            "list_item_case": "no_change",
        }
        final_form_result = await hass.config_entries.flow.async_configure(
            credentials_form_result["flow_id"], user_input=options_input
        )

        # Check the final result for entry creation
        assert final_form_result["type"] == "create_entry"
        assert final_form_result["title"] == user_name.lower()
        assert final_form_result["data"] == {
            "username": user_name,
            "token": user_token,
            "lists_to_sync": ["list_id_1", "list_id_2"],
            "list_prefix": "testprefix",
            "list_auto_sort": False,
            "list_item_case": "no_change",
        }


async def test_reauth_with_oauth_token(hass: HomeAssistant, mock_google_keep_api):
    """Test reauthentication flow with an OAuth token."""
    user_name = "testuser@example.com"
    old_token = "old_token"
    new_oauth_token = "oauth2_4/valid_oauth_token"  # Example OAuth token

    # Create a mock entry to simulate existing config entry
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=user_name.lower(),
        data={"username": user_name, "token": old_token},
    )
    mock_entry.add_to_hass(hass)

    # Configure the mock to support OAuth tokens
    mock_instance = mock_google_keep_api.return_value
    with patch(
        "custom_components.google_keep_sync.api.GoogleKeepAPI.is_oauth_token"
    ) as mock_is_oauth:
        mock_is_oauth.return_value = True  # Simulate an OAuth token
        mock_instance.authenticate.return_value = True  # Successful authentication
        mock_instance.token = new_oauth_token

        # Initiate the reauthentication flow
        init_flow_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
        )

        # Provide the new OAuth token
        new_token_input = {"token": new_oauth_token}
        config_flow_result = await hass.config_entries.flow.async_configure(
            init_flow_result["flow_id"], new_token_input
        )

        # Assert that reauthentication is successful and the flow is aborted
        assert config_flow_result["type"] == "abort"
        assert config_flow_result["reason"] == "reauth_successful"

        # Verify the entry data is updated with the new token
        updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
        assert updated_entry.data["token"] == new_oauth_token


async def test_options_flow_authentication_failure(hass, mock_api_instance):
    """Test options flow handling authentication failure."""
    # Patch GoogleKeepAPI in config_flow to use our mock
    with patch(
        "custom_components.google_keep_sync.config_flow.GoogleKeepAPI",
        return_value=mock_api_instance,
    ):
        mock_api_instance.authenticate = AsyncMock(return_value=False)

        # Create a config entry
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"username": "user@example.com", "token": "token123"},
            entry_id="test_entry",
        )
        config_entry.add_to_hass(hass)

        # Initialize options flow
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        # Should abort due to reauthentication required
        assert result["type"] == "abort"
        assert result["reason"] == "reauth_required"


async def test_options_flow_fetch_lists_error(hass, mock_api_instance):
    """Test options flow handling API errors when fetching lists."""
    # Mock API authentication to succeed but list fetch to fail
    mock_api_instance.authenticate = AsyncMock(return_value=True)
    mock_api_instance.fetch_all_lists = AsyncMock(side_effect=Exception("API Error"))

    # Create a config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "user@example.com", "token": "token123"},
        entry_id="test_entry",
    )
    config_entry.add_to_hass(hass)

    # Initialize options flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    # Verify we show form with error
    assert result["type"] == "form"
    assert result["errors"]["base"] == "list_fetch_error"


async def test_reauth_confirm_with_invalid_token(hass, mock_api_instance):
    """Test reauth confirm step with invalid token."""
    # Patch GoogleKeepAPI in config_flow
    with patch(
        "custom_components.google_keep_sync.config_flow.GoogleKeepAPI",
        return_value=mock_api_instance,
    ):
        mock_api_instance.authenticate = AsyncMock(return_value=False)

        # Create a config entry
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"username": "user@example.com", "token": "old_token"},
            entry_id="test",
        )
        config_entry.add_to_hass(hass)

        # Start reauth flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": config_entry.entry_id,
            },
            data=config_entry.data,
        )

        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

        # Submit invalid token
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"token": "invalid_token"}
        )

        # Check that we're shown the form again with invalid_auth error
        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_entry_not_found(hass, mock_api_instance):
    """Test reauth flow when entry is not found."""
    # Start reauth flow with an entry_id that doesn't exist
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": "non_existent_id"},
    )

    # Should abort with config_entry_not_found
    assert result["type"] == "abort"
    assert result["reason"] == "config_entry_not_found"


async def test_step_options_with_user_input(hass, mock_api_instance, mock_keep_list):
    """Test options flow with user input."""
    # Mock API to succeed and return lists
    mock_api_instance.authenticate = AsyncMock(return_value=True)
    mock_api_instance.fetch_all_lists = AsyncMock(return_value=[mock_keep_list])

    # Create a config flow
    flow = ConfigFlow()
    flow.hass = hass
    flow.api = mock_api_instance
    flow.user_data = {"username": "user@example.com", "token": "token123"}

    # Call async_step_options with user input
    user_input = {
        "lists_to_sync": ["list1"],
        "list_prefix": "Test: ",
        "list_auto_sort": True,
        "list_item_case": "upper",
    }

    result = await flow.async_step_options(user_input)

    # Verify result creates entry with correct data
    assert result["type"] == "create_entry"
    assert result["data"]["lists_to_sync"] == ["list1"]
    assert result["data"]["list_prefix"] == "Test: "
    assert result["data"]["list_auto_sort"] is True
    assert result["data"]["list_item_case"] == "upper"
