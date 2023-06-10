"""Sample API Client."""
from __future__ import annotations
from ast import List

import asyncio
import socket
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus

import aiohttp
from aiohttp import web

import defusedxml.ElementTree as DET
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import NS

from .const import LOGGER

Callback = Callable[[Mapping[str, str]], Awaitable[None]]


class NotifyServer:
    """Notify Server API Client."""

    _source_ip: str
    _source_port: int
    _subscription_timeout: int

    _requester: AiohttpRequester

    _socket = socket.socket | None
    _aiohttp_server: web.Server | None
    _resubscribe_task: asyncio.Task = None

    _subscription_registry: dict[str, tuple[str, str, Callback]] = {}
    _buffer: dict[str, List[Mapping[str, str]]]

    def __init__(
        self, source_ip: str, source_port: int = 0, subscription_timeout: int = 300
    ) -> None:
        """Sample API Client.
        Telekom uses 8058 as local port.
        """

        assert source_ip is not None
        assert source_port is not None
        assert subscription_timeout is not None

        self._source_ip = source_ip
        self._source_port = source_port
        self._subscription_timeout = subscription_timeout

        self._requester = AiohttpRequester(
            http_headers={
                "User-Agent": "Darwin/16.5.0 UPnP/1.0 HUAWEI_iCOS/iCOS V1R1C00 DLNADOC/1.50"
            }
        )

        self._socket = None
        self._aiohttp_server = None
        self._server = None

        self._resubscribe_task = None

        self._subscription_registry = {}
        self._buffer = {}

    @staticmethod
    def create_socket(
        source_ip, port_range=tuple[int, int]
    ) -> tuple[int, socket.socket]:
        port, max_port = port_range
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        while port <= max_port:
            try:
                sock.bind((source_ip, port))
                # sock.close()
                return port, sock
            except OSError:
                port += 1
        raise OSError("No free ports detected")

    async def async_subscribe_to_service(
        self, target, service: str, callback: Callback
    ) -> str:
        sid = await self._async_subscribe(target, service)
        self._subscription_registry[sid] = (target, service, callback)

        for changes in self._buffer.pop(sid, []):
            callback(changes)

        return sid

    async def async_unsubscribe(self, sid: str):
        target, service, _ = self._subscription_registry.pop(sid)
        await self._async_unsubscribe(
            target,
            service,
            sid,
        )

    async def _async_subscribe(self, target, service) -> str:
        response = await self._requester.async_http_request(
            method="SUBSCRIBE",
            url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
            headers={
                "NT": "upnp:event",
                "TIMEOUT": f"Second-{self._subscription_timeout}",
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
                "TIMEOUT": f"Second-{self._subscription_timeout}",
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
        LOGGER.info("Stopping Notify Server")
        if self._resubscribe_task:
            self._resubscribe_task.cancel()
            self._resubscribe_task = None

        await self._async_unsubscribe_all()

        if self._aiohttp_server:
            await self._aiohttp_server.shutdown(5)
            self._aiohttp_server = None

        if self._server:
            self._server.close()
            self._server = None

        if self._socket:
            self._socket.close()
            self._socket = None

        self._buffer = {}

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

        LOGGER.debug("Starting Notify Server on %s ...", _source)

        self._aiohttp_server = web.Server(self._handle_request)
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
            raise err

        # Get listening port.
        socks = self._server.sockets
        assert socks and len(socks) == 1
        sock = socks[0]
        _source = sock.getsockname()
        LOGGER.debug("Started Notify Server on %s", _source)
        self._source_ip, self._source_port = _source

        await self._start_resubscriber()

    async def _start_resubscriber(self):
        loop = asyncio.get_event_loop()
        self._resubscribe_task = loop.create_task(self._async_resubscribe_all())

    async def _async_unsubscribe_all(self):
        LOGGER.debug("Unsubscribing all subscriptions")
        for sid in self._subscription_registry:
            await self.async_unsubscribe(sid)

    async def _async_resubscribe_all(self):
        while True:
            await asyncio.sleep(self._subscription_timeout - 5)
            for sid, (target, service, _) in self._subscription_registry.items():
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

        await self._notify_subscribed_callbacks(headers.get("SID"), changes)

        return HTTPStatus.OK

    async def _notify_subscribed_callbacks(
        self, sid: str, changes
    ) -> Mapping[str, str]:
        subscription = self._subscription_registry.get(sid)
        if subscription:
            (_, _, callback) = subscription
            await callback(changes)
        else:
            # subscriber not yet subscribed -> save to buffer
            self._buffer.setdefault(sid, []).append(changes)
