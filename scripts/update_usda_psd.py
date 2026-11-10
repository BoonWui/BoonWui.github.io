"""Build data/usda_palm_psd.json: USDA's palm oil balance for the main importers and producers.

Source: USDA Foreign Agricultural Service, Production, Supply and Distribution (PSD) database, oilseeds
download (public domain, US government work): https://apps.fas.usda.gov/psdonline/downloads/psd_oilseeds_csv.zip
USDA updates it with each monthly WASDE report (around the 10th-12th). Values are thousand tonnes by USDA
market year: "2026" means the 2026/27 season (for most countries October to September).

Run: python scripts/update_usda_psd.py   (needs requests)
"""
import csv
import io
import json
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "usda_palm_psd.json"
URL = "https://apps.fas.usda.gov/psdonline/downloads/psd_oilseeds_csv.zip"
UA = {"User-Agent": "palm-oil-monitor (github.com/BoonWui/BoonWui.github.io)"}
COUNTRIES = ["India", "China", "Pakistan", "European Union", "United States", "Bangladesh", "Philippines", "Egypt",
             "Indonesia", "Malaysia", "Thailand"]
ATTRS = {"Production": "prod", "Imports": "imp", "Exports": "exp", "Domestic Consumption": "cons",
         "Food Use Dom. Cons.": "food", "Industrial Dom. Cons.": "ind", "Ending Stocks": "stocks"}
YEARS = 8


def build(rows):
    palm = [r for r in rows if r["Commodity_Description"].strip() == "Oil, Palm"]
    if not palm:
        raise RuntimeError("no palm oil rows in the PSD file")
    years = sorted({r["Market_Year"] for r in palm})[-YEARS:]
    out = {"years": years, "countries": {}, "world": {k: [0.0] * len(years) for k in ATTRS.values()}}
    for r in palm:
        a = ATTRS.get(r["Attribute_Description"].strip())
        if not a or r["Market_Year"] not in years:
            continue
        i, v, c = years.index(r["Market_Year"]), float(r["Value"]), r["Country_Name"].strip()
        out["world"][a][i] += v
        if c in COUNTRIES:
            out["countries"].setdefault(c, {k: [None] * len(years) for k in ATTRS.values()})[a][i] = v
    out["world"] = {k: [round(x, 1) for x in v] for k, v in out["world"].items()}
    latest = max((int(r["Calendar_Year"]), int(r["Month"])) for r in palm if r["Market_Year"] == years[-1])
    out["as_of"] = f"{latest[0]}-{latest[1]:02d}"
    return out


def main():
    raw = requests.get(URL, headers=UA, timeout=180).content
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8-sig")))
    data = build(rows)
    data["source"] = URL
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    c = data["countries"].get("China", {})
    print(f"USDA PSD as of {data['as_of']}: years {data['years'][0]}-{data['years'][-1]}; "
          f"China imports {c.get('imp', [None])[-1]} kt; world imports {data['world']['imp'][-1]} kt -> {OUT}")


if __name__ == "__main__":
    main()
