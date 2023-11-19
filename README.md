# Google Keep Sync for Home Assistant

Google Keep Sync is an unofficial custom integration for Home Assistant that allows users to synchronize their Google Keep lists with Home Assistant. This project is in no way affiliated with, created, or endorsed by Google.

## Why?

There are existing Home Assistant integrations for Google Keep, why create a new one? Basically, I tried all of them and none of them quite worked the way I wanted them to.

## Features
Bidirectional synchronization of lists between Google Keep and Home Assistant. You select the lists
you wish to sync, and they are created as todo
entities in your Home Assistant instance.

## Requirements

As a result of the fact that we are using the new todo entities that were introduced in Home Assistant 2023.11, you must be running that version or later.

## Installation

To install and use the Google Keep Sync integration in Home Assistant, follow these steps:

1. **Copy Integration Files**: Download the `google_keep_sync` folder and place it into the `custom_components` directory of your Home Assistant installation. If `custom_components` doesn't exist, create it in the same directory as your `configuration.yaml`.

2. **Add Integration in Home Assistant**:
    - Go to `Settings` -> `Devices & Services`.
    - Click `Add Integration`.
    - Search for and select `Google Keep Sync`.

3. **Configuration**:
    - Enter your Google account username.
    - Generate and use an **App Password** for your Google account (see https://myaccount.google.com/apppasswords).
    - Follow the prompts to select the Google Keep lists you want to synchronize with Home Assistant.

## Usage

After setup, your selected Google Keep lists will be available in Home Assistant. You can view and interact with these lists, and any changes you make in Home Assistant will be instantly synced to Google Keep.

## Services

As a result of the fact that we are working directly with native todo entities, you can
use the built-in services to add, remove and update items from your synchronized lists.

### Available Services

- `todo.add_item`
- `todo.remove_item`
- `todo.update_item`


## Limitations

- **Polling Interval**: While changes made in Home Assistant are instantly reflected in Google Keep, changes made in Google Keep are not instantly reflected in Home Assistant. The integration polls Google Keep for updates every 15 minutes. Therefore, any changes made directly in Google Keep will be visible in Home Assistant after the next polling interval.

- **Authentication**: Use of an app password is strongly recommended, as there is no way for accounts with 2-Factor-Authentication to be connected otherwise. This will also allow you to easily revoke access to the integration without affecting your Google account and requiring you to change your password.

## Security
As an additional security precaution, you can sign up for a new Google account to use exclusively with this integration. Afterward, on your primary account, add this new Google account as a collaborator on your Google Keep lists.

Then provide the credentials for this new account (preferably still using an app password) to the integration. This will allow the integration limited access your Google Keep lists without having access to your entire primary Google account.



## Disclaimer

This is an unofficial integration and is not created, endorsed, or supported by Google.
