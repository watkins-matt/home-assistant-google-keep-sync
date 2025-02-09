"""API for synchronization with Google Keep."""

import functools
import logging
from enum import StrEnum

import gkeepapi
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

from .exponential_backoff import exponential_backoff

STORAGE_KEY = "google_keep_sync"
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


class ListCase(StrEnum):
    """Enumeration for different list case options."""

    NO_CHANGE = "no_change"
    UPPER = "upper"
    LOWER = "lower"
    SENTENCE = "sentence"
    TITLE = "title"


class GoogleKeepAPI:
    """Class to authenticate and interact with Google Keep."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str = "",
        token: str | None = None,
    ):
        """Initialize the API."""
        self._keep = gkeepapi.Keep()

        self._hass = hass
        self._username = username
        self._username_redacted = self.redact_username(username)
        self._password = password
        self._store = storage.Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{username}.json"
        )
        self._authenticated = False
        self._token = token if token else None
        self._last_synced: list[gkeepapi.node.List] = []
        _LOGGER.debug("GoogleKeepAPI initialized for user: %s", self._username_redacted)

    def redact_username(self, username: str) -> str:
        """Return a redacted version of the username for logging."""
        if not username:
            return "Unknown"

        if "@" in username:
            local, domain = username.split("@", 1)
            # Redact the local part: keep only the first character
            redacted_local = local[0] + "*" * (len(local) - 1) if local else ""
            # Extract the TLD from the domain if possible
            if "." in domain:
                tld = domain.split(".")[-1]
                return f"{redacted_local}@.{tld}"
            return f"{redacted_local}@"

        return username[0] + "*" * (len(username) - 1)

    async def async_login_with_saved_state(self) -> bool:
        """Log in to Google Keep using the saved state and token."""
        _LOGGER.debug(
            "Attempting login with saved state for user: %s", self._username_redacted
        )
        # Load the saved token and state
        (
            saved_token,
            saved_state,
            saved_username,
        ) = await self._async_load_state_and_token()

        if saved_token and saved_state and saved_username:
            try:
                await self._hass.async_add_executor_job(
                    self._keep.resume, self._username, saved_token, saved_state
                )
                self._token = saved_token  # Use the saved token
                _LOGGER.debug(
                    "Successfully logged in with saved state for user: %s",
                    self._username_redacted,
                )
            except gkeepapi.exception.LoginException as e:
                _LOGGER.error(
                    "Failed to resume Google Keep with token and state for user %s: %s",
                    self._username_redacted,
                    e,
                )
                return False
            except gkeepapi.exception.ResyncRequiredException as e:
                _LOGGER.warning(
                    "Full resync required for user %s: %s", self._username_redacted, e
                )
                return False
        else:
            _LOGGER.debug("No saved state found for user: %s", self._username_redacted)
            return False

        self._authenticated = True
        return True

    async def async_login_with_saved_token(self) -> bool:
        """Log in to Google Keep using the saved token."""
        _LOGGER.debug(
            "Attempting login with saved token for user: %s", self._username_redacted
        )
        if self._username and self._token:
            try:
                await self._hass.async_add_executor_job(
                    self._keep.resume, self._username, self._token, None
                )
                self._token = self._keep.getMasterToken()  # Store the new token
                await self._async_save_state_and_token()
                _LOGGER.debug(
                    "Successfully logged in with saved token for user: %s",
                    self._username_redacted,
                )
            except gkeepapi.exception.LoginException as e:
                _LOGGER.error(
                    "Failed to resume Google Keep with token for user %s: %s",
                    self._username_redacted,
                    e,
                )
                return False
        else:
            _LOGGER.debug("No saved token found for user: %s", self._username_redacted)
            return False

        self._authenticated = True
        return True

    async def async_login_with_password(self) -> bool:
        """Login to Google Keep using the username and password."""
        _LOGGER.debug(
            "Attempting login with password for user: %s", self._username_redacted
        )
        try:
            await self._hass.async_add_executor_job(
                self._keep.login, self._username, self._password
            )
            self._token = self._keep.getMasterToken()  # Store the new token
            await self._async_save_state_and_token()
            _LOGGER.debug(
                "Successfully logged in with password for user: %s", self._username
            )
        except gkeepapi.exception.LoginException as e:
            _LOGGER.error(
                "Failed to login to Google Keep with "
                "username and password for user %s: %s",
                self._username_redacted,
                e,
            )
            return False

        self._authenticated = True
        return True

    async def authenticate(self) -> bool:
        """Log in to Google Keep."""
        _LOGGER.debug(
            "Starting authentication process for user: %s", self._username_redacted
        )
        if not await self.async_login_with_saved_state():
            if not await self.async_login_with_saved_token():
                if not await self.async_login_with_password():
                    _LOGGER.error(
                        "All authentication methods failed for user: %s", self._username
                    )
                    return False

        _LOGGER.debug("Authentication successful for user: %s", self._username_redacted)
        return True

    @property
    def username(self) -> str:
        """Return the username."""
        return self._username

    @property
    def token(self) -> str | None:
        """Return the stored token."""
        return self._token

    @staticmethod
    def authenticated_required(func):
        """Ensure the user is authenticated before calling the function."""

        @functools.wraps(func)
        async def wrapper(api_instance, *args, **kwargs):
            if not api_instance._authenticated:
                _LOGGER.error(
                    "Attempted to call %s without authentication for user: %s",
                    func.__name__,
                    api_instance._username,
                )
                raise Exception(
                    "Not authenticated with Google Keep. Please authenticate first."
                )
            return await func(api_instance, *args, **kwargs)

        return wrapper

    @authenticated_required
    async def async_create_todo_item(self, list_id: str, text: str) -> None:
        """Create a new item in a specified list in Google Keep."""
        _LOGGER.debug("Creating new todo item in list %s: %s", list_id, text)
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            await self._hass.async_add_executor_job(keep_list.add, text, False)
            _LOGGER.debug("Successfully created new todo item in list %s", list_id)
        else:
            _LOGGER.error(
                "List with ID %s not found in Google Keep for user: %s",
                list_id,
                self._username_redacted,
            )
            raise Exception(f"List with ID {list_id} not found in Google Keep.")

    async def _async_save_state_and_token(self) -> None:
        """Save the current state, token, and username of Google Keep."""
        _LOGGER.debug("Saving state and token for user: %s", self._username_redacted)
        state = await self._hass.async_add_executor_job(self._keep.dump)

        if not self._token:
            self._token = self._keep.getMasterToken()

        await self._store.async_save(
            {"token": self._token, "state": state, "username": self._username}
        )
        _LOGGER.debug("State and token saved for user: %s", self._username_redacted)

    async def _async_clear_token(self) -> None:
        """Clear the saved token."""
        _LOGGER.debug("Clearing token for user: %s", self._username_redacted)
        await self._store.async_save({"token": None, "username": None})
        _LOGGER.debug("Token cleared for user: %s", self._username_redacted)

    async def _async_load_state_and_token(
        self,
    ) -> tuple[str | None, str | None, str | None]:
        """Load the saved state and token of Google Keep."""
        _LOGGER.debug("Loading state and token for user: %s", self._username_redacted)
        data = await self._store.async_load()
        if not data:
            _LOGGER.debug(
                "No saved state or token found for user: %s", self._username_redacted
            )
            return None, None, None

        state = data.get("state")
        token = data.get("token")
        saved_username = data.get("username")
        _LOGGER.debug("Loaded state and token for user: %s", self._username_redacted)
        return token, state, saved_username

    @authenticated_required
    async def async_delete_todo_item(self, list_id: str, item_id: str) -> None:
        """Delete a specific item from a Google Keep list."""
        _LOGGER.debug("Deleting todo item %s from list %s", item_id, list_id)
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            item_to_delete = next(
                (item for item in keep_list.items if item.id == item_id), None
            )
            if item_to_delete:
                # Delete the item using the delete method on the ListItem object
                await self._hass.async_add_executor_job(item_to_delete.delete)
                _LOGGER.debug(
                    "Item %s deleted from list %s in Google Keep", item_id, list_id
                )
            else:
                _LOGGER.warning("Item %s not found in list %s", item_id, list_id)
        else:
            _LOGGER.error("List %s not found in Google Keep", list_id)

    @authenticated_required
    async def async_update_todo_item(
        self,
        list_id: str,
        item_id: str,
        new_text: str | None = None,
        checked: bool = False,
    ) -> None:
        """Update an existing item within a list in Google Keep."""
        _LOGGER.debug("Updating todo item %s in list %s", item_id, list_id)
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            for item in keep_list.items:
                if item.id == item_id:
                    if new_text is not None:
                        item.text = new_text
                    if checked is not None:
                        item.checked = checked
                    _LOGGER.debug(
                        "Successfully updated item %s in list %s", item_id, list_id
                    )
                    break
            else:
                _LOGGER.warning("Item %s not found in list %s", item_id, list_id)
        else:
            _LOGGER.error("List %s not found in Google Keep", list_id)

    @authenticated_required
    async def fetch_all_lists(self) -> list[gkeepapi.node.List]:
        """Fetch all lists from Google Keep."""
        _LOGGER.debug("Fetching all lists from Google Keep")
        # Ensure the API is synced
        await self._hass.async_add_executor_job(self._keep.sync)

        # Retrieve all lists
        lists = [
            note for note in self._keep.all() if isinstance(note, gkeepapi.node.List)
        ]
        _LOGGER.debug("Fetched %d lists from Google Keep", len(lists))
        return lists

    @exponential_backoff(
        max_retries=5,
        base_delay=1.0,
        backoff_factor=3.0,
        exceptions=(Exception,),
    )
    async def _sync_with_google_keep(self):
        """Sync with Google Keep using exponential backoff for retry."""
        await self._hass.async_add_executor_job(self._keep.sync)
        _LOGGER.debug("Successfully synced with Google Keep")

    @authenticated_required
    async def async_sync_data(
        self,
        lists_to_sync: list[str],
        sort_lists=False,
        change_case: ListCase = ListCase.NO_CHANGE,
    ) -> tuple[list[gkeepapi.node.List], list[str]]:
        """Synchronize data only from configured lists with Google Keep."""
        _LOGGER.debug("Starting sync for %d lists", len(lists_to_sync))
        lists_changed: bool = False
        deleted_list_ids: list[str] = []
        synced_lists: list[gkeepapi.node.List] = []

        try:
            await self._sync_with_google_keep()

            # Only get the lists that are configured to sync
            for list_id in lists_to_sync:
                keep_list: gkeepapi.node.List | None = (
                    await self._hass.async_add_executor_job(self._keep.get, list_id)
                )
                if keep_list is None:
                    _LOGGER.warning(
                        f"List with ID {list_id} not found. It may have been deleted."
                    )
                    deleted_list_ids.append(list_id)
                    continue

                _LOGGER.debug("Processing list: %s", keep_list.title)

                # Change the case of the list items if necessary
                if change_case != ListCase.NO_CHANGE:
                    list_changed = await self._hass.async_add_executor_job(
                        self.change_list_case, keep_list.items, change_case
                    )

                    if list_changed:
                        lists_changed = True
                        _LOGGER.debug("Case changed for list: %s", keep_list.title)

                # Sort the lists if the option is enabled
                if sort_lists:
                    unchecked: list[gkeepapi.node.ListItem] = keep_list.unchecked

                    # Don't sort the list if it's already sorted
                    if not self.is_list_sorted(unchecked):
                        # Sort the items, case-insensitive by default
                        await self._hass.async_add_executor_job(
                            keep_list.sort_items, lambda item: item.text.lower()
                        )
                        lists_changed = True
                        _LOGGER.debug("List sorted: %s", keep_list.title)

                synced_lists.append(keep_list)

            # If we made changes, we need to force an immediate resync
            # to ensure that the user's changes are not overwritten on
            # the next global sync interval
            if lists_changed:
                await self._hass.async_add_executor_job(self._keep.sync)
                _LOGGER.debug("Lists were modified, forced immediate resync completed")

            _LOGGER.debug("Sync completed, returning %d lists", len(synced_lists))

            self._last_synced = synced_lists
            return synced_lists, deleted_list_ids

        except Exception as e:
            _LOGGER.error("Failed to sync with Google Keep: %s", e)
            return (self._last_synced, [])

    @staticmethod
    def is_list_sorted(items: list[gkeepapi.node.ListItem]) -> bool:
        """Check if a list is sorted, case-insensitive by default."""
        return all(
            items[i].text.lower() <= items[i + 1].text.lower()
            for i in range(len(items) - 1)
        )

    @staticmethod
    def change_list_case(
        items: list[gkeepapi.node.ListItem], case_type: ListCase
    ) -> bool:
        """Change the case of all items in a list based on the specified case type."""
        list_changed = False

        for item in items:
            original_text = item.text
            new_text = GoogleKeepAPI.change_case(item.text, case_type)

            if original_text != new_text:
                item.text = new_text
                list_changed = True

        return list_changed

    @staticmethod
    def change_case(text: str, case_type: ListCase) -> str:
        """Change the case of the given text based on the specified case type."""
        if case_type == ListCase.UPPER:
            return text.upper()
        elif case_type == ListCase.LOWER:
            return text.lower()
        elif case_type == ListCase.SENTENCE:
            return text.capitalize()
        elif case_type == ListCase.TITLE:
            return text.title()
        return text
