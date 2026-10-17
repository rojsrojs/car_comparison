"""Build (or refresh) the Volvo V40 entry in data/cars.json from data/carpay_transactions.csv.

Usage: python build_v40.py

The V40 is expressed in the same item format as every other car (see CLAUDE.md, "cars.json").
Items with "auto": true are recomputed from the transactions on every run; their "enabled" flag is kept.
Editing such an item's value in the app sets "auto": false, after which only its "auto_value" (the computed
value, used by the app's "use data value" button) is updated here.
Assumption items (fuel consumption, depreciation, capital) and items added by hand are left alone.
"""

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, NamedTuple

from summarize import CSV_PATH, load_costs, monthly_totals

CARS_PATH: Path = Path(__file__).parent / "data" / "cars.json"
V40_ID: str = "v40"

Item = dict[str, Any]

DEFAULT_SETTINGS: dict[str, Any] = {
    "mil_per_year": 1750,
    "return_rate_pct": 7.0,
    "prices": {"diesel": 23.19, "petrol": 18.74, "el_home": 1.80, "el_public": 4.50},
    "prices_note": (
        "Diesel/petrol: list prices 14 Oct 2026 (carup.se). A tax rise of ~3 kr/l is planned for 1 Dec 2026. "
        "Electricity is an estimate: home = SE3 spot ~0.75 + energy tax + grid fee + VAT; "
        "public = mix of AC and fast charging. Check your own electricity contract."
    ),
}

Period = Literal["all", "last12"]


class AutoItem(NamedTuple):
    id: str
    name: str
    category: str  # category in the CSV
    type: str
    enabled: bool  # default; the user's choice is kept on rebuild
    period: Period = "all"
    group: str | None = None  # items in the same group are either/or: ticking one unticks the others


AUTO_ITEMS: list[AutoItem] = [
    AutoItem("repairs", "Repairs & service (all-period average)", "workshop", "fixed", True, group="repairs"),
    AutoItem("repairs_12m", "Repairs & service (last 12 months)", "workshop", "fixed", False, "last12", "repairs"),
    AutoItem("tyres", "New tyres", "tyres", "fixed", True),
    AutoItem("tyre_service", "Tyre shift + storage", "tyre_service", "fixed", True),
    AutoItem("insurance", "Insurance (Volvia)", "insurance", "fixed", True),
    AutoItem("vehicle_tax", "Vehicle tax", "vehicle_tax", "per_year", True),
    AutoItem("inspection", "Inspection (latest cost)", "inspection", "per_year", True),
    AutoItem("car_parts", "Car parts", "car_parts", "fixed", True),
    AutoItem("parking", "Parking (same for every car)", "parking", "fixed", False),
    AutoItem("wash", "Car wash (same for every car)", "wash", "fixed", False),
    AutoItem("fuel_history", "Fuel, historical average", "fuel", "fixed", False, group="fuel"),
]


def assumption_items(n_months: int) -> list[Item]:
    """Items that are not in the transactions. Created once; later edits in the app are kept."""
    return [
        {"id": "fuel", "name": "Diesel at current price", "type": "fuel", "energy": "diesel",
         "consumption": 0.45, "share_pct": 100, "enabled": True, "group": "fuel",
         "note": "Estimate: historical spend ~1 290 kr/month at ~20 kr/l average gives ~0.45 l/mil. "
                 "Check with odometer + litres."},
        {"id": "depreciation", "name": "Depreciation (13 %/year)", "type": "depreciation", "value_now": 130_000,
         "rate_pct": 13, "months": 36, "enabled": True,
         "note": "Same share of its value lost every year: 180 000 -> 130 000 kr in 29 months is ~12.6 %/year."},
        {"id": "capital", "name": "Missed index-fund return", "type": "capital", "amount": 180_000, "rate_pct": 7, "months": 36,
         "enabled": False, "hidden": True,
         "note": "Not counted on purpose (unsure the money would be invested). 180 000 kr at 7 % over 36 months, compounded = 1 125 kr/month."},
    ]


def latest_amount(category: str) -> float:
    """The most recent single charge in a category (e.g. this year's insurance premium)."""
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["category"] == category and r["is_cost"] == "true"]
    return -float(max(rows, key=lambda r: r["date"])["amount"])


def auto_items() -> tuple[list[Item], str, int]:
    last_month = (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    months = monthly_totals(load_costs(), last_month)
    keys = sorted(months)

    def avg(category: str, ks: list[str]) -> float:
        return sum(months[k].get(category, 0.0) for k in ks) / len(ks)

    basis = f"{keys[0]} to {keys[-1]} ({len(keys)} complete months)"
    items: list[Item] = []
    last12 = keys[-12:]
    for a in AUTO_ITEMS:
        whole, recent = avg(a.category, keys), avg(a.category, last12)
        if a.id == "insurance":
            value, note = latest_amount("insurance"), f"Latest monthly premium. Average {basis}: {whole:.0f} kr/month."
        elif a.id == "vehicle_tax":
            value, note = latest_amount("vehicle_tax"), "Latest yearly tax."
        elif a.id == "inspection":
            value = latest_amount("inspection")
            note = f"Latest inspection cost, counted once a year. Average {basis}: {whole * 12:.0f} kr/year."
        elif a.period == "last12":
            value = recent
            note = f"Average {last12[0]} to {last12[-1]}. All-period average: {whole:.0f} kr/month."
        else:
            value = whole
            note = f"Average {basis}. Last 12 months: {recent:.0f} kr/month."
        if a.type == "per_year" and a.id not in ("vehicle_tax", "inspection"):  # these two already hold a yearly amount
            value *= 12
        item: Item = {"id": a.id, "name": a.name, "type": a.type, "value": round(value), "auto_value": round(value),
                      "enabled": a.enabled, "auto": True, "note": note}
        if a.group:
            item["group"] = a.group
        items.append(item)
    return items, basis, len(keys)


def build() -> None:
    data: dict[str, Any] = (json.loads(CARS_PATH.read_text(encoding="utf-8")) if CARS_PATH.exists()
                            else {"settings": DEFAULT_SETTINGS, "cars": []})
    items, basis, n_months = auto_items()
    car = next((c for c in data["cars"] if c["id"] == V40_ID), None)
    if car is None:
        car = {"id": V40_ID, "name": "Volvo V40 diesel (2018)", "kind": "own", "default": True,
               "notes": "Current car, bought April 2024. Costs from CarPay + manual rows.",
               "items": [*items, *assumption_items(n_months)]}
        data["cars"].insert(0, car)
    else:
        existing = {i["id"]: i for i in car["items"]}
        previous_id: str | None = None
        for item in items:
            if item["id"] in existing:
                old = existing[item["id"]]
                if old.get("auto", True):
                    item["enabled"] = old["enabled"]
                    old.update(item)
                else:  # edited in the app: keep the user's value, but remember the computed one for "back to auto"
                    old["auto_value"] = item["auto_value"]
            else:  # new auto item: place it right after the auto item that precedes it in AUTO_ITEMS
                ids = [i["id"] for i in car["items"]]
                car["items"].insert(ids.index(previous_id) + 1 if previous_id in ids else len(ids), item)
            previous_id = item["id"]
        for default in assumption_items(n_months):  # add groups introduced after the item was created
            if default["id"] in existing and "group" in default:
                existing[default["id"]].setdefault("group", default["group"])
    car["basis"] = basis

    tmp = CARS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CARS_PATH)
    print(f"V40 built from {basis}")


if __name__ == "__main__":
    build()
