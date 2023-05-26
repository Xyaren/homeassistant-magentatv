"""Sample API Client."""
from __future__ import annotations

from .const import LOGGER

import aiohttp
import asyncio

from async_upnp_client.aiohttp import AiohttpNotifyServer, AiohttpRequester
from async_upnp_client.client import UpnpDevice, UpnpService, UpnpStateVariable
from async_upnp_client.client_factory import UpnpFactory
from async_upnp_client.const import (
    StateVariableInfo,
    StateVariableTypeInfo,
    STATE_VARIABLE_TYPE_MAPPING,
)
from async_upnp_client.exceptions import UpnpResponseError
from async_upnp_client.search import async_search
from async_upnp_client.utils import CaseInsensitiveDict, get_local_ip
from ipaddress import ip_network
from datetime import timedelta

from homeassistant.components import network
from xml.etree.ElementTree import Element
from typing import Sequence
import asyncio
import logging
import weakref
import hashlib
from abc import ABC
from datetime import timedelta
from http import HTTPStatus
from ipaddress import ip_address
from typing import Dict, Mapping, Optional, Set, Tuple, Type, Union
from urllib.parse import urlparse
from async_upnp_client.client import NS

import defusedxml.ElementTree as DET
from uuid import getnode as get_mac


class IntegrationBlueprintApiClientError(Exception):
    """Exception to indicate a general API error."""


class IntegrationBlueprintApiClientCommunicationError(
    IntegrationBlueprintApiClientError
):
    """Exception to indicate a communication error."""


class IntegrationBlueprintApiClientAuthenticationError(
    IntegrationBlueprintApiClientError
):
    """Exception to indicate an authentication error."""


