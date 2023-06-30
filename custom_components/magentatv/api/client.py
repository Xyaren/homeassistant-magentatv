"""Sample API Client."""
from __future__ import annotations

import asyncio
import xml.etree.ElementTree as Et
from collections.abc import Mapping
from urllib.parse import urlencode

from async_upnp_client.aiohttp import AiohttpRequester

from .const import LOGGER, KeyCode
from .notify_server import NotifyServer
from .utils import magneta_hash


class Client:
    """Sample API Client."""

    def __init__(
        self,
        host: str,
        port: int,
        user_id: str,
        instance_id: str,
        notify_server: NotifyServer,
    ) -> None:
        """Sample API Client."""
        self._host = host
        self._port = port
        self._url = "http://" + self._host + ":" + str(self._port)

        self._notify_server = notify_server

        self._terminal_id = magneta_hash(instance_id)

        self._user_id = magneta_hash(user_id)
        self._requester = AiohttpRequester(
            http_headers={"User-Agent": "Homeassistant MagentaTV Integration"}
        )

        self._verification_code = None

        self._event_registration_id = None
        self._event_listeners = []

    def subscribe(self, callback):
        if callback not in self._event_listeners:
            self._event_listeners.append(callback)

    async def async_close(self):
        if self._event_registration_id:
            await self._notify_server.async_unsubscribe(self._event_registration_id)

    async def async_pair(self) -> str:
        _pairing_event = asyncio.Event()

        async def _async_on_pair_event(changes):
            if _pairing_event.is_set():
                asyncio.gather(
                    *[listener(changes) for listener in self._event_listeners]
                )
            if "messageBody" in changes:
                pairing_code = changes.get("messageBody").removeprefix(
                    "X-pairingCheck:"
                )
                self._verification_code = magneta_hash(
                    pairing_code + self._terminal_id + self._user_id
                )
                _pairing_event.set()

        while not _pairing_event.is_set():
            try:
                self._event_registration_id = (
                    await self._notify_server.async_subscribe_to_service(
                        (self._host, self._port),
                        "X-CTC_RemotePairing",
                        _async_on_pair_event,
                    )
                )

                LOGGER.debug(
                    "Event Registration ID of %s: %s",
                    self._host,
                    self._event_registration_id,
                )
                await self._async_send_pairing_request()
                LOGGER.info("Waiting for Pairing Code")
                await asyncio.wait_for(_pairing_event.wait(), timeout=10)
                LOGGER.info("Received Pairing Code")
                await self._async_verify_pairing()
                LOGGER.info("Pairing Verified. Success !")
            except (
                asyncio.CancelledError,
                asyncio.TimeoutError,
            ) as ex:
                LOGGER.warning("Pairing Issue", exc_info=ex)
                raise ex

        assert self._verification_code is not None

        return self._verification_code

    async def async_get_player_state(self) -> str:
        response = await self._async_send_upnp_soap(
            "X-CTC_RemotePairing",
            "X-getPlayerState",
            {
                "pairingDeviceID": self._terminal_id,
                "verificationCode": self._verification_code,
            },
        )
        assert response[0] == 200
        tree = Et.fromstring(text=response[2])
        result = {}
        for child in tree[0][0]:
            result[child.tag] = child.text
        return result

    async def _async_send_pairing_request(self):
        response = await self._async_send_upnp_soap(
            "X-CTC_RemotePairing",
            "X-pairingRequest",
            {
                "pairingDeviceID": self._terminal_id,
                "friendlyName": "Homeassistant Integration",
                "userID": self._user_id,
            },
        )
        assert response[0] == 200

    async def _async_verify_pairing(self):
        response = await self._async_send_upnp_soap(
            "X-CTC_RemotePairing",
            "X-pairingCheck",
            {
                "pairingDeviceID": self._terminal_id,
                "verificationCode": self._verification_code,
            },
        )

        assert response[0] == 200
        assert "<pairingResult>0</pairingResult>" in response[2]

    async def _async_send_upnp_soap(
        self, service: str, action: str, attributes: Mapping[str, str]
    ) -> tuple[int, Mapping, str]:
        attributes = "".join([f"   <{k}>{v}</{k}>\n" for k, v in attributes.items()])
        full_body = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\n'
            " <s:Body>\n"
            f'  <u:{action} xmlns:u="urn:schemas-upnp-org:service:{service}:1">\n'
            f"{attributes}"
            f"  </u:{action}>\n"
            " </s:Body>\n"
            "</s:Envelope>"
        )
        return await self._requester.async_http_request(
            method="POST",
            url=f"{self._url}/upnp/service/{service}/Control",
            headers={
                "SOAPACTION": f"urn:schemas-upnp-org:service:{service}:1#{action}",
                "HOST": f"{self._host}:{self._port}",
                "Content-Type": 'text/xml; charset="utf-8"',
            },
            body=full_body,
        )

    async def async_send_action(self):
        # TODO - make it work

        params = {
            "type": "EVENT_REMOTE_CONTROL",
            "action": "functionCall",
            "functionType": "startPlay",
            "mediaCode": "7216",  # ?
            "mediaType": "1",  # ?
            "userID": self._user_id,
            "ContentID": "0",  # ?
            "playByBookmark": "0",
            "playByTime": "0",
        }

        response = await self._async_send_upnp_soap(
            "AVTransport",
            "SetAVTransportURI",
            {
                "InstanceID": "0",
                "CurrentURI": f"http://iptv?{urlencode(params)}&pairingInfo={self._terminal_id}:{self._verification_code}&platform=IPTV",
                "CurrentURIMetaData": "",
            },
        )
        LOGGER.debug("%s: %s", "Set URI", response[2])

        response = await self._async_send_upnp_soap(
            "AVTransport",
            "Play",
            {"InstanceID": "0", "Speed": "1"},
        )
        LOGGER.debug("%s: %s", "Play", response[2])

    async def async_send_key(self, key: KeyCode):
        assert self._verification_code is not None
        response = await self._async_send_upnp_soap(
            "X-CTC_RemoteControl",
            "X_CTC_RemoteKey",
            {
                "InstanceID": "0",
                "KeyCode": f"keyCode={key.value}^{self._terminal_id}:{self._verification_code}^userID:{self._user_id}",
            },
        )
        LOGGER.info("%s - %s: %s", "RemoteKey", key, response)

    async def async_send_character_input(self, character_input: str):
        assert self._verification_code is not None
        response = await self._async_send_upnp_soap(
            "X-CTC_RemoteControl",
            "X_CTC_RemoteKey",
            {
                "InstanceID": "0",
                "KeyCode": f"characterInput={character_input}^{self._terminal_id}:{self._verification_code}^userID:{self._user_id}",
            },
        )
        LOGGER.info(
            "%s - '%s': %s", "Send Character Input", character_input, response[2]
        )
        assert response[0] == 200
