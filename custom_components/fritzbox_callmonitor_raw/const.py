from __future__ import annotations

from typing import Final

DOMAIN: Final = "fritzbox_callmonitor_raw"

DEFAULT_PORT: Final = 1012
DEFAULT_TR064_PORT: Final = 49000
DEFAULT_NAME: Final = "FRITZ!Box CallMonitor"

CONF_PREFIXES: Final = "prefixes"
CONF_PHONEBOOK_ID: Final = "phonebook_id"
CONF_TR064_PORT: Final = "tr064_port"

ATTR_PREFIXES: Final = "prefixes"
ATTR_FROM: Final = "from"
ATTR_TO: Final = "to"
ATTR_WITH: Final = "with"
ATTR_DEVICE: Final = "device"
ATTR_INITIATED: Final = "initiated"
ATTR_ACCEPTED: Final = "accepted"
ATTR_CLOSED: Final = "closed"
ATTR_DURATION: Final = "duration"
ATTR_TYPE: Final = "type"
ATTR_FROM_NAME: Final = "from_name"
ATTR_TO_NAME: Final = "to_name"
ATTR_WITH_NAME: Final = "with_name"
ATTR_RAW: Final = "raw"

ATTR_PHONEBOOK_STATUS: Final = "phonebook_status"
ATTR_PHONEBOOK_ENTRIES: Final = "phonebook_entries"
ATTR_PHONEBOOK_LAST_REFRESH: Final = "phonebook_last_refresh"

# Fritz callmonitor event types
FRITZ_RING: Final = "RING"
FRITZ_CALL: Final = "CALL"
FRITZ_CONNECT: Final = "CONNECT"
FRITZ_DISCONNECT: Final = "DISCONNECT"