# Google Keep Sync for Home Assistant

[![Tests](https://github.com/watkins-matt/home-assistant-google-keep-sync/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/watkins-matt/home-assistant-google-keep-sync/actions/workflows/test.yml)
[![Coverage](https://watkins-matt.github.io/home-assistant-google-keep-sync/badges/coverage.svg)](https://github.com/watkins-matt/home-assistant-google-keep-sync/actions)

Google Keep Sync is an unofficial custom integration for Home Assistant that allows users to synchronize their Google Keep lists with Home Assistant. This project is in no way affiliated with, created, or endorsed by Google.

## Features

Bidirectional synchronization of lists between Google Keep and Home Assistant. You select the lists
you wish to sync, and they are created as todo
entities in your Home Assistant instance.

## Requirements

The integration requires Home Assistant 2023.11 or later, due to the fact that todo entities were introduced in that version.

## Installation

1. **Ensure that you have [HACS](https://www.hacs.xyz/) installed.**

1. **Add Integration via HACS**:

    After you have HACS installed, you can simply click this button:

    [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=watkins-matt&repository=home-assistant-google-keep-sync&category=integration)
    - Click `Download`.
    - Restart Home Assistant.

    Alternatively, you can follow these instructions to add it via HACS:

    1. **Add Custom Repository**:
        - Open HACS in Home Assistant.
        - Go to `Integrations`.
        - Click on the `...` in the top right corner and select `Custom repositories`.
        - Add the URL `https://github.com/watkins-matt/home-assistant-google-keep-sync`
        - Set the category to `Integration` and click `Add`.

    2. **Install the Integration**:
        - Search for `Google Keep Sync` in the HACS Integrations.
        - Click `Download`.
        - Restart Home Assistant.

2. **Configure Integration**:
    - Get a token by following [Getting a Token](#getting-a-token) below. Have the integration's setup open before you start, because the token expires after a short time.
    - Go to `Settings` -> `Devices & Services`.
    - Click `Add Integration`.
    - Search for and select `Google Keep Sync`.
    - Enter your Google account's email address and paste the token.
    - Select the Google Keep lists you want to sync. Each one becomes a to-do list in Home Assistant. To add or remove lists later, go to `Settings` -> `Devices & Services` -> `Google Keep Sync` -> `Configure`.

## Getting a Token

The integration signs in to Google Keep with a token you copy from your browser while signing in to Google. You only need to do this once. Home Assistant asks again only if the sign-in stops working.

Use a computer; phone browsers can't show the token. If you use a [dedicated account](#recommended-use-a-dedicated-account) for the integration, sign in with that account.

1. Open a private window and go to <https://accounts.google.com/EmbeddedSetup>. A private window is `Ctrl+Shift+N` in Chrome, Edge, Brave and Opera, `Ctrl+Shift+P` in Firefox, and `Cmd+Shift+N` in Safari (on a Mac, use `Cmd` instead of `Ctrl`).
2. Enter your email address and click `Next`. Enter your password and click `Next`. Complete 2-step verification if Google asks for it.
3. If Google asks how you will use the device, choose `I will be using this device` and click `Next`.
4. On the page with Google's Terms of Service, click `I agree`.
5. **The page now keeps loading and never finishes. This is expected: your token is ready.** Don't wait for it, reload it or close it. Continue with the next step on this page.
6. Open the browser's developer tools and copy the value of the cookie named `oauth_token`:

    **Chrome, Edge, Brave and Opera**

    1. Press `F12` (Mac: `Cmd+Option+I`).
    2. Open the `Application` tab. If you don't see it, click `>>` at the end of the tab row.
    3. In the left sidebar, under `Storage`, expand `Cookies` and click `https://accounts.google.com`.
    4. In the list of cookies, find the row whose `Name` is `oauth_token`.
    5. Double-click the text in that row's `Value` column, press `Ctrl+A` to select all of it, then `Ctrl+C` to copy it (Mac: `Cmd+A`, `Cmd+C`).

    **Firefox**

    1. Press `F12` (Mac: `Cmd+Option+I`).
    2. Open the `Storage` tab.
    3. In the left sidebar, expand `Cookies` and click `https://accounts.google.com`.
    4. In the list of cookies, find the row whose `Name` is `oauth_token`.
    5. Double-click the text in that row's `Value` column, press `Ctrl+A` to select all of it, then `Ctrl+C` to copy it (Mac: `Cmd+A`, `Cmd+C`).

    **Safari (Mac)**

    1. If you haven't before, turn on the developer tools: `Safari` -> `Settings` -> `Advanced` -> `Show features for web developers` (on older versions: `Show Develop menu in menu bar`).
    2. Press `Cmd+Option+I`.
    3. Open the `Storage` tab.
    4. In the left sidebar, expand `Cookies` and click `accounts.google.com`.
    5. In the list of cookies, find the row whose `Name` is `oauth_token`.
    6. Double-click the text in that row's `Value` column, press `Cmd+A` to select all of it, then `Cmd+C` to copy it.

7. Check what you copied. It is the cookie's value, not its name: it starts with `oauth2_4/`, followed by a long string of letters, numbers and symbols. If it doesn't start with `oauth2_4/`, you copied the wrong cell or only part of it.
8. Paste it into the `Token` field of the integration's setup right away. It expires after a short time; if the integration says the token is invalid, repeat these steps to get a new one.

The integration exchanges this token for a long-lived token for your Google account when you first sign in. **That token gives access to your whole Google account, not just Google Keep**, so treat it like your password; see [Security](#security).

## Usage

After setup, your selected Google Keep lists will be available in Home Assistant. You can view and interact with these lists, and any changes you make in Home Assistant will be instantly synced to Google Keep.

## How Sync Works

The integration syncs in both directions, but with different timing:

- **Home Assistant → Google Keep**: changes are pushed immediately when you add, update, delete, or reorder an item.
- **Google Keep → Home Assistant**: changes are pulled on a polling interval (default every 15 minutes, configurable in the integration options).

### Conflict Resolution

Changes made in Home Assistant are pushed to Google Keep immediately and will overwrite whatever is currently on the Keep side for that item. Changes made directly in Google Keep are only seen on the next poll. If you edit the same item in both places between polls, the Home Assistant edit wins and the Keep-side change is overwritten and lost.

## List Ordering

The integration offers two approaches to organizing your list items:

### Manual Reordering

By default, you can drag and drop items in the Home Assistant UI to reorder them. Changes are synced to Google Keep, so your custom order is preserved across both platforms.

### Auto Sort

If you prefer alphabetical organization, enable **Automatically Sort Lists** in the integration options. When enabled:

- Items are automatically sorted alphabetically on each sync
- Sorting is bidirectional (applies to both Home Assistant and Google Keep)
- Manual reordering is disabled to prevent conflicts

Choose the approach that best fits your workflow. You cannot use both simultaneously—enabling auto sort disables manual reordering.

## Empty Items

Google Keep allows creating empty items, which some users use as visual separators between groups of items. By default, empty items are filtered out since Home Assistant doesn't support displaying empty todo items.

### Empty Item Placeholder

If you use empty items as separators in Google Keep, you can enable the **Empty Item Placeholder** option in the integration settings. When configured:

- Empty items from Google Keep are displayed using your chosen placeholder text (e.g., `---`)
- Creating an item with the placeholder text in Home Assistant syncs as an empty item to Google Keep
- Choose placeholder text that you won't use for actual list items

**Note:** This feature is incompatible with auto-sort. When auto-sort is enabled, the placeholder option is automatically disabled since empty items would sort to the top of the list.

## Nested Items

Google Keep lets you indent an item under another one (for example, the things to buy under a store's name). Home Assistant todo items are a flat list, so the integration shows every item at the top level and reports the nesting in the list entity's `item_parents` attribute: it maps the uid of each indented item to the uid of the item it's under.

```yaml
item_parents:
  "1a2b3c.4d5e6f": "9z8y7x.6w5v4u" # Eggs → Costco
```

Dashboards, templates and other integrations can read it to group items the way Keep does, for example with `state_attr('todo.google_keep_groceries', 'item_parents')`. Item uids come from the `todo.get_items` action. The attribute isn't recorded in history.

## Services

As a result of the fact that we are working directly with native todo entities, you can
use the built-in services to add, remove and update items from your synchronized lists.

### Available Services

- `todo.add_item`
- `todo.remove_item`
- `todo.update_item`
- `google_keep_sync.request_sync`

#### google_keep_sync.request_sync

This service can be used to trigger a manual sync of all of your lists. This is
helpful because you can use it from an automation or script. While you can use also
use `homeassistant.update_entity` to trigger a sync, that service requires you
to specify a certain entity id, while this service targets all of your lists.

There is a built in cooldown to ensure that this service is not called
too frequently. Instead, it will log a warning if you call it too quickly.

Note that in some cases, the Google Keep Android app does not immediately send
changes you have made to Google's servers. This means that if you call the service
right after making the change on the Android app, it may not pick it up. It is
recommended to add a delay before calling the service if you are trying to capture
changes made on the Android app.

If you are using the Google Keep website or webapp, you can see the sync progress
icon in the top right corner of the screen. Once it has finished
spinning and you see the cloud icon with a checkmark, you can
safely call the service.

## Events

Google recently removed third party integrations from Google Assistant. Now you can re-create these integrations.

When a new item is added to a synced list via Google Assistant or from Google Keep, an `add_item` service call event will be triggered. This allows Home Assistant to pick up new items from Google Keep and sync them with third party systems such as Trello, Bring, Anylist etc.

This plugin extends Home Assistant's events so that the `add_item` service call is fired regardless of where the new item was added. The `origin` field in the event will be `REMOTE` if the item was added remotely to Google Keep, or `LOCAL` if it was added within Home Assistant.

Note: Only new items that are not completed at the time of syncing will trigger the event.

Below are some examples of how to do this, click to expand.

<details>
<summary>Sync Google Todo List with Trello via email</summary>

1.  Install and configure this plugin

1.  Install and configure the Anylist plugin

1.  Create an email notify service in Home assistant

    1. Have the SMTP server, username and password of the email account you will send from.

    1. Setup [creating cards by email]([https://support.atlassian.com/trello/docs/creating-cards-by-email/) in Trello

    1. Add the following to your config.yaml file.

    ```yaml
    notify:
      - name: "Email to Trello Todo"
        platform: smtp
        server: "smtp.gmail.com"
        port: 587
        timeout: 15
        encryption: starttls
        sender: "your_email@gmail.com"
        username: "your_email@gmail.com"
        password: "your SMTP password"
        sender_name: "your name"
        recipient: "your_cards_by_email_address@boards.trello.com"
    ```

1.  Create an Automation in Home Assistant:

    ```yaml
    alias: Google Todo List
    description: Send new items added to Google's Todo List to Trello
    trigger:
      - platform: event
        event_type: call_service
        event_data:
          domain: todo
          service: add_item
        variables:
          item_name: "{{ trigger.event.data.service_data.item }}"
          list_name: "{{state_attr((trigger.event.data.service_data.entity_id)[0], 'friendly_name')}}"
          list_entity_id: "{{ (trigger.event.data.service_data.entity_id)[0] }}"
          origin: "{{ trigger.event.origin }}"
    condition:
      # Update this to the name of your To-do list in Home Assistant.
      - condition: template
        value_template: "{{ list_entity_id == 'todo.google_keep_to_do' }}"
    action:
      # Optional: Send a notification of new item in HA.
      - service: notify.persistent_notification
        data:
          message: "'{{item_name}}' was just added to the '{{list_name}}' list."
      # Call Home Assistant Notify service to send item to Trello Board.
      - service: notify.email_to_trello_todo
        data:
          title: "{{item_name}}"
          message:
      # Complete item from google shopping list. Can also call todo.remove_item to delete it from the list.
      # Update entity_id to the id of your google list in Home Assistant.
      - service: todo.update_item
        target:
          entity_id: todo.google_keep_to_do
        data:
          status: completed
          item: "{{item_name}}"
    # The maximum number of updates you want to process each update. If you make frequent changes, increase this number.
    mode: parallel
    max: 50
    ```

    </details>

<details>
<summary>Sync Google Shopping List with Anylist</summary>

The same process works for Bring Shopping list or any other integrated list to Home Assistant.

1.  Install and configure this plugin

1.  Install and configure the Anylist plugin

1.  Create an Automation in Home Assistant:

    ```yaml
    alias: Google Shopping List
    description: Sync Google Shopping List with Anylist
    trigger:
      - platform: event
        event_type: call_service
        event_data:
          domain: todo
          service: add_item
        variables:
          item_name: "{{ trigger.event.data.service_data.item }}"
          list_name: "{{state_attr((trigger.event.data.service_data.entity_id)[0],'friendly_name')}}"
          list_entity_id: "{{ (trigger.event.data.service_data.entity_id)[0] }}"
          origin: "{{ trigger.event.origin }}"
    condition:
      # Update this to the name of your To-do list in Home Assistant.
      - condition: template
        value_template: "{{ list_entity_id == 'todo.google_keep_shopping_list' }}"
    action:
      # Optional: Send a notification of new item in Home Assistant.
      - service: notify.persistent_notification
        data:
          message: "'{{item_name}}' was just added to the '{{list_name}}' list."
      # Add new item to your Anylist list
      # Update the entity_id list name to your list in Home Assistant.
      - service: todo.add_item
        data:
          item: "{{item_name}}"
        target:
          entity_id: todo.anylist_alexa_shopping_list
      # Complete item from google shopping list. Can also call todo.remove_item to delete it from the list
      # Update entity_id to the id of your google list in Home Assistant.
      - service: todo.update_item
        target:
          entity_id: todo.google_keep_shopping_list
        data:
          status: completed
          item: "{{item_name}}"
    # The maximum number of updates you want to process each update. If you make frequent changes, increase this number.
    mode: parallel
    max: 50
    ```

    </details>

## Limitations

- **Polling Interval**: While changes made in Home Assistant are instantly reflected in Google Keep, changes made in Google Keep are not instantly reflected in Home Assistant. The integration polls Google Keep for updates every 15 minutes. Therefore, any changes made directly in Google Keep will be visible in Home Assistant after the next polling interval.

- **Authentication**: The integration signs in with a token from your browser (see [Getting a Token](#getting-a-token)). Signing in with your password is not supported.

- **Checkboxes in Keep**: Only Google Keep notes with `Show checkboxes` selected will appear as options to sync with Home Assistant using this integration.

## Security

### Token Scope

The integration exchanges the token you paste for a long-lived token for your Google account, and uses that to talk to Google Keep. **That token is not limited to Google Keep.** Anyone who has it can use it to get access to the account's other Google services as well, such as Gmail, Drive and Photos. Its scope can't be restricted, not to Keep and not to specific lists. Home Assistant stores it with the integration's configuration, so it is also part of your Home Assistant backups.

Changing the Google account's password signs the token out. After that, get a new token and re-authenticate the integration.

### Recommended: Use a Dedicated Account

Because the token gives access to the whole account, **using a dedicated Google account for this integration is strongly recommended**:

1. Create a new Google account. It can be empty, with no other Google data stored in it.
2. On your primary account, share the Google Keep lists you want to sync with the new account using Keep's collaborator option.
3. Get the token while signed in to the new account (see [Getting a Token](#getting-a-token)) and use it in the integration.

This way, even if the token is exposed (for example through a Home Assistant backup), it only gives access to an otherwise empty account and the lists you explicitly shared with it, not to your primary account.

## Troubleshooting

Encountering issues? Here are some common problems and their potential solutions:

### Invalid Authentication Errors

If the integration says the token is invalid, or keeps asking you for a token:

- Get a new token with the steps in [Getting a Token](#getting-a-token) and paste it right away. The token expires after a short time, so one copied earlier may no longer work.
- Copy the whole value of the `oauth_token` cookie. It starts with `oauth2_4/` and is long; a missing character at either end makes it invalid.
- Copy the cookie while the page is still loading after you click `I agree`. Don't wait for the page to finish; it never does.
- Use the token, not your password.

### The Sign-in Page Keeps Loading

This is expected. After you click `I agree`, the page never finishes loading. Copy the `oauth_token` cookie at that point, as described in [Getting a Token](#getting-a-token).

### Sync Delays

- Remember that changes made in Google Keep might not immediately reflect in Home Assistant due to the polling interval of the integration, which is set to every 15 minutes.

### Connection Issues

- If you're unable to connect, check your network settings and ensure your Home Assistant instance can access the internet.

### Integration Does Not Appear in Home Assistant

- After installing via HACS or manually, ensure you have restarted Home Assistant.
- Check the `custom_components` directory to verify that the `google_keep_sync` folder is present and correctly named.

### Lists Not Syncing

- Select the lists you want to sync during setup, or later with `Settings` -> `Devices & Services` -> `Google Keep Sync` -> `Configure`. Each selected list becomes a to-do list in Home Assistant.
- Only Google Keep notes with `Show checkboxes` turned on can be synced.
- Verify that the Google account used has access to the desired Google Keep lists. With a dedicated account, share the lists with it first.

## Disclaimer

This is an unofficial integration and is not created, endorsed, or supported by Google.

## Development

Open the repository in VS Code with the Dev Containers extension (and Docker or Podman, or use a Codespace) and choose **Reopen in Container**. Setup clones Home Assistant core (newest release) and gpsoauth next to the repository and links the integration into core's config.

- Press F5 (**Home Assistant**) and go to http://localhost:8123. For the full workspace (Home Assistant core, its config and gpsoauth next to this repository), open `google-keep-sync.code-workspace`.
- Run the tests from the Testing view, or `~/.venvs/ha/bin/pytest`.
- Releases: release-please keeps a release PR open from the `feat:`/`fix:` commits on `main` (version in `manifest.json`, `CHANGELOG.md`). Merging it tags the release and publishes it to HACS. PR titles must be conventional too, since "Squash and merge" uses them as the commit message.
- Each container start moves core to the newest release the test tools support (a few days behind a new Home Assistant release), so tests and Home Assistant share one version. It stays put while a branch is checked out there or it has local changes.
