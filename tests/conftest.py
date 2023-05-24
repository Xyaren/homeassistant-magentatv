"""Global fixtures for Roborock integration."""
from unittest.mock import patch

import pytest

from .mock_data import PROP


# This fixture enables loading custom integrations in all tests.
# Remove to enable selective use of this fixture
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integration loading."""
    yield


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture():
    """Skip calls to the API."""
    with  patch(
        "roborock.cloud_api.mqtt"
    ), patch(
            "roborock.cloud_api.RoborockMqttClient.async_connect"
    ), patch(
        "roborock.cloud_api.RoborockMqttClient.async_disconnect", return_value=PROP
    ), patch(
        "roborock.cloud_api.RoborockMqttClient.send_command"
    ), patch(
        "roborock.cloud_api.RoborockMqttClient.get_prop", return_value=PROP
    ), patch(
        "roborock.local_api.RoborockLocalClient.async_connect"
    ), patch(
        "roborock.local_api.RoborockLocalClient.async_disconnect"
    ), patch(
        "roborock.local_api.RoborockLocalClient.send_command"
    ), patch(
        "roborock.local_api.RoborockLocalClient.get_prop", return_value=PROP
    ):
        yield
