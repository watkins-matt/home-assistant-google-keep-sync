"""Config flow for Google Keep Sync integration."""

import logging
import re
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .api import GoogleKeepAPI, ListCase
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INVALID_AUTH_URL = "https://github.com/watkins-matt/home-assistant-google-keep-sync?tab=readme-ov-file#invalid-authentication-errors"

SCHEMA_USER_DATA_STEP = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Optional("password"): str,
        vol.Optional("token"): str,
    }
)

SCHEMA_REAUTH = vol.Schema(
    {
        vol.Optional("password"): str,
        vol.Optional("token"): str,
    }
)

CHOICES_LIST_CASE = {
    "no_change": "Do not change",
    "upper": "UPPERCASE",
    "lower": "lowercase",
    "sentence": "Sentence case",
    "title": "Title Case",
}


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the Google Keep Sync integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        _LOGGER.debug("Initializing OptionsFlowHandler for %s", config_entry.title)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        _LOGGER.debug("Starting async_step_init in OptionsFlowHandler")
        errors = {}
        lists = []

        if user_input is not None:
            _LOGGER.debug("Processing user input in OptionsFlowHandler")
            # Update the config entry with new data
            updated_data = {
                **self.config_entry.data,
                **user_input,
                "list_auto_sort": user_input.get("list_auto_sort", False),
                "list_item_case": user_input.get(
                    "list_item_case", ListCase.NO_CHANGE.value
                ),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=updated_data
            )
            _LOGGER.debug("Updated config entry with new data")
            # Reload the integration to apply new settings
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            _LOGGER.debug("Reloaded integration with new settings")
            return self.async_create_entry(title="", data=user_input)

        try:
            _LOGGER.debug("Authenticating with Google Keep API")
            api = GoogleKeepAPI(
                self.hass,
                self.config_entry.data["username"],
                self.config_entry.data["password"],
            )

            if not await api.authenticate():
                _LOGGER.warning("Authentication failed, reauth required")
                return self.async_abort(reason="reauth_required")

            _LOGGER.debug("Fetching all lists from Google Keep API")
            all_lists = await api.fetch_all_lists()
            _LOGGER.info(
                "Fetched %d lists for user %s",
                len(all_lists),
                self.config_entry.data["username"],
            )

            visible_lists = [
                list
                for list in all_lists
                if not list.deleted and not list.trashed and not list.archived
            ]
            hidden_lists = [
                list
                for list in all_lists
                if list.deleted or list.trashed or list.archived
            ]

            if hidden_lists:
                _LOGGER.info(
                    "Showing %d lists that are not hidden, trashed, or archived. "
                    "%d lists are hidden/trashed/archived and not shown. "
                    "These must be untrashed/unhidden/unarchived to show.",
                    len(visible_lists),
                    len(hidden_lists),
                )
            else:
                _LOGGER.info("Showing %d lists", len(visible_lists))

            lists = visible_lists

        except Exception as e:
            _LOGGER.error("Error fetching lists: %s", e, exc_info=True)
            errors["base"] = "list_fetch_error"

        # Retrieve existing values
        existing_lists = self.config_entry.data.get("lists_to_sync", [])
        list_prefix = self.config_entry.data.get("list_prefix", "")
        auto_sort = self.config_entry.data.get("list_auto_sort", False)
        list_item_case = self.config_entry.data.get(
            "list_item_case", ListCase.NO_CHANGE.value
        )

        # Create a set of existing_lists for quick lookup
        existing_list_set = set(existing_lists)

        # Select all lists that are not deleted, trashed or archived. Keep
        # lists if we already had them selected previously
        lists = [
            list
            for list in lists
            if (not list.deleted and not list.trashed and not list.archived)
            or list.id in existing_list_set
        ]

        # Sort the lists by name
        lists.sort(key=lambda x: x.title)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "lists_to_sync", default=existing_lists
                    ): cv.multi_select({list.id: list.title for list in lists}),
                    vol.Optional(
                        "list_item_case", default=list_item_case
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=value)
                                for key, value in CHOICES_LIST_CASE.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("list_prefix", default=list_prefix): str,
                    vol.Optional("list_auto_sort", default=auto_sort): bool,
                }
            ),
            errors=errors,
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Google Keep Sync."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self.api = None
        self.user_data = {}
        _LOGGER.debug("Initializing ConfigFlow for Google Keep Sync.")

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth upon authentication error."""
        _LOGGER.debug("Starting reauth process")
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Google Keep."""
        _LOGGER.debug("Confirming reauth")
        errors = {}

        if user_input:
            if self.entry is None:
                _LOGGER.error("Configuration entry not found")
                return self.async_abort(reason="config_entry_not_found")

            # Add the username to user_input, since the reauth step doesn't include it
            user_input["username"] = self.entry.data["username"]

            # Process validation and handle errors
            errors = await self.handle_user_input(user_input)

            # No errors, so update the entry and reload the integration
            if not errors:
                _LOGGER.debug("Reauth successful, updating entry")
                unique_id = f"{DOMAIN}_{user_input['username']}".lower()
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data=user_input,
                    unique_id=unique_id,
                    title=user_input["username"].lower(),
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=SCHEMA_REAUTH, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def validate_input(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Validate the user input allows us to connect."""
        _LOGGER.debug("Validating user input")
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        token = data.get("token", "").strip()

        # Check for blank username
        if not username:
            raise BlankUsernameError

        # Validate email address
        if not re.match(r"[^@]+@[^@]+\.[^@]+", username):
            raise InvalidEmailError

        # Check password and token conditions
        if password and token:
            raise BothPasswordAndTokenError
        if not (password or token):
            raise NeitherPasswordNorTokenError

        # Validate token format
        valid_token_length = 223
        if token and (
            not token.startswith("aas_et/") or len(token) != valid_token_length
        ):
            raise InvalidTokenFormatError

        self.api = GoogleKeepAPI(hass, username, password, token)
        success = await self.api.authenticate()

        if not success:
            raise InvalidAuthError

        self.user_data = {"username": username, "password": password, "token": token}

    async def handle_user_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        """Handle user input, checking for any errors."""
        _LOGGER.debug("Checking user input for any errors")
        errors = {}
        try:
            await self.validate_input(self.hass, user_input)
        except InvalidAuthError:
            _LOGGER.warning("Invalid authentication")
            errors["base"] = "invalid_auth"
        except CannotConnectError:
            _LOGGER.warning("Cannot connect to Google Keep")
            errors["base"] = "cannot_connect"
        except BlankUsernameError:
            _LOGGER.warning("Blank username provided")
            errors["base"] = "blank_username"
        except InvalidEmailError:
            _LOGGER.warning("Invalid email format")
            errors["base"] = "invalid_email"
        except BothPasswordAndTokenError:
            _LOGGER.warning("Both password and token provided")
            errors["base"] = "both_password_and_token"
        except NeitherPasswordNorTokenError:
            _LOGGER.warning("Neither password nor token provided")
            errors["base"] = "neither_password_nor_token"
        except InvalidTokenFormatError:
            _LOGGER.warning("Invalid token format")
            errors["base"] = "invalid_token_format"
        except Exception as exc:
            _LOGGER.exception("Unexpected exception: %s", exc)
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step for the user to enter their credentials."""
        _LOGGER.debug("Starting async_step_user")
        errors = {}
        if user_input:
            # Check to see if the same username has already been configured
            try:
                _LOGGER.debug("Checking for existing configuration")
                unique_id = f"{DOMAIN}.{user_input['username']}".lower()
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                self._abort_if_unique_id_configured()

            # Show an error if the same username has already been configured
            except AbortFlow as abort:
                _LOGGER.warning("Configuration already exists for this username")
                errors["base"] = abort.reason
                return self.async_show_form(
                    step_id="user",
                    data_schema=SCHEMA_USER_DATA_STEP,
                    errors=errors,
                    description_placeholders={"invalid_auth_url": INVALID_AUTH_URL},
                )

            # Validate the user input for any issues
            errors = await self.handle_user_input(user_input)

            # No errors, so proceed to the next step
            if not errors:
                _LOGGER.debug("User input validated, proceeding to options step")
                return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA_USER_DATA_STEP,
            errors=errors,
            description_placeholders={"invalid_auth_url": INVALID_AUTH_URL},
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the options step."""
        _LOGGER.debug("Starting async_step_options")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("Processing user input in async_step_options")
            entry_data = {
                **self.user_data,
                "lists_to_sync": user_input.get("lists_to_sync", []),
                "list_prefix": user_input.get("list_prefix", ""),
                "list_auto_sort": user_input.get("list_auto_sort", False),
                "list_item_case": user_input.get(
                    "list_item_case", ListCase.NO_CHANGE.value
                ),
            }
            _LOGGER.info(
                "Creating config entry for user %s", self.user_data["username"]
            )
            return self.async_create_entry(
                title=self.user_data["username"].lower(), data=entry_data
            )

        # Get existing configuration options
        existing_lists = self.user_data.get("lists_to_sync", [])
        list_prefix = self.user_data.get("list_prefix", "")
        auto_sort = self.user_data.get("list_auto_sort", False)
        list_item_case = self.user_data.get("list_item_case", ListCase.NO_CHANGE.value)

        try:
            # Fetch all lists from Google Keep to display as options
            _LOGGER.debug("Fetching all lists from Google Keep API")
            all_lists = await self.api.fetch_all_lists()
            _LOGGER.info(
                "Fetched %d lists for user %s",
                len(all_lists),
                self.user_data["username"],
            )

            # Create a set of existing_lists for quick lookup
            existing_list_set = set(existing_lists)

            # Select all lists that are not deleted, trashed or archived
            visible_lists = [
                list
                for list in all_lists
                if (not list.deleted and not list.trashed and not list.archived)
                or list.id in existing_list_set
            ]
            hidden_lists = [
                list
                for list in all_lists
                if list.deleted or list.trashed or list.archived
            ]

            _LOGGER.info(
                "Showing %d lists that are not hidden, trashed, or archived. "
                "%d lists are hidden/trashed/archived and not shown. "
                "These must be untrashed/unhidden/unarchived to show.",
                len(visible_lists),
                len(hidden_lists),
            )

            # Sort the lists by name
            visible_lists.sort(key=lambda x: x.title)

            options_schema = vol.Schema(
                {
                    vol.Required(
                        "lists_to_sync", default=existing_lists
                    ): cv.multi_select({list.id: list.title for list in visible_lists}),
                    vol.Optional(
                        "list_item_case", default=list_item_case
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=value)
                                for key, value in CHOICES_LIST_CASE.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("list_prefix", default=list_prefix): str,
                    vol.Optional("list_auto_sort", default=auto_sort): bool,
                }
            )

            return self.async_show_form(
                step_id="options",
                data_schema=options_schema,
                errors=errors,
            )

        except Exception as e:
            _LOGGER.error("Error fetching lists: %s", e, exc_info=True)
            errors["base"] = "list_fetch_error"
            return self.async_show_form(
                step_id="options",
                data_schema=vol.Schema(
                    {}
                ),  # Empty schema as we couldn't fetch the lists
                errors=errors,
            )


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BlankUsernameError(HomeAssistantError):
    """Exception raised when the username is blank."""


class InvalidEmailError(HomeAssistantError):
    """Exception raised when the username is not a valid email."""


class BothPasswordAndTokenError(HomeAssistantError):
    """Exception raised when both password and token are provided."""


class NeitherPasswordNorTokenError(HomeAssistantError):
    """Exception raised when neither password nor token are provided."""


class InvalidTokenFormatError(HomeAssistantError):
    """Exception raised when the token format is invalid."""
