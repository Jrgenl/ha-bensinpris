"""Oppsett via brukergrensesnittet."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    PROVIDER_NAMES,
    BensinprisClient,
    BensinprisError,
    normalize_base_url,
)
from .const import (
    ALL_FUEL_TYPES,
    CONF_BASE_URL,
    CONF_FUEL_TYPES,
    CONF_LOCATION,
    CONF_PROVIDERS,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    DEFAULT_FUEL_TYPES,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL_MIN,
    DOMAIN,
    MIN_SCAN_INTERVAL_MIN,
)

FUEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=ALL_FUEL_TYPES,
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key=CONF_FUEL_TYPES,
    )
)
RADIUS_SELECTOR = NumberSelector(
    NumberSelectorConfig(
        min=1, max=100, step=1, unit_of_measurement="km", mode=NumberSelectorMode.BOX
    )
)


class BensinprisConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input[CONF_BASE_URL] = normalize_base_url(
                    user_input[CONF_BASE_URL]
                )
            except ValueError:
                errors[CONF_BASE_URL] = "invalid_url"
            else:
                errors = await self._async_validate(user_input)
            if not errors:
                location = user_input[CONF_LOCATION]
                await self.async_set_unique_id(
                    f"{user_input[CONF_BASE_URL]}"
                    f"_{location['latitude']:.3f}_{location['longitude']:.3f}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Bensinpris ({user_input[CONF_RADIUS]:g} km)",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_BASE_URL): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.URL)
                ),
                vol.Required(
                    CONF_LOCATION,
                    default={
                        "latitude": self.hass.config.latitude,
                        "longitude": self.hass.config.longitude,
                    },
                ): LocationSelector(),
                vol.Required(CONF_RADIUS, default=DEFAULT_RADIUS_KM): RADIUS_SELECTOR,
                vol.Required(
                    CONF_FUEL_TYPES, default=DEFAULT_FUEL_TYPES
                ): FUEL_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> dict[str, str]:
        client = BensinprisClient(
            async_get_clientsession(self.hass), user_input[CONF_BASE_URL]
        )
        location = user_input[CONF_LOCATION]
        try:
            # /statistics/nearest bekrefter både adresse og svarformat.
            await client.async_nearest(
                location["latitude"], location["longitude"], user_input[CONF_RADIUS]
            )
        except BensinprisError:
            return {"base": "cannot_connect"}
        return {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return BensinprisOptionsFlow()


class BensinprisOptionsFlow(OptionsFlow):
    """Radius, drivstofftyper, intervall og kjeder med egne sensorer."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        providers = set(PROVIDER_NAMES)
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is not None and coordinator.data is not None:
            # Ta med kjeder backend har lagt til etter at listen vår ble skrevet.
            providers |= set(coordinator.data.providers.last_24h)
        provider_options = [
            SelectOptionDict(value=p, label=PROVIDER_NAMES.get(p, p))
            for p in sorted(providers, key=lambda p: PROVIDER_NAMES.get(p, p))
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RADIUS, default=current.get(CONF_RADIUS, DEFAULT_RADIUS_KM)
                ): RADIUS_SELECTOR,
                vol.Required(
                    CONF_FUEL_TYPES,
                    default=current.get(CONF_FUEL_TYPES, DEFAULT_FUEL_TYPES),
                ): FUEL_SELECTOR,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MIN),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_MIN,
                        max=24 * 60,
                        step=5,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_PROVIDERS, default=current.get(CONF_PROVIDERS, [])
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=provider_options,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
