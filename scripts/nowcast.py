"""Freeze the MPOB nowcast for the next month in data/mpob_nowcast_log.json.

Run right after a new MPOB month lands in data/mpob_malaysia.csv (the update-mpob workflow does this).
It adds one entry for the month after the latest MPOB month and never changes an existing entry, so every
forecast in the log was saved before MPOB published that month; the git history of the log is the proof.

The formula is the same as the one on mpob-nowcast/index.html (keep the two in step); see estimate().
Domestic use and imports: average of the last 3 months. Stocks: last month's stocks + production + imports
- exports - domestic use.
The likely range is the 10th-90th percentile of the misses (actual - estimate) over the last 36 back-tested months.

Run: python scripts/nowcast.py            # add the next month if missing
     python scripts/nowcast.py --show     # print the current estimate and range, write nothing
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import add_mpob as A

LOG = A.ROOT / "data" / "mpob_nowcast_log.json"
KEYS = ["prod", "imp", "exp", "dom", "stock"]
COLS = {"prod": "production_t", "imp": "imports_t", "exp": "exports_t", "dom": "domestic_t", "stock": "end_stocks_t"}
BACKTEST_MONTHS = 36


def add(m, k):
    y, mo = map(int, m.split("-"))
    i = y * 12 + mo - 1 + k
    return f"{i // 12}-{i % 12 + 1:02d}"


def table(rows):
    return {r["month"]: {k: r[c] for k, c in COLS.items()} for r in rows}


FORMULA = "v2"   # v1 (to Oct 2026): production and exports = last year's month x recent trend


def estimate(by, t):
    """Nowcast for month t using only months before t; None if history is short.

    v2 (from Nov 2026), chosen by back-test over 2020-2026:
    - production = last month x the usual change into this calendar month (geometric mean of the last 5 years)
    - exports = half of that seasonal rule, half of last year's month x the 3-month year-on-year trend
    """
    m = add(t, -1)
    need = ([add(m, -j) for j in range(3)] + [add(m, -j - 12) for j in range(3)] + [add(t, -12)]
            + [add(t, -12 * y - d) for y in range(1, 6) for d in (0, 1)])
    if any(x not in by for x in need):
        return None

    def trend(k):   # last year's month x geometric mean of the last 3 months' year-on-year ratios
        return by[add(t, -12)][k] * math.prod(by[add(m, -j)][k] / by[add(m, -j - 12)][k] for j in range(3)) ** (1 / 3)

    def seasonal(k):   # last month x geometric mean of the same month-on-month change in the last 5 years
        return by[m][k] * math.prod(by[add(t, -12 * y)][k] / by[add(t, -12 * y - 1)][k] for y in range(1, 6)) ** (1 / 5)

    last3 = [by[add(m, -j)] for j in range(3)]
    e = {"prod": seasonal("prod"), "exp": 0.5 * trend("exp") + 0.5 * seasonal("exp"),
         "dom": sum(x["dom"] for x in last3) / 3, "imp": sum(x["imp"] for x in last3) / 3}
    e["stock"] = by[m]["stock"] + e["prod"] + e["imp"] - e["exp"] - e["dom"]
    return e


def quantile(xs, q):
    """Linear interpolation between order statistics (same as numpy's default and the page's JavaScript)."""
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    return s[lo] + (s[min(lo + 1, len(s) - 1)] - s[lo]) * (pos - lo)


def backtest(by, upto):
    """Misses (actual - estimate) per item over the last BACKTEST_MONTHS months up to and including `upto`."""
    months = sorted(m for m in by if m <= upto)[-BACKTEST_MONTHS:]
    miss = {k: [] for k in KEYS}
    for t in months:
        e = estimate(by, t)
        if e:
            for k in KEYS:
                miss[k].append(by[t][k] - e[k])
    return miss


def forecast(by, t):
    """Estimate for t plus its likely (80%) range, rounded to tonnes."""
    e = estimate(by, t)
    if e is None:
        return None
    miss = backtest(by, add(t, -1))
    rng = {k: [round(e[k] + quantile(miss[k], 0.1)), round(e[k] + quantile(miss[k], 0.9))] for k in KEYS}
    return {"est": {k: round(e[k]) for k in KEYS}, "range80": rng, "backtest_months": len(miss["stock"])}


def load_log(path=LOG):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def freeze(rows, log, made=None):
    """Return (log, entry_or_None). Adds the month after the latest MPOB month if it is not logged yet."""
    by = table(rows)
    last = max(by)
    t = add(last, 1)
    if any(x["month"] == t for x in log):
        return log, None
    f = forecast(by, t)
    if f is None:
        return log, None
    entry = {"month": t, "made": made or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "data_to": last, "formula": FORMULA, **f}
    return sorted(log + [entry], key=lambda x: x["month"]), entry


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args(argv)
    rows = A.load()
    by = table(rows)
    t = add(max(by), 1)
    if a.show:
        print(json.dumps({"month": t, **forecast(by, t)}, indent=1))
        return 0
    log, entry = freeze(rows, load_log())
    if entry is None:
        print(f"Log already has {t}; nothing changed.")
        return 0
    LOG.write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
    e, r = entry["est"]["stock"], entry["range80"]["stock"]
    print(f"Saved forecast for {t}: stocks {e:,} t (likely {r[0]:,}-{r[1]:,})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
