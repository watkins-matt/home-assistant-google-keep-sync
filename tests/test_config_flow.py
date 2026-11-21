"""Test config flow for Google Keep Sync."""

import json
import re
import secrets
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import gkeepapi
import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry as HAMockConfigEntry,
)

from custom_components.google_keep_sync.config_flow import (
    CannotConnectError,
    ConfigFlow,
)
from custom_components.google_keep_sync.const import (
    DEFAULT_SYNC_INTERVAL_MINUTES,
    DOMAIN,
)
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
        mock_instance.async_login_with_token = AsyncMock(return_value=True)
        mock_instance.fetch_all_lists = AsyncMock(return_value=mock_lists)
        mock_instance.async_enable_state_persistence = AsyncMock()
        yield mock

        mock.reset_mock()


async def test_user_form_setup(hass: HomeAssistant, mock_google_keep_api):
    """Test the initial user setup form, with a username and token."""
    user_name = "testuser@example.com"
    user_token = "aas_et/" + "x" * 216  # master token
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
    # Sign-in state is kept in memory until the entry is created
    mock_google_keep_api.assert_called_once_with(
        hass, user_name, user_token, persist_state=False
    )
    mock_instance = mock_google_keep_api.return_value
    mock_instance.async_enable_state_persistence.assert_not_awaited()

    # Simulate options selection - including list selection and list prefix
    options_input = {
        "lists_to_sync": ["list_id_1", "list_id_2"],
        "list_prefix": "testprefix",
        "list_auto_sort": False,
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
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
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "",
    }
    mock_instance.async_enable_state_persistence.assert_awaited_once()


@pytest.fixture
def fake_keep():
    """Replace gkeepapi.Keep so the real GoogleKeepAPI signs in without Google."""
    with patch(
        "custom_components.google_keep_sync.api.gkeepapi.Keep", autospec=True
    ) as keep_class:
        keep = keep_class.return_value
        keep.dump.return_value = {"nodes": []}
        keep.all.return_value = []
        yield keep


async def _start_flow_to_list_selection(
    hass: HomeAssistant, keep: MagicMock, username: str
) -> str:
    """Sign in through the user step and return the flow id at list selection."""
    master_token = "aas_et/" + secrets.token_urlsafe(32)
    keep.getMasterToken.return_value = master_token
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"username": username, "token": master_token}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "options"
    return result["flow_id"]


