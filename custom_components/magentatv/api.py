"""Sample API Client."""
from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Mapping

from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.utils import get_local_ip
from homeassistant.exceptions import PlatformNotReady

from custom_components.magentatv.const import LOGGER

from .api_notify_server import NotifyServer


import xml.etree.ElementTree as ET
from uuid import getnode as get_mac


class PairingClient(NotifyServer):
    """Sample API Client."""

    def __init__(self, host: str, port: int, user_id: str, instance_id: str) -> None:
        """Sample API Client."""
        self._host = host
        self._port = port
        self._url = "http://" + self._host + ":" + str(self._port)  # + "/xml/xctc.xml"

        super().__init__(source_ip=get_local_ip(target_url=self._url))

        mac = get_mac()
        self._terminal_id = (
            hashlib.md5(("%012X" % mac).encode("UTF-8")).hexdigest().upper()
        )
        # self._terminal_id = (
        #    hashlib.md5((instance_id).encode("UTF-8")).hexdigest().upper()
        # )

        self._user_id = hashlib.md5(user_id.encode("UTF-8")).hexdigest().upper()
        self._requester = AiohttpRequester(
            http_headers={
                # "User-Agent": "Darwin/16.5.0 UPnP/1.0 HUAWEI_iCOS/iCOS V1R1C00 DLNADOC/1.50"
            }
        )
        self._pairing_event = asyncio.Event()

        self._verification_code = None

        self._listeners = []

    async def _async_on_pair_event(self, changes):
        if "messageBody" in changes:
            pairing_code = changes.get("messageBody").removeprefix("X-pairingCheck:")
            self._verification_code = (
                hashlib.md5(
                    (pairing_code + self._terminal_id + self._user_id).encode("UTF-8")
                )
                .hexdigest()
                .upper()
            )
            self._pairing_event.set()
        else:
            asyncio.gather(*[listener(changes) for listener in self._listeners])

    async def async_subscribe(self, callback) -> str:
        return self._listeners.append(callback)

    async def _async_subscribe_to_services(self, services: list[str], callback) -> str:
        return await super().async_subscribe_to_services(
            (self._host, self._port), services, callback
        )

    async def async_pair(self) -> str:
        while not self._pairing_event.is_set():
            try:
                await self._async_subscribe_to_services(
                    [
                        "X-CTC_RemotePairing",
                        "X-CTC_OpenApp",
                        "X-CTC_RemoteControl",
                        "RenderingControl",
                        "AVTransport",
                        "ConnectionManager",
                    ],
                    self._async_on_pair_event,
                )
                await self._async_send_pairing_request()
                LOGGER.info("Waiting for Pairing Code")
                await asyncio.wait_for(self._pairing_event.wait(), timeout=5)
                LOGGER.info("Waiting for Pairing Code")
                await self._async_verify_pairing()
            except (
                asyncio.CancelledError,
                asyncio.TimeoutError,
            ) as ex:
                LOGGER.warning("Pairing Issue", exc_info=ex)
                raise PlatformNotReady() from ex

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
        tree = ET.fromstring(text=response[2])
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
