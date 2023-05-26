"""BlueprintEntity class."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import CONF_MODEL, CONF_URL, CONF_ID

from .const import ATTRIBUTION, DOMAIN
from .coordinator import BlueprintDataUpdateCoordinator


class IntegrationBlueprintEntity(CoordinatorEntity):
    """BlueprintEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: BlueprintDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, self.unique_id),
                ("udn", coordinator.config_entry.data.get(CONF_ID)),
            },
            name=coordinator.config_entry.title,
            model=coordinator.config_entry.data.get(CONF_MODEL),
            configuration_url=coordinator.config_entry.data.get(CONF_URL),
            manufacturer=coordinator.config_entry.data.get("manufacturer"),
        )
