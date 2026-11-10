"""Add (or correct) one month of MPOB Malaysian palm oil figures in data/mpob_malaysia.csv.

Usage (tonnes; commas allowed):
    python scripts/add_mpob.py 2026-10 --prod 1,950,000 --imp 50,000 --exp 1,400,000 --stock 3,700,000
    python scripts/add_mpob.py 2026-10 ... --dom 400,000     # also give MPOB's own domestic figure to cross-check
    python scripts/add_mpob.py 2026-10 ... --dry-run         # show the checks, write nothing
    python scripts/add_mpob.py 2026-10 ... --force           # write even if a sanity check warns

Domestic use is worked out from the stock balance:
    domestic = opening stocks + production + imports - exports - closing stocks
which is how every row in the file is built. The month must be the next one after the last row,
or an existing month (a correction; the row is replaced and later rows are re-checked).
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MPOB = ROOT / "data" / "mpob_malaysia.csv"
FIELDS = ["month", "production_t", "imports_t", "exports_t", "domestic_t", "end_stocks_t"]

# Ranges a real month should fall in (tonnes). Wide enough for records, tight enough to catch a missing/extra digit.
LIMITS = {
    "production_t": (800_000, 2_300_000),
    "imports_t": (0, 400_000),
    "exports_t": (700_000, 2_200_000),
    "domestic_t": (100_000, 650_000),
    "end_stocks_t": (1_000_000, 4_000_000),
}
MAX_STOCK_MOVE = 600_000   # history 2014-2026: largest monthly move about 450 kt (excluding Sep 2026)
DOM_TOLERANCE = 15_000     # allowed gap between the residual and MPOB's published domestic figure


def num(s):
    return int(round(float(str(s).replace(",", "").replace("_", ""))))


def next_month(m):
    y, mo = map(int, m.split("-"))
    return f"{y + mo // 12}-{mo % 12 + 1:02d}"


def load(path=MPOB):
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: (r[k] if k == "month" else int(r[k])) for k in FIELDS} for r in csv.DictReader(f)]


def save(rows, path=MPOB):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def build_row(rows, month, prod, imp, exp, stock, dom=None):
    """Return (new_rows, row, warnings). Raises ValueError for things that can never be right."""
    months = [r["month"] for r in rows]
    if month in months:
        i = months.index(month)
    elif month == next_month(months[-1]):
        i = len(rows)
    else:
        raise ValueError(f"{month} is neither the next month ({next_month(months[-1])}) nor an existing month")
    if i == 0:
        raise ValueError("cannot rebuild the first row: it has no opening stocks")
    opening = rows[i - 1]["end_stocks_t"]
    residual = opening + prod + imp - exp - stock
    row = {"month": month, "production_t": prod, "imports_t": imp, "exports_t": exp,
           "domestic_t": residual, "end_stocks_t": stock}
    if residual <= 0:
        raise ValueError(f"domestic use comes out at {residual:,} t: the figures do not balance "
                         f"(opening {opening:,} + prod + imp - exp - closing). Check for a typo.")

    warn = []
    for k, (lo, hi) in LIMITS.items():
        if not lo <= row[k] <= hi:
            warn.append(f"{k} {row[k]:,} t is outside the usual range {lo:,}-{hi:,}")
    move = stock - opening
    if abs(move) > MAX_STOCK_MOVE:
        warn.append(f"stocks move {move:+,} t in one month (usual max about 450 kt)")
    if dom is not None and abs(dom - residual) > DOM_TOLERANCE:
        warn.append(f"MPOB domestic {dom:,} t vs balance residual {residual:,} t (gap {dom - residual:+,} t)")

    new = rows[:i] + [row] + rows[i + 1:]
    if i + 1 < len(new):   # a correction changes the next month's opening stocks
        nxt = new[i + 1]
        dom_next = stock + nxt["production_t"] + nxt["imports_t"] - nxt["exports_t"] - nxt["end_stocks_t"]
        if dom_next != nxt["domestic_t"]:
            warn.append(f"{nxt['month']} domestic changes {nxt['domestic_t']:,} -> {dom_next:,} t (new opening stocks); updated")
            new[i + 1] = {**nxt, "domestic_t": dom_next}
    return new, row, warn


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("month", help="YYYY-MM")
    ap.add_argument("--prod", required=True, type=num)
    ap.add_argument("--imp", required=True, type=num)
    ap.add_argument("--exp", required=True, type=num)
    ap.add_argument("--stock", required=True, type=num, help="closing stocks")
    ap.add_argument("--dom", type=num, help="MPOB's published domestic figure, to cross-check only")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    rows = load()
    try:
        new, row, warn = build_row(rows, a.month, a.prod, a.imp, a.exp, a.stock, a.dom)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    prev = new[[r["month"] for r in new].index(a.month) - 1]
    print(f"{a.month}: production {row['production_t']:,} | imports {row['imports_t']:,} | exports {row['exports_t']:,} "
          f"| domestic {row['domestic_t']:,} (residual) | stocks {row['end_stocks_t']:,} "
          f"({row['end_stocks_t'] - prev['end_stocks_t']:+,} vs {prev['month']})")
    for w in warn:
        print("WARNING:", w)
    blocking = [w for w in warn if "updated" not in w]
    if blocking and not a.force:
        print("Nothing written. Check the figures; rerun with --force if they are right.")
        return 1
    if a.dry_run:
        print("Dry run: nothing written.")
        return 0
    save(new)
    print(f"Saved {MPOB.relative_to(ROOT)}. Next: python scripts/update_palm_monitor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
