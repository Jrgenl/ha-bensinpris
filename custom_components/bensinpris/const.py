"""Konstanter for Bensinpris."""

from __future__ import annotations

from datetime import timedelta

from .api import DIESEL, FUEL_TYPES, GASOLINE_95

DOMAIN = "bensinpris"

CONF_BASE_URL = "base_url"
CONF_LOCATION = "location"
CONF_RADIUS = "radius"
CONF_FUEL_TYPES = "fuel_types"
CONF_PROVIDERS = "providers"
CONF_SCAN_INTERVAL = "scan_interval_minutes"

# Fra nettverkstrafikken til web.drivstoffpriser.net. Kan overstyres ved oppsett.
DEFAULT_BASE_URL = "https://api.drivstoffpriser.net"
DEFAULT_RADIUS_KM = 10
DEFAULT_FUEL_TYPES = [GASOLINE_95, DIESEL]
DEFAULT_SCAN_INTERVAL_MIN = 30
# Én oppdatering er tre kall. Backend tillater 10 kall per 10 sekunder, men vi
# vil ikke belaste et gratis dugnadsprosjekt mer enn nødvendig.
MIN_SCAN_INTERVAL_MIN = 10

ALL_FUEL_TYPES = list(FUEL_TYPES)
UNIT = "NOK/L"


def scan_interval(minutes: float) -> timedelta:
    return timedelta(minutes=max(MIN_SCAN_INTERVAL_MIN, minutes))
