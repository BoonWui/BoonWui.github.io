"""Write <folder>/live.json: the latest price of every symbol in <folder>/data.json during trading hours.

Usage: python scripts/update_bursa_live.py [folder]     (folder defaults to bursa-monitor; also used for sp500-monitor)
Runs hourly from GitHub Actions while the market is open. The page merges these prices into the daily history.
Source: Yahoo Finance via yfinance (usually delayed by about 15 minutes).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]


def main(folder: str = "bursa-monitor"):
    data_path, out = ROOT / folder / "data.json", ROOT / folder / "live.json"
    base = json.loads(data_path.read_text(encoding="utf-8"))
    idx = base["index"]["symbol"]
    syms = [idx] + [s for s in base["close"] if s != idx]
    df = yf.download(syms, period="5d", interval="1d", auto_adjust=True, progress=False, threads=True)["Close"].sort_index()
    df = df[df[idx].notna()]
    if df.empty:
        print("No prices returned; leaving live.json unchanged.")
        return
    last = df.iloc[-1]
    prices = {s: round(float(last[s]), 4) for s in syms if s in last and pd.notna(last[s])}
    result = {"date": df.index[-1].strftime("%Y-%m-%d"), "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "prices": prices}
    out.write_text(json.dumps(result, separators=(",", ":")), encoding="utf-8")
    print(f"{folder}: {len(prices)} prices for {result['date']} fetched {result['fetched']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "bursa-monitor")
