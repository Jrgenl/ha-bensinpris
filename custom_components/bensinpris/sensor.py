"""Sensorer for billigste pris i nærheten, i landet og per kjede."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PriceExtremes, provider_name
from .const import (
    CONF_FUEL_TYPES,
    CONF_PROVIDERS,
    DEFAULT_FUEL_TYPES,
    DOMAIN,
    UNIT,
)
from .coordinator import BensinprisConfigEntry, BensinprisCoordinator, BensinprisData

ATTRIBUTION = "Data fra Drivstoffpriser (drivstoffpriser.net), innrapportert av brukere"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BensinprisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    options = {**entry.data, **entry.options}
    fuel_types: list[str] = options.get(CONF_FUEL_TYPES, DEFAULT_FUEL_TYPES)

    entities: list[SensorEntity] = [ActivitySensor(coordinator)]
    for fuel_type in fuel_types:
        entities.append(ExtremesSensor(coordinator, fuel_type, "nearby"))
        entities.append(ExtremesSensor(coordinator, fuel_type, "national"))
        entities.append(CheapestProviderSensor(coordinator, fuel_type))
        for provider in options.get(CONF_PROVIDERS, []):
            entities.append(ProviderSensor(coordinator, fuel_type, provider))
    async_add_entities(entities)


class BensinprisEntity(CoordinatorEntity[BensinprisCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: BensinprisCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Drivstoffpriser",
            configuration_url="https://github.com/Drivstoffpriser",
        )


class _PriceSensor(BensinprisEntity, SensorEntity):
    _attr_native_unit_of_measurement = UNIT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2


class ExtremesSensor(_PriceSensor):
    """Laveste siste pris, i radius (nearby) eller i hele landet (national)."""

    def __init__(
        self, coordinator: BensinprisCoordinator, fuel_type: str, scope: str
    ) -> None:
        key = f"{scope}_{fuel_type.lower()}"
        super().__init__(coordinator, key)
        self.fuel_type = fuel_type
        self.scope = scope
        self._attr_translation_key = key

    def _stats(self) -> PriceExtremes | None:
        data: BensinprisData | None = self.coordinator.data
        if data is None:
            return None
        source = data.nearby if self.scope == "nearby" else data.national
        return source.get(self.fuel_type)

    @property
    def native_value(self) -> float | None:
        stats = self._stats()
        return stats.lowest_price if stats else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._stats()
        attrs: dict[str, Any] = {}
        if self.scope == "nearby":
            attrs["radius_km"] = self.coordinator.radius_km
        if stats is None:
            return attrs
        attrs.update(
            station=stats.lowest_station_name,
            station_id=stats.lowest_station_id,
            highest_price=stats.highest_price,
            highest_station=stats.highest_station_name,
            highest_station_id=stats.highest_station_id,
        )
        if stats.lowest_price is not None and stats.highest_price is not None:
            attrs["spread"] = round(stats.highest_price - stats.lowest_price, 2)
        return attrs


class CheapestProviderSensor(_PriceSensor):
    """Kjeden med lavest snittpris siste døgn (hele landet)."""

    def __init__(self, coordinator: BensinprisCoordinator, fuel_type: str) -> None:
        key = f"cheapest_provider_{fuel_type.lower()}"
        super().__init__(coordinator, key)
        self.fuel_type = fuel_type
        self._attr_translation_key = key

    def _averages(self) -> dict[str, float]:
        data: BensinprisData | None = self.coordinator.data
        if data is None:
            return {}
        return {
            provider: fuels[self.fuel_type]
            for provider, fuels in data.providers.last_24h.items()
            if self.fuel_type in fuels
        }

    @property
    def native_value(self) -> float | None:
        averages = self._averages()
        return min(averages.values()) if averages else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        averages = self._averages()
        if not averages:
            return {}
        ranked = sorted(averages.items(), key=lambda item: item[1])
        return {
            "provider": provider_name(ranked[0][0]),
            "averages": {provider_name(p): price for p, price in ranked},
        }


class ProviderSensor(_PriceSensor):
    """Snittpris for én valgt kjede, siste døgn, med 30-dagers trend."""

    def __init__(
        self, coordinator: BensinprisCoordinator, fuel_type: str, provider: str
    ) -> None:
        super().__init__(
            coordinator, f"provider_{provider.lower()}_{fuel_type.lower()}"
        )
        self.fuel_type = fuel_type
        self.provider = provider
        self._attr_translation_key = f"provider_{fuel_type.lower()}"
        self._attr_translation_placeholders = {"provider": provider_name(provider)}

    @property
    def native_value(self) -> float | None:
        data: BensinprisData | None = self.coordinator.data
        if data is None:
            return None
        return data.providers.last_24h.get(self.provider, {}).get(self.fuel_type)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data: BensinprisData | None = self.coordinator.data
        if data is None:
            return {}
        series = data.providers.last_30d.get(self.provider, {}).get(self.fuel_type, [])
        if not series:
            return {}
        prices = [price for _, price in series]
        return {
            "average_30d": round(sum(prices) / len(prices), 2),
            "min_30d": min(prices),
            "max_30d": max(prices),
            "days_with_data": len(series),
            "last_date": series[-1][0].isoformat(),
        }


class ActivitySensor(BensinprisEntity, SensorEntity):
    """Hvor mange priser som er meldt inn siste døgn. Sier noe om hvor ferske tallene er."""

    _attr_translation_key = "reports_24h"
    _attr_native_unit_of_measurement = "registreringer"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: BensinprisCoordinator) -> None:
        super().__init__(coordinator, "reports_24h")

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data
        return data.activity.last_24_hours if data else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "last_7_days": data.activity.last_7_days,
            "last_30_days": data.activity.last_30_days,
        }
