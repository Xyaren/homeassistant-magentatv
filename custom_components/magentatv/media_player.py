"""Support for Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

import json
from datetime import timedelta

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_PORT,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import instance_id
from homeassistant.components import network
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PairingClient
from .api_event import EitChangedEvent, PlayContentEvent
from .const import DOMAIN, LOGGER

SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
)

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    entities = []

    _client = PairingClient(
        host=config_entry.data.get(CONF_HOST),
        port=config_entry.data.get(CONF_PORT),
        user_id=config_entry.data.get("user_id"),
        instance_id=(await instance_id.async_get(hass)),
    )

    async def async_close_connection(event: Event) -> None:
        """Close connection on HA Stop."""
        await _client.async_stop()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    entities.append(MediaReceiver(config_entry=config_entry, client=_client))
    async_add_entities(entities, update_before_add=True)


class MediaReceiver(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    _last_event_eit_changed: EitChangedEvent | None
    _last_event_play_content: PlayContentEvent | None

    def __init__(self, config_entry: ConfigEntry, client: PairingClient) -> None:
        """Initialize the device."""
        self.client = client

        self._attr_unique_id = config_entry.data.get(CONF_ID)
        self._attr_name = config_entry.title
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
                ("udn", config_entry.data.get(CONF_ID)),
            },
            name=config_entry.title,
            model=config_entry.data.get(CONF_MODEL),
            configuration_url=config_entry.data.get(CONF_URL),
            manufacturer=config_entry.data.get("manufacturer"),
        )
        self._attr_icon = "mdi:audio-video"
        assert config_entry.unique_id

        self._last_event_eit_changed = {}
        self._last_event_play_content = {}

    async def _async_on_event(self, changes):
        LOGGER.info("Event %s", changes)

        if "STB_playContent" in changes:
            self._last_event_play_content = PlayContentEvent(
                **json.loads(changes["STB_playContent"])
            )

        if "STB_EitChanged" in changes:
            self._last_event_eit_changed = EitChangedEvent(
                **json.loads(changes["STB_EitChanged"])
            )

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for telnet events."""

        await self.client.async_subscribe(self._async_on_event)
        await self.client.async_start()
        await self.client.async_pair()

        data = await self.client.async_get_player_state()
        self._last_event_play_content = PlayContentEvent(**data)
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self.client.async_stop()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        try:
            _play_mode = self._last_event_play_content.new_play_mode
            if _play_mode == 0:
                self._last_event_eit_changed = None
                # return MediaPlayerState.OFF
                return MediaPlayerState.IDLE
            elif _play_mode == 1:
                return MediaPlayerState.PAUSED
            elif _play_mode in [2, 3, 4, 5]:
                return MediaPlayerState.PLAYING
            elif _play_mode == 20:
                return MediaPlayerState.BUFFERING
            return MediaPlayerState.IDLE
        except (NameError, AttributeError):
            return None

    @property
    def media_title(self):
        """Title of current playing media."""
        try:
            _playing_event = self._last_event_eit_changed.program_info[0].short_event[0]
            _parts = [
                _playing_event.event_name,
                _playing_event.text_char,
            ]
            return " - ".join([x for x in _parts if x is not None and x != ""])
        except (NameError, AttributeError):
            return None

    @property
    def media_channel(self) -> str | None:
        try:
            return self._last_event_eit_changed.channel_num
        except (NameError, AttributeError):
            return None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        # return SUPPORTED_FEATURES
        return 0

    @property
    def media_duration(self) -> int | None:
        try:
            return self._last_event_play_content.duration or None
        except (NameError, AttributeError):
            return None

    @property
    def media_position(self) -> int | None:
        try:
            if (self._last_event_play_content.duration or 0) > 0:
                return self._last_event_play_content.play_position
        except (NameError, AttributeError):
            return None
