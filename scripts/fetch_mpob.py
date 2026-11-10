"""Fetch the latest MPOB monthly release and add it to data/mpob_malaysia.csv.

Source: MPOB Economics & Industry Development Division, "Performance of the Malaysian Palm Oil Industry"
(https://bepi.mpob.gov.my/index.php/monthly-release). MPOB only keeps the newest month online, as an HTML
table inside the release article, so the script follows: release list -> newest article -> embedded report.

The report has two columns: the previous month (revised) and the new month (preliminary). Both are used:
the previous month's row is corrected if MPOB revised it, then the new month is added. Domestic use is the
stock-balance residual, as for every row in the CSV (see add_mpob.py).

Run:  python scripts/fetch_mpob.py            # update the CSV if MPOB has a newer month
      python scripts/fetch_mpob.py --dry-run  # show what would change
      python scripts/fetch_mpob.py --file report.html   # parse a saved report instead of downloading
Exit code 0 = updated or nothing new; 1 = the figures failed a sanity check (nothing written); 2 = fetch/parse error.
"""
import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import add_mpob as A

BASE = "https://bepi.mpob.gov.my"
LIST_URL = BASE + "/index.php/monthly-release"
UA = {"User-Agent": "Mozilla/5.0 (compatible; palm-oil-monitor; +https://github.com/BoonWui/BoonWui.github.io)"}
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
          "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]


class Rows(HTMLParser):
    """Collect table rows as lists of cell texts."""

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def to_int(s):
    s = s.strip()
    neg = s.startswith("(") and s.endswith(")")
    v = int(s.strip("()").replace(",", ""))
    return -v if neg else v


def parse_report(html):
    """Return {"month": "YYYY-MM", "prev": {...}, "cur": {...}} with prod/imp/exp/stock in tonnes."""
    m = re.search(r"MALAYSIAN PALM OIL INDUSTRY,\s*([A-Z]+)\s+(\d{4})", html, re.I)
    if not m or m.group(1).upper() not in MONTHS:
        raise ValueError("report title (month and year) not found")
    month = f"{m.group(2)}-{MONTHS.index(m.group(1).upper()) + 1:02d}"

    p = Rows()
    p.feed(html)
    section = sub = None
    got = {}
    for r in p.rows:
        label = r[0].upper().strip()
        nums = [c for c in r[1:] if re.fullmatch(r"\(?[\d,]+(\.\d+)?\)?", c.strip())]
        if label.startswith("PRODUCTION"):
            section = "prod"
        elif label.startswith("STOCK"):
            section = "stock"
        elif label.startswith("EXPORT"):
            section = "exp"
        elif label.startswith("IMPORT"):
            section = "imp"
        elif label.startswith("PRICE") or label.startswith("EXPLANATORY"):
            section = None
        if len(nums) < 2:
            if label and not nums:
                sub = label          # a heading row such as "CRUDE PALM OIL" or "TOTAL PALM OIL"
            continue
        if section is None:
            continue
        prev, cur = to_int(nums[0]), to_int(nums[1])
        key = None
        if section == "prod" and sub == "CRUDE PALM OIL" and label == "TOTAL":
            key = "prod"
        elif section == "stock" and sub == "TOTAL PALM OIL" and label == "TOTAL":
            key = "stock"
        elif section == "exp" and label == "PALM OIL":
            key = "exp"
        elif section == "imp" and label == "PALM OIL":
            key = "imp"
        if key and key not in got:
            got[key] = (prev, cur)
    missing = {"prod", "stock", "exp", "imp"} - set(got)
    if missing:
        raise ValueError(f"could not find {', '.join(sorted(missing))} in the report")
    return {"month": month,
            "prev": {k: v[0] for k, v in got.items()},
            "cur": {k: v[1] for k, v in got.items()}}


