"""Custom integration to integrate magentatv with Home Assistant.

For more details about this integration, please refer to
https://github.com/xyaren/magentatv
"""
from __future__ import annotations

from asyncio import Lock

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.typing import ConfigType

from custom_components.magentatv.api.api_notify_server import NotifyServer

from .const import (
    CONF_ADVERTISE_ADDRESS,
    CONF_ADVERTISE_PORT,
    CONF_LISTEN_ADDRESS,
    CONF_LISTEN_PORT,
    CONF_USER_ID,
    DATA_ADVERTISE_ADDRESS,
    DATA_ADVERTISE_PORT,
    DATA_LISTEN_ADDRESS,
    DATA_LISTEN_PORT,
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
                vol.Optional(CONF_LISTEN_PORT, default="11223"): cv.port,
                vol.Optional(CONF_LISTEN_ADDRESS, default="0.0.0.0"): str,
                vol.Optional(CONF_ADVERTISE_PORT): cv.port,
                vol.Optional(CONF_ADVERTISE_ADDRESS): str,
                vol.Optional(CONF_USER_ID): int,  # optional -> not required to
            },
            extra=vol.PREVENT_EXTRA,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, entry: ConfigType):
    LOGGER.info("MagentaTV setup")

    domain_data = hass.data.setdefault(DOMAIN, {})

    if DOMAIN in entry:
        config = entry[DOMAIN]

        mapping = {
            CONF_USER_ID: DATA_USER_ID,
            CONF_LISTEN_ADDRESS: DATA_LISTEN_ADDRESS,
            CONF_LISTEN_PORT: DATA_LISTEN_PORT,
            CONF_ADVERTISE_ADDRESS: DATA_ADVERTISE_ADDRESS,
            CONF_ADVERTISE_PORT: DATA_ADVERTISE_PORT,
        }
        for k, v in mapping.items():
            if k in config:
                domain_data.setdefault(v, config[k])

    # Return boolean to indicate that initialization was successful.
    return True


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    LOGGER.info("MagentaTV setup entry")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


notification_server_lock = Lock()


async def async_get_notification_server(hass: HomeAssistant) -> NotifyServer:
    async with notification_server_lock:
        domain_data = hass.data.setdefault(DOMAIN, {})
        if DATA_NOTIFICATION_SERVER in domain_data:
            return domain_data[DATA_NOTIFICATION_SERVER]
        else:
            LOGGER.info("Setup Notify Server for MagentaTV")

            domain_data[DATA_NOTIFICATION_SERVER] = notify_server = NotifyServer(
                listen=(
                    domain_data.get(DATA_LISTEN_ADDRESS, "0.0.0.0"),
                    domain_data.get(DATA_LISTEN_PORT, 11223),
                ),
                advertise=(
                    domain_data.get(DATA_ADVERTISE_ADDRESS, None),
                    domain_data.get(DATA_ADVERTISE_PORT, None),
                ),
            )

            async def async_close_connection(_: Event) -> None:
                """Close connection on HA Stop."""
                await notify_server.async_stop()

            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)

            return notify_server
