"""Config flow for MyTankApp."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import MyTankAppAuthError, MyTankAppClient, MyTankAppConnectionError, MyTankAppError
from .const import (
    CONF_LOW_LEVEL,
    CONF_SCAN_INTERVAL,
    DEFAULT_LOW_LEVEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class MyTankAppConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a MyTankApp config flow."""

    VERSION = 3

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect and validate account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            try:
                client = await self._async_validate(username, user_input[CONF_PASSWORD])
                account = await client.async_get_account()
                await client.async_get_tanks()
            except MyTankAppAuthError:
                errors["base"] = "invalid_auth"
            except MyTankAppConnectionError:
                errors["base"] = "cannot_connect"
            except MyTankAppError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(username.casefold())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=account.display_name or username,
                    data={CONF_USERNAME: username, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Start reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Validate a replacement password."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._async_validate(
                    entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except MyTankAppAuthError:
                errors["base"] = "invalid_auth"
            except MyTankAppConnectionError:
                errors["base"] = "cannot_connect"
            except MyTankAppError:
                errors["base"] = "unknown"
            else:
                return self.async_update_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
        )

    async def _async_validate(self, username: str, password: str) -> MyTankAppClient:
        client = MyTankAppClient(
            async_get_clientsession(self.hass),
            username,
            password,
            retry_failed_login=False,
        )
        await client.async_login()
        return client

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MyTankAppOptionsFlow:
        """Return the options flow."""
        return MyTankAppOptionsFlow()


class MyTankAppOptionsFlow(config_entries.OptionsFlow):
    """Configure polling and low-level settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Required(
                        CONF_LOW_LEVEL,
                        default=self.config_entry.options.get(
                            CONF_LOW_LEVEL, DEFAULT_LOW_LEVEL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=99)),
                }
            ),
        )
