"""Support for Denon AVR receivers using their HTTP interface."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MANUFACTURER,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_PORT,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_platform, instance_id
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from httpcore import TimeoutException

from custom_components.magentatv import async_get_notification_server

from .api import Client, KeyCode, MediaReceiverStateMachine, NotifyServer, State
from .const import (
    CONF_USER_ID,
    DOMAIN,
    LOGGER,
    SERVICE_SEND_KEY,
    SERVICE_SEND_TEXT,
    key_code,
)

SCAN_INTERVAL = timedelta(seconds=10)  # only backup in case events have been missed
PARALLEL_UPDATES = 0

STATE_MAP: Mapping[State, MediaPlayerState] = {
    None: None,
    State.OFF: MediaPlayerState.OFF,
    State.PLAYING: MediaPlayerState.PLAYING,
    State.PAUSED: MediaPlayerState.PAUSED,
    State.BUFFERING: MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    entities = []

    _host = config_entry.data.get(CONF_HOST)
    _port = config_entry.data.get(CONF_PORT)

    _client = Client(
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

    try:
        await _client.async_pair()
    except (asyncio.TimeoutError, TimeoutException) as ex:
        raise ConfigEntryNotReady(f"Timeout while connecting to {_host}") from ex

    entities.append(
        MediaReceiver(
            config_entry=config_entry,
            client=_client,  # notify_server=_notify_server
        )
    )
    async_add_entities(entities, update_before_add=False)

    platform = entity_platform.async_get_current_platform()

    # This will call Entity.set_sleep_timer(sleep_time=VALUE)
    platform.async_register_entity_service(
        SERVICE_SEND_KEY,
        {
            vol.Required("key_code"): key_code,
        },
        "send_key",
    )
    platform.async_register_entity_service(
        SERVICE_SEND_TEXT,
        {
            vol.Required("text"): str,
        },
        "send_text",
    )


class MediaReceiver(MediaPlayerEntity):
    """Representation of a Denon Media Player Device."""

    _last_events: list[dict] = []

    _client: Client
    _notify_server: NotifyServer

    def __init__(
        self,
        config_entry: ConfigEntry,
        client: Client,
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
            manufacturer=config_entry.data.get(ATTR_MANUFACTURER),
        )
        # self._attr_icon = "mdi:audio-video"
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        assert config_entry.unique_id

        self._state_machine = MediaReceiverStateMachine()

    async def _async_on_event(self, changes):
        LOGGER.debug("%s: Event %s", self.entity_id, changes)
        if "STB_playContent" in changes:
            self._state_machine.on_event_play_content(
                json.loads(changes["STB_playContent"])
            )
        elif "STB_EitChanged" in changes:
            self._state_machine.on_event_eit_changed(
                json.loads(changes["STB_EitChanged"])
            )
        elif "messageBody" in changes and "X-pairingCheck" in changes["messageBody"]:
            return  # ignore event
        else:
            raise NotImplementedError()

        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register for telnet events."""

        # await self._notify_server.async_start()

        # subscibe for player events
        self._client.subscribe(self._async_on_event)

        # await self._client.async_pair()

        # trigger manual update
        await self.async_update()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await self._client.async_close()
        # await self._notify_server.async_stop()

    async def async_update(self) -> None:
        data = await self._client.async_get_player_state()
        self._state_machine.on_poll_player_state(data)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""  #
        return STATE_MAP[self._state_machine.state]

    @property
    def media_title(self):
        """Title of current playing media."""
        if self._state_machine.program_current is not None:
            _playing_event = self._state_machine.program_current.short_event[0]
            _parts = [
                _playing_event.event_name,
                _playing_event.text_char,
            ]
            return " - ".join([x for x in _parts if x is not None and x != ""])
        return None

    @property
    def media_channel(self) -> str | None:
        return self._state_machine.chan_key

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
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
        return self._state_machine.duration

    @property
    def media_position(self) -> int | None:
        return self._state_machine.position

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Content type of current playing media."""
        return MediaType.CHANNEL

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._client.async_send_key(KeyCode.ON)

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._client.async_send_key(KeyCode.OFF)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""

        # reset mute: colume keys always unmute
        await self._client.async_send_key(KeyCode.VOL_DOWN)
        await self._client.async_send_key(KeyCode.VOL_UP)

        # player is now unmuted, now set the desired state

        if mute:
            await self._client.async_send_key(KeyCode.MUTE)

    async def async_volume_up(self) -> None:
        await self._client.async_send_key(KeyCode.VOL_UP)

    async def async_volume_down(self) -> None:
        await self._client.async_send_key(KeyCode.VOL_DOWN)

    async def async_media_pause(self) -> None:
        if self.state == MediaPlayerState.PLAYING:
            await self._client.async_send_key(KeyCode.PAUSE)

    async def async_media_play(self) -> None:
        if self.state not in [MediaPlayerState.PLAYING, MediaPlayerState.BUFFERING]:
            await self._client.async_send_key(KeyCode.PLAY)

    async def send_key(self, key_code: KeyCode) -> None:
        await self._client.async_send_key(key_code)

    async def send_text(self, text: str) -> None:
        await self._client.async_send_character_input(text)
