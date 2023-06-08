"""Adds config flow for Blueprint."""
from __future__ import annotations

import asyncio
from typing import Any, cast
from collections.abc import Mapping
from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_UNIQUE_ID,
    CONF_ID,
    CONF_MODEL,
    CONF_PORT,
    CONF_TYPE,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import instance_id, selector

from .api import PairingClient
from .const import DOMAIN, LOGGER

FlowInput = Mapping[str, Any] | None
ST = "urn:schemas-upnp-org:device:MediaRenderer:1"


class MagentaTvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MagentaTv."""

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
            await self._async_set_info_from_discovery(discovery)
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
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def _async_get_discoveries(self) -> list[ssdp.SsdpServiceInfo]:
        """Get list of unconfigured DLNA devices discovered by SSDP."""
        LOGGER.debug("_get_discoveries")

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

    async def async_step_manual(self, user_input: FlowInput = None) -> FlowResult:
        """Manual URL entry by the user."""
        LOGGER.debug("async_step_manual: user_input: %s", user_input)

        # Device setup manually, assume we don't get SSDP broadcast notifications
        errors = {}
        if user_input is not None:
            self.host = user_input[CONF_HOST]
            self.port = user_input[CONF_PORT]
            # try:
            errors["base"] = "Not Implemented"  # TODO Implement setup by host + port
            # except ConnectError as err:
            #    errors["base"] = err.args[0]
            # else:
            #    return self._create_entry()

        data_schema = vol.Schema({CONF_HOST: str, CONF_PORT: int})

        # TODO: Finish form (title,labels etc)
        return self.async_show_form(
            step_id="manual", data_schema=data_schema, errors=errors
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
                discovery, abort_if_configured=False
            )
            self.context["title_placeholders"] = {"name": self.friendly_name}

            return await self.async_step_enter_user_id()
        else:
            return self.async_abort(reason="discovery_error")

    async def _async_set_info_from_discovery(
        self,
        discovery_info: ssdp.SsdpServiceInfo,
        abort_if_configured: bool = True,
    ) -> None:
        """Set information required for a config entry from the SSDP discovery."""
        self._udn = discovery_info.upnp.get(ssdp.ATTR_UPNP_UDN)
        self.friendly_name = discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
        self.model_name = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)
        self.model_number = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NUMBER)
        self.manufacturer = discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER)

        assert discovery_info.ssdp_location is not None
        self.descriptor_url = discovery_info.ssdp_location

        parsed_location = urlparse(discovery_info.ssdp_location)
        self.host = parsed_location.hostname
        self.port = parsed_location.port

        assert self._udn is not None
        assert self.friendly_name is not None
        assert self.model_name is not None
        assert self.model_number is not None
        assert self.host is not None
        assert self.port is not None

        await self.async_set_unique_id(self._udn, raise_on_progress=abort_if_configured)

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
            discovery_info=discovery_info, abort_if_configured=True
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
            client = PairingClient(
                host=self.host,
                port=self.port,
                user_id=self.user_id,
                instance_id=await instance_id.async_get(self.hass),
            )
            await client.async_start()
            self.verification_code = await client.async_pair()
            # A task that take some time to complete.
        except asyncio.exceptions.TimeoutError:
            self.last_error = "timeout"
        finally:
            await client.async_stop()

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
                "user_id": self.user_id,
                "verification_code": self.verification_code,
            },
        )

    async def async_step_pair(self, user_input=None) -> FlowResult:
        if not self.verification_code:
            # start async pairing process
            if self.task_pair:
                return self.async_show_progress_done(next_step_id="pair")
            else:
                self.task_pair = self.hass.async_create_task(self._async_task_pair())

                # TODO: Finish form (title,labels etc)
                return self.async_show_progress(
                    step_id="pair", progress_action="pairing"
                )
        else:
            # verification code is present -> pairing done
            return self.async_show_progress_done(next_step_id="finish")

    async def async_step_enter_user_id(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to enter his user id adding the device."""

        self._abort_if_unique_id_configured()

        _errors = {}

        if self.last_error is None and user_input is not None:
            self.user_id = user_input[CONF_USERNAME]
            self.hass.data[DOMAIN][CONF_USERNAME] = self.user_id
            return await self.async_step_pair()

        if self.last_error:
            _errors["base"] = self.last_error
            self.last_error = None

        prefilled_user_id = (
            (user_input or {}).get(CONF_USERNAME, None)
            or await self._async_find_existing_user_id()
            or None
        )

        # TODO: Finish form (title,labels etc)
        return self.async_show_form(
            step_id="enter_user_id",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=prefilled_user_id,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                }
            ),
            errors=_errors,
        )

    async def _async_find_existing_user_id(self) -> str | None:
        for entry in self.hass.config_entries.async_entries(domain=DOMAIN):
            if entry.data is not None:
                user_id = entry.data.get("user_id", None)
                if user_id is not None:
                    return user_id
        return None
