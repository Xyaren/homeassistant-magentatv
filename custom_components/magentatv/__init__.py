"""Custom integration to integrate magentatv with Home Assistant.

For more details about this integration, please refer to
https://github.com/xyaren/magentatv
"""
from __future__ import annotations


import homeassistant.helpers.config_validation as cv
from numpy import uint
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from custom_components.magentatv.api.api_notify_server import NotifyServer

from .const import (
    CONF_ADDRESS,
    CONF_PORT,
    CONF_USER_ID,
    DATA_NOTIFICATION_SERVER,
    DATA_USER_ID,
    DOMAIN,
    LOGGER,
)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


# CONFIG_SCHEMA: vol.Schema = vol.Schema(
#     {DOMAIN: vol.Schema({vol.Optional("port_range", default="1024-1100"): str})},
#     extra=vol.PREVENT_EXTRA,
# )


CONFIG_SCHEMA: vol.Schema = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_PORT, default="11223"): cv.port,
                vol.Optional(CONF_ADDRESS, default="0.0.0.0"): str,
                vol.Optional(CONF_USER_ID): int,  # optional -> not required to
            },
            extra=vol.PREVENT_EXTRA,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, entry: ConfigType | None):
    # Return boolean to indicate that initialization was successful.
    domain_data = hass.data.setdefault(DOMAIN, {})
    config = entry[DOMAIN]

    if CONF_USER_ID in config:
        domain_data.setdefault(DATA_USER_ID, config[CONF_USER_ID])

    domain_data[DATA_NOTIFICATION_SERVER] = _create_notify_server(hass, config)

    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _create_notify_server(hass: HomeAssistant, config: ConfigType) -> NotifyServer:
    LOGGER.info("Setup Notify Server for MagentaTV")

    notify_server = NotifyServer(
        source_ip=config[CONF_ADDRESS], source_port=config[CONF_PORT]
    )

    async def async_close_connection(_: Event) -> None:
        """Close connection on HA Stop."""
        await notify_server.async_stop()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    return notify_server
