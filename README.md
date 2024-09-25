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
    - Go to `Settings` -> `Devices & Services`.
    - Click `Add Integration`.
    - Search for and select `Google Keep Sync`.
    - Enter your Google account username.
    - Generate a token using the instructions below and enter the token.
    - Follow the prompts to select the Google Keep lists you want to synchronize with Home Assistant.

## Generating a Token Using the Docker Container

You can use the [Docker container](https://github.com/Brephlas/dockerfile_breph-ha-google-home_get-token) created by @Brephlas.

#### Requirements

You need a computer that you can install Docker on. This can be any Linux computer,
or you can even use a Windows machine by installing WSL. Note that you do not run these
commands on your Home Assistant server itself, it must be a separate machine. Raspberry Pi
machines will likely not work due to the ARM architecture.

#### Windows with WSL

If you want to use a Windows machine, you can install WSL2 and Docker. Follow the instructions [here to install WSL2](https://docs.microsoft.com/en-us/windows/wsl/install). Then, open Ubuntu
and run the command `sudo apt-get install docker.io`.

#### Linux

If you are using a Linux machine, you can install Docker using the package manager of your choice. For Ubuntu, you can use the following commands:

```bash
sudo apt-get update
sudo apt-get install docker.io
```

#### Steps

1. After you have Docker installed, enter the following commands.

   ```bash
   docker pull breph/ha-google-home_get-token:latest
   docker run -it -d breph/ha-google-home_get-token
   ```

2. Copy the returned container ID to use in the following command.

   ```bash
   docker exec -it <ID> bash
   ```

3. Inside the container, enter the following command and answer the prompts to generate a master token. For the password, you should preferably use an app password,

   ```bash
   python3 get_tokens.py
   ```

4. The script will generate two tokens, a "master token" and an "access token". Copy the entire master token, including the "aas_et/" at the beginning.

5. Use this token in the integration's configuration process by entering it into the token field (make sure you leave the password field blank).

## Usage

After setup, your selected Google Keep lists will be available in Home Assistant. You can view and interact with these lists, and any changes you make in Home Assistant will be instantly synced to Google Keep.

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

    1. Create a new [app password](https://myaccount.google.com/apppasswords>) in your Gmail.

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
        password: "app password"
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

- **Authentication**: Using a token is strongly encouraged. Password login usually doesn't work and is deprecated by the underlying library this integration uses.

- **Checkboxes in Keep**: Only Google Keep notes with `Show checkboxes` selected will appear as options to sync with Home Assistant using this integration.

## Security

As an additional security precaution, you can sign up for a new Google account to use exclusively with this integration. Afterward, on your primary account, add this new Google account as a collaborator on any lists you wish to synchronize.

Then provide the credentials for this new account (using a token) to the integration. This will allow the integration limited access your Google Keep lists without having access to your entire primary Google account.

## Troubleshooting

Encountering issues? Here are some common problems and their potential solutions:

### Invalid Authentication Errors

If you're experiencing `Invalid authentication` errors, these are due to incompatible versions of certain underlying libraries used by the integration, such as OpenSSL. To resolve this, make sure you are using a manually-generated token for authentication instead of a password.

### Sync Delays

- Remember that changes made in Google Keep might not immediately reflect in Home Assistant due to the polling interval of the integration, which is set to every 15 minutes.

### Connection Issues

- If you're unable to connect, check your network settings and ensure your Home Assistant instance can access the internet.

### Integration Does Not Appear in Home Assistant

- After installing via HACS or manually, ensure you have restarted Home Assistant.
- Check the `custom_components` directory to verify that the `google_keep_sync` folder is present and correctly named.

### Lists Not Syncing

- Ensure the lists you want to sync are selected during the integration setup.
- Verify that the Google account used has access to the desired Google Keep lists.

## Disclaimer

This is an unofficial integration and is not created, endorsed, or supported by Google.
