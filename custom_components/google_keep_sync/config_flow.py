"""Config flow for Google Keep Sync integration."""

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import GoogleKeepAPI
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
        vol.Required("password"): str,
    }
)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the Google Keep Sync integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors = {}
        lists = []

        if user_input is not None:
            # Update the config entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, **user_input}
            )
            # Reload the integration to apply new settings
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        try:
            api = GoogleKeepAPI(
                self.hass,
                self.config_entry.data["username"],
                self.config_entry.data["password"],
            )

            if not await api.authenticate():
                return self.async_abort(reason="reauth_required")

            lists = await api.fetch_all_lists()
        except Exception as e:
            _LOGGER.error("Error fetching lists: %s", e)
            errors["base"] = "list_fetch_error"

        existing_lists = self.config_entry.data.get("lists_to_sync", [])
        list_prefix = self.config_entry.data.get("list_prefix", "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "lists_to_sync", default=existing_lists
                    ): cv.multi_select({list.id: list.title for list in lists}),
                    vol.Optional("list_prefix", default=list_prefix): str,
                }
            ),
            errors=errors,
        )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Google Keep Sync."""

    VERSION = 1

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth upon authentication error."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Google Keep."""
        errors = {}

        if user_input:
            if self.entry is None:
                _LOGGER.error("Configuration entry not found")
                return self.async_abort(reason="config_entry_not_found")

            password = user_input["password"]
            data = {
                "username": self.entry.data["username"],
                "password": password,
            }

            try:
                await self.validate_input(self.hass, data)

            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        "username": self.entry.data["username"],
                        "password": password,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=SCHEMA_REAUTH,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self.api = None
        self.user_data = {}

    async def validate_input(
        self, hass: HomeAssistant, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate the user input allows us to connect."""
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        token = data.get("token", "").strip()

        if not (username and (password or token)):
            _LOGGER.error(
                "Credentials are missing; a username and password or "
                "token must be provided."
            )
            raise InvalidAuthError

        self.api = GoogleKeepAPI(hass, username, password, token)
        success = await self.api.authenticate()

        if not success:
            raise InvalidAuthError

        self.user_data = {"username": username, "password": password, "token": token}
        return {"title": "Google Keep", "entry_id": username.lower()}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step for the user to enter their credentials."""
        errors = {}
        if user_input:
            try:
                info = await self.validate_input(self.hass, user_input)

                unique_id = info["entry_id"]
                await self.async_set_unique_id(unique_id)

                # Check if an entry with the same unique_id already exists
                self._abort_if_unique_id_configured()

                return await self.async_step_options()

            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except AbortFlow:
                errors["base"] = "already_configured"
            except Exception as exc:
                _LOGGER.exception("Unexpected exception: %s", exc)
                errors["base"] = "unknown"

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
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = {
                **self.user_data,
                "lists_to_sync": user_input.get("lists_to_sync", []),
                "list_prefix": user_input.get("list_prefix", ""),
            }
            return self.async_create_entry(
                title=self.context["unique_id"], data=entry_data
            )

        lists = await self.api.fetch_all_lists()

        options_schema = vol.Schema(
            {
                vol.Required("lists_to_sync"): cv.multi_select(
                    {list.id: list.title for list in lists}
                ),
                vol.Optional("list_prefix"): str,
            }
        )

        return self.async_show_form(
            step_id="options",
            data_schema=options_schema,
            errors=errors,
        )


class CannotConnectError(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuthError(HomeAssistantError):
    """Error to indicate there is invalid auth."""
