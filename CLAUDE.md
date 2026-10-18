# Car cost comparison web app

Project context for Claude Code. All amounts are SEK; 1 mil = 10 km. Respond in the language the user writes in (Swedish or English).

## Purpose

Compare the monthly cost of cars (owned, leased, bought) so someone can decide whether to keep their current car or switch. Costs are entered as items per car; the page adds them up per month, per mil and per year.

## Web app (car comparison)

Start: double-click `start.bat` (runs `python app.py`, opens http://localhost:8765). Standard library only, no installs.
Files: `app.py` (server), `web/` (page), `data/cars.json` (the car database).

### Local and hosted

The same `web/` page runs two ways. Locally, `app.py` serves it and saves every change to `data/cars.json`
(`GET`/`PUT /api/data`). On GitHub Pages there is no server: the page finds that `/api/data` does not exist, reads the published
`data/cars.json` read-only, and keeps a visitor's changes only in that browser tab (`sessionStorage`), under a banner with a
"Reset to published data" button. The workflow `.github/workflows/pages.yml` builds the site (`web/` plus `data/cars.json`) on every
push to `main`. To update the published data, change `data/cars.json` and push.

### cars.json

```json
{
  "settings": {"mil_per_year": 1750, "return_rate_pct": 7.0,
               "prices": {"diesel": 23.19, "petrol": 18.74, "el_home": 1.80, "el_public": 4.50},
               "prices_note": "where the prices come from"},
  "cars": [{"id": "yaris-cross", "name": "...", "kind": "lease|own|buy", "notes": "...",
            "items": [{"id": "rent", "name": "...", "type": "fixed", "value": 3528, "enabled": true, "note": "..."}]}]
}
```

Every cost is an item, converted to kr/month by the page. Item types and their fields:

| type | fields | kr/month |
|---|---|---|
| `fixed` | `value` (kr/month) | value |
| `per_year` | `value` (kr/year) | value / 12 |
| `one_time` | `value` (kr), `months` | value / months (e.g. setup fee over the contract) |
| `fuel` | `energy` (diesel, petrol, el_home, el_public), `consumption` (per mil: l or kWh), `share_pct` | consumption × mil_per_year × price × share / 12 |
| `capital` | `amount` (kr tied up), `rate_pct` (own interest per year; if missing, `settings.return_rate_pct`), `months` (default 36) | (amount × (1 + rate)^(months/12) − amount) / months: the return the money would have earned, compounded |
| `depreciation` | `value_now` (kr), `rate_pct` (% lost per year), `months` | (value_now − value_now × (1 − rate)^(months/12)) / months. A used car keeps losing the same share of its value, not the same kronor |
| `excess_mileage` | `rate` (kr/mil), `limit_per_year` (mil) | max(0, mil_per_year − limit) × rate / 12 |

Optional `group` on any item makes items either/or within a car: ticking one unticks the others in the same
group (used for V40 repairs all-period vs last-12-month average, and fuel at current price vs historical).

A car with items in group `repairs` (the V40) also gets a "repairs & service it can afford" box: for each other car, how
many kr/year of repairs the car can have and still cost no more, given the other ticked items (live, not stored).

Optional `"hidden": true` on an item hides it in the app and leaves it out of the total (the item and its
`enabled` state stay in the file; a card shows "N hidden costs" with a link to show them).

Fuel/electricity always uses the current prices in `settings`, not historical spend. An EV that charges partly
in public gets two `fuel` items (e.g. el_home 80 % + el_public 20 %).

### New-car template

`settings.new_car_template` is a list of items (same format, without `id`) that the app's "+ Add car" button copies
into every new car, so only the numbers need filling in. It is based on the Skoda Kamiq: fuel (petrol), lease fee,
service agreement, insurance, setup fee, tax, winter wheels (8 000 kr) and inspection (529 kr), with the car-specific
prices at 0 (except the setup fee, 590 kr). Edit the list in `cars.json` to change what new cars start with.

### Size and equipment (`specs`)

Each car can have a `specs` object, shown in the app's "Size & equipment" table (all cells editable):
`power_hp`, `power_kw`, `gearbox` (text), `gears` (number; null for electric/CVT), `range_km` (WLTP electric
range, electric cars only; say which battery version in `source`), `boot_l` (luggage up to the luggage cover, seats up), `boot_roof_l` (up to the roof, seats up),
`boot_max_l` (seats folded), `length_mm`, `width_mm`, `height_mm`, and the equipment answers `rear_camera`,
`parking_front`, `parking_rear`, `adaptive_cruise` (each `yes`, `no`, `option` = extra cost, or `unknown`).
`checked` says how well the specs are backed up: `official` (manufacturer spec sheet), `dealer` (dealer listing for
that exact trim) or `unverified`; `source` says where each figure comes from. Luggage is measured differently by each
maker (to the cover or to the roof), so say which in `source`. Never guess equipment: use `unknown` and say so.
The user compares the cheapest trim of each car unless told otherwise (Audi A3 = 35 TFSI Proline 110 kW S tronic).

### Adding a car from a dealer quote

When the user gives a quote, add a car to `data/cars.json`: one item per cost line (rent, insurance, winter
wheels, invoice fee as `fixed`; setup fee as `one_time` over the contract months; vehicle tax as `per_year`;
fuel as `fuel` with real-world consumption, typically WLTP + 10-20 %; excess mileage as `excess_mileage`).
Inspection (besiktning): count
the whole inspections that actually fall inside the contract and add them as `one_time` (value = 529 × number of
inspections, months = contract length). A new car's first inspection is due 36 months after first registration, so
a new 36-month lease usually has none (value 0; check the registration date). A car inspected every second year
has 1 or 2 inside a 36-month contract, depending on the dates.
Every lease car also gets a `winter_tyres` item (`one_time`, 8 000 kr, months = contract length: a used set of 4 winter wheels,
rims included since a new car has none, the user's assumption) so it is compared fairly with an owned car, which has its own winter-tyre item.
Put the source and anything unverified in `note`. Fill in `specs` too (see above). Show the user a summary of the car before writing it.
Keep the JSON valid and the format above; the open page reloads the file within a few seconds.

### Rows generated from bank data

The default car (id `v40`) has rows marked `"auto": true`. They are generated from bank transactions by a private pipeline in
another repository: do not recompute them here and do not invent values for them. In the app they carry an "auto" badge;
editing such a row's value sets `"auto": false` (badge "edited") and the generator then keeps the user's value and only
refreshes `auto_value`, which the app's "use data value" button restores.

## Principle: compare only what differs

Costs that are equal in every scenario can be left out of the comparison (garage/parking at home, congestion tax, washing, fines). Congestion tax (trängselskatt) is the same for EVs, no exemption in Stockholm/Gothenburg. Costs that differ must be included: depreciation + capital cost vs. lease fee, fuel/charging, service, tyres, insurance, vehicle tax, inspection, mileage/wear fees at lease return.

Fuel is only excluded if the cars are equivalent. Diesel vs hybrid vs EV differ, so include it.

## Swedish vehicle tax rules used

- Petrol/hybrid new car (first 3 years, malus): 360 + 107 kr x (CO2 - 75) for 75-125 g/km, and 132 kr/g above 125 g/km. After 3 years: base tax + CO2 part (roughly 380-620 kr/year for a Yaris Cross hybrid, source: ownership-cost site, not verified).
- Diesel adds fuel surcharge 13.52 x CO2 + 250 kr.
- Check exact figures with the registration number at Transportstyrelsen. EV rules and PHEV changes from 2026 not fully verified.
