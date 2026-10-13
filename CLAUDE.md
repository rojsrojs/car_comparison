# Car cost comparison: keep Volvo V40 vs. lease/buy

Project context for Claude Code. The user is Swedish (conversation was in Swedish). All amounts are SEK. Respond in the language the user writes in.

## Goal

Decide whether to keep the current car (Volvo V40 diesel) or switch to a leasing car or a 3-4 year old used car. Build:

1. A bookkeeping/analysis of actual car costs from CarPay statements (categorized by fuel, workshop, tyres, parking, etc.).
2. A fair cost comparison (per month and per mil, where 1 mil = 10 km) between the alternatives, ideally as an interactive calculator (HTML) and/or an Excel file where assumptions can be changed.

## Principle: compare only what differs

Costs that are equal in every scenario can be left out of the comparison (garage/parking at home, congestion tax, washing, fines). Congestion tax (trängselskatt) is the same for EVs, no exemption in Stockholm/Gothenburg. Costs that differ must be included: depreciation + capital cost vs. lease fee, fuel/charging, service, tyres, insurance, vehicle tax, inspection, mileage/wear fees at lease return.

Fuel is only excluded if the cars are equivalent. Diesel vs hybrid vs EV differ, so include it.

## Current car: Volvo V40 (2018, diesel)

- Bought April 2024 (~30 months ago). Mileage now ~16 800 mil. Timing belt replaced at 7 500 mil, not expected to need replacing within the next years (check service book).
- Total cost **6 300 kr/month**, average since April 2024, covering everything: parking, fuel, repairs, depreciation, insurance, tax, congestion tax, etc.
- Parking + congestion tax is ~500 kr/month, so the comparable figure is **~5 800 kr/month**.
- ~130 000 kr is tied up in the car. If invested in an index fund at an assumed 5-7 % per year, the opportunity cost is ~540-760 kr/month. Comparable figure including capital cost: **~6 340-6 560 kr/month**.
- Expensive workshop visits this year: springs, dust boots (damasker), injector. A slightly damaged damasker from the inspection is still pending. The 6 300 average already includes these.
- Usage: max 2 000 mil/year allowed in the lease; actual driving ~1 700-1 800 mil/year.
- Housing: rental apartment, garage probably without charging possibility (worth asking the landlord).

## Data source: CarPay

- Everything is paid with the CarPay card. Issuer is Ziklo Bank (formerly Volvofinans Bank). App login via Mobile BankID.
- No CSV export confirmed. Ideas, in order: look for web login / transaction export, download statement PDFs, copy the transaction list or "Copy response" from the browser Network tab (JSON), screenshots from the app, or ask Ziklo customer service (031-83 89 30).
- Some costs (some inspections, parking, vehicle tax, congestion tax) were paid from another account. Not needed for the comparison as long as they are equal across alternatives.
- Planned pipeline: extract transactions to CSV, categorize (fuel, workshop, tyres, parking, wash, ...), sum per month/category. Compute diesel cost per mil from fuel transactions (needed to compare against hybrid/EV).

## Alternatives evaluated

### Lease: Toyota Yaris Cross 1.5 Hybrid 130 Active (actual quote)

- Rent 3 528 + insurance (Toyota Bilförsäkring) 304 + winter wheels 16" steel 335 = **4 167 kr/month**.
- 36 months, 2 000 mil/year, service included, excess mileage 8 kr/mil.
- Setup fee 695 kr, invoice fee 59 kr/month. Vehicle tax and fuel are extra.
- WLTP: 4.4 l/100 km and 100 g CO2/km. Automatic (e-CVT).
- Estimated **~5 590 kr/month** total (see calculation below).
- Active trim reportedly has adaptive cruise, reversing camera, parking sensors. Blind spot (BLIS) probably requires the safety package. Not verified.

### Lease: Volvo EX30 Long Range Plus

- 5 741 kr/month including insurance and winter wheels. Charging is extra: assumed ~2 kWh/mil (~3 500 kWh/year), home/work charging ~450-600 kr/month, public ~1 400-1 800 kr/month (all assumptions, check prices).
- Roughly 6 200-7 500 kr/month depending on where charging is possible. Unknown whether the quote is for 2 000 mil and whether tyre change/storage is included.

### Lease: Nissan Qashqai MHEV 158 hp (automatic)

