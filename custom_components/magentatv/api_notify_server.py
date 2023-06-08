"""Sample API Client."""
from __future__ import annotations

import asyncio
import socket
import uuid
from http import HTTPStatus
from collections.abc import Awaitable, Callable, Mapping

import aiohttp
import defusedxml.ElementTree as DET
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import NS

from .const import LOGGER

Callback = Callable[[Mapping[str, str]], Awaitable[None]]


class NotifyServer:
    """Notify Server API Client."""

    _subscription_registry: Mapping[str, list[tuple[str, str, str, Callback]]] = {}
    _resubscribe_task: asyncio.Task = None

    def __init__(
        self, source_ip: str, source_port: int = 0, timeout: int = 300
    ) -> None:
        """Sample API Client.
        Telekom uses 8058 as local port.
        """

        assert source_ip is not None
        assert source_port is not None
        assert timeout > 5

        self._source_ip = source_ip
        self._source_port = source_port

        self._timeout = timeout

        self._requester = AiohttpRequester(
            http_headers={
                "User-Agent": "Darwin/16.5.0 UPnP/1.0 HUAWEI_iCOS/iCOS V1R1C00 DLNADOC/1.50"
            }
        )

        self._socket = None
        self._aiohttp_server = None
        self._server = None

        self._subscribed_services = {}
        self._subscription_registry = {}
        self._resubscribe_task = None

    @staticmethod
    def create_socket(source_ip, port_range=tuple[int, int]):
        port, max_port = port_range
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while port <= max_port:
            try:
                sock.bind((source_ip, port))
                # sock.close()
                return port, sock
            except OSError:
                port += 1
        raise OSError("no free ports")

    async def async_subscribe_to_services(
        self, target, services: list[str], callback
    ) -> str:
        registration_id = str(uuid.uuid4())
        registrations = self._subscription_registry.get(registration_id, [])
        self._subscription_registry[registration_id] = registrations

        for service in services:
            if service not in [x[1] for x in registrations]:
                sid = await self._async_subscribe(target, service)
                registrations.append((target, service, sid, callback))
        return registration_id

    async def _async_subscribe(self, target, service) -> str:
        response = await self._requester.async_http_request(
            method="SUBSCRIBE",
            url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
            headers={
                "NT": "upnp:event",
                "TIMEOUT": f"Second-{self._timeout}",
                "HOST": f"{target[0]}:{target[1]}",
                "CALLBACK": f"<http://{self._source_ip}:{self._source_port}/eventSub>",
            },
            body=None,
        )
        assert response[0] == 200
        sid = response[1]["SID"]
        LOGGER.debug("Subscribed %s on %s at %s", sid, service, target)
        return sid

    async def _async_resubscribe(self, target, service, sid) -> str:
        response = await self._requester.async_http_request(
            method="SUBSCRIBE",
            url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
            headers={
                "SID": sid,
                "TIMEOUT": f"Second-{self._timeout}",
            },
            body=None,
        )
        assert response[0] == 200
        return response[1]["SID"]

    async def _async_unsubscribe(self, target, service, sid) -> str:
        response = await self._requester.async_http_request(
            method="UNSUBSCRIBE",
            url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
            headers={
                "SID": sid,
            },
            body=None,
        )
        assert response[0] in [200, 412]
        LOGGER.debug("Unsubscribed %s on %s at %s", sid, service, target)

    async def async_stop(self):
        LOGGER.info("Stopping")
        if self._resubscribe_task:
            self._resubscribe_task.cancel()

        await self._async_unsubscribe_all()

        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(2)
            self._aiohttp_server = None

        if self._server:
            self._server.close()
            self._server = None

        if self._socket:
            self._socket.close()

    async def async_start(self):
        if self._source_port == 0:
            self._source_port, self._socket = NotifyServer.create_socket(
                self._source_ip, (1024, 3000)
            )
        else:
            self._source_port, self._socket = NotifyServer.create_socket(
                self._source_ip, (self._source_port, self._source_port)
            )

        _source = (self._source_ip, self._source_port)
        self._aiohttp_server = aiohttp.web.Server(self._handle_request)
        try:
            self._server = await asyncio.get_event_loop().create_server(
                self._aiohttp_server,
                # host=_source[0],
                # port=_source[1],
                sock=self._socket,
            )
        except OSError as err:
            LOGGER.error(
                "Failed to create HTTP server at %s:%d: %s",
                _source[0],
                _source[1],
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
        _source = sock.getsockname()
        LOGGER.debug("New source for UpnpNotifyServer: %s", _source)
        self._source_ip, self._source_port = _source

        await self._start_resubscriber()

    async def _start_resubscriber(self):
        loop = asyncio.get_event_loop()
        self._resubscribe_task = loop.create_task(self._async_resubscribe_all())

    async def _async_unsubscribe_all(self):
        LOGGER.debug("Unsubscribing all subscriptions")
        for subscriptions in self._subscription_registry.values():
            for sub in subscriptions:
                target, service, sid, _ = sub
                await self._async_unsubscribe(target, service, sid)
                subscriptions.remove(sub)

    async def _async_resubscribe_all(self):
        while True:
            await asyncio.sleep(self._timeout * 0.8)
            for subscriptions in self._subscription_registry.values():
                for sub in subscriptions:
                    target, service, sid, _ = sub
                    await self._async_resubscribe(target, service, sid)

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
        # TODO detect service by SID
        await self._notify_changed_state_variables(headers.get("SID"), changes)

        return HTTPStatus.OK

    async def _notify_changed_state_variables(
        self, sid: str, changes
    ) -> Mapping[str, str]:
        callbacks = [
            sub[3](changes)
            for subs in self._subscription_registry.values()
            for sub in subs
            if sub[2] == sid
        ]
        await asyncio.gather(*callbacks)