def download():
    import requests
    s = requests.Session()
    s.headers.update(UA)
    lst = s.get(LIST_URL, timeout=30)
    lst.raise_for_status()
    links = re.findall(r'href="([^"]*monthly-release/\d+-monthly-release-\d{4}/\d+-[a-z]+-\d{4})"', lst.text)
    if not links:
        raise ValueError("no release article linked from the monthly-release page")
    art_url = urljoin(BASE, links[0])
    art = s.get(art_url, timeout=30, headers={"Referer": LIST_URL})
    art.raise_for_status()
    src = re.search(r'<iframe[^>]+src="([^"]*web_report1\.php[^"]*)"', art.text)
    if not src:
        raise ValueError(f"no report frame in {art_url}")
    rep_url = urljoin(BASE + "/", src.group(1).replace("&amp;", "&").replace("/../", "/"))
    rep = s.get(rep_url, timeout=30, headers={"Referer": art_url})
    rep.raise_for_status()
    if "under construction" in rep.text.lower() or "being updated" in rep.text.lower():
        raise ValueError("MPOB says the report is being updated; try later")
    print(f"Report: {rep_url} (from {art_url})")
    return rep.text


def apply(rows, rep):
    """Return (new_rows, notes, blocking_warnings)."""
    months = [r["month"] for r in rows]
    prev_m = rep["month"]
    y, mo = map(int, prev_m.split("-"))
    prev_m = f"{y - (mo == 1)}-{(mo - 2) % 12 + 1:02d}"
    notes, blocking = [], []

    def put(rows, month, d):
        new, row, warn = A.build_row(rows, month, d["prod"], d["imp"], d["exp"], d["stock"])
        for w in warn:
            # range limits catch parse errors; a big stock move from MPOB itself is real data
            (blocking if "usual range" in w else notes).append(f"{month}: {w}")
        return new, row

    if prev_m in months:
        old = rows[months.index(prev_m)]
        want = {"production_t": rep["prev"]["prod"], "imports_t": rep["prev"]["imp"],
                "exports_t": rep["prev"]["exp"], "end_stocks_t": rep["prev"]["stock"]}
        diff = {k: (old[k], v) for k, v in want.items() if old[k] != v}
        if diff:
            rows, _ = put(rows, prev_m, rep["prev"])
            notes.append(f"{prev_m} revised by MPOB: " + ", ".join(f"{k} {a:,} -> {b:,}" for k, (a, b) in diff.items()))
    elif rep["month"] not in months:
        raise ValueError(f"CSV ends at {months[-1]} but the report is for {rep['month']}: a month is missing")

    cur = rows[[r["month"] for r in rows].index(rep["month"])] if rep["month"] in [r["month"] for r in rows] else None
    same = cur and all(cur[k] == rep["cur"][s] for k, s in
                       (("production_t", "prod"), ("imports_t", "imp"), ("exports_t", "exp"), ("end_stocks_t", "stock")))
    if not same:
        rows, row = put(rows, rep["month"], rep["cur"])
        notes.append(f"{rep['month']} {'corrected' if cur else 'added'}: production {row['production_t']:,}, "
                     f"imports {row['imports_t']:,}, exports {row['exports_t']:,}, domestic {row['domestic_t']:,}, "
                     f"stocks {row['end_stocks_t']:,}")
    return rows, notes, blocking


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--file", help="parse a saved report HTML instead of downloading")
    a = ap.parse_args(argv)
    try:
        html = Path(a.file).read_text(encoding="utf-8", errors="ignore") if a.file else download()
        rep = parse_report(html)
        rows = A.load()
        new, notes, blocking = apply(rows, rep)
    except Exception as e:  # network, layout change, missing month
        print(f"ERROR: {e}")
        return 2
    print(f"MPOB report for {rep['month']}: {rep['cur']}")
    for n in notes:
        print(" -", n)
    if blocking:
        for b in blocking:
            print("WARNING:", b)
        print("Nothing written: a figure is outside its usual range, which usually means the page layout changed.")
        return 1
    if new == rows:
        print("CSV already up to date.")
        return 0
    if a.dry_run:
        print("Dry run: nothing written.")
        return 0
    A.save(new)
    print(f"Saved {A.MPOB.relative_to(A.ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