- Ads at 3 395-4 000 kr/month, but for 1 000 mil/year. 2 000 mil will cost more.
- ~145 g CO2/km gives malus tax ~8 350 kr/year (~700 kr/month). Estimated total ~6 500 kr/month. No saving over V40, larger than needed.

### Buying used (3-4 years, petrol/hybrid)

- Used-ad price ranges (asking prices, not verified recently): Golf 2022-23 ~210-260k, Corolla Hybrid 2022 ~240k (check not ex-taxi), Yaris Cross 2022-23 ~210-265k, Volvo XC40 mild hybrid ~270-360k.
- Would require ~80-230k on top of what the V40 sells for (~130k). Include interest/opportunity cost.
- Volvo no longer sells pure diesel/petrol (only mild hybrid/PHEV/EV). Corolla Hybrid cannot be plugged in (self-charging hybrid).

## Cost calculation for Yaris Cross lease (current estimate)

| Item | kr/month |
|---|---|
| Quote (rent + insurance + winter wheels) | 4 167 |
| Invoice fee | 59 |
| Setup fee 695 / 36 | 19 |
| Fuel: 0.44 l/mil x 1 750 mil x 17 kr/l / 12 | ~1 090 |
| Vehicle tax, malus years: (360 + 107 x (100-75)) / 12 | ~253 |
| **Total** | **~5 590** |

Compare: V40 ~5 800 (without capital cost) or ~6 340-6 560 (with capital cost).

## Swedish vehicle tax rules used

- Petrol/hybrid new car (first 3 years, malus): 360 + 107 kr x (CO2 - 75) for 75-125 g/km, and 132 kr/g above 125 g/km. After 3 years: base tax + CO2 part (roughly 380-620 kr/year for a Yaris Cross hybrid, source: ownership-cost site, not verified).
- Diesel adds fuel surcharge 13.52 x CO2 + 250 kr.
- Check exact figures with the registration number at Transportstyrelsen. EV rules and PHEV changes from 2026 not fully verified.

## Size reference (approximate, from memory, verify)

| | Length | Width | Height | Boot |
|---|---|---|---|---|
| Volvo V40 | 4.37 m | 1.80 m | 1.42 m | ~335 l |
| Yaris Cross | 4.18 m | 1.77 m | 1.56 m | ~390-400 l |
| Volvo EX30 | 4.23 m | 1.84 m | 1.56 m | ~318 l |
| Corolla (hatch) | 4.37 m | 1.79 m | 1.45 m | ~360 l |
| VW Golf | 4.28 m | 1.79 m | 1.46 m | ~380 l |
| Nissan Qashqai | 4.42 m | 1.84 m | 1.62 m | ~500 l (MHEV) |
| Yaris | 3.94 m | 1.74 m | n/a | ~286 l |

The household is rarely more than two people in the car. Rear seat space matters little.

## Assumptions that are NOT verified (replace with real numbers)

- Fuel price 17 kr/l, electricity/charging prices, investment return 5-7 %.
- Insurance for the Yaris Cross is only the quoted 304 kr/month. Check coverage and excess.
- V40 diesel consumption per mil (derive from CarPay fuel data).
- Real-world consumption is typically higher than WLTP (fuel may be 1 200-1 400 kr/month).
- Depreciation of the V40 and of any used car purchase.

## Questions for the dealer (not yet answered)

- Can winter wheels be opted out of / own tyres used? Does the option include tyre change and storage? Tyre wear rules at return (minimum tread depth).
- What does the safety package include (BLIS, rear cross traffic, parking sensors front/rear)?
- Exact CO2 value and annual tax; has the car already been registered (malus period)? Is vehicle tax invoiced separately?
- Price for 2 000 mil/year if the quote is for 1 000 (EX30, Qashqai).

## Suggested next steps

1. Get CarPay statement data into CSV and categorize it. Compute actual diesel cost per mil and repair costs per year.
2. Build the interactive calculator (single HTML file) with scenarios: keep V40, Yaris Cross lease, EX30 lease with home/public charging, used purchase. Inputs: mileage, holding period, fuel/electricity price, depreciation, capital return, insurance.
3. Add a "break-even repair cost" view: how much extra repair cost per year makes keeping the V40 more expensive than leasing.
4. Add real offers and insurance quotes as they arrive.
