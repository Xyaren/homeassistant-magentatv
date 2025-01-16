"""Sample API Client."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.const import HttpRequest, HttpResponse
from async_upnp_client.exceptions import UpnpCommunicationError, UpnpConnectionError, UpnpConnectionTimeoutError

from .const import LOGGER, KeyCode
from .exceptions import (
    CommunicationException,
    CommunicationTimeoutException,
    NotPairedException,
    PairingTimeoutException,
)
from .notify_server import NotifyServer
from .utils import magneta_hash

PAIRING_EVENT_TIMEOUT = 5
PAIRING_ATTEMPTS = 3


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
        self._requester = AiohttpRequester(http_headers={"User-Agent": "Homeassistant MagentaTV Integration"})

        self._verification_code = None

        self._event_registration_id = None
        self._pairing_event = asyncio.Event()

        self._event_listeners = []

    def subscribe(self, callback):
        if callback not in self._event_listeners:
            self._event_listeners.append(callback)

    async def async_close(self):
        if self._event_registration_id:
            await self._notify_server.async_unsubscribe(self._event_registration_id)
            self._event_registration_id = None
        self._pairing_event.clear()
        self._verification_code = None

    async def _on_event(self, changes):
        # is paired:
        if self._pairing_event.is_set():
            # notify listeners
            asyncio.gather(*[listener(changes) for listener in self._event_listeners])
        elif "messageBody" in changes:
            body = changes.get("messageBody")
            if "X-pairingCheck:" in body:
                pairing_code = changes.get("messageBody").removeprefix("X-pairingCheck:")
                self._verification_code = magneta_hash(pairing_code + self._terminal_id + self._user_id)
                self._pairing_event.set()

    async def _register_for_events(self):
        self._event_registration_id = await self._notify_server._async_subscribe_to_service(
            (self._host, self._port),
            "X-CTC_RemotePairing",
            self._on_event,
        )
        LOGGER.debug(
            "Registered for events on %s. ID: %s",
            self._host,
            self._event_registration_id,
        )

    async def async_pair(self) -> str:
        attempts = 0
        while not self._pairing_event.is_set():
            attempts += 1
            LOGGER.debug("Attempt %s", attempts)
            try:
                await self._register_for_events()

                await self._async_send_pairing_request()

                LOGGER.info("Waiting for Pairing Code")
                await asyncio.wait_for(self._pairing_event.wait(), timeout=PAIRING_EVENT_TIMEOUT)
                LOGGER.info("Received Pairing Code")

                await self._async_verify_pairing()
                LOGGER.info("Pairing Verified. Success !")
            except UpnpConnectionError as ex:
                await self.async_close()
                LOGGER.debug("Could not connect", exc_info=ex)
                raise CommunicationException("No connection could be made to the receiver") from ex
            except (asyncio.TimeoutError, PairingTimeoutException) as ex:
                await self.async_close()
                # pairing was not successfull, reset the client to start fresh
                LOGGER.debug("Pairing Timed out", exc_info=ex)
                if attempts > PAIRING_ATTEMPTS:
                    LOGGER.warning("Repeated failure")
                    raise PairingTimeoutException(
                        f"No pairingCode received from the receiver within {attempts} attempts waiting {PAIRING_EVENT_TIMEOUT} each"
                    ) from ex

        self.assert_paired()
        return self._verification_code

    def is_paired(self) -> bool:
        return self._verification_code is not None

    def assert_paired(self):
        if self._verification_code is None:
            raise NotPairedException("Client needs to be paired in order to use this function")

    async def async_get_player_state(self) -> str:
        self.assert_paired()
        response = await self._async_send_upnp_soap(
            "X-CTC_RemotePairing",
            "X-getPlayerState",
            {
                "pairingDeviceID": self._terminal_id,
                "verificationCode": self._verification_code,
            },
        )
        assert response.status_code == 200
        tree = ET.fromstring(text=response.body)
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
        assert response.status_code == 200

    async def _async_verify_pairing(self):
        self.assert_paired()

        response = await self._async_send_upnp_soap(
            "X-CTC_RemotePairing",
            "X-pairingCheck",
            {
                "pairingDeviceID": self._terminal_id,
                "verificationCode": self._verification_code,
            },
        )

        assert response.status_code == 200
        assert "<pairingResult>0</pairingResult>" in response.body

    async def _async_send_upnp_soap(self, service: str, action: str, attributes: Mapping[str, str]) -> HttpResponse:
        try:
            attributes = "".join([f"   <{k}>{escape(v)}</{k}>\n" for k, v in attributes.items()])
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
                http_request=HttpRequest(
                    method="POST",
                    url=f"{self._url}/upnp/service/{service}/Control",
                    headers={
                        "SOAPACTION": f"urn:schemas-upnp-org:service:{service}:1#{action}",
                        "HOST": f"{self._host}:{self._port}",
                        "Content-Type": 'text/xml; charset="utf-8"',
                    },
                    body=full_body,
                )
            )
        except UpnpConnectionTimeoutError as ex:
            raise CommunicationTimeoutException() from ex
        except UpnpCommunicationError as ex:
            raise CommunicationException() from ex

    async def async_send_action(self):
        self.assert_paired()
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
        LOGGER.debug("%s: %s", "Set URI", response.body)

        response = await self._async_send_upnp_soap(
            "AVTransport",
            "Play",
            {"InstanceID": "0", "Speed": "1"},
        )
        LOGGER.debug("%s: %s", "Play", response.body)

    async def async_send_key(self, key: KeyCode):
        self.assert_paired()
        response = await self._async_send_upnp_soap(
            "X-CTC_RemoteControl",
            "X_CTC_RemoteKey",
            {
                "InstanceID": "0",
                "KeyCode": f"keyCode={key.value}^{self._terminal_id}:{self._verification_code}^userID:{self._user_id}",
            },
        )
        LOGGER.info("%s - %s: %s", "RemoteKey", key, response)
        assert response.status_code == 200

    async def async_send_character_input(self, character_input: str):
        self.assert_paired()
        assert "^" not in character_input  # broken
        response = await self._async_send_upnp_soap(
            "X-CTC_RemoteControl",
            "X_CTC_RemoteKey",
            {
                "InstanceID": "0",
                "KeyCode": f"characterInput={character_input}^{self._terminal_id}:{self._verification_code}^userID:{self._user_id}",
            },
        )
        LOGGER.info("%s - '%s': %s", "Send Character Input", character_input, response.body)
        assert response.status_code == 200
