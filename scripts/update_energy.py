"""Build energy-monitor/data.json: daily Brent crude, US Gulf Coast diesel and the ringgit.

Sources (both official and free to reuse):
- U.S. Energy Information Administration (EIA) spot price history files, public domain.
- Bank Negara Malaysia Open API, USD/MYR exchange rate (mid of buying and selling rate at noon).
Run: python scripts/update_energy.py   (needs requests, pandas, xlrd)
"""
import io
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "energy-monitor" / "data.json"
UA = {"User-Agent": "palm-energy-monitor (github.com/BoonWui/BoonWui.github.io)"}
START = "2021-01-01"
EIA = {
    "brent": "https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls",                 # $/barrel
    "diesel": "https://www.eia.gov/dnav/pet/hist_xls/EER_EPD2DXL0_PF4_RGC_DPGd.xls",  # $/gallon, ULSD US Gulf Coast
}
BNM = "https://api.bnm.gov.my/public/exchange-rate/USD/year/{y}/month/{m}"
BNM_H = {"Accept": "application/vnd.BNM.API.v1+json", **UA}


def eia(url):
    r = requests.get(url, headers=UA, timeout=120)
    r.raise_for_status()
    df = pd.read_excel(io.BytesIO(r.content), sheet_name="Data 1", skiprows=2)
    df.columns = ["date", "v"]
    df = df.dropna()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return {d: float(v) for d, v in zip(df["date"], df["v"]) if d >= START}


def bnm_month(y, m):
    for attempt in range(3):
        try:
            r = requests.get(BNM.format(y=y, m=m), headers=BNM_H, timeout=60)
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            rates = r.json()["data"]["rate"]
            return {x["date"]: round((x["buying_rate"] + x["selling_rate"]) / 2, 4) for x in rates if x.get("buying_rate") and x.get("selling_rate")}
        except Exception as exc:
            print("retry BNM", y, m, exc)
            time.sleep(15 * (attempt + 1))
    return {}


def ringgit(old):
    """Keep what we already have; fetch only the last two months (or everything on the first run)."""
    have = dict(old)
    today = date.today()
    months = []
    y, m = (int(START[:4]), 1) if not have else ((today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12))
    while (y, m) <= (today.year, today.month):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for y, m in months:
        have.update(bnm_month(y, m))
        time.sleep(1)
    return have


def main():
    old = {}
    if OUT.exists():
        d = json.loads(OUT.read_text(encoding="utf-8"))
        old = {k: v for k, v in zip(d["dates"], d["usdmyr"]) if v is not None}
    brent, diesel = eia(EIA["brent"]), eia(EIA["diesel"])
    myr = ringgit(old)
    dates = sorted(set(brent) | set(diesel) | set(myr))
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sources": {"brent": "EIA, Europe Brent spot FOB ($/bbl)", "diesel": "EIA, US Gulf Coast ultra-low sulfur diesel spot ($/gal)",
                    "usdmyr": "Bank Negara Malaysia, USD/MYR noon rate (mid)"},
        "dates": dates,
        "brent": [brent.get(d) for d in dates],
        "diesel": [diesel.get(d) for d in dates],
        "usdmyr": [myr.get(d) for d in dates],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    last = lambda k: max(d for d, v in zip(dates, data[k]) if v is not None)
    print(f"{len(dates)} days; brent to {last('brent')}, diesel to {last('diesel')}, USD/MYR to {last('usdmyr')} -> {OUT}")


if __name__ == "__main__":
    main()
