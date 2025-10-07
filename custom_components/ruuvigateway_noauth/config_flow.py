"""Config flow for Ruuvi Gateway integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from . import DOMAIN
from .api import CannotConnect, InvalidAuth, async_get_gateway_history_data
from .schemata import CONFIG_SCHEMA, get_config_schema_with_default_host

_LOGGER = logging.getLogger(__name__)


class RuuviConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ruuvi Gateway."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self.config_schema = CONFIG_SCHEMA

    async def _async_validate(
        self,
        user_input: dict[str, Any],
    ) -> tuple[ConfigFlowResult | None, dict[str, str]]:
        """Validate configuration (either discovered or user input)."""
        errors: dict[str, str] = {}

        try:
            token_input = user_input.get(CONF_TOKEN)
            if isinstance(token_input, str):
                token = token_input.strip()
                if token == "":
                    token = None
            else:
                token = None
            resp = await async_get_gateway_history_data(
                async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                bearer_token=token,
            )
            await self.async_set_unique_id(
                format_mac(resp.gw_mac), raise_on_progress=False
            )
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: user_input[CONF_HOST]}
            )
            info = {"title": f"Ruuvi Gateway {resp.gw_mac_suffix}"}
            entry_data: dict[str, Any] = {CONF_HOST: user_input[CONF_HOST]}
            if token:
                entry_data[CONF_TOKEN] = token
            return (
                self.async_create_entry(title=info["title"], data=entry_data),
                errors,
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return (None, errors)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle requesting or validating user input."""
        if user_input is not None:
            result, errors = await self._async_validate(user_input)
        else:
            result, errors = None, {}
        if result is not None:
            return result
        return self.async_show_form(
            step_id="user",
            data_schema=self.config_schema,
            errors=(errors or None),
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Prepare configuration for a DHCP discovered Ruuvi Gateway."""
        await self.async_set_unique_id(format_mac(discovery_info.macaddress))
        self._abort_if_unique_id_configured(updates={CONF_HOST: discovery_info.ip})
        self.config_schema = get_config_schema_with_default_host(host=discovery_info.ip)
        return await self.async_step_user()
