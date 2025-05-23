from __future__ import annotations

import asyncio
import re
import socket
from ast import List
from collections.abc import Awaitable, Callable, Mapping
from functools import wraps
from http import HTTPStatus

import aiohttp
import defusedxml.ElementTree as Et
from aiohttp import web
from async_upnp_client.aiohttp import AiohttpRequester
from async_upnp_client.client import NS
from async_upnp_client.const import HttpRequest
from async_upnp_client.exceptions import UpnpCommunicationError, UpnpConnectionTimeoutError
from async_upnp_client.utils import get_local_ip

from .const import LOGGER
from .exceptions import (
    CommunicationException,
    CommunicationTimeoutException,
)

Callback = Callable[[Mapping[str, str]], Awaitable[None]]


def wrap_exceptions(f):
    @wraps(f)
    def applicator(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except UpnpConnectionTimeoutError as ex:
            raise CommunicationTimeoutException() from ex
        except UpnpCommunicationError as ex:
            raise CommunicationException() from ex

    return applicator


class NotifyServer:
    """Notification server listening for subscribed events and invoking the corresponding callbacks"""

    # https://regex101.com/r/ojU2H9/1
    _invalid_ampersand_re = re.compile(r"&(?![a-z0-9]+;)")

    _listen_ip_port = (tuple[str, int],)
    _advertise_ip_port = tuple[str | None, int | None] | None

    _subscription_timeout: int

    _requester: AiohttpRequester

    _socket = socket.socket | None
    _aiohttp_server: web.Server | None
    _resubscribe_task: asyncio.Task = None

    _subscription_registry: dict[str, tuple[str, str, Callback]] = {}
    _buffer: dict[str, List[Mapping[str, str]]]

    start_stop_lock = asyncio.Lock()
    subscription_lock = asyncio.Lock()

    def __init__(
        self,
        listen: tuple[str, int],
        advertise: tuple[str | None, int | None] | None = None,
        subscription_timeout: int = 300,
    ) -> None:
        """Sample API Client.
        Telekom uses 8058 as local port.
        """

        assert listen is not None
        assert subscription_timeout is not None

        self._listen_ip_port = listen
        self._advertise_ip_port = advertise

        self._subscription_timeout = subscription_timeout

        self._requester = AiohttpRequester(http_headers={"User-Agent": "Homeassistant MagentaTV Integration"})

        self._socket = None
        self._aiohttp_server = None
        self._server = None

        self._resubscribe_task = None

        self._subscription_registry = {}
        self._buffer = {}

    @staticmethod
    def create_socket(source_ip, source_port: int) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Allow reuse of socket directly after close
        # https://stackoverflow.com/a/29217540
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        sock.bind((source_ip, source_port))
        return sock

    async def _async_subscribe_to_service(self, target, service: str, callback: Callback) -> str:
        await self.async_start()
        sid = await self._async_subscribe(target, service)
        self._subscription_registry[sid] = (target, service, callback)

        for changes in self._buffer.pop(sid, []):
            await callback(changes)

        return sid

    async def async_unsubscribe(self, sid: str):
        async with self.subscription_lock:
            if sid in self._subscription_registry:
                target, service, _ = self._subscription_registry.pop(sid)
                await self._async_unsubscribe(
                    target,
                    service,
                    sid,
                )

        if self._is_running() and not await self._async_has_subscriptions():
            LOGGER.info("No more subscriptions. Shutting down")
            await self.async_stop()

    @wrap_exceptions
    async def _async_subscribe(self, target, service) -> str:
        url = f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event"

        adv_host, adv_port = self._advertise_ip_port or (None, None)
        if adv_host is None:
            adv_host = get_local_ip(target_url=url)
        if adv_port is None:
            adv_port = self._listen_ip_port[1]

        try:
            response = await self._requester.async_http_request(
                http_request=HttpRequest(
                    method="SUBSCRIBE",
                    url=url,
                    headers={
                        "NT": "upnp:event",
                        "TIMEOUT": f"Second-{self._subscription_timeout}",
                        "HOST": f"{target[0]}:{target[1]}",
                        "CALLBACK": f"<http://{adv_host}:{adv_port}/eventSub>",
                    },
                    body=None,
                )
            )
        except UpnpConnectionTimeoutError as ex:
            LOGGER.error("Failed to subscribe %s on %s at %s", service, target, url, exc_info=ex)
            raise ex
        assert response.status_code == 200
        sid = response.headers["SID"]
        LOGGER.debug("Subscribed %s on %s at %s", sid, service, target)
        return sid

    @wrap_exceptions
    async def _async_resubscribe(self, target, service, sid) -> str:
        try:
            response = await self._requester.async_http_request(
                http_request=HttpRequest(
                    method="SUBSCRIBE",
                    url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
                    headers={
                        "SID": sid,
                        "TIMEOUT": f"Second-{self._subscription_timeout}",
                    },
                    body=None,
                )
            )
            assert response.status_code == 200
            return response.headers["SID"]
        except UpnpConnectionTimeoutError as ex:
            LOGGER.error("Failed to resubscribe %s on %s at %s", sid, service, target, exc_info=ex)
            raise ex

    @wrap_exceptions
    async def _async_unsubscribe(self, target, service, sid) -> str:
        try:
            response = await self._requester.async_http_request(
                http_request=HttpRequest(
                    method="UNSUBSCRIBE",
                    url=f"http://{target[0]}:{target[1]}/upnp/service/{service}/Event",
                    headers={
                        "SID": sid,
                    },
                    body=None,
                )
            )
            assert response.status_code in [200, 412]
            LOGGER.debug("Unsubscribed %s on %s at %s", sid, service, target)
        except UpnpConnectionTimeoutError as ex:
            LOGGER.warning("Failed to unsubscribe %s on %s at %s", sid, service, target, exc_info=ex)

    async def _async_has_subscriptions(self) -> bool:
        async with self.subscription_lock:
            if self._subscription_registry:
                for regs in self._subscription_registry.values():
                    if len(regs) > 0:
                        return True
            return False

    def _is_running(self) -> bool:
        return self._resubscribe_task or self._aiohttp_server or self._server or self._socket

    async def async_stop(self):
        async with self.start_stop_lock:
            if not self._is_running():
                # already stopped
                return

            LOGGER.info("Stopping Notify Server")
            if self._resubscribe_task:
                self._resubscribe_task.cancel()
                self._resubscribe_task = None

            if await self._async_has_subscriptions():
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
        async with self.start_stop_lock:
            if self._is_running():
                # already running
                return

            self._socket = NotifyServer.create_socket(*self._listen_ip_port)

            LOGGER.debug("Starting Notify Server on %s:%s ...", *self._listen_ip_port)

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
                    *self._listen_ip_port,
                    err,
                )
                raise err

            await self._start_resubscriber()

    async def _start_resubscriber(self):
        loop = asyncio.get_event_loop()
        self._resubscribe_task = loop.create_task(self._async_resubscribe_all())

    async def _async_unsubscribe_all(self):
        async with self.subscription_lock:
            LOGGER.debug("Unsubscribing all subscriptions")
            for sid in list(self._subscription_registry):
                target, service, _ = self._subscription_registry.pop(sid)
                await self._async_unsubscribe(
                    target,
                    service,
                    sid,
                )

    async def _async_resubscribe_all(self):
        while True:
            await asyncio.sleep(self._subscription_timeout - 5)
            for sid, (target, service, _) in self._subscription_registry.items():
                await self._async_resubscribe(target, service, sid)

    async def _handle_request(self, request: aiohttp.web.BaseRequest) -> aiohttp.web.Response:
        """Handle incoming requests."""
        headers = request.headers
        body = await request.text()

        if request.method != "NOTIFY":
            LOGGER.debug("Not notify")
            return aiohttp.web.Response(status=405)

        LOGGER.debug(
            "Incoming request:\nNOTIFY\n%s\n\n%s",
            "\n".join([key + ": " + value for key, value in headers.items()]),
            body,
        )

        status = await self._handle_notify(headers, body)
        LOGGER.debug("NOTIFY response status: %s", status)
        LOGGER.debug("Sending response: %s", status)

        return aiohttp.web.Response(status=status)

    async def _handle_notify(self, headers: Mapping[str, str], body: str) -> HTTPStatus:
        """Handle a NOTIFY request."""
        # ensure valid request
        if "NT" not in headers or "NTS" not in headers:
            return HTTPStatus.BAD_REQUEST

        if headers["NT"] != "upnp:event" or headers["NTS"] != "upnp:propchange" or "SID" not in headers:
            return HTTPStatus.PRECONDITION_FAILED

        # decode event and send updates to service
        changes = {}

        try:
            # fixed unencoded ampersands in original body - someone did not read the spec - & -> &amp;
            fixed_body = self._invalid_ampersand_re.sub("&amp;", body)

            el_root = Et.fromstring(fixed_body)
            for el_property in el_root.findall("./event:property", NS):
                for el_state_var in el_property:
                    name = el_state_var.tag
                    value = el_state_var.text or ""
                    changes[name] = value
        except Et.ParseError as ex:
            LOGGER.error("Failed to parse event:\n%s", body, exc_info=ex)
            raise ex

        await self._notify_subscribed_callbacks(headers.get("SID"), changes)

        return HTTPStatus.OK

    async def _notify_subscribed_callbacks(self, sid: str, changes) -> Mapping[str, str]:
        subscription = self._subscription_registry.get(sid)
        if subscription:
            (_, _, callback) = subscription
            await callback(changes)
        else:
            # subscriber not yet subscribed -> save to buffer
            self._buffer.setdefault(sid, []).append(changes)
