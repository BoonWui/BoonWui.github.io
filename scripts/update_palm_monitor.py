"""Build palm-oil-monitor/data.json from public sources.

Sources
- World Bank Commodity Price Data (Pink Sheet), monthly. CC BY 4.0.
- NOAA Climate Prediction Center, Oceanic Nino Index (ONI). Public domain.
- MPOB Malaysian palm oil balance, kept in data/mpob_malaysia.csv and updated by hand each month.

Run: python scripts/update_palm_monitor.py   (needs pandas, openpyxl, requests)
"""
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "palm-oil-monitor" / "data.json"
MPOB = ROOT / "data" / "mpob_malaysia.csv"
UA = {"User-Agent": "palm-oil-monitor (github.com/BoonWui/BoonWui.github.io)"}
WB_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
WB_COLS = {
    "Palm oil": "palm", "Soybean oil": "soy", "Sunflower oil": "sun",
    "Rapeseed oil": "rape", "Coconut oil": "coco", "Crude oil, Brent": "brent",
}
SEASONS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def world_bank():
    page = requests.get(WB_PAGE, headers=UA, timeout=60).text
    m = re.search(r'https?://[^"\'\s]+CMO-Historical-Data-Monthly\.xlsx', page)
    if not m:
        raise RuntimeError("World Bank monthly price file link not found")
    raw = requests.get(m.group(0), headers=UA, timeout=120).content
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Monthly Prices", header=None)
    updated = str(df.iloc[3, 0]).replace("Updated on", "").strip()
    hdr = df.iloc[4].tolist()
    idx = {key: hdr.index(name) for name, key in WB_COLS.items()}
    rows = []
    for _, r in df.iloc[6:].iterrows():
        m2 = re.fullmatch(r"(\d{4})M(\d{2})", str(r.iloc[0]).strip())
        if not m2 or int(m2.group(1)) < 2010:
            continue
        rec = {"month": f"{m2.group(1)}-{m2.group(2)}"}
        for key, j in idx.items():
            v = pd.to_numeric(r.iloc[j], errors="coerce")
            rec[key] = None if pd.isna(v) else round(float(v), 2)
        if rec["palm"] is not None:
            rows.append(rec)
    return rows, updated, m.group(0)


def oni():
    txt = requests.get(ONI_URL, headers=UA, timeout=60).text
    out = []
    for line in txt.splitlines()[1:]:
        p = line.split()
        if len(p) == 4 and p[0] in SEASONS and int(p[1]) >= 2000:
            out.append({"season": p[0], "year": int(p[1]), "i": SEASONS.index(p[0]) + 1, "anom": float(p[3])})
    return out


def mpob():
    with open(MPOB, encoding="utf-8") as f:
        return [{"month": r["month"], "prod": int(r["production_t"]), "exp": int(r["exports_t"]),
                 "stock": int(r["end_stocks_t"]), "dom": int(r["domestic_t"]), "imp": int(r["imports_t"])}
                for r in csv.DictReader(f)]


def archive(data, folder):
    """Keep a copy of each monthly edition (named by its latest price month) and list them in index.json.

    A later run in the same month replaces that month's copy, so each edition holds the final data for its month.
    """
    folder.mkdir(parents=True, exist_ok=True)
    last = data["prices"][-1]
    edition = last["month"]
    (folder / f"{edition}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    idx_file = folder / "index.json"
    items = json.loads(idx_file.read_text(encoding="utf-8")) if idx_file.exists() else []
    items = [i for i in items if i["edition"] != edition]
    items.append({"edition": edition, "built": data["built"], "palm": last["palm"], "mpob": data["mpob"][-1]["month"] if data["mpob"] else None})
    items.sort(key=lambda i: i["edition"], reverse=True)
    idx_file.write_text(json.dumps(items, indent=1), encoding="utf-8")
    return edition


def main():
    prices, wb_updated, wb_url = world_bank()
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "sources": {"world_bank_updated": wb_updated, "world_bank_url": wb_url, "oni_url": ONI_URL},
        "prices": prices, "oni": oni(), "mpob": mpob(),
    }
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    edition = archive(data, OUT.parent / "archive")
    print(f"prices to {prices[-1]['month']} (WB {wb_updated}); ONI to {data['oni'][-1]['season']} {data['oni'][-1]['year']}; "
          f"MPOB to {data['mpob'][-1]['month']} -> {OUT}; archived edition {edition}")


if __name__ == "__main__":
    main()
