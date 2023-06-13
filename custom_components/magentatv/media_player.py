"""Support for Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

import json
from datetime import timedelta

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.magentatv import async_get_notification_server

from custom_components.magentatv.api.api_notify_server import NotifyServer

from .api import EitChangedEvent, PairingClient, PlayContentEvent
from .const import CONF_USER_ID, DOMAIN, LOGGER

SUPPORTED_FEATURES = (
    0
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    # | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
)

SCAN_INTERVAL = timedelta(seconds=10)  # only backup in case events have been missed
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    entities = []

    _host = config_entry.data.get(CONF_HOST)
    _port = config_entry.data.get(CONF_PORT)

    _client = PairingClient(
        host=_host,
        port=_port,
        user_id=config_entry.data.get(CONF_USER_ID),
        instance_id=(await instance_id.async_get(hass)),
        notify_server=await async_get_notification_server(hass=hass),
    )

    async def async_close_connection(event: Event) -> None:
        """Close connection on HA Stop."""
        await _client.async_close()

    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_close_connection)
    )

    entities.append(
        MediaReceiver(
            config_entry=config_entry,
            client=_client,  # notify_server=_notify_server
        )
    )
    async_add_entities(entities, update_before_add=False)


class MediaReceiver(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    _last_event_eit_changed: EitChangedEvent | None
    _last_event_play_content: PlayContentEvent | None

    _client: PairingClient
    _notify_server: NotifyServer

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: PairingClient,
        # notify_server: NotifyServer,
    ) -> None:
        """Initialize the device."""

        self._client = client
        # self._notify_server = notify_server

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
        LOGGER.info("%s: Event %s", self.entity_id, changes)

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

        # await self._notify_server.async_start()

        # subscibe for player events
        self._client.subscribe(self._async_on_event)

        await self._client.async_pair()

        # trigger manual update
        await self.async_update()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self._client.async_close()
        # await self._notify_server.async_stop()

    async def async_update(self) -> None:
        data = await self._client.async_get_player_state()
        LOGGER.debug("%s: New Data Polled: %s", self.entity_id, data)
        self._last_event_play_content = PlayContentEvent(**data)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        try:
            lepc = self._last_event_play_content

            new_play_mode = lepc.new_play_mode
            if new_play_mode is not None:
                if new_play_mode == 0:
                    self._last_event_eit_changed = None
                    # return MediaPlayerState.OFF
                    return MediaPlayerState.IDLE
                elif new_play_mode == 1:
                    return MediaPlayerState.PAUSED
                elif new_play_mode in [2, 3, 4, 5]:
                    return MediaPlayerState.PLAYING
                elif new_play_mode == 20:
                    return MediaPlayerState.BUFFERING
                return MediaPlayerState.IDLE

            lepc_dict = lepc.dict()
            if (
                "media_type" in lepc_dict
                and "media_code" in lepc_dict
                and "chan_key" in lepc_dict
            ):
                if lepc.play_back_state == 1:
                    if "fast_speed" in lepc_dict:
                        if lepc.fast_speed == 0:
                            return MediaPlayerState.PAUSED
                        elif lepc.fast_speed == 1:
                            return MediaPlayerState.PLAYING
                    return MediaPlayerState.PLAYING
                else:
                    raise NotImplementedError("")

            if lepc.play_back_state == 1:
                return MediaPlayerState.OFF
            elif lepc.play_back_state == 0:
                return MediaPlayerState.OFF  # deep sleep ?

        except (NameError, AttributeError):
            return None
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

        features = 0

        if self.state in [MediaPlayerState.OFF]:
            features = features | MediaPlayerEntityFeature.TURN_ON
        else:
            features = (
                features
                | MediaPlayerEntityFeature.TURN_OFF
                | MediaPlayerEntityFeature.VOLUME_STEP
                | MediaPlayerEntityFeature.VOLUME_MUTE
            )

            if self.state in [MediaPlayerState.PAUSED]:
                features = features | MediaPlayerEntityFeature.PLAY

            if self.state in [MediaPlayerState.BUFFERING, MediaPlayerState.PLAYING]:
                features = features | MediaPlayerEntityFeature.PAUSE

        return features

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

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        if self._last_event_play_content.media_type == 1:
            return MediaType.CHANNEL
        return None

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._client.async_send_key("ON")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._client.async_send_key("OFF")

    async def async_toggle(self) -> None:
        """Toggle the power on the media player."""

        if self.state in {
            MediaPlayerState.OFF,
            # MediaPlayerState.IDLE, # idle == on
            MediaPlayerState.STANDBY,
        }:
            await self.async_turn_on()
        else:
            await self.async_turn_off()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""

        # reset mute: colume keys always unmute
        await self._client.async_send_key("VOL_DOWN")
        await self._client.async_send_key("VOL_UP")

        # player is now unmuted, now set the desired state

        if mute:
            await self._client.async_send_key("MUTE")

    async def async_volume_up(self) -> None:
        await self._client.async_send_key("VOL_UP")

    async def async_volume_down(self) -> None:
        await self._client.async_send_key("VOL_DOWN")

    async def async_media_pause(self) -> None:
        if self.state == MediaPlayerState.PLAYING:
            await self._client.async_send_key("PAUSE")

    async def async_media_play(self) -> None:
        if self.state not in [MediaPlayerState.PLAYING, MediaPlayerState.BUFFERING]:
            await self._client.async_send_key("PLAY")
