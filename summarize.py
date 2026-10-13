"""Average monthly cost summary from data/carpay_transactions.csv.

Usage: python summarize.py [--end YYYY-MM-DD]

Only complete calendar months are used: the month containing --end (default today) is skipped.
Writes data/monthly_summary.csv (one row per complete month) and prints the averages.
Costs are shown as positive SEK. 1 mil = 10 km.
"""

import csv
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median

DATA_DIR: Path = Path(__file__).parent / "data"
CSV_PATH: Path = DATA_DIR / "carpay_transactions.csv"
OUT_PATH: Path = DATA_DIR / "monthly_summary.csv"

CATEGORIES: list[str] = [
    "fuel", "workshop", "tyres", "tyre_service", "insurance", "vehicle_tax",
    "inspection", "parking", "wash", "car_parts",
]
# Costs that are the same in every scenario (project principle: compare only what differs).
EQUAL_ACROSS_SCENARIOS: frozenset[str] = frozenset({"parking", "wash"})
# Comparison with a lease: fuel, parking and wash are paid either way, so they are left out.
LEFT_OUT_FOR_LEASE: frozenset[str] = frozenset({"fuel", "parking", "wash"})
MIL_PER_YEAR: int = 1750  # project notes: actual driving ~1 700-1 800 mil/year
# Not in the CarPay data. Both are assumptions to adjust.
DEPRECIATION_TOTAL: float = 50_000  # approximate value loss since the purchase (end of April 2024), spread evenly
INVESTED: float = 180_000  # purchase price; what the same money could have earned in index funds
ANNUAL_RETURN: float = 0.07  # opportunity-cost rate (simple, not compounded)

MonthTotals = dict[str, float]


def load_costs() -> list[tuple[str, str, float]]:
    """(YYYY-MM, category, positive amount) for every row that counts as a cost."""
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        return [(r["date"][:7], r["category"], -float(r["amount"]))
                for r in csv.DictReader(f) if r["is_cost"] == "true"]


def monthly_totals(costs: list[tuple[str, str, float]], last_month: str) -> dict[str, MonthTotals]:
    months: dict[str, MonthTotals] = defaultdict(lambda: defaultdict(float))
    for month, category, amount in costs:
        if month <= last_month:
            months[month][category] += amount
    return dict(months)


def average(months: dict[str, MonthTotals], keys: list[str], categories: list[str]) -> float:
    return sum(months[k].get(c, 0.0) for k in keys for c in categories) / len(keys)


def main(end: date) -> None:
    last_month = (end.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")  # last complete month

    months = monthly_totals(load_costs(), last_month)
    keys = sorted(months)
    comparable = [c for c in CATEGORIES if c not in EQUAL_ACROSS_SCENARIOS]

    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["month", *CATEGORIES, "total", "total_comparable"])
        for k in keys:
            writer.writerow([k, *[round(months[k].get(c, 0)) for c in CATEGORIES],
                             round(sum(months[k].values())),
                             round(sum(months[k].get(c, 0) for c in comparable))])

    periods: dict[str, list[str]] = {
        f"All {len(keys)} months": keys,
        "Last 12": keys[-12:],
        "Previous 12": keys[-24:-12],
        f"First {len(keys) - 24}": keys[:-24],
    }
    print(f"complete months: {keys[0]} to {keys[-1]} ({len(keys)})\n")
    header = f"{'kr/month':14}" + "".join(f"{name:>14}" for name in periods)
    print(header)
    for c in CATEGORIES:
        print(f"{c:14}" + "".join(f"{average(months, ks, [c]):14.0f}" for ks in periods.values()))
    print("-" * len(header))
    print(f"{'TOTAL':14}" + "".join(f"{average(months, ks, CATEGORIES):14.0f}" for ks in periods.values()))
    print(f"{'excl. park/wash':14}" + "".join(f"{average(months, ks, comparable):14.0f}" for ks in periods.values()))
    print(f"{'median month':14}" + "".join(
        f"{median(sum(months[k].get(c, 0) for c in comparable) for k in ks):14.0f}" for ks in periods.values()))
    vs_lease = [c for c in CATEGORIES if c not in LEFT_OUT_FOR_LEASE]
    without_service = [c for c in vs_lease if c != "tyre_service"]
    print(f"\nFor the lease comparison (excl. {', '.join(sorted(LEFT_OUT_FOR_LEASE))}):")
    print(f"{'WITH shift/stor.':16}" + "".join(f"{average(months, ks, vs_lease):14.0f}" for ks in periods.values()))
    print(f"{'WITHOUT shift':16}" + "".join(f"{average(months, ks, without_service):14.0f}" for ks in periods.values()))

    depreciation = DEPRECIATION_TOTAL / len(keys)
    capital = INVESTED * ANNUAL_RETURN / 12
    print(f"\nAdded per month: depreciation {depreciation:.0f} kr, "
          f"capital cost {capital:.0f} kr ({INVESTED:,.0f} kr at {ANNUAL_RETURN:.0%})")
    for label, cats in (("with shift/stor.", vs_lease), ("without shift", without_service)):
        print(f"{label}")
        for name, extra in (("  + depreciation", depreciation), ("  + depr. + capital", depreciation + capital)):
            print(f"{name:18}" + "".join(f"{average(months, ks, cats) + extra:14.0f}" for ks in periods.values()))
    print(f"\n{'kr per mil':14}" + "".join(
        f"{average(months, ks, comparable) * 12 / MIL_PER_YEAR:14.1f}" for ks in periods.values()))


if __name__ == "__main__":
    end_date = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--end" else date.today()
    main(end_date)
