"""Tester for api.py. Kjøres uten Home Assistant."""

import re
from datetime import date

import aiohttp
import pytest
from aioresponses import aioresponses
from api import (
    BensinprisClient,
    BensinprisError,
    BensinprisRateLimitError,
    normalize_base_url,
    parse_provider_prices,
    provider_name,
    to_price,
)

from .conftest import BASE_URL, LATEST, NEAREST, PROVIDER_PRICES

NEAREST_URL = re.compile(rf"^{re.escape(BASE_URL)}/statistics/nearest\?.*$")


def test_helpers():
    assert to_price("17.00") == 17.0
    assert to_price(None) is None
    assert to_price("") is None
    assert to_price("abc") is None
    assert to_price("0") is None
    assert normalize_base_url(" https://x.no/ ") == "https://x.no"
    with pytest.raises(ValueError):
        normalize_base_url("x.no")
    assert provider_name("UNO_X") == "Uno-X"
    assert provider_name("NY_KJEDE") == "Ny Kjede"


async def test_nearest_sends_meters_and_parses():
    async with aiohttp.ClientSession() as session:
        client = BensinprisClient(session, BASE_URL + "/")
        with aioresponses() as mock:
            mock.get(NEAREST_URL, payload=NEAREST)
            result = await client.async_nearest(60.885, 10.94, 12.5)
            (_, url), calls = next(iter(mock.requests.items()))
    assert url.query["distance"] == "12500"
    assert url.query["lat"] == "60.885"
    diesel = result["DIESEL"]
    assert diesel.lowest_price == 17.0
    assert diesel.lowest_station_name == "Uno-X Moelv"
    assert diesel.highest_price == 25.0


async def test_nearest_empty():
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(NEAREST_URL, payload={"nearbyStations": {}})
            assert (
                await BensinprisClient(session, BASE_URL).async_nearest(60, 10, 5) == {}
            )


async def test_latest_and_health():
    async with aiohttp.ClientSession() as session:
        client = BensinprisClient(session, BASE_URL)
        with aioresponses() as mock:
            mock.get(f"{BASE_URL}/statistics/latest", payload=LATEST)
            mock.get(f"{BASE_URL}/health", payload={"status": "ok"})
            latest = await client.async_latest()
            assert await client.async_health()
    assert latest.all_stations["DIESEL"].lowest_price == 16.49
    assert latest.activity.last_24_hours == 42
    assert latest.activity.last_30_days == 1204


def test_provider_prices():
    result = parse_provider_prices(PROVIDER_PRICES)
    assert result.last_24h["UNO_X"]["DIESEL"] == 17.5
    series = result.last_30d["CIRCLE_K"]["DIESEL"]
    # Sortert eldste først selv om backend sender i annen rekkefølge.
    assert series == [(date(2026, 9, 27), 18.5), (date(2026, 9, 28), 19.5)]
    assert parse_provider_prices({"last30d": {}, "last24h": {}}).last_24h == {}


@pytest.mark.parametrize(
    ("status", "error"),
    [(500, BensinprisError), (401, BensinprisError), (429, BensinprisRateLimitError)],
)
async def test_http_errors(status, error):
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(f"{BASE_URL}/statistics/latest", status=status)
            with pytest.raises(error):
                await BensinprisClient(session, BASE_URL).async_latest()


async def test_unexpected_payload():
    async with aiohttp.ClientSession() as session:
        with aioresponses() as mock:
            mock.get(f"{BASE_URL}/statistics/latest", payload={"detail": "Not Found"})
            with pytest.raises(BensinprisError):
                await BensinprisClient(session, BASE_URL).async_latest()
