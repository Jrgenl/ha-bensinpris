"""Koordinator som henter alle åpne endepunkter i én oppdatering."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    Activity,
    BensinprisClient,
    BensinprisError,
    PriceExtremes,
    ProviderPrices,
)
from .const import (
    CONF_BASE_URL,
    CONF_LOCATION,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    scan_interval,
)

_LOGGER = logging.getLogger(__name__)

type BensinprisConfigEntry = ConfigEntry[BensinprisCoordinator]


@dataclass(slots=True)
class BensinprisData:
    nearby: dict[str, PriceExtremes]
    national: dict[str, PriceExtremes]
    activity: Activity
    providers: ProviderPrices


class BensinprisCoordinator(DataUpdateCoordinator[BensinprisData]):
    config_entry: BensinprisConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BensinprisConfigEntry) -> None:
        options = {**entry.data, **entry.options}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=scan_interval(
                float(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN))
            ),
        )
        self.client = BensinprisClient(
            async_get_clientsession(hass), entry.data[CONF_BASE_URL]
        )
        location = options[CONF_LOCATION]
        self.latitude: float = location["latitude"]
        self.longitude: float = location["longitude"]
        self.radius_km = float(options.get(CONF_RADIUS, DEFAULT_RADIUS_KM))

    async def _async_update_data(self) -> BensinprisData:
        try:
            nearby, latest, providers = await asyncio.gather(
                self.client.async_nearest(
                    self.latitude, self.longitude, self.radius_km
                ),
                self.client.async_latest(),
                self.client.async_provider_prices(),
            )
        except BensinprisError as err:
            raise UpdateFailed(str(err)) from err
        return BensinprisData(
            nearby=nearby,
            national=latest.all_stations,
            activity=latest.activity,
            providers=providers,
        )