class PairingClient:
    """Sample API Client."""

    def __init__(self, host: str, port: int, user_id: str, instance_id: str) -> None:
        """Sample API Client."""
        self._host = host
        self._port = port
        self._user_id = hashlib.md5(user_id.encode("UTF-8")).hexdigest().upper()
        self._verification_code = None

        self._terminal_id = hashlib.md5(instance_id.encode("UTF-8")).hexdigest().upper()

        self._requester = AiohttpRequester(
            http_headers={
                "User-Agent": "Darwin/16.5.0 UPnP/1.0 HUAWEI_iCOS/iCOS V1R1C00 DLNADOC/1.50"
            }
        )
        self._factory = UpnpFactory(self._requester, non_strict=True)
        self._pairing_event = asyncio.Event()

        self._url = "http://" + self._host + ":" + str(self._port)  # + "/xml/xctc.xml"
        self._source = None
        self._aiohttp_server = None
        self._server = None

    async def async_get_verification_code(self) -> any:
        """Get information from the API."""

        await self._async_start_notify_server()
        await self._async_subscribe_to_service("X-CTC_RemotePairing")
        await self._async_send_pairing_request()

        await self._pairing_event.wait()
        await self._async_stop_notify_server()

        await self._async_verify_pairing()
        return self._verification_code

    async def _async_subscribe_to_service(self, service: str):
        await self._requester.async_http_request(
            method="SUBSCRIBE",
            url=f"{self._url}/upnp/service/{service}/Event",
            headers={
                "NT": "upnp:event",
                "TIMEOUT": "Second-300",
                "HOST": f"{self._host}:{self._port}",
                "CALLBACK": f"<http://{self._source[0]}:{self._source[1]}/notify>",
            },
            body=None,
        )

    async def _async_send_pairing_request(self):
        response = await self._requester.async_http_request(
            method="POST",
            url=f"{self._url}/upnp/service/X-CTC_RemotePairing/Control",
            headers={
                "SOAPAction": "urn:schemas-upnp-org:service:X-CTC_RemotePairing:1#X-pairingRequest",
                "HOST": f"{self._host}:{self._port}",
                "Content-Type": 'text/xml; charset="utf-8"',
            },
            body=(
                '<?xml version="1.0"?>'
                '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                "   <s:Body>"
                '      <u:X-pairingRequest xmlns:u="urn:schemas-upnp-org:service:X-CTC_RemotePairing:1">'
                f"         <pairingDeviceID>{self._terminal_id}</pairingDeviceID>"
                "         <friendlyName>Homeassistant</friendlyName>"
                f"         <userID>{self._user_id}</userID>"
                "      </u:X-pairingRequest>"
                "   </s:Body>"
                "</s:Envelope>"
            ),
        )
        assert response[0] == 200

    async def _async_verify_pairing(self):
        response = await self._requester.async_http_request(
            method="POST",
            url=f"{self._url}/upnp/service/X-CTC_RemotePairing/Control",
            headers={
                "SOAPAction": "urn:schemas-upnp-org:service:X-CTC_RemotePairing:1#X-pairingCheck",
                "HOST": f"{self._host}:{self._port}",
                "Content-Type": 'text/xml; charset="utf-8"',
            },
            body=(
                '<?xml version="1.0"?>'
                '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
                "  <s:Body>"
                '    <u:X-pairingCheck xmlns:u="urn:schemas-upnp-org:service:X-CTC_RemotePairing:1">'
                f"      <pairingDeviceID>{self._terminal_id}</pairingDeviceID>"
                f"      <verificationCode>{self._verification_code}</verificationCode>"
                "    </u:X-pairingCheck>"
                "  </s:Body>"
                "</s:Envelope>"
            ),
        )
        assert response[0] == 200
        assert "<pairingResult>0</pairingResult>" in response[2]

    async def _async_stop_notify_server(self):
        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(10)
            self._aiohttp_server = None

        if self._server:
            self._server.close()
            self._server = None

        self._pairing_event.clear()

    async def _async_start_notify_server(self):
        self._source = (get_local_ip(target_url=self._url), 0)

        self._aiohttp_server = aiohttp.web.Server(self._handle_request)
        try:
            self._server = await asyncio.get_event_loop().create_server(
                self._aiohttp_server, self._source[0], self._source[1]
            )
        except OSError as err:
            LOGGER.error(
                "Failed to create HTTP server at %s:%d: %s",
                self._source[0],
                self._source[1],
                err,
            )
            raise Exception(
                errno=err.errno,
                strerror=err.strerror,
            ) from err

        # Get listening port.
        socks = self._server.sockets
        assert socks and len(socks) == 1
        sock = socks[0]
        self._source = sock.getsockname()
        LOGGER.debug("New source for UpnpNotifyServer: %s", self._source)

        # upnp_device = await self._factory.async_create_device(url)

        # notify_server = AiohttpNotifyServer(self._requester, source=source)
        # await notify_server.async_start_server()
        # print("Listening on: %s", notify_server.callback_url)

        # service = await self._get_remote_control_service(upnp_device)

        # try:
        #     print("Subscribing")
        #     result = await notify_server.event_handler.async_subscribe(
        #         service, timeout=timedelta(seconds=300)
        #     )
        #     print(result)
        # except UpnpResponseError as ex:
        #     print("Unable to subscribe to %s: %s", service, ex)

        # event = asyncio.Event()

        # def on_event_listener(
        #     service: UpnpService, stateVars: Sequence[UpnpStateVariable]
        # ):
        #     if len(stateVars) > 0:
        #         if stateVars[0].name == "messageBody":
        #             value = str(stateVars[0].value)
        #             if value.startswith("X-pairingCheck"):
        #                 event.set()
        #                 self._pairing_code = value.removeprefix("X-pairingCheck:")

        # service.on_event = on_event_listener

        # await event.wait()
        # await notify_server.async_stop_server()
        # assert self._pairing_code is not None
        # return self._pairing_code

    async def _handle_request(
        self, request: aiohttp.web.BaseRequest
    ) -> aiohttp.web.Response:
        """Handle incoming requests."""
        LOGGER.debug("Received request: %s", request)

        headers = request.headers
        body = await request.text()
        LOGGER.debug(
            "Incoming request:\nNOTIFY\n%s\n\n%s",
            "\n".join([key + ": " + value for key, value in headers.items()]),
            body,
        )

        if request.method != "NOTIFY":
            LOGGER.debug("Not notify")
            return aiohttp.web.Response(status=405)

        status = await self._handle_notify(headers, body)
        LOGGER.debug("NOTIFY response status: %s", status)
        LOGGER.debug("Sending response: %s", status)

        return aiohttp.web.Response(status=status)

    async def _handle_notify(self, headers: Mapping[str, str], body: str) -> HTTPStatus:
        """Handle a NOTIFY request."""
        # ensure valid request
        if "NT" not in headers or "NTS" not in headers:
            return HTTPStatus.BAD_REQUEST

        if (
            headers["NT"] != "upnp:event"
            or headers["NTS"] != "upnp:propchange"
            or "SID" not in headers
        ):
            return HTTPStatus.PRECONDITION_FAILED

        # decode event and send updates to service
        changes = {}
        stripped_body = body.rstrip(" \t\r\n\0")
        el_root = DET.fromstring(stripped_body)
        for el_property in el_root.findall("./event:property", NS):
            for el_state_var in el_property:
                name = el_state_var.tag
                value = el_state_var.text or ""
                changes[name] = value

        # send changes to service
        await self._notify_changed_state_variables(changes)

        return HTTPStatus.OK

    async def _notify_changed_state_variables(self, changes: Mapping[str, str]):
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
        pass

    async def _get_remote_control_service(self, upnp_device):
        service = upnp_device.service(
            "urn:schemas-upnp-org:service:X-CTC_RemotePairing:1"
        )
        await self._fake_variable(service, name="messageBody")
        await self._fake_variable(service, name="uniqueDeviceID")
        return service

    async def _fake_variable(self, service, name: str):
        element = Element("dummy")
        type_info = StateVariableTypeInfo(
            "string", STATE_VARIABLE_TYPE_MAPPING["string"], None, {}, None, element
        )
        state_var_info = StateVariableInfo(
            name,
            send_events=False,
            type_info=type_info,
            xml=element,
        )
        service.state_variables[name] = UpnpStateVariable(
            state_var_info,
            self._factory._state_variable_create_schema(type_info),
        )
