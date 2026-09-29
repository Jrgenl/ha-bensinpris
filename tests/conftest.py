"""Felles testdata. Formatene er hentet fra testene i Drivstoffpriser/backend."""

import sys
from pathlib import Path

import pytest

# Gjør `api` importerbar uten Home Assistant (api.py er selvstendig).
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components" / "bensinpris"))

BASE_URL = "https://api.example.no"

NEAREST = {
    "nearbyStations": {
        "DIESEL": {
            "highestPrice": "25.00",
            "highestStationId": "11111111-1111-1111-1111-111111111111",
            "highestStationName": "Circle K Brumunddal",
            "lowestPrice": "17.00",
            "lowestStationId": "22222222-2222-2222-2222-222222222222",
            "lowestStationName": "Uno-X Moelv",
        },
        "GASOLINE_95": {
            "highestPrice": "22.49",
            "highestStationId": "11111111-1111-1111-1111-111111111111",
            "highestStationName": "Circle K Brumunddal",
            "lowestPrice": "20.99",
            "lowestStationId": "22222222-2222-2222-2222-222222222222",
            "lowestStationName": "Uno-X Moelv",
        },
    }
}

LATEST = {
    "allStations": {
        "DIESEL": {
            "highestPrice": "26.90",
            "highestStationId": "33333333-3333-3333-3333-333333333333",
            "highestStationName": "YX Hammerfest",
            "lowestPrice": "16.49",
            "lowestStationId": "44444444-4444-4444-4444-444444444444",
            "lowestStationName": "Automat1 Hokksund",
        }
    },
    "activity": {"last24Hours": 42, "last7Days": 310, "last30Days": 1204},
}

PROVIDER_PRICES = {
    "last30d": {
        "CIRCLE_K": {
            "DIESEL": [
                {"date": "2026-09-28", "averagePrice": "19.50"},
                {"date": "2026-09-27", "averagePrice": "18.50"},
            ]
        },
        "UNO_X": {"DIESEL": [{"date": "2026-09-28", "averagePrice": "17.50"}]},
    },
    "last24h": {
        "CIRCLE_K": {"DIESEL": "19.50", "GASOLINE_95": "21.90"},
        "UNO_X": {"DIESEL": "17.50"},
    },
}


@pytest.fixture
def api_payloads():
    return {"nearest": NEAREST, "latest": LATEST, "provider_prices": PROVIDER_PRICES}
