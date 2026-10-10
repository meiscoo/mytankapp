"""Binary sensor entities for MyTankApp."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyTankAppConfigEntry
from .const import CONF_LOW_LEVEL, DEFAULT_LOW_LEVEL
from .entity import MyTankAppEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MyTankAppConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add low-level binary sensors."""
    coordinator = entry.runtime_data.coordinator
    known_device_ids: set[str] = set()

    @callback
    def add_new_entities() -> None:
        new_device_ids = coordinator.data.keys() - known_device_ids
        if not new_device_ids:
            return
        async_add_entities(
            MyTankAppLowLevelBinarySensor(entry, device_id)
            for device_id in new_device_ids
        )
        known_device_ids.update(new_device_ids)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))


class MyTankAppLowLevelBinarySensor(MyTankAppEntity, BinarySensorEntity):
    """Indicate when a tank is below the configured threshold."""

    entity_description = BinarySensorEntityDescription(
        key="low_level",
        translation_key="low_level",
        device_class=BinarySensorDeviceClass.PROBLEM,
    )

    def __init__(self, entry: MyTankAppConfigEntry, device_id: str) -> None:
        super().__init__(entry, device_id, self.entity_description.key)
        self._threshold = entry.options.get(CONF_LOW_LEVEL, DEFAULT_LOW_LEVEL)

    @property
    def is_on(self) -> bool | None:
        """Return true when the tank level is below the threshold."""
        tank = self.tank
        if tank is None:
            return None
        level = self.calibrated_level(tank)
        if level is None:
            return None
        return level < self._threshold

    @property
    def extra_state_attributes(self) -> dict[str, float]:
        """Expose the active threshold and calibration for diagnostics."""
        return {
            "threshold": self._threshold,
            "level_offset": self.level_offset,
        }
