# Bensinpris for Home Assistant

Viser drivstoffpriser i Norge fra det dugnadsbaserte prosjektet
[Drivstoffpriser](https://github.com/Drivstoffpriser). Integrasjonen bruker
bare backendens åpne statistikk-endepunkter, så den krever verken konto eller
API-nøkkel.

> Prisene er meldt inn av brukere og kan være gamle. Sensoren
> «Innmeldte priser siste døgn» sier noe om hvor aktivt det er.

## Sensorer

For hver valgt drivstofftype (bensin 95, bensin 98, diesel):

| Sensor | Verdi | Attributter |
|---|---|---|
| Billigste … i nærheten | Laveste siste pris innenfor radius | `station`, `station_id`, `highest_price`, `highest_station`, `spread`, `radius_km` |
| Billigste … i Norge | Laveste siste pris i hele landet | Som over |
| Billigste kjede … (24 t) | Laveste kjedesnitt siste døgn | `provider`, `averages` (alle kjeder, billigst først) |
| *Kjede* … (snitt 24 t) | Snitt for en kjede du velger under Innstillinger | `average_30d`, `min_30d`, `max_30d`, `days_with_data`, `last_date` |

I tillegg: **Innmeldte priser siste døgn** (diagnostikk), med antall for 7 og
30 dager som attributter.

## Installasjon

1. HACS → Integrasjoner → ⋮ → *Egendefinerte repoer* → legg til
   `https://github.com/Jrgenl/ha-bensinpris` som *Integrasjon*.
2. Installer **Bensinpris** og start Home Assistant på nytt.
3. Innstillinger → Enheter og tjenester → Legg til integrasjon → **Bensinpris**.

### Adressen til backend

Standard er `https://api.drivstoffpriser.net`, som er adressen web-appen på
[web.drivstoffpriser.net](https://web.drivstoffpriser.net/) bruker. Feltet kan
endres ved oppsett hvis prosjektet flytter API-et.

## Endepunkter som brukes

Alle er åpne (se `app/statistics/routers.py` i
[Drivstoffpriser/backend](https://github.com/Drivstoffpriser/backend)):

| Endepunkt | Brukes til |
|---|---|
| `GET /statistics/nearest?lat=&lng=&distance=` | Billigste og dyreste innenfor radius |
| `GET /statistics/latest` | Billigste og dyreste i Norge, og antall innmeldinger |
| `GET /statistics/provider-prices` | Snitt per kjede, siste døgn og 30 dager |

Én oppdatering er tre kall. Standard intervall er 30 minutter (minimum 10).
Backend tillater 10 kall per 10 sekunder.

## Begrensninger

- «Billigste» er blant stasjonenes *siste* innmeldte pris, uansett alder.
  Backend oppgir ikke tidspunkt i statistikken.
- Bare bensin 95, bensin 98 og diesel. Backend har ikke HVO100.
- Kjedesnitt gjelder hele landet, ikke bare radiusen din.

## Utvikling

```bash
# api.py alene (uten Home Assistant)
python -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest

# Alt, mot Home Assistant (Python 3.13+)
pip install -r requirements_test.txt pytest-homeassistant-custom-component
pytest
```

## Lisens

Koden er MIT-lisensiert. Dataene tilhører Drivstoffpriser-prosjektet og
bidragsyterne der.
