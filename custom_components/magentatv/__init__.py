"""Custom integration to integrate magentatv with Home Assistant.

For more details about this integration, please refer to
https://github.com/xyaren/magentatv
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [
    # Platform.SENSOR,
    Platform.MEDIA_PLAYER
    # Platform.BINARY_SENSOR,
    # Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    # hass.data[DOMAIN][entry.entry_id] = coordinator = BlueprintDataUpdateCoordinator(
    #     hass=hass,
    #     # client=IntegrationBlueprintApiClient(
    #     #     username=entry.data[CONF_USERNAME],
    #     #     password=entry.data[CONF_PASSWORD],
    #     #     session=async_get_clientsession(hass),
    #     # ),
    # )
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    # await coordinator.async_config_entry_first_refresh()

    # TODO: Verify pairing

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    # hass.data[DOMAIN].pop(entry.entry_id)
    # return True
    return unloaded
