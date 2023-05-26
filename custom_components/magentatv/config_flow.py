"""Adds config flow for Blueprint."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlparse
from uu import Error
import voluptuous as vol
from asyncio import sleep
from homeassistant import config_entries

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_HOST,
    CONF_PORT,
    CONF_MODEL,
    CONF_TYPE,
    CONF_ID,
    CONF_URL,
)
from homeassistant.helpers import selector, instance_id
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.components import ssdp
from homeassistant.data_entry_flow import FlowResult

from .api import (
    PairingClient,
)
from .const import DOMAIN, LOGGER


class MagentaTvFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for MagentaTv."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.friendly_name: str | None = None
        self.model_name: str | None = None
        self.model_number: str | None = None
        self.manufacturer: str | None = None
        self.udn: str | None = None
        self.host: str | None = None
        self.port: str | None = None
        self.descriptor_url: str | None = None

        self.verification_code: str | None = None

        self.user_id: str | None = None
        self.task_pair = None

        self.verification_code = None

    async def async_step_ssdp(self, discovery_info: ssdp.SsdpServiceInfo) -> FlowResult:
        """Handle ssdp discovery flow."""

        LOGGER.debug("async_step_ssdp %s", discovery_info)

        assert discovery_info.ssdp_location is not None

        self.udn = discovery_info.upnp.get(ssdp.ATTR_UPNP_UDN)
        self.friendly_name = discovery_info.upnp.get(ssdp.ATTR_UPNP_FRIENDLY_NAME)
        self.model_name = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NAME)
        self.model_number = discovery_info.upnp.get(ssdp.ATTR_UPNP_MODEL_NUMBER)
        self.manufacturer = discovery_info.upnp.get(ssdp.ATTR_UPNP_MANUFACTURER)
        self.descriptor_url = discovery_info.ssdp_location
        parsed_location = urlparse(discovery_info.ssdp_location)
        self.host = parsed_location.hostname
        self.port = parsed_location.port

        assert self.udn is not None
        assert self.friendly_name is not None
        assert self.model_name is not None
        assert self.model_number is not None
        assert self.host is not None
        assert self.port is not None

        await self.async_set_unique_id(self.udn)
        self._abort_if_unique_id_configured(
            {
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_MODEL: self.model_name + "/" + self.model_number,
                CONF_TYPE: "Media Receiver",
                "manufacturer": self.manufacturer,
                CONF_ID: self.udn,
                CONF_URL: self.descriptor_url,
            }
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
        return await self.async_step_confirm()

    async def _async_do_task(self):
        client = PairingClient(
            host=self.host,
            port=self.port,
            user_id=self.user_id,
            instance_id=await instance_id.async_get(self.hass),
        )

        try:
            self.verification_code = (
                await client.async_get_verification_code()
            )  # A task that take some time to complete.
        except Exception as ex:
            LOGGER.error("Error Pairing", exc_info=ex)

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
                CONF_ID: self.udn,
                CONF_URL: self.descriptor_url,
                "user_id": self.user_id,
                "verification_code": self.verification_code,
            },
        )

    async def async_step_pair(self, user_input=None) -> FlowResult:
        # if not self.task_pair:
        #    self.task_pair = self.hass.async_create_task(self._async_do_task())
        if not self.verification_code:
            self.task_pair = self.hass.async_create_task(self._async_do_task())
            return self.async_show_progress(step_id="pair", progress_action="pairing")
        else:
            return self.async_show_progress_done(next_step_id="finish")

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Allow the user to confirm adding the device."""

        _errors = {}

        if user_input is not None:
            self.user_id = user_input[CONF_USERNAME]
            return await self.async_step_pair()

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT
                        ),
                    ),
                }
            ),
            errors=_errors,
        )
