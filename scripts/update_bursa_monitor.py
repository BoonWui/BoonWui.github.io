"""Build bursa-monitor/data.json: daily closes for the FBM KLCI and Bursa Malaysia plantation stocks.

Source: Yahoo Finance via the yfinance library (prices adjusted for dividends and splits).
Palm oil prices for the comparison come from palm-oil-monitor/data.json (World Bank).
Run: python scripts/update_bursa_monitor.py   (needs yfinance, pandas)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bursa-monitor" / "data.json"
INDEX = ("^KLSE", "FBM KLCI")
STOCKS = [
    ("2445.KL", "KLK", "Kuala Lumpur Kepong"),
    ("5285.KL", "SDG", "SD Guthrie"),
    ("1961.KL", "IOI", "IOI Corporation"),
    ("2291.KL", "GENP", "Genting Plantations"),
    ("2089.KL", "UTDPLT", "United Plantations"),
    ("5126.KL", "SOP", "Sarawak Oil Palms"),
    ("5138.KL", "HSPLANT", "Hap Seng Plantations"),
    ("5012.KL", "TAANN", "Ta Ann Holdings"),
    ("9059.KL", "TSH", "TSH Resources"),
]


def closes(symbols, period="3y"):
    df = yf.download(symbols, period=period, auto_adjust=True, progress=False, threads=True)["Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame(symbols[0])
    return df.sort_index()


def main():
    syms = [INDEX[0]] + [s[0] for s in STOCKS]
    df = closes(syms)
    df = df[df[INDEX[0]].notna()]           # keep Bursa trading days only
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    series = {}
    for sym in syms:
        col = df[sym] if sym in df else pd.Series(dtype=float)
        vals = [None if pd.isna(v) else round(float(v), 4) for v in col.reindex(df.index)]
        if sum(v is not None for v in vals) < 60:
            print(f"skipping {sym}: not enough data")
            continue
        series[sym] = vals
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "index": {"symbol": INDEX[0], "name": INDEX[1]},
        "stocks": [{"symbol": s, "code": c, "name": n} for s, c, n in STOCKS if s in series],
        "dates": dates,
        "close": series,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(dates)} trading days to {dates[-1]}, {len(data['stocks'])} stocks -> {OUT}")


if __name__ == "__main__":
    main()
