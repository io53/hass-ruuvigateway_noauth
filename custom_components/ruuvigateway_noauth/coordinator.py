"""Update coordinator for Ruuvi Gateway."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import TagData, async_get_gateway_history_data
from .const import SCAN_INTERVAL


class RuuviGatewayUpdateCoordinator(DataUpdateCoordinator[list[TagData]]):
    """Polls the gateway for data and returns a list of TagData objects that have changed since the last poll."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        logger: logging.Logger,
    ) -> None:
        """Initialize the coordinator using the given configuration (host, token)."""
        super().__init__(
            hass,
            logger,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.host = config_entry.data[CONF_HOST]
        self.token = config_entry.data.get(CONF_TOKEN) or None
        self.last_tag_datas: dict[str, TagData] = {}

    async def _async_update_data(self) -> list[TagData]:
        changed_tag_datas: list[TagData] = []
        data = await async_get_gateway_history_data(
            async_get_clientsession(self.hass),
            host=self.host,
            bearer_token=self.token,
        )
        for tag in data.tags:
            if (
                tag.mac not in self.last_tag_datas
                or self.last_tag_datas[tag.mac].data != tag.data
            ):
                changed_tag_datas.append(tag)
                self.last_tag_datas[tag.mac] = tag
        return changed_tag_datas
