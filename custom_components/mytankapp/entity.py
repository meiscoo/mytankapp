"""Base entity for MyTankApp."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyTankAppConfigEntry
from .const import CONF_LEVEL_OFFSET, DEFAULT_LEVEL_OFFSET, DOMAIN
from .coordinator import MyTankAppCoordinator
from .models import MyTankAppTank


class MyTankAppEntity(CoordinatorEntity[MyTankAppCoordinator]):
    """Base class for entities belonging to one tank."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: MyTankAppConfigEntry,
        device_id: str,
        key: str,
    ) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"

    @property
    def tank(self) -> MyTankAppTank | None:
        """Return the current tank model."""
        return self.coordinator.data.get(self._device_id)

    @property
    def level_offset(self) -> float:
        """Return configured percentage points to subtract from reported level."""
        return float(
            self.coordinator.config_entry.options.get(
                CONF_LEVEL_OFFSET, DEFAULT_LEVEL_OFFSET
            )
        )

    def calibrated_level(self, tank: MyTankAppTank) -> float | None:
        """Return the corrected tank level percentage."""
        if tank.level is None:
            return None
        return min(100.0, max(0.0, tank.level - self.level_offset))

    def calibrated_inventory(self, tank: MyTankAppTank) -> float | None:
        """Return corrected inventory without affecting consumption deltas."""
        if tank.inventory is None:
            return None
        if tank.tank_size is None or tank.tank_size <= 0:
            return tank.inventory
        corrected = tank.inventory - (tank.tank_size * self.level_offset / 100)
        return min(tank.tank_size, max(0.0, corrected))

    def calibrated_ullage(self, tank: MyTankAppTank) -> float | None:
        """Return corrected empty volume."""
        inventory = self.calibrated_inventory(tank)
        if inventory is None:
            return None
        if tank.tank_size is None or tank.tank_size <= 0:
            return tank.ullage
        return max(0.0, tank.tank_size - inventory)

    @property
    def available(self) -> bool:
        """Return whether the coordinator and tank are available."""
        return super().available and self.tank is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Describe the physical tank as a Home Assistant device."""
        tank = self.tank
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            manufacturer="Anova",
            model=(tank.fuel_type if tank and tank.fuel_type else "Tank monitor"),
            name=(tank.display_name if tank else f"Tank {self._device_id[-4:]}"),
            configuration_url="https://www.mytankapp.com/main",
        )

