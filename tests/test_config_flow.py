"""Test Roborock config flow."""
from unittest.mock import patch

import homeassistant.helpers.config_validation as cv
import pytest
import voluptuous_serialize
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.magentatv.const import CAMERA, \
    CONF_BOTTOM, \
    CONF_ENTRY_CODE, \
    CONF_ENTRY_USERNAME, \
    CONF_INCLUDE_IGNORED_OBSTACLES, \
    CONF_INCLUDE_NOGO, \
    CONF_INCLUDE_SHARED, \
    CONF_LEFT, \
    CONF_MAP_TRANSFORM, \
    CONF_RIGHT, \
    CONF_ROTATE, \
    CONF_SCALE, \
    CONF_TOP, \
    CONF_TRIM, \
    DOMAIN, \
    VACUUM
from .mock_data import HOME_DATA, MOCK_CONFIG, USER_DATA, USER_EMAIL


@pytest.mark.asyncio
async def test_successful_config_flow(hass: HomeAssistant, bypass_api_fixture):
    """Test a successful config flow."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        # Initialize a config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONF_ENTRY_CODE}
        )
        # Check that user form requesting username (email) is shown
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "email"

        # Provide email address to config flow
        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.request_code",
                return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_ENTRY_USERNAME: USER_EMAIL}
            )
            # Check that user form requesting a code is shown
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "code"

        # Provide code from email to config flow
        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.code_login",
                return_value=USER_DATA,
        ), patch(
            "roborock.api.RoborockApiClient.get_home_data",
            return_value=HOME_DATA,
        ), patch(
            "custom_components.roborock.get_local_devices_info",
            side_effect=lambda: {device.duid: {"ip": "127.0.0.1"} for device in HOME_DATA.devices}
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )
        # Check config flow completed and a new entry is created
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == USER_EMAIL
        assert result["data"] == MOCK_CONFIG
        assert result["result"]


@pytest.mark.asyncio
async def test_invalid_code(hass: HomeAssistant, bypass_api_fixture):
    """Test invalid verification code."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        """Test a failed config flow due to incorrect code."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONF_ENTRY_CODE}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "email"

        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.request_code",
                return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"username": USER_EMAIL}
            )

            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "code"
        # Raise exception for invalid code
        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.code_login",
                side_effect=Exception("invalid code"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_ENTRY_CODE: "123456"}
            )
        # Check the user form is presented with the error
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "no_device"}


@pytest.mark.asyncio
async def test_no_devices(hass: HomeAssistant, bypass_api_fixture):
    """Test no device found."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        """Test a failed config flow due to no devices on Roborock account."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONF_ENTRY_CODE}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "email"

        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.request_code",
                return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"username": USER_EMAIL}
            )

            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "code"
        # Return None from code_login (no devices)
        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.code_login",
                return_value=None,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"code": "123456"}
            )
        # Check the user form is presented with the error
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "no_device"}


@pytest.mark.asyncio
async def test_unknown_user(hass: HomeAssistant, bypass_api_fixture):
    """Test a failed config flow due to credential validation failure."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": CONF_ENTRY_CODE}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "email"

        with patch(
                "custom_components.roborock.config_flow.RoborockApiClient.request_code",
                side_effect=Exception("unknown user"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {"username": "USER_EMAIL"}
            )
        # Check the user form is presented with the error
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "auth"}


@pytest.mark.asyncio
async def test_camera_options_flow(hass: HomeAssistant, bypass_api_fixture):
    """Test options flow."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        # Create a new MockConfigEntry and add to HASS (we're bypassing config
        # flow entirely)
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        entry.add_to_hass(hass)
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Initialize an options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        # Verify that the first options step is a user form
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": CAMERA}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "camera"

        # Check if its serializable
        serialized_schemas = voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
        for serialized_schema in serialized_schemas:
            assert (serialized_schema["name"], serialized_schema["default"]) in {
                f"{CONF_MAP_TRANSFORM}:{CONF_SCALE}": 1,
                f"{CONF_MAP_TRANSFORM}:{CONF_ROTATE}": "0",
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_LEFT}": 0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_RIGHT}": 0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_TOP}": 0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_BOTTOM}": 0,
                CONF_INCLUDE_IGNORED_OBSTACLES: True,
                CONF_INCLUDE_NOGO: True
            }.items()

        # Change map transformation options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                f"{CONF_MAP_TRANSFORM}:{CONF_SCALE}": 1.2,
                f"{CONF_MAP_TRANSFORM}:{CONF_ROTATE}": "90",
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_LEFT}": 5.0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_RIGHT}": 5.0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_TOP}": 5.0,
                f"{CONF_MAP_TRANSFORM}:{CONF_TRIM}:{CONF_BOTTOM}": 5.0,
            },
        )

        # Verify that the flow finishes
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        # Verify the options were set
        assert dict(entry.options) == {
            CAMERA: {
                CONF_MAP_TRANSFORM: {
                    CONF_SCALE: 1.2,
                    CONF_ROTATE: 90,
                    CONF_TRIM: {CONF_LEFT: 5, CONF_RIGHT: 5, CONF_TOP: 5, CONF_BOTTOM: 5},
                },
                CONF_INCLUDE_IGNORED_OBSTACLES: True,
                CONF_INCLUDE_NOGO: True
            }
        }


@pytest.mark.asyncio
async def test_vacuum_options_flow(hass: HomeAssistant, bypass_api_fixture):
    """Test options flow."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        # Create a new MockConfigEntry and add to HASS (we're bypassing config
        # flow entirely)
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        entry.add_to_hass(hass)
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Initialize an options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        # Verify that the first options step is a user form
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": VACUUM}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "vacuum"
        # Check if its serializable
        serialized_schemas = voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
        for serialized_schema in serialized_schemas:
            assert (serialized_schema["name"], serialized_schema["default"]) in {
                CONF_INCLUDE_SHARED: True,
            }.items()

        # Change map transformation options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_SHARED: False
            },
        )

        # Verify that the flow finishes
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        # Verify the options were set
        assert dict(entry.options) == {
            VACUUM: {
                CONF_INCLUDE_SHARED: False
            }
        }


@pytest.mark.asyncio
async def test_vacuum_options_flow_persistence(hass: HomeAssistant, bypass_api_fixture):
    """Test options flow."""
    with patch(
            "custom_components.roborock.async_setup_entry", return_value=True
    ):
        # Create a new MockConfigEntry and add to HASS (we're bypassing config
        # flow entirely)
        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        entry.add_to_hass(hass)
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Initialize an options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        # Verify that the first options step is a user form
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": VACUUM}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "vacuum"
        # Check if its serializable
        serialized_schemas = voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
        for serialized_schema in serialized_schemas:
            assert (serialized_schema["name"], serialized_schema["default"]) in {
                CONF_INCLUDE_SHARED: True,
            }.items()

        # Change map transformation options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_INCLUDE_SHARED: False
            },
        )

        # Verify that the flow finishes
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        # Verify the options were set
        assert dict(entry.options) == {
            VACUUM: {
                CONF_INCLUDE_SHARED: False
            }
        }

        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        # Initialize an options flow
        result = await hass.config_entries.options.async_init(entry.entry_id)
        # Verify that the first options step is a user form
        assert result["type"] == data_entry_flow.RESULT_TYPE_MENU
        assert result["step_id"] == "user"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": VACUUM}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "vacuum"
        # Check if its serializable
        serialized_schemas = voluptuous_serialize.convert(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
        for serialized_schema in serialized_schemas:
            assert (serialized_schema["name"], serialized_schema["default"]) in {
                CONF_INCLUDE_SHARED: False,
            }.items()
