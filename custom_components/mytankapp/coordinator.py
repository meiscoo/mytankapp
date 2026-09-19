"""Polling coordinator for MyTankApp."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .api import MyTankAppAuthError, MyTankAppClient, MyTankAppError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGIN_RETRY_INTERVAL,
)
from .models import MyTankAppAccount, MyTankAppConsumption, MyTankAppTank

_LOGGER = logging.getLogger(__name__)


class MyTankAppCoordinator(DataUpdateCoordinator[dict[str, MyTankAppTank]]):
    """Fetch all tank data in one request."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: MyTankAppClient,
        account: MyTankAppAccount,
    ) -> None:
        self.client = client
        self.account = account
        self.last_successful_sync: datetime | None = None
        self.consumption: dict[str, MyTankAppConsumption] = {}
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, 1, f"{DOMAIN}.{entry.entry_id}.consumption"
        )
        self._normal_update_interval = timedelta(
            minutes=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._normal_update_interval,
            # A successful sync timestamp must be published even when the tank
            # payload is identical to the previous poll.
            always_update=True,
        )

    async def async_load_consumption(self) -> None:
        """Load cumulative consumption before the first API refresh."""
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        self.consumption = {
            device_id: MyTankAppConsumption.from_dict(value)
            for device_id, value in stored.items()
            if isinstance(device_id, str) and isinstance(value, dict)
        }

    async def _async_update_data(self) -> dict[str, MyTankAppTank]:
        try:
            tanks = await self.client.async_get_tanks()
        except MyTankAppAuthError as err:
            raise ConfigEntryAuthFailed from err
        except MyTankAppError as err:
            self.update_interval = timedelta(minutes=LOGIN_RETRY_INTERVAL)
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._normal_update_interval

        changed = False
        refresh_flow_for: list[str] = []
        for device_id, tank in tanks.items():
            if not tank.is_propane:
                continue
            consumption = self.consumption.setdefault(
                device_id, MyTankAppConsumption()
            )
            if (
                consumption.flow_rate_per_hour is None
                or (
                    tank.last_reported is not None
                    and (
                        consumption.flow_calculated_at is None
                        or tank.last_reported > consumption.flow_calculated_at
                    )
                )
            ):
                refresh_flow_for.append(device_id)
            changed |= consumption.update(
                tank, uses_liters=self.account.uses_liters
            )

        for device_id in refresh_flow_for:
            try:
                readings = await self.client.async_get_recent_readings(device_id)
            except MyTankAppAuthError as err:
                raise ConfigEntryAuthFailed from err
            except MyTankAppError as err:
                _LOGGER.warning(
                    "Unable to update flow rate for tank ending in %s: %s",
                    device_id[-4:],
                    err,
                )
                continue
            changed |= self.consumption[device_id].update_flow_rate(
                readings, tank_size=tanks[device_id].tank_size
            )

        if changed:
            await self._store.async_save(
                {
                    device_id: consumption.as_dict()
                    for device_id, consumption in self.consumption.items()
                }
            )
        self.last_successful_sync = datetime.now(timezone.utc)
        return tanks
