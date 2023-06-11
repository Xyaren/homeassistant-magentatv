"""Adds config flow for Blueprint."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from async_upnp_client.aiohttp import AiohttpSessionRequester
from async_upnp_client.description_cache import DescriptionCache
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_ID,
    CONF_MODEL,
    CONF_PORT,
    CONF_TYPE,
    CONF_UNIQUE_ID,
    CONF_URL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.magentatv import async_get_notification_server


from .api import PairingClient
from .const import CONF_USER_ID, DATA_NOTIFICATION_SERVER, DATA_USER_ID, DOMAIN, LOGGER

FlowInput = Mapping[str, Any] | None
ST = "urn:schemas-upnp-org:device:MediaRenderer:1"


# Config Flow:
#
# ┌───────────────────┐  ┌───────────────┐       ┌───────────────┐
# │async_step_unignore│  │async_step_ssdp│       │async_step_user│
# │                   │  │               │       │               │
# │on unignore by user│  │SSDP discovery │       │user triggered │
# └────────────────┬──┘  └───────┬───────┘       └─┬────────┬────┘
#                  │             │        Select Device     │No Selection
#                  │             │        from List│        │
#            ┌─────▼─────────────▼─────┐           │  ┌─────▼───────────┐
#            │async_step_enter_user_id │◄──────────┘  │async_step_manual│
#            │                         │              │                 │
#            │request user_id from user│◄────Check────┤  enter host+IP  │
#            └─────────────┬───────────┘              └─────────────────┘
#                          │
#                    Enter User Id
#                          │
#                ┌─────────▼─────────┐
#                │  async_step_pair  │
#                │                   │
#                │Test Device Pairing│
#                └─────────┬─────────┘
#                          │
#                ┌─────────▼─────────┐
#                │ async_step_finish │
#                └───────────────────┘
class MagentaTvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MagentaTV."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._discoveries: dict[str, ssdp.SsdpServiceInfo] = {}

        self.friendly_name: str | None = None
        self.model_name: str | None = None
        self.model_number: str | None = None
        self.manufacturer: str | None = None
        self._udn: str | None = None
        self.host: str | None = None
        self.port: str | None = None
        self.descriptor_url: str | None = None

        self.verification_code: str | None = None

        self.user_id: str | None = None
        self.task_pair = None

        self.verification_code = None
        self.last_error = None

    async def async_step_user(self, user_input: FlowInput = None) -> FlowResult:
        """Handle a flow initialized by the user.

        Let user choose from a list of found and unconfigured devices or to
        enter an URL manually.
        """
        LOGGER.debug("async_step_user: user_input: %s", user_input)

        if user_input is not None:
            if not (host := user_input.get(CONF_HOST)):
                # No device chosen, user might want to directly enter an URL
                return await self.async_step_manual()
            # User has chosen a device, ask for confirmation
            discovery = self._discoveries[host]
            await self._async_set_info_from_discovery(
                discovery, abort_if_configured=True, raise_on_progress=False
            )
            return await self.async_step_enter_user_id()

        if not (discoveries := await self._async_get_discoveries()):
            # Nothing found, maybe the user knows an URL to try
            return await self.async_step_manual()

        self._discoveries = {
            discovery.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
            or cast(str, urlparse(discovery.ssdp_location).hostname): discovery
            for discovery in discoveries
        }

        data_schema = vol.Schema(
            {vol.Optional(CONF_HOST): vol.In(self._discoveries.keys())}
        )
        # TODO: Finish form (title,labels etc)
        return self.async_show_form(
            step_id="user", data_schema=data_schema, last_step=False
        )

    async def _async_get_discoveries(self) -> list[ssdp.SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""

        # Get all compatible devices from ssdp's cache
        discoveries = await ssdp.async_get_discovery_info_by_st(self.hass, ST)

        # Filter out devices already configured
        current_unique_ids = {
            entry.unique_id
            for entry in self._async_current_entries(include_ignore=False)
        }
        discoveries = [
            disc for disc in discoveries if disc.ssdp_udn not in current_unique_ids
        ]

        return discoveries

    async def _async_identify_device(self) -> FlowResult:
        assert self.host is not None
        assert self.port is not None

        session = async_get_clientsession(self.hass, verify_ssl=False)
        requester = AiohttpSessionRequester(session, True, 10)
        description_cache = DescriptionCache(requester)

        url = "http://" + self.host + ":" + str(self.port) + "/xml/xctc.xml"
        device_attributes = await description_cache.async_get_description_dict(
            location=url
        )
        self.descriptor_url = url
        self._set_from_upnp(device_attributes)

        await self.async_set_unique_id(self._udn, raise_on_progress=False)

        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_MODEL: self.model_name + "/" + self.model_number,
                CONF_TYPE: "Media Receiver",
                "manufacturer": self.manufacturer,
                CONF_ID: self._udn,
                CONF_UNIQUE_ID: self._udn,
                CONF_URL: self.descriptor_url,
            },
            reload_on_update=False,
        )

        return await self.async_step_enter_user_id()

    async def async_step_manual(self, user_input: FlowInput = None) -> FlowResult:
        """Manual URL entry by the user."""
        LOGGER.debug("async_step_manual: user_input: %s", user_input)

        # Device setup manually, assume we don't get SSDP broadcast notifications
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]

            # self.user_id = user_input[CONF_USERNAME]
            try:
                return await self._async_identify_device()
            except NotImplementedError as err:
                errors["base"] = str(err)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Required(CONF_PORT, default=8081): cv.port,
            }
        )

        # TODO: Finish form (title,labels etc)
        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors, last_step=False
        )

    async def async_step_unignore(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Rediscover previously ignored devices by their unique_id."""
        LOGGER.debug("async_step_unignore: user_input: %s", user_input)
        self._udn = user_input[CONF_UNIQUE_ID]
        assert self._udn
        await self.async_set_unique_id(self._udn)

        # Find a discovery matching the unignored unique_id for a DMR device
        discovery = await ssdp.async_get_discovery_info_by_udn_st(
            self.hass, udn=self._udn, st=ST
        )
        if discovery:
            await self._async_set_info_from_discovery(
                discovery, abort_if_configured=True, raise_on_progress=False
            )
            self.context["title_placeholders"] = {"name": self.friendly_name}

            return await self.async_step_enter_user_id()
        else:
            return self.async_abort(reason="discovery_error")

    def _set_from_upnp(self, device_info: Mapping[str, Any]):
        self._udn = device_info.get(ssdp.ATTR_UPNP_UDN)
        self.friendly_name = device_info.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
        self.model_name = device_info.get(ssdp.ATTR_UPNP_MODEL_NAME)
        self.model_number = device_info.get(ssdp.ATTR_UPNP_MODEL_NUMBER)
        self.manufacturer = device_info.get(ssdp.ATTR_UPNP_MANUFACTURER)

        assert self._udn is not None
        assert self.friendly_name is not None
        assert self.model_name is not None
        assert self.model_number is not None
        assert self.manufacturer is not None

    async def _async_set_info_from_discovery(
        self,
        discovery_info: ssdp.SsdpServiceInfo,
        raise_on_progress: bool = True,
        abort_if_configured: bool = True,
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""

        parsed_location = urlparse(discovery_info.ssdp_location)
        self.host = parsed_location.hostname
        self.port = parsed_location.port
        assert self.host is not None
        assert self.port is not None

        assert discovery_info.ssdp_location is not None
        self.descriptor_url = discovery_info.ssdp_location
        assert self.descriptor_url is not None
        self._set_from_upnp(discovery_info.upnp)

        await self.async_set_unique_id(self._udn, raise_on_progress=raise_on_progress)

        if abort_if_configured:
            self._abort_if_unique_id_configured(
                updates={
                    CONF_HOST: self.host,
                    CONF_PORT: self.port,
                    CONF_MODEL: self.model_name + "/" + self.model_number,
                    CONF_TYPE: "Media Receiver",
                    "manufacturer": self.manufacturer,
                    CONF_ID: self._udn,
                    CONF_UNIQUE_ID: self._udn,
                    CONF_URL: self.descriptor_url,
                },
                reload_on_update=False,
            )

        return await self.async_step_enter_user_id()

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp %s", discovery_info)

        await self._async_set_info_from_discovery(
            discovery_info=discovery_info,
            abort_if_configured=True,
            raise_on_progress=True,
        )

        self.context.update(
            {
                "title_placeholders": {
                    "name": self.friendly_name,
                    "host": self.host,
                    "configuration_url": self.descriptor_url,
                }
            }
        )
        return await self.async_step_enter_user_id()

    async def _async_task_pair(self):
        try:
            _notify_server = await async_get_notification_server(hass=self.hass)
            client = PairingClient(
                host=self.host,
                port=self.port,
                user_id=self.user_id,
                instance_id=await instance_id.async_get(self.hass),
                notify_server=_notify_server,
            )
            # await _notify_server.async_start()

            self.verification_code = await client.async_pair()
            # A task that take some time to complete.
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
            self.last_error = "timeout"
        except Exception as err:
            LOGGER.error("Error during pairing", exc_info=err)
            self.last_error = "unknown"
        finally:
            if client is not None:
                await client.async_close()
                # await _notify_server.async_stop()

            # Continue the flow after show progress when the task is done.
            # To avoid a potential deadlock we create a new task that continues the flow.
            # The task must be completely done so the flow can await the task
            # if needed and get the task result.
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
            )

    async def async_step_finish(self, user_input=None):
        return self.async_create_entry(
            title=self.friendly_name,
            data={
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_MODEL: self.model_name + "/" + self.model_number,
                CONF_TYPE: "Media Receiver",
                "manufacturer": self.manufacturer,
                CONF_ID: self._udn,
                CONF_UNIQUE_ID: self._udn,
                CONF_URL: self.descriptor_url,
                CONF_USER_ID: self.user_id,
                # "verification_code": self.verification_code,
            },
        )

    async def async_step_pairing_failed(self, user_input=None) -> FlowResult:
        return self.async_abort(reason="pairing_timeout")

    async def async_step_pair(self, user_input=None) -> FlowResult:
        if self.last_error is not None:
            return self.async_show_progress_done(next_step_id="pairing_failed")

        if not self.verification_code:
            # start async pairing process
            if not self.task_pair:
                self.task_pair = self.hass.async_create_task(self._async_task_pair())

                # TODO: Finish form (title,labels etc)
            return self.async_show_progress(
                step_id="pair",
                progress_action="wait_for_pairing",
                description_placeholders={"name": self.friendly_name},
            )
        else:
            # verification code is present -> pairing done
            return self.async_show_progress_done(next_step_id="finish")

    async def async_step_enter_user_id(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to enter his user id adding the device."""

        self._abort_if_unique_id_configured()
        self.hass.data.setdefault(DOMAIN, {})

        _errors = {}

        if self.last_error is None and user_input is not None:
            self.user_id = user_input[CONF_USER_ID]

            self.hass.data[DOMAIN][CONF_USER_ID] = self.user_id
            return await self.async_step_pair()

        if self.last_error:
            _errors["base"] = self.last_error
            self.last_error = None

        prefilled_user_id = (
            (user_input or {}).get(CONF_USER_ID, None)  # already entered
            or self.hass.data[DOMAIN].get(DATA_USER_ID, None)  # yaml config (via data)
            or await self._async_find_existing_user_id()  # already configured entries
            or None
        )
        if prefilled_user_id is not None:
            prefilled_user_id = str(prefilled_user_id)

        # TODO: Finish form (title,labels etc)
        return self.async_show_form(
            step_id="enter_user_id",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USER_ID,
                        default=prefilled_user_id,
                    ): str
                }
            ),
            description_placeholders={"name": self.friendly_name},
            errors=_errors,
            last_step=False,
        )

    async def _async_find_existing_user_id(self) -> int | None:
        for entry in self.hass.config_entries.async_entries(domain=DOMAIN):
            if entry.data is not None:
                user_id = entry.data.get(CONF_USER_ID, None)
                if user_id is not None:
                    return user_id
        return None
