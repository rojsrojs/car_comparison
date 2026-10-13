"""Parse CarPay transaction-list HTML (copied from the browser) and merge it into the CSV/JSONL files.

Usage:
    python parse_carpay.py pasted.html          merge a CarPay paste
    python parse_carpay.py --manual rows.csv    merge manual rows (columns: date,description,amount,approximate)
    python parse_carpay.py --split DATE DESC AMOUNT PART_AMOUNT PART_DESC   split a row into remainder + part
    python parse_carpay.py --recategorize       re-apply the rules to existing CarPay rows
"""

import csv
import html
import json
import re
import sys
from pathlib import Path

DATA_DIR: Path = Path(__file__).parent / "data"
CSV_PATH: Path = DATA_DIR / "carpay_transactions.csv"
OVERRIDES_PATH: Path = DATA_DIR / "category_overrides.csv"  # per-row categories: date,description,amount,category
JSONL_PATH: Path = DATA_DIR / "carpay_transactions.jsonl"
FIELDS: list[str] = ["date", "description", "amount", "category", "is_cost", "source", "approximate", "split_of"]

MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "mars": 3, "apr": 4, "april": 4, "maj": 5, "jun": 6, "juni": 6,
    "jul": 7, "juli": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dec": 12,
}

# Order matters: first match wins.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("inbetalt", "payment"),
    ("kjell", "not_car"),  # electronics store
    ("vinted", "not_car"),  # girlfriend using the card for non-car purchases
    ("volvia", "insurance"),
    ("app wa", "wash"),  # e.g. "OKQ8 33117 APP WA": app car wash, assumed
    ("okq8", "fuel"),
    ("st1", "fuel"),
    ("preem", "fuel"),
    ("circle k", "fuel"),
    ("tanka", "fuel"),
    ("ingo", "fuel"),
    ("bilia", "workshop"),
    ("bilverkstad", "workshop"),
    ("mobill", "parking"),  # parking app
    ("parkster", "parking"),
    ("easypark", "parking"),
    ("aimo park", "parking"),
    ("apcoa", "parking"),
    ("wash world", "wash"),
    ("rejmes", "wash"),  # assumed car wash
    ("carspect", "inspection"),  # besiktning
    ("besiktning", "inspection"),
    ("fordonsskatt", "vehicle_tax"),
    ("zor sweden", "tyres"),
    ("biltema", "car_parts"),
]

# Categories that are never a car cost (card repayments, non-car purchases).
NON_COST_CATEGORIES: frozenset[str] = frozenset({"payment", "not_car"})

ROW_RE = re.compile(r'data-test="TableRow-Row".*?(?=data-test="TableRow-Row"|\Z)', re.S)
DATE_RE = re.compile(r'<span[^>]*>([^<]+)</span><span[^>]*>(\d{4})</span>')
CELL_RE = re.compile(r'data-test="TableCell" role="cell"[^>]*>([^<]*)</div>')


def categorize(description: str) -> str:
    lowered = description.lower()
    for needle, category in CATEGORY_RULES:
        if needle in lowered:
            return category
    return "other"


def parse_amount(raw: str) -> float:
    cleaned = html.unescape(raw).replace("\xa0", "").replace(" ", "")
    cleaned = cleaned.removesuffix("kr").replace(",", ".").replace("−", "-")
    return float(cleaned)


