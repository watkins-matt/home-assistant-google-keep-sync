#!/bin/bash

# --------------------------------------------------------------------
# VSCode Devcontainer Bootstrap Script for Google Keep Sync
# --------------------------------------------------------------------
# This script quickly sets up a development environment for Google Keep Sync within
# a VSCode devcontainer. First, set up the devcontainer by following the instructions at:
# https://developers.home-assistant.io/docs/development_environment/#developing-with-visual-studio-code--devcontainer
#
# Usage Instructions:
# 1. CD into the /workspaces directory:
#    cd /workspaces
# 2. Clone the Google Keep Sync repository:
#    git clone https://github.com/watkins-matt/home-assistant-google-keep-sync.git
# 3. Navigate into the cloned repository:
#    cd home-assistant-google-keep-sync
# 4. Run this bootstrap script:
#    ./devcontainer-bootstrap.sh
# 5. Open the VSCode workspace file by going to File > Open Workspace... and selecting the
#    workspace file in the /workspaces directory.
#
# What This Script Does:
# - Symlinks the custom component directory from the cloned repository to the Home Assistant core
# so that changes to the custom component are reflected when running Home Assistant inside
# the devcontainer.
# - Generates a VSCode workspace file in the /workspaces directory that includes the cloned
# repository, the custom component directory, the Home Assistant core directory, and the
# Home Assistant configuration directory.
# --------------------------------------------------------------------

# Determine the directory of this script and the name of the repository
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
REPO_NAME=$(basename "$SCRIPT_DIR")

# Define the fixed path for Home Assistant core and workspaces directory
WORKSPACES_DIR="/workspaces"
HA_CORE_DIR="$WORKSPACES_DIR/home-assistant-core"
COMPONENT_NAME="google_keep_sync"
CONFIG_DIR="$HA_CORE_DIR/config"
CUSTOM_COMPONENTS_DIR="$CONFIG_DIR/custom_components"
SYMLINK_TARGET="$CUSTOM_COMPONENTS_DIR/$COMPONENT_NAME"
VS_CODE_WORKSPACE="$WORKSPACES_DIR/$REPO_NAME.code-workspace"  # Workspace file in /workspaces

# Ensure /workspaces directory exists
if [ ! -d "$WORKSPACES_DIR" ]; then
    echo "Error: /workspaces directory does not exist."
    exit 1
fi

# Ensure the repository contains the expected custom component structure
if [ ! -d "$SCRIPT_DIR/custom_components/$COMPONENT_NAME" ]; then
    echo "Error: The repository does not contain the expected custom component structure."
    exit 1
fi

# Ensure /config/custom_components exists in Home Assistant core
if [ ! -d "$CUSTOM_COMPONENTS_DIR" ]; then
    echo "Creating /config/custom_components directory in Home Assistant core..."
    mkdir -p "$CUSTOM_COMPONENTS_DIR"
    echo "/config/custom_components directory created."
else
    echo "/config/custom_components directory already exists."
fi

# Create symbolic link for the custom component
if [ ! -L "$SYMLINK_TARGET" ]; then
    echo "Creating symbolic link for custom component..."
    ln -s "$SCRIPT_DIR/custom_components/$COMPONENT_NAME" "$SYMLINK_TARGET"
    echo "Symbolic link created: $SYMLINK_TARGET -> $SCRIPT_DIR/custom_components/$COMPONENT_NAME"
else
    echo "Symbolic link already exists: $SYMLINK_TARGET"
fi

# Generate VSCode workspace file in /workspaces
echo "Generating VSCode workspace file in /workspaces..."
cat <<EOL > "$VS_CODE_WORKSPACE"
{
    "folders": [
        {
            "path": "$SCRIPT_DIR",
            "name": "Google Keep Sync Root"
        },
        {
            "path": "$SCRIPT_DIR/custom_components/$COMPONENT_NAME",
            "name": "Google Keep Sync"
        },
        {
            "path": "$HA_CORE_DIR",
            "name": "Home Assistant Core",
            "state": {
                "expanded": false
            }
        },
        {
            "path": "$CONFIG_DIR",
            "name": "Home Assistant Config",
            "state": {
                "expanded": false
            }
        }
    ],
    "settings": {
        "files.exclude": {
            "**/__pycache__": true,
            "**/*.pyc": true
        },
        "python.analysis.extraPaths": [
            "/workspaces/home-assistant-core/homeassistant"
        ]
    }
}
EOL
echo "VSCode workspace file generated: $VS_CODE_WORKSPACE"

# Install dependencies for Google Keep Sync
echo "Installing Google Keep Sync dependencies..."
if [ -f "$SCRIPT_DIR/requirements.test.txt" ]; then
    pip install -r "$SCRIPT_DIR/requirements.test.txt"
else
    echo "No requirements.test.txt found for Google Keep Sync. Skipping."
fi

echo "Bootstrap process completed."
