"""MyTankApp integration setup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MyTankAppAuthError, MyTankAppClient, MyTankAppError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, PLATFORMS
from .coordinator import MyTankAppCoordinator
from .models import MyTankAppAccount


@dataclass(slots=True)
class MyTankAppRuntimeData:
    """Runtime objects stored on a config entry."""

    client: MyTankAppClient
    account: MyTankAppAccount
    coordinator: MyTankAppCoordinator


MyTankAppConfigEntry: TypeAlias = ConfigEntry[MyTankAppRuntimeData]


async def async_migrate_entry(
    hass: HomeAssistant, entry: MyTankAppConfigEntry
) -> bool:
    """Migrate existing entries to six-hour polling."""
    if entry.version == 1:
        options = dict(entry.options)
        options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        hass.config_entries.async_update_entry(entry, options=options, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MyTankAppConfigEntry) -> bool:
    """Set up MyTankApp from a config entry."""
    client = MyTankAppClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await client.async_login()
        account = await client.async_get_account()
    except MyTankAppAuthError as err:
        raise ConfigEntryAuthFailed from err
    except MyTankAppError as err:
        raise ConfigEntryNotReady(str(err)) from err
    coordinator = MyTankAppCoordinator(hass, entry, client, account)
    await coordinator.async_load_consumption()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MyTankAppRuntimeData(client, account, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyTankAppConfigEntry) -> bool:
    """Unload a MyTankApp config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: MyTankAppConfigEntry) -> None:
    """Reload after options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
