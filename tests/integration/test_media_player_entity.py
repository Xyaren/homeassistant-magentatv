"""Test sensor for simple integration."""

import datetime
from unittest.mock import AsyncMock, Mock, call

from freezegun import freeze_time
from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.const import (
    ATTR_MANUFACTURER,
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_PORT,
    CONF_TYPE,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magentatv.api import KeyCode
from custom_components.magentatv.api.exceptions import CommunicationException
from custom_components.magentatv.const import CONF_USER_ID, DOMAIN

MOCK_CONFIG_ENTRY = MockConfigEntry(
    domain=DOMAIN,
    unique_id="abcdefg",
    title="Livingroom TV Receiver",
    data={
        CONF_HOST: "1.2.3.4",
        CONF_PORT: "1234",
        CONF_MODEL: "Model X",
        CONF_TYPE: "Media Receiver",
        ATTR_MANUFACTURER: "Huawei",
        CONF_ID: "abcdefg",
        CONF_URL: "http://1.2.3.4/spec.xml",
        CONF_USER_ID: "1234567890",
    },
)

MOCK_POLL_RESPONSE = {
    "chanKey": "5",
    "duration": "15",
    "mediaCode": "3710",
    "mediaType": "1",
    "playBackState": "1",
    "playPostion": "15",
}

MOCK_POLL_RESPONSE_OFF = {"playBackState": "0"}
MOCK_POLL_RESPONSE_PAUSE = {
    "chanKey": "2",
    "duration": "1733",
    "fastSpeed": "0",
    "mediaCode": "3733",
    "mediaType": "1",
    "playBackState": "1",
    "playPostion": "1718",
}


@freeze_time("2012-01-01")
async def test_entity_loads_data(hass, mock_api_client):
    """Test sensor."""

    mock_api_client.is_paired.return_value = False
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    entry = MOCK_CONFIG_ENTRY

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.livingroom_tv_receiver")

    mock_api_client.subscribe.assert_called_once()
    mock_api_client.async_pair.assert_awaited_once()
    mock_api_client.async_get_player_state.assert_awaited_once()

    assert state
    assert state.state == "playing"
    assert state.name == "Livingroom TV Receiver"
    assert state.attributes == {
        "media_content_type": MediaType.CHANNEL,
        "media_duration": 15,
        "media_position": 15,
        "media_channel": 5,
        "media_position_updated_at": datetime.datetime(2012, 1, 1),
        "device_class": "receiver",
        "friendly_name": "Livingroom TV Receiver",
        "supported_features": 0
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP,
    }


async def test_entity_unavailble(hass, mock_api_client):
    """Test sensor."""
    mock_api_client.is_paired.return_value = False
    mock_api_client.async_pair.side_effect = CommunicationException()
    mock_api_client.async_get_player_state.side_effect = CommunicationException()

    entry = MOCK_CONFIG_ENTRY

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.livingroom_tv_receiver")

    assert state
    assert state.state == "unavailable"


async def test_send_key_service(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "send_key")
    await hass.services.async_call(
        domain=DOMAIN,
        service="send_key",
        blocking=True,
        service_data={
            "key_code": "NUM0",
            "entity_id": "media_player.livingroom_tv_receiver",
        },
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_awaited_once_with(KeyCode.NUM0)


async def test_service_power_off(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "turn_off")
    await hass.services.async_call(
        domain="media_player",
        service="turn_off",
        blocking=True,
        service_data={
            "entity_id": "media_player.livingroom_tv_receiver",
        },
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_awaited_once_with(KeyCode.OFF)


async def test_service_power_on(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE_OFF

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "turn_on")
    await hass.services.async_call(
        domain="media_player",
        service="turn_on",
        blocking=True,
        service_data={
            "entity_id": "media_player.livingroom_tv_receiver",
        },
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_awaited_once_with(KeyCode.ON)


async def test_service_volume_up(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "volume_up")
    await hass.services.async_call(
        domain="media_player",
        service="volume_up",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.VOL_UP)])


async def test_service_volume_down(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "volume_down")
    await hass.services.async_call(
        domain="media_player",
        service="volume_down",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.VOL_DOWN)])


async def test_service_channel_up(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "media_next_track")
    await hass.services.async_call(
        domain="media_player",
        service="media_next_track",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.CHANNEL_UP)])


async def test_service_channel_down(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "media_previous_track")
    await hass.services.async_call(
        domain="media_player",
        service="media_previous_track",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.CHANNEL_DOWN)])


async def test_service_pause(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "media_pause")
    await hass.services.async_call(
        domain="media_player",
        service="media_pause",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.PAUSE)])


async def test_service_play(hass: HomeAssistant, mock_api_client: Mock):
    """Test sending a key to the receiver. Test checks if the client is called"""
    mock_api_client.is_paired.return_value = True
    mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE_PAUSE

    MOCK_CONFIG_ENTRY.add_to_hass(hass)
    await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service("media_player", "media_play")
    await hass.services.async_call(
        domain="media_player",
        service="media_play",
        blocking=True,
        service_data={"entity_id": "media_player.livingroom_tv_receiver"},
    )

    send_key_method: AsyncMock = mock_api_client.async_send_key
    send_key_method.assert_has_awaits([call(KeyCode.PLAY)])


# async def test_send_text_service(hass: HomeAssistant, mock_api_client: Mock):
#     """Test sending text to the receiver. Test checks if the client is called"""
#     mock_api_client.async_get_player_state.return_value = MOCK_POLL_RESPONSE

#     MOCK_CONFIG_ENTRY.add_to_hass(hass)
#     await hass.config_entries.async_setup(MOCK_CONFIG_ENTRY.entry_id)
#     await hass.async_block_till_done()

#     assert hass.services.has_service(DOMAIN, "send_text")
#     await hass.services.async_call(
#         domain=DOMAIN,
#         service="send_text",
#         blocking=True,
#         service_data={
#             "text": "Testing 123",
#             "entity_id": "media_player.livingroom_tv_receiver",
#         },
#     )

#     send_key_method: AsyncMock = mock_api_client.async_send_character_input
#     send_key_method.assert_awaited_once_with("Testing 123")
