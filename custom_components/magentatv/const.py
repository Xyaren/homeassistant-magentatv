"""Constants for homeassistant-magentatv."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

NAME = "MagentaTV"
DOMAIN = "magentatv"
VERSION = "0.0.0"
ATTRIBUTION = ""

CONF_PORT = "port"
CONF_ADDRESS = "address"
CONF_USER_ID = "user_id"

DATA_USER_ID = CONF_USER_ID
DATA_NOTIFICATION_SERVER = "notification_server"
