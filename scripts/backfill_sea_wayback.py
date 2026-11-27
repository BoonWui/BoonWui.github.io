"""One-off backfill of SEA India daily rates from Internet Archive (Wayback Machine) copies of https://seaofindia.com/.

The archive holds about two copies a month since 2024. Each copy is read with the same parser as the daily job
(scripts/fetch_sea_daily.py) and written to data/sea_daily_history.csv, one row per SEA quote date, with the
archive copy as the source. The daily file (data/sea_daily_prices.csv) is left untouched.

Run: python scripts/backfill_sea_wayback.py
"""
import csv
import time
from pathlib import Path

import requests

import fetch_sea_daily as sea

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sea_daily_history.csv"
CDX = "https://web.archive.org/cdx/search/cdx?url=seaofindia.com/&from=2023&output=json&fl=timestamp&filter=statuscode:200&collapse=timestamp:8"


def main():
    stamps = [r[0] for r in requests.get(CDX, headers=sea.UA, timeout=120).json()[1:]]
    ecb = sea.get_with_retry(sea.ECB, timeout=120).content
    rows = {}
    if OUT.exists():
        with open(OUT, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows[r["date"]] = r
    done = {r.get("source", "").split("/web/")[-1][:14] for r in rows.values()}
    for ts in stamps:
        if ts in done:
            continue
        url = f"https://web.archive.org/web/{ts}id_/https://seaofindia.com/"
        try:
            page = None
            for k in range(4):
                try:
                    page = requests.get(url, headers=sea.UA, timeout=90).text
                    break
                except requests.RequestException:
                    time.sleep(30 * (k + 1))
            if page is None:
                raise ValueError("archive refused the connection")
            r = sea.parse(page)
        except Exception as e:  # layout differs or copy is broken
            print(ts, "skipped:", str(e)[:80])
            time.sleep(6)
            continue
        if r["date"] not in rows:
            r["usdinr_ecb"] = sea.usdinr(r["date"], ecb)
            r["source"] = url
            rows[r["date"]] = r
            print(ts, "->", r["date"], r["cpo_cf_mumbai_usd"], r["cpo_kandla_inr"])
        time.sleep(6)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=sea.FIELDS + ["source"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows[d] for d in sorted(rows))
    print(len(rows), "dates written to", OUT)


if __name__ == "__main__":
    main()
