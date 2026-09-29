"""Klient for de åpne statistikk-endepunktene i Drivstoffpriser-backend.

Modulen er uavhengig av Home Assistant og bruker bare aiohttp.

Endepunktene krever ikke innlogging (se app/statistics/routers.py i
github.com/Drivstoffpriser/backend):

- GET /statistics/nearest?lat=&lng=&distance=   billigste og dyreste i radius
- GET /statistics/latest                        det samme for hele landet
- GET /statistics/provider-prices               snitt per kjede
- GET /health                                   helsesjekk

Backend begrenser til 10 kall per 10 sekunder per klient. Priser kommer som
strenger ("17.00") fordi backend bruker Decimal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

import aiohttp

USER_AGENT = "ha-bensinpris (+https://github.com/Jrgenl/ha-bensinpris)"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

GASOLINE_95 = "GASOLINE_95"
GASOLINE_98 = "GASOLINE_98"
DIESEL = "DIESEL"
FUEL_TYPES = (GASOLINE_95, GASOLINE_98, DIESEL)

# Visningsnavn for kjedene backend kjenner (ProviderType i backend).
PROVIDER_NAMES = {
    "AUTOMAT_1": "Automat1",
    "BEST": "Best",
    "BUNKER_OIL": "Bunker Oil",
    "CIRCLE_K": "Circle K",
    "DRIV": "Driv",
    "ESSO": "Esso",
    "HALTBAKK_EXPRESS": "Haltbakk Express",
    "OLJELEVERANDØREN": "Oljeleverandøren",
    "ST1": "St1",
    "TANKEN": "Tanken",
    "TRONDER_OIL": "Trønder Oil",
    "UNO_X": "Uno-X",
    "YX": "YX",
    "YX_TRUCK": "YX Truck",
}


class BensinprisError(Exception):
    """Backend svarte ikke, eller svarte med noe vi ikke forstår."""


class BensinprisRateLimitError(BensinprisError):
    """Backend svarte 429 (for mange kall)."""


@dataclass(slots=True)
class PriceExtremes:
    """Billigste og dyreste siste pris for én drivstofftype."""

    fuel_type: str
    lowest_price: float | None
    lowest_station_id: str | None
    lowest_station_name: str | None
    highest_price: float | None
    highest_station_id: str | None
    highest_station_name: str | None


@dataclass(slots=True)
class Activity:
    """Antall innmeldte priser i hele landet."""

    last_24_hours: int
    last_7_days: int
    last_30_days: int


@dataclass(slots=True)
class ProviderPrices:
    """Snittpris per kjede og drivstofftype."""

    #: kjede -> drivstofftype -> snitt siste døgn
    last_24h: dict[str, dict[str, float]] = field(default_factory=dict)
    #: kjede -> drivstofftype -> [(dato, snitt)], eldste først
    last_30d: dict[str, dict[str, list[tuple[date, float]]]] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class LatestStatistics:
    all_stations: dict[str, PriceExtremes]
    activity: Activity


class BensinprisClient:
    """Tynn klient mot backend."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self.base_url = normalize_base_url(base_url)

    async def async_health(self) -> bool:
        data = await self._get("/health")
        return isinstance(data, dict) and data.get("status") == "ok"

    async def async_nearest(
        self, latitude: float, longitude: float, radius_km: float
    ) -> dict[str, PriceExtremes]:
        data = await self._get(
            "/statistics/nearest",
            params={
                "lat": str(latitude),
                "lng": str(longitude),
                # Backend tar meter.
                "distance": str(int(radius_km * 1000)),
            },
        )
        return parse_extremes(_require(data, "nearbyStations"))

    async def async_latest(self) -> LatestStatistics:
        data = await self._get("/statistics/latest")
        return LatestStatistics(
            all_stations=parse_extremes(_require(data, "allStations")),
            activity=parse_activity(_require(data, "activity")),
        )

    async def async_provider_prices(self) -> ProviderPrices:
        return parse_provider_prices(await self._get("/statistics/provider-prices"))

    async def _get(self, path: str, params: dict[str, str] | None = None) -> object:
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        try:
            async with self._session.get(
                url, params=params, headers=headers, timeout=REQUEST_TIMEOUT
            ) as resp:
                if resp.status == 429:
                    raise BensinprisRateLimitError(f"{path}: for mange kall (429)")
                if resp.status >= 400:
                    raise BensinprisError(f"{path} svarte {resp.status}")
                return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise BensinprisError(f"Feil ved henting av {path}: {err}") from err


def normalize_base_url(url: str) -> str:
    """Fjern mellomrom og avsluttende skråstrek, og krev http(s)."""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("Adressen må starte med http:// eller https://")
    return url


def _require(data: object, key: str) -> dict:
    if not isinstance(data, dict) or not isinstance(data.get(key), dict):
        raise BensinprisError(f"Uventet svar: mangler {key}")
    return data[key]


def to_price(value: object) -> float | None:
    """Tolk pris fra streng eller tall. Tomme og ugyldige verdier blir None."""
    if value is None or value == "":
        return None
    try:
        price = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return price if math.isfinite(price) and price > 0 else None


def parse_extremes(raw: dict) -> dict[str, PriceExtremes]:
    result: dict[str, PriceExtremes] = {}
    for fuel_type, stats in raw.items():
        if not isinstance(stats, dict):
            continue
        result[fuel_type] = PriceExtremes(
            fuel_type=fuel_type,
            lowest_price=to_price(stats.get("lowestPrice")),
            lowest_station_id=stats.get("lowestStationId"),
            lowest_station_name=stats.get("lowestStationName"),
            highest_price=to_price(stats.get("highestPrice")),
            highest_station_id=stats.get("highestStationId"),
            highest_station_name=stats.get("highestStationName"),
        )
    return result


def parse_activity(raw: dict) -> Activity:
    return Activity(
        last_24_hours=int(raw.get("last24Hours", 0)),
        last_7_days=int(raw.get("last7Days", 0)),
        last_30_days=int(raw.get("last30Days", 0)),
    )


def parse_provider_prices(data: object) -> ProviderPrices:
    if not isinstance(data, dict):
        raise BensinprisError("Uventet svar fra /statistics/provider-prices")
    result = ProviderPrices()

    for provider, fuels in (data.get("last24h") or {}).items():
        for fuel_type, value in (fuels or {}).items():
            price = to_price(value)
            if price is not None:
                result.last_24h.setdefault(provider, {})[fuel_type] = price

    for provider, fuels in (data.get("last30d") or {}).items():
        for fuel_type, days in (fuels or {}).items():
            series = []
            for day in days or []:
                price = to_price(day.get("averagePrice"))
                try:
                    day_date = date.fromisoformat(day.get("date", ""))
                except (TypeError, ValueError):
                    continue
                if price is not None:
                    series.append((day_date, price))
            if series:
                series.sort()
                result.last_30d.setdefault(provider, {})[fuel_type] = series
    return result


def provider_name(provider: str) -> str:
    return PROVIDER_NAMES.get(provider, provider.replace("_", " ").title())
