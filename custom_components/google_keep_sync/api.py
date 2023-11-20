"""API for synchronization with Google Keep."""
import functools
import logging
from typing import Any

import gkeepapi
from homeassistant.core import HomeAssistant
from homeassistant.helpers import storage

STORAGE_KEY = "google_keep_sync"
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


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
        self._password = password
        self._store = storage.Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{username}.json"
        )
        self._authenticated = False
        self._token = token if token else None

    async def async_login_with_saved_state(self) -> bool:
        """Log in to Google Keep using the saved state and token."""
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
            except gkeepapi.exception.LoginException as e:
                _LOGGER.error(
                    "Failed to resume Google Keep with token and state: %s", e
                )
                return False
        else:
            return False

        return True

    async def async_login_with_saved_token(self) -> bool:
        """Log in to Google Keep using the saved token."""
        if self._username and self._token:
            try:
                await self._hass.async_add_executor_job(
                    self._keep.resume, self._username, self._token, None
                )
                self._token = self._keep.getMasterToken()  # Store the new token
                await self._async_save_state_and_token()

            except gkeepapi.exception.LoginException as e:
                _LOGGER.error("Failed to resume Google Keep with token: %s", e)
                return False
        else:
            return False

        return True

    async def async_login_with_password(self) -> bool:
        """Login to Google Keep using the username and password."""
        try:
            await self._hass.async_add_executor_job(
                self._keep.login, self._username, self._password
            )
            self._token = self._keep.getMasterToken()  # Store the new token
            await self._async_save_state_and_token()
        except gkeepapi.exception.LoginException as e:
            _LOGGER.error(
                "Failed to login to Google Keep with username and password: %s", e
            )
            return False

        return True

    async def authenticate(self) -> bool:
        """Log in to Google Keep."""
        if not await self.async_login_with_saved_state():
            if not await self.async_login_with_saved_token():
                if not await self.async_login_with_password():
                    return False

        self._authenticated = True
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
                raise Exception(
                    "Not authenticated with Google Keep. Please authenticate first."
                )
            return await func(api_instance, *args, **kwargs)

        return wrapper

    @authenticated_required
    async def async_create_todo_item(self, list_id: str, text: str) -> str:
        """Create a new item in a specified list in Google Keep."""
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            await self._hass.async_add_executor_job(keep_list.add, text, False)
            await self._hass.async_add_executor_job(self._keep.sync)

            # Iterate through the list items to find the newly added item
            for item in reversed(keep_list.items):
                if item.text == text and not item.checked:
                    return item.id  # Return the ID of the newly created item

            raise Exception("Failed to find the newly created item in Google Keep.")
        else:
            raise Exception(f"List with ID {list_id} not found in Google Keep.")

    async def _async_save_state_and_token(self) -> None:
        """Save the current state, token, and username of Google Keep."""
        state = await self._hass.async_add_executor_job(self._keep.dump)

        if not self._token:
            self._token = self._keep.getMasterToken()

        await self._store.async_save(
            {"token": self._token, "state": state, "username": self._username}
        )

    async def _async_clear_token(self) -> None:
        """Clear the saved token."""
        await self._store.async_save({"token": None, "username": None})

    async def _async_load_state_and_token(
        self,
    ) -> tuple[str | None, str | None, str | None]:
        """Load the saved state and token of Google Keep."""
        data = await self._store.async_load()
        if not data:
            return None, None, None

        state = data.get("state")
        token = data.get("token")
        saved_username = data.get("username")
        return token, state, saved_username

    @authenticated_required
    async def async_delete_todo_item(self, list_id: str, item_id: str) -> None:
        """Delete a specific item from a Google Keep list."""
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            item_to_delete = next(
                (item for item in keep_list.items if item.id == item_id), None
            )
            if item_to_delete:
                # Delete the item using the delete method on the ListItem object
                await self._hass.async_add_executor_job(item_to_delete.delete)
                await self._hass.async_add_executor_job(self._keep.sync)
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
        keep_list = self._keep.get(list_id)
        if keep_list and isinstance(keep_list, gkeepapi.node.List):
            for item in keep_list.items:
                if item.id == item_id:
                    if new_text is not None:
                        item.text = new_text
                    if checked is not None:
                        item.checked = checked
                    break
            await self._hass.async_add_executor_job(self._keep.sync)

    @authenticated_required
    async def fetch_all_lists(self) -> list[gkeepapi.node.List]:
        """Fetch all lists from Google Keep."""
        # Ensure the API is synced
        await self._hass.async_add_executor_job(self._keep.sync)

        # Retrieve all lists
        return [
            note for note in self._keep.all() if isinstance(note, gkeepapi.node.List)
        ]

    @authenticated_required
    async def async_sync_data(self) -> list[dict[str, Any]] | None:
        """Asynchronously synchronize data with Google Keep."""
        try:
            # Run the synchronous Keep sync method in the executor
            await self._hass.async_add_executor_job(self._keep.sync)

            # Process and return the list data with their items' checked status
            lists = []
            for node in self._keep.all():
                if isinstance(node, gkeepapi.node.List):
                    list_items = [
                        {"id": item.id, "text": item.text, "checked": item.checked}
                        for item in node.items
                    ]
                    lists.append(
                        {"id": node.id, "title": node.title, "items": list_items}
                    )

            return lists

        except gkeepapi.exception.SyncException as e:
            _LOGGER.error("Failed to sync with Google Keep: %s", e)
            return None
