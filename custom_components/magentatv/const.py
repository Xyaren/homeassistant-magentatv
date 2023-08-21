"""Constants for homeassistant-magentatv."""
from logging import Logger, getLogger
from typing import Any

import voluptuous as vol

from custom_components.magentatv.api.const import KeyCode

LOGGER: Logger = getLogger(__package__)

NAME = "MagentaTV"
DOMAIN = "magentatv"
VERSION = "0.0.0"
ATTRIBUTION = ""


CONF_LISTEN_PORT = "listen_port"
CONF_LISTEN_ADDRESS = "listen_address"
CONF_ADVERTISE_PORT = "advertise_port"
CONF_ADVERTISE_ADDRESS = "advertise_address"
CONF_USER_ID = "user_id"


DATA_USER_ID = CONF_USER_ID
DATA_LISTEN_ADDRESS = CONF_LISTEN_ADDRESS
DATA_LISTEN_PORT = CONF_LISTEN_PORT
DATA_ADVERTISE_ADDRESS = CONF_ADVERTISE_ADDRESS
DATA_ADVERTISE_PORT = CONF_ADVERTISE_PORT
DATA_NOTIFICATION_SERVER = "notification_server"

SERVICE_SEND_KEY = "send_key"
SERVICE_SEND_TEXT = "send_text"


def key_code(value: Any) -> KeyCode:
    """Coerce value to string, except for None."""
    if value is None:
        raise vol.Invalid("value is None")

    # This is expected to be the most common case, so check it first.
    if isinstance(value, str):
        return KeyCode[value]

    elif isinstance(value, KeyCode):
        return value

    raise vol.Invalid("value is not a valid Key Code")
