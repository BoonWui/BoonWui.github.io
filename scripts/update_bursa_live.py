"""Write bursa-monitor/live.json: the latest price of the KLCI and each tracked stock during trading hours.

Runs hourly from GitHub Actions while Bursa Malaysia is open. The page merges these prices into the
daily history from data.json. Source: Yahoo Finance via yfinance (usually delayed by about 15 minutes).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "bursa-monitor" / "data.json"
OUT = ROOT / "bursa-monitor" / "live.json"


def main():
    base = json.loads(DATA.read_text(encoding="utf-8"))
    syms = [base["index"]["symbol"]] + [s["symbol"] for s in base["stocks"]]
    df = yf.download(syms, period="5d", interval="1d", auto_adjust=True, progress=False, threads=True)["Close"].sort_index()
    df = df[df[syms[0]].notna()]
    if df.empty:
        print("No prices returned; leaving live.json unchanged.")
        return
    last = df.iloc[-1]
    prices = {s: round(float(last[s]), 4) for s in syms if s in last and pd.notna(last[s])}
    out = {
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prices": prices,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(prices)} prices for {out['date']} fetched {out['fetched']}")


if __name__ == "__main__":
    main()