def parse_html(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for block in ROW_RE.findall(text):
        date_match = DATE_RE.search(block)
        cells = CELL_RE.findall(block)
        if not date_match or len(cells) < 2:
            continue
        day, month_name = date_match.group(1).split()
        year = date_match.group(2)
        month = MONTHS[month_name.lower().rstrip(".")]
        description = html.unescape(cells[0]).strip()
        category = categorize(description)
        rows.append({
            "date": f"{year}-{month:02d}-{int(day):02d}",
            "description": description,
            "amount": f"{parse_amount(cells[1]):.2f}",
            "category": category,
            "is_cost": str(category not in NON_COST_CATEGORIES).lower(),
            "source": "carpay",
            "approximate": "false",
            "split_of": "",
        })
    return rows


def parse_manual(path: str) -> list[dict[str, str]]:
    """Manual rows: amounts are given as positive costs and stored negative, like the statement."""
    rows: list[dict[str, str]] = []
    with Path(path).open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            category = categorize(r["description"])
            rows.append({
                "date": r["date"].strip(),
                "description": r["description"].strip(),
                "amount": f"{-abs(float(r['amount'])):.2f}",
                "category": category,
                "is_cost": str(category not in NON_COST_CATEGORIES).lower(),
                "source": "manual",
                "approximate": r.get("approximate", "false").strip().lower(),
                "split_of": "",
            })
    return rows


def load_existing() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:  # older files lack the newer columns
        r.setdefault("source", "carpay")
        r.setdefault("approximate", "false")
        r.setdefault("split_of", "")
    return rows


def apply_overrides(rows: list[dict[str, str]]) -> None:
    """Rows from the same merchant can need different categories (e.g. Bilia: repair vs tyre shift)."""
    if not OVERRIDES_PATH.exists():
        return
    with OVERRIDES_PATH.open(encoding="utf-8", newline="") as f:
        overrides = {(o["date"], o["description"], f"{float(o['amount']):.2f}"): o["category"]
                     for o in csv.DictReader(f)}
    for r in rows:
        category = overrides.get((r["date"], r["description"], r["amount"]))
        if category:
            r["category"] = category
            r["is_cost"] = str(category not in NON_COST_CATEGORIES).lower()


def split_row(date: str, description: str, amount: str, part_amount: str, part_description: str) -> None:
    """Split one statement row into a remainder (original description) and a part (new description).

    The part's category comes from category_overrides.csv, so add an override for it afterwards.
    """
    rows = load_existing()
    amount_key = f"{float(amount):.2f}"
    index = next(i for i, r in enumerate(rows)
                 if (r["date"], r["description"], r["amount"]) == (date, description, amount_key))
    original = rows[index]
    part = -abs(float(part_amount))
    origin = f"{date}|{description}|{amount_key}"
    remainder = {**original, "amount": f"{float(amount_key) - part:.2f}", "split_of": origin}
    piece = {**original, "description": part_description, "amount": f"{part:.2f}", "split_of": origin}
    rows[index:index + 1] = [remainder, piece]
    write_rows(rows)
    print(f"split {origin} into {remainder['amount']} + {piece['amount']}")


def write_rows(rows: list[dict[str, str]]) -> None:
    apply_overrides(rows)
    rows.sort(key=lambda r: r["date"], reverse=True)
    DATA_DIR.mkdir(exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with JSONL_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({**r, "amount": float(r["amount"]), "is_cost": r["is_cost"] == "true",
                                "approximate": r["approximate"] == "true"}, ensure_ascii=False) + "\n")


def main(path: str) -> None:
    merged = load_existing()
    if path == "--recategorize":
        new_rows: list[dict[str, str]] = []
        for r in merged:
            if r["source"] != "carpay":
                continue
            r["category"] = categorize(r["description"])
            r["is_cost"] = str(r["category"] not in NON_COST_CATEGORIES).lower()
    elif path == "--manual":
        new_rows = parse_manual(sys.argv[2])
    else:
        new_rows = parse_html(Path(path).read_text(encoding="utf-8"))
    seen = {(r["date"], r["description"], r["amount"]) for r in merged}
    # A split row's original statement row must not be re-added by a later paste.
    seen |= {tuple(r["split_of"].split("|")) for r in merged if r["split_of"]}
    added = 0
    duplicates: list[dict[str, str]] = []
    for row in new_rows:
        key = (row["date"], row["description"], row["amount"])
        if key not in seen:  # exact duplicates are treated as overlap between pastes
            merged.append(row)
            seen.add(key)
            added += 1
        else:
            duplicates.append(row)
    write_rows(merged)
    for row in new_rows:
        if row["category"] == "other":
            print(f"UNCATEGORIZED: {row['date']} {row['description']} {row['amount']}")
    for row in duplicates:
        print(f"DUPLICATE (skipped): {row['date']} {row['description']} {row['amount']}")
    print(f"parsed {len(new_rows)} rows, added {added}, total {len(merged)}")


if __name__ == "__main__":
    if sys.argv[1] == "--split":
        split_row(*sys.argv[2:7])
    else:
        main(sys.argv[1])
