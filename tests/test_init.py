"""Tester mot Home Assistant (krever pytest-homeassistant-custom-component)."""

from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.bensinpris.api import (  # noqa: E402
    BensinprisError,
    LatestStatistics,
    parse_activity,
    parse_extremes,
    parse_provider_prices,
)
from custom_components.bensinpris.const import DOMAIN  # noqa: E402

from .conftest import BASE_URL, LATEST, NEAREST, PROVIDER_PRICES  # noqa: E402

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

CLIENT = "custom_components.bensinpris.api.BensinprisClient"
USER_INPUT = {
    "base_url": BASE_URL + "/",
    "location": {"latitude": 60.885, "longitude": 10.94},
    "radius": 10,
    "fuel_types": ["GASOLINE_95", "DIESEL"],
}


@pytest.fixture
def mock_client():
    with (
        patch(
            f"{CLIENT}.async_nearest",
            AsyncMock(return_value=parse_extremes(NEAREST["nearbyStations"])),
        ) as nearest,
        patch(
            f"{CLIENT}.async_latest",
            AsyncMock(
                return_value=LatestStatistics(
                    parse_extremes(LATEST["allStations"]),
                    parse_activity(LATEST["activity"]),
                )
            ),
        ),
        patch(
            f"{CLIENT}.async_provider_prices",
            AsyncMock(return_value=parse_provider_prices(PROVIDER_PRICES)),
        ),
    ):
        yield nearest


async def test_config_flow(hass, mock_client):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with patch(
        "custom_components.bensinpris.async_setup_entry", AsyncMock(return_value=True)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["base_url"] == BASE_URL  # skråstrek fjernet


async def test_config_flow_errors(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, "base_url": "api.example.no"}
    )
    assert result["errors"] == {"base_url": "invalid_url"}
    with patch(
        f"{CLIENT}.async_nearest", AsyncMock(side_effect=BensinprisError("nede"))
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_sensors(hass, mock_client):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**USER_INPUT, "base_url": BASE_URL},
        options={"providers": ["UNO_X"]},
        title="Bensinpris",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    states = {s.entity_id: s for s in hass.states.async_all("sensor")}
    # Aktivitet + 2 typer x (nærheten, Norge, billigste kjede, Uno-X)
    assert len(states) == 9, sorted(states)

    nearby = states["sensor.bensinpris_cheapest_diesel_nearby"]
    assert float(nearby.state) == 17.0
    assert nearby.attributes["station"] == "Uno-X Moelv"
    assert nearby.attributes["spread"] == 8.0
    assert nearby.attributes["radius_km"] == 10

    national_95 = states["sensor.bensinpris_cheapest_petrol_95_in_norway"]
    assert national_95.state == "unknown"  # ingen 95-data i landsstatistikken

    chain = states["sensor.bensinpris_cheapest_chain_diesel_24_h"]
    assert float(chain.state) == 17.5
    assert chain.attributes["provider"] == "Uno-X"
    assert chain.attributes["averages"] == {"Uno-X": 17.5, "Circle K": 19.5}

    uno_x = states["sensor.bensinpris_uno_x_diesel_24_h_average"]
    assert float(uno_x.state) == 17.5
    assert uno_x.attributes["days_with_data"] == 1

    assert states["sensor.bensinpris_price_reports_last_24_h"].state == "42"
    mock_client.assert_awaited_with(60.885, 10.94, 10.0)