async def test_canceled_flow_saves_nothing(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """Canceling at list selection leaves no saved token or state."""
    flow_id = await _start_flow_to_list_selection(
        hass, fake_keep, "testuser@example.com"
    )
    assert "google_keep_sync.testuser@example.com.json" not in hass_storage

    hass.config_entries.flow.async_abort(flow_id)
    await hass.async_block_till_done()

    assert not [name for name in hass_storage if name.startswith("google_keep_sync")]


async def test_finished_flow_saves_state_for_setup(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """Finishing the flow saves the sign-in state before setup reads it."""
    flow_id = await _start_flow_to_list_selection(
        hass, fake_keep, "testuser@example.com"
    )
    with patch(
        "custom_components.google_keep_sync.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"lists_to_sync": []}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    saved = hass_storage["google_keep_sync.testuser@example.com.json"]["data"]
    assert saved == {
        "token": result["data"]["token"],
        "state": {"nodes": []},
        "username": "testuser@example.com",
    }


async def test_finished_flow_creates_entry_when_save_fails(
    hass: HomeAssistant, mock_google_keep_api
):
    """A failed save doesn't block the entry; setup signs in with the token."""
    mock_instance = mock_google_keep_api.return_value
    mock_instance.token = "aas_et/" + secrets.token_urlsafe(32)
    mock_instance.async_enable_state_persistence.side_effect = OSError("disk full")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"username": "testuser@example.com", "token": mock_instance.token},
    )
    with patch(
        "custom_components.google_keep_sync.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"lists_to_sync": []}
        )

    assert result["type"] == "create_entry"
    mock_instance.async_enable_state_persistence.assert_awaited_once()


async def test_user_form_blank_username(hass: HomeAssistant, mock_google_keep_api):
    """Test handling of a blank username."""
    user_input = {"username": " ", "token": "sometoken"}

    # Get the mock instance and set authenticate to return False
    mock_instance = mock_google_keep_api.return_value
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.side_effect = Exception("Test Exception")

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
    mock_instance.async_login_with_token.return_value = True
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


async def test_reauth_flow_invalid_token_format(hass: HomeAssistant):
    """Test reauth shows the invalid_token_format error for a malformed token.

    Uses the real GoogleKeepAPI (not mocked), since its constructor raises
    ValueError for a malformed token if the flow does not validate it first.
    """
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={"username": "user@example.com", "token": "aas_et/old_token"},
    )
    mock_entry.add_to_hass(hass)

    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    config_flow_result = await hass.config_entries.flow.async_configure(
        init_flow_result["flow_id"], {"token": "4/0AVMBsJh-partial-cookie"}
    )

    assert config_flow_result["type"] == "form"
    assert config_flow_result["step_id"] == "reauth_confirm"
    assert config_flow_result["errors"] == {"base": "invalid_token_format"}
    # The stored token must be left unchanged
    assert mock_entry.data["token"] == "aas_et/old_token"


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
    mock_instance.async_login_with_token.return_value = False

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
    mock_instance.async_login_with_token.side_effect = CannotConnectError()

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
    mock_instance.async_login_with_token.return_value = True
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
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
    }

    # Submit user input
    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "create_entry"
    # Result data includes the raw user_input plus empty_item_placeholder default
    expected_data = {**user_input, "empty_item_placeholder": ""}
    assert result["data"] == expected_data


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
    mock_instance.async_login_with_token.side_effect = CannotConnectError()

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
    mock_instance.async_login_with_token.side_effect = CannotConnectError()

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
        entry_id="test_entry_id",  # Add a specific entry ID for consistent testing
    )

    # Initiate the reauthentication flow with the non-existent entry's ID
    init_flow_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_entry.entry_id}
    )

    # Assert that the flow is aborted due to the missing config entry
    assert init_flow_result["type"] == "abort"
    assert init_flow_result["reason"] == "config_entry_not_found"


async def test_reauth_entry_not_found(
    hass: HomeAssistant, mock_api_instance: MagicMock
):
    """Test reauth flow when entry is not found."""
    # Start reauth flow with an entry_id that doesn't exist
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": "non_existent_id"},
    )

    # Should abort with config_entry_not_found
    assert result["type"] == "abort"
    assert result["reason"] == "config_entry_not_found"


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
            "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
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
            "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
            "empty_item_placeholder": "",
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
        mock_instance.async_login_with_token.return_value = True
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
        assert config_flow_result["reason"] in (
            "reauth_successful",
            "unique_id_mismatch",
        )

        # Verify the entry data is updated with the new token
        updated_entry = hass.config_entries.async_get_entry(mock_entry.entry_id)
        assert updated_entry.data["token"] == new_oauth_token


async def test_options_flow_authentication_failure(
    hass: HomeAssistant, mock_api_instance: MagicMock
):
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


async def test_options_flow_fetch_lists_error(
    hass: HomeAssistant, mock_api_instance: MagicMock
):
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


async def test_reauth_confirm_with_invalid_token(
    hass: HomeAssistant, mock_api_instance: MagicMock
):
    """Test reauth confirm step with invalid token."""
    # Patch GoogleKeepAPI in config_flow
    with patch(
        "custom_components.google_keep_sync.config_flow.GoogleKeepAPI",
        return_value=mock_api_instance,
    ):
        mock_api_instance.async_login_with_token = AsyncMock(return_value=False)

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


