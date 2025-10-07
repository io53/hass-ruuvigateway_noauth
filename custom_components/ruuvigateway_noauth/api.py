"""API helpers for the Ruuvi Gateway integration."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout
from bluetooth_data_tools import BLEGAPAdvertisement, parse_advertisement_data

from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error raised when the gateway cannot be reached."""


class InvalidAuth(HomeAssistantError):
    """Error raised when authentication with the gateway fails."""


@dataclasses.dataclass(slots=True)
class TagData:
    """Tag observation reported by the gateway."""

    mac: str
    rssi: int
    timestamp: int
    data: bytes
    age_seconds: int | None = None

    def parse_announcement(self) -> BLEGAPAdvertisement:
        """Decode the advertisement payload for the tag."""
        return parse_advertisement_data([self.data])

    @property
    def datetime(self) -> dt.datetime:
        """Return the UTC datetime for the timestamp."""
        return dt.datetime.utcfromtimestamp(self.timestamp)

    @classmethod
    def from_gateway_history_json_tag(
        cls,
        mac: str,
        payload: dict[str, Any],
        response_timestamp: int | None,
    ) -> "TagData":
        """Create a tag from the gateway history payload."""
        tag_timestamp = int(payload["timestamp"])
        age_seconds = (
            (response_timestamp - tag_timestamp) if response_timestamp else None
        )
        return cls(
            mac=mac,
            rssi=int(payload["rssi"]),
            timestamp=tag_timestamp,
            data=bytes.fromhex(payload["data"]),
            age_seconds=age_seconds,
        )


@dataclasses.dataclass(slots=True)
class HistoryResponse:
    """History response payload from the gateway."""

    timestamp: int
    gw_mac: str
    tags: list[TagData]
    coordinates: str = ""

    @property
    def datetime(self) -> dt.datetime:
        """Return the UTC datetime for the response timestamp."""
        return dt.datetime.utcfromtimestamp(self.timestamp)

    @property
    def gw_mac_suffix(self) -> str:
        """Return the suffix shown to the user."""
        return self.gw_mac[-5:].upper()

    @classmethod
    def from_gateway_history_json(cls, data: dict[str, Any]) -> "HistoryResponse":
        """Create a history response from JSON."""
        payload = data["data"]
        response_timestamp = int(payload["timestamp"])
        tags = [
            TagData.from_gateway_history_json_tag(
                mac=mac,
                payload=tag_payload,
                response_timestamp=response_timestamp,
            )
            for mac, tag_payload in payload.get("tags", {}).items()
        ]
        return cls(
            timestamp=response_timestamp,
            gw_mac=payload["gw_mac"],
            tags=tags,
            coordinates=payload.get("coordinates", ""),
        )


async def async_get_gateway_history_data(
    session: ClientSession,
    *,
    host: str,
    bearer_token: str | None = None,
    timeout: float | None = None,
) -> HistoryResponse:
    """Fetch history data from the gateway."""
    request_timeout = ClientTimeout(total=timeout) if timeout is not None else None
    try:
        headers: dict[str, str] | None = None
        if bearer_token:
            headers = {"Authorization": f"Bearer {bearer_token}"}
        async with session.get(
            f"http://{host}/history",
            headers=headers,
            timeout=request_timeout,
        ) as response:
            if response.status == 401:
                raise InvalidAuth
            if response.status != 200:
                raise CannotConnect(
                    f"Unexpected response from gateway: HTTP {response.status}"
                )
            data = await response.json(content_type=None)
    except InvalidAuth:
        raise
    except asyncio.TimeoutError as err:
        raise CannotConnect("Timeout communicating with gateway") from err
    except ClientError as err:
        raise CannotConnect("Error communicating with gateway") from err
    except (KeyError, ValueError, TypeError) as err:
        raise CannotConnect("Invalid response from gateway") from err

    return HistoryResponse.from_gateway_history_json(data)


__all__ = [
    "CannotConnect",
    "HistoryResponse",
    "InvalidAuth",
    "TagData",
    "async_get_gateway_history_data",
]
