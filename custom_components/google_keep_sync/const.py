"""Constants for the Google Keep Sync integration."""

DOMAIN = "google_keep_sync"

# Todo entity state attribute mapping indented item uids to their parent uids
ATTR_ITEM_PARENTS = "item_parents"

# Service that moves an item and sets its indent
SERVICE_MOVE_ITEM = "move_item"

# Sync interval configuration
DEFAULT_SYNC_INTERVAL_MINUTES = 15
MIN_SYNC_INTERVAL_MINUTES = 1
MAX_SYNC_INTERVAL_MINUTES = 1440  # 24 hours