async def test_step_options_with_user_input(
    hass: HomeAssistant, mock_api_instance: MagicMock, mock_keep_list: MagicMock
):
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
    custom_sync_interval = DEFAULT_SYNC_INTERVAL_MINUTES * 2  # 30 minutes
    user_input = {
        "lists_to_sync": ["list1"],
        "list_prefix": "Test: ",
        "list_auto_sort": True,
        "list_item_case": "upper",
        "sync_interval": custom_sync_interval,
    }

    result = await flow.async_step_options(user_input)

    # Verify result creates entry with correct data
    assert result["type"] == "create_entry"
    assert result["data"]["lists_to_sync"] == ["list1"]
    assert result["data"]["list_prefix"] == "Test: "
    assert result["data"]["list_auto_sort"] is True
    assert result["data"]["list_item_case"] == "upper"
    assert result["data"]["sync_interval"] == custom_sync_interval


async def test_options_flow_with_empty_item_placeholder(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow correctly stores empty_item_placeholder."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initialize the options flow
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert init_result["type"] == "form"
    assert init_result["step_id"] == "init"

    # Assert the form includes the 'empty_item_placeholder' field
    assert "empty_item_placeholder" in init_result["data_schema"].schema

    # Submit user input with empty_item_placeholder
    user_input = {
        "lists_to_sync": ["list_id_1", "list_id_2"],
        "list_prefix": "",
        "list_auto_sort": False,
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "---",
    }

    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "create_entry"
    assert result["data"]["empty_item_placeholder"] == "---"


async def test_options_flow_placeholder_whitespace_stripped(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow strips whitespace from empty_item_placeholder."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initialize the options flow
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    # Submit user input with whitespace-padded placeholder
    user_input = {
        "lists_to_sync": ["list_id_1"],
        "list_prefix": "",
        "list_auto_sort": False,
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "  ---  ",  # Has leading/trailing whitespace
    }

    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "create_entry"
    # Whitespace should be stripped in the config entry data
    updated_entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert updated_entry.data["empty_item_placeholder"] == "---"


async def test_options_flow_placeholder_empty_stored_as_empty(
    hass: HomeAssistant, mock_google_keep_api, mock_config_entry
):
    """Test options flow stores empty placeholder as empty string."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initialize the options flow
    init_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    # Submit user input with empty placeholder (disabled)
    user_input = {
        "lists_to_sync": ["list_id_1"],
        "list_prefix": "",
        "list_auto_sort": False,
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "",
    }

    result = await hass.config_entries.options.async_configure(
        init_result["flow_id"], user_input=user_input
    )

    assert result["type"] == "create_entry"
    assert result["data"]["empty_item_placeholder"] == ""


async def test_step_options_with_placeholder(
    hass: HomeAssistant, mock_api_instance: MagicMock, mock_keep_list: MagicMock
):
    """Test ConfigFlow options step stores empty_item_placeholder correctly."""
    # Mock API to succeed and return lists
    mock_api_instance.authenticate = AsyncMock(return_value=True)
    mock_api_instance.fetch_all_lists = AsyncMock(return_value=[mock_keep_list])

    # Create a config flow
    flow = ConfigFlow()
    flow.hass = hass
    flow.api = mock_api_instance
    flow.user_data = {"username": "user@example.com", "token": "token123"}

    # Call async_step_options with user input including placeholder
    user_input = {
        "lists_to_sync": ["list1"],
        "list_prefix": "",
        "list_auto_sort": False,
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "---",
    }

    result = await flow.async_step_options(user_input)

    # Verify result creates entry with correct data including placeholder
    assert result["type"] == "create_entry"
    assert result["data"]["empty_item_placeholder"] == "---"


async def test_step_options_auto_sort_clears_placeholder(
    hass: HomeAssistant, mock_api_instance: MagicMock, mock_keep_list: MagicMock
):
    """Test that auto_sort clears empty_item_placeholder (incompatible features)."""
    # Mock API to succeed and return lists
    mock_api_instance.authenticate = AsyncMock(return_value=True)
    mock_api_instance.fetch_all_lists = AsyncMock(return_value=[mock_keep_list])

    # Create a config flow
    flow = ConfigFlow()
    flow.hass = hass
    flow.api = mock_api_instance
    flow.user_data = {"username": "user@example.com", "token": "token123"}

    # Call async_step_options with auto_sort enabled AND placeholder set
    user_input = {
        "lists_to_sync": ["list1"],
        "list_prefix": "",
        "list_auto_sort": True,  # Auto-sort enabled
        "list_item_case": "no_change",
        "sync_interval": DEFAULT_SYNC_INTERVAL_MINUTES,
        "empty_item_placeholder": "---",  # Should be cleared
    }

    result = await flow.async_step_options(user_input)

    # Verify placeholder was cleared because auto_sort is enabled
    assert result["type"] == "create_entry"
    assert result["data"]["empty_item_placeholder"] == ""
    assert result["data"]["list_auto_sort"] is True


def _new_master_token() -> str:
    """Return a master token made up for one test."""
    return "aas_et/" + secrets.token_urlsafe(32)


def _accept_only(keep: MagicMock, accepted: str) -> None:
    """Make the fake Keep accept one token, with or without a saved state."""

    def authenticate(email, master_token, state=None, sync=True, device_id=None):
        if master_token != accepted:
            raise gkeepapi.exception.LoginException("BadAuthentication")
        keep.getMasterToken.return_value = master_token

    keep.authenticate.side_effect = authenticate


def _seed_cache(hass_storage: dict, username: str, cached_token: str) -> str:
    """Store a working saved state for username under cached_token."""
    storage_name = f"google_keep_sync.{username}.json"
    hass_storage[storage_name] = {
        "version": 1,
        "key": storage_name,
        "data": {"token": cached_token, "state": {"nodes": []}, "username": username},
    }
    return storage_name


def _loaded_entry(hass: HomeAssistant, username: str, entry_token: str):
    """Add a real config entry for username with entry_token."""
    entry = HAMockConfigEntry(
        domain=DOMAIN,
        title=username,
        unique_id=f"{DOMAIN}.{username}",
        data={"username": username, "token": entry_token, "lists_to_sync": []},
    )
    entry.add_to_hass(hass)
    return entry


async def _submit_reauth(hass: HomeAssistant, entry, submitted: str):
    """Run the reauth flow for entry with the submitted token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"token": submitted}
    )
    await hass.async_block_till_done()
    return result


