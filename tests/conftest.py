"""Fixtures for testing."""
from unittest.mock import patch

import pytest
from async_upnp_client.server import UpnpServer
from async_upnp_client.ssdp_listener import SsdpListener

from custom_components.magentatv.api import NotifyServer


@pytest.fixture(autouse=True)
async def mock_local_ip():
    """Disable Api Notify Server startup."""
    with patch(
        "custom_components.magentatv.api.notify_server.get_local_ip"
    ) as mocked_function:
        mocked_function.return_value = "10.0.0.0"
        yield mocked_function


@pytest.fixture(autouse=True)
async def mock_api_client():
    """Disable Api Notify Server startup."""
    with patch(
        "custom_components.magentatv.media_player.Client", autospec=True, spec_set=True
    ) as mock:
        instance = mock.return_value
        yield instance


@pytest.fixture(autouse=True)
async def mock_notify_server():
    """Disable Api Notify Server startup."""
    with patch(
        "custom_components.magentatv.NotifyServer", autospec=True, spec_set=True
    ):
        yield NotifyServer


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading."""
    yield


@pytest.fixture(autouse=True)
async def silent_ssdp_listener():
    """Patch SsdpListener class, preventing any actual SSDP traffic."""
    with patch("homeassistant.components.ssdp.SsdpListener.async_start"), patch(
        "homeassistant.components.ssdp.SsdpListener.async_stop"
    ), patch("homeassistant.components.ssdp.SsdpListener.async_search"):
        # Fixtures are initialized before patches. When the component is started here,
        # certain functions/methods might not be patched in time.
        yield SsdpListener


@pytest.fixture(autouse=True)
async def disabled_upnp_server():
    """Disable UPnpServer."""
    with patch("homeassistant.components.ssdp.UpnpServer.async_start"), patch(
        "homeassistant.components.ssdp.UpnpServer.async_stop"
    ), patch("homeassistant.components.ssdp._async_find_next_available_port"):
        yield UpnpServer


# @pytest.fixture(autouse=True)
# async def disabled_notify_server():
#     """Disable Api Notify Server startup."""
#     with patch("custom_components.magentatv.api.NotifyServer.async_start"), patch(
#         "custom_components.magentatv.api.NotifyServer.async_stop"
#     ):
#         yield NotifyServer