async def test_reauth_rejects_bad_token_even_with_working_cache(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """A bad replacement token fails reauth; the old token stays in place."""
    username = "testuser@example.com"
    old_token = _new_master_token()
    _accept_only(fake_keep, old_token)
    storage_name = _seed_cache(hass_storage, username, old_token)
    entry = _loaded_entry(hass, username, old_token)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await _submit_reauth(hass, entry, _new_master_token())

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["token"] == old_token
    assert hass_storage[storage_name]["data"]["token"] == old_token


async def test_reauth_switches_running_entry_to_new_token(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """A good replacement token is stored, and the reloaded entry uses it."""
    username = "testuser@example.com"
    old_token = _new_master_token()
    new_token = _new_master_token()
    _accept_only(fake_keep, old_token)
    storage_name = _seed_cache(hass_storage, username, old_token)
    entry = _loaded_entry(hass, username, old_token)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The old token is revoked and only the new one works from now on
    _accept_only(fake_keep, new_token)
    fake_keep.authenticate.reset_mock()
    result = await _submit_reauth(hass, entry, new_token)

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == new_token
    assert entry.state is ConfigEntryState.LOADED
    used_tokens = {call.args[1] for call in fake_keep.authenticate.call_args_list}
    assert used_tokens == {new_token}
    assert hass_storage[storage_name]["data"]["token"] == new_token


async def test_user_step_ignores_cache_left_from_earlier_install(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """The user step checks the submitted token, not a leftover saved state."""
    username = "testuser@example.com"
    leftover_token = _new_master_token()
    _accept_only(fake_keep, leftover_token)
    _seed_cache(hass_storage, username, leftover_token)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"username": username, "token": _new_master_token()},
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


def _reauth_flows(hass: HomeAssistant) -> list:
    """Return the reauth flows Home Assistant has started for this integration."""
    return [
        flow
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        if flow["context"]["source"] == config_entries.SOURCE_REAUTH
    ]


@pytest.fixture
def no_backoff_delay():
    """Skip the sleeps between sync retries."""
    with patch(
        "custom_components.google_keep_sync.exponential_backoff.asyncio.sleep",
        AsyncMock(),
    ):
        yield


async def test_rejected_token_at_startup_prompts_reauth(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """A token Google rejects at startup opens the reauth prompt by itself."""
    _accept_only(fake_keep, _new_master_token())
    entry = _loaded_entry(hass, "testuser@example.com", _new_master_token())

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert [flow["context"]["entry_id"] for flow in _reauth_flows(hass)] == [
        entry.entry_id
    ]


async def test_network_failure_at_startup_retries_without_reauth(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """If Google can't be reached at startup, setup is retried; no reauth."""
    fake_keep.authenticate.side_effect = ConnectionError("Network is unreachable")
    entry = _loaded_entry(hass, "testuser@example.com", _new_master_token())

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert _reauth_flows(hass) == []


async def test_token_revoked_while_running_prompts_reauth(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock, no_backoff_delay
):
    """A token revoked while running opens the reauth prompt on the next sync."""
    entry_token = _new_master_token()
    _accept_only(fake_keep, entry_token)
    entry = _loaded_entry(hass, "testuser@example.com", entry_token)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _reauth_flows(hass) == []

    # gkeepapi raises LoginException when it can't refresh a revoked token
    fake_keep.sync.reset_mock()
    fake_keep.sync.side_effect = gkeepapi.exception.LoginException("BadAuthentication")
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()

    assert [flow["context"]["entry_id"] for flow in _reauth_flows(hass)] == [
        entry.entry_id
    ]
    # Prompted on the first refusal, without the retries a network error gets
    assert fake_keep.sync.call_count == 1


async def test_network_failure_while_running_keeps_lists_without_reauth(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock, no_backoff_delay
):
    """A sync that can't reach Google keeps the entry loaded and asks nothing."""
    entry_token = _new_master_token()
    _accept_only(fake_keep, entry_token)
    entry = _loaded_entry(hass, "testuser@example.com", entry_token)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    fake_keep.sync.side_effect = ConnectionError("Network is unreachable")
    await hass.data[DOMAIN][entry.entry_id].async_refresh()
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert _reauth_flows(hass) == []


async def test_reauth_prompt_from_startup_recovers_the_entry(
    hass: HomeAssistant, hass_storage: dict, fake_keep: MagicMock
):
    """Answering the automatic prompt with a working token loads the entry."""
    new_token = _new_master_token()
    _accept_only(fake_keep, new_token)
    entry = _loaded_entry(hass, "testuser@example.com", _new_master_token())
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    (flow,) = _reauth_flows(hass)

    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"token": new_token}
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["token"] == new_token


@pytest.mark.parametrize(
    ("source", "step_id"),
    [(config_entries.SOURCE_USER, "user"), ("reauth", "reauth_confirm")],
)
async def test_form_provides_every_placeholder_in_its_text(
    hass: HomeAssistant, source: str, step_id: str
):
    """Test the token forms fill in every placeholder their text uses.

    A placeholder the flow doesn't pass shows up as raw text such as
    "{token_help_url}" instead of a link.
    """
    strings = json.loads(
        (
            Path(__file__).parents[1]
            / "custom_components"
            / "google_keep_sync"
            / "strings.json"
        ).read_text(encoding="utf-8")
    )
    description = strings["config"]["step"][step_id]["description"]
    context: dict[str, str] = {"source": source}
    if source == "reauth":
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="user@example.com",
            data={"username": "user@example.com", "token": "aas_et/old_token"},
        )
        entry.add_to_hass(hass)
        context["entry_id"] = entry.entry_id

    result = await hass.config_entries.flow.async_init(DOMAIN, context=context)

    assert result["step_id"] == step_id
    used = set(re.findall(r"\{([a-z_]+)\}", description))
    assert used == {"embedded_setup_url", "token_help_url"}
    assert used <= set(result["description_placeholders"])
    for name in used:
        assert result["description_placeholders"][name].startswith("https://")
