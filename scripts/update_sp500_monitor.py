"""Build sp500-monitor/data.json: daily closes for the S&P 500, VIX, 10-year yield, sector ETFs and large US stocks.

Source: Yahoo Finance via yfinance (prices adjusted for dividends and splits). Symbols with too little data are skipped.
Run: python scripts/update_sp500_monitor.py   (needs yfinance, pandas)
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sp500-monitor" / "data.json"
INDEX = ("^GSPC", "S&P 500")
EXTRAS = {"^VIX": "VIX volatility index", "^TNX": "US 10-year Treasury yield", "SPY": "S&P 500 ETF (cap-weighted)", "RSP": "S&P 500 Equal Weight ETF"}
SECTOR_ETFS = {
    "XLK": "Information Technology", "XLF": "Financials", "XLV": "Health Care", "XLY": "Consumer Discretionary",
    "XLC": "Communication Services", "XLI": "Industrials", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLU": "Utilities", "XLRE": "Real Estate", "XLB": "Materials",
}
STOCKS = [  # (symbol, company, GICS sector)
    ("AAPL", "Apple", "Information Technology"), ("MSFT", "Microsoft", "Information Technology"), ("NVDA", "NVIDIA", "Information Technology"),
    ("AVGO", "Broadcom", "Information Technology"), ("ORCL", "Oracle", "Information Technology"), ("CRM", "Salesforce", "Information Technology"),
    ("AMD", "Advanced Micro Devices", "Information Technology"), ("ADBE", "Adobe", "Information Technology"), ("CSCO", "Cisco", "Information Technology"),
    ("QCOM", "Qualcomm", "Information Technology"), ("IBM", "IBM", "Information Technology"),
    ("JPM", "JPMorgan Chase", "Financials"), ("V", "Visa", "Financials"), ("MA", "Mastercard", "Financials"), ("BAC", "Bank of America", "Financials"),
    ("WFC", "Wells Fargo", "Financials"), ("GS", "Goldman Sachs", "Financials"), ("BRK-B", "Berkshire Hathaway", "Financials"), ("SPGI", "S&P Global", "Financials"),
    ("LLY", "Eli Lilly", "Health Care"), ("UNH", "UnitedHealth", "Health Care"), ("JNJ", "Johnson & Johnson", "Health Care"), ("ABBV", "AbbVie", "Health Care"),
    ("MRK", "Merck", "Health Care"), ("TMO", "Thermo Fisher", "Health Care"), ("ABT", "Abbott", "Health Care"), ("PFE", "Pfizer", "Health Care"),
    ("AMZN", "Amazon", "Consumer Discretionary"), ("TSLA", "Tesla", "Consumer Discretionary"), ("HD", "Home Depot", "Consumer Discretionary"),
    ("MCD", "McDonald's", "Consumer Discretionary"), ("LOW", "Lowe's", "Consumer Discretionary"), ("NKE", "Nike", "Consumer Discretionary"),
    ("GOOGL", "Alphabet", "Communication Services"), ("META", "Meta Platforms", "Communication Services"), ("NFLX", "Netflix", "Communication Services"),
    ("DIS", "Walt Disney", "Communication Services"), ("VZ", "Verizon", "Communication Services"), ("T", "AT&T", "Communication Services"),
    ("GE", "GE Aerospace", "Industrials"), ("CAT", "Caterpillar", "Industrials"), ("RTX", "RTX", "Industrials"), ("HON", "Honeywell", "Industrials"),
    ("UNP", "Union Pacific", "Industrials"), ("BA", "Boeing", "Industrials"),
    ("WMT", "Walmart", "Consumer Staples"), ("COST", "Costco", "Consumer Staples"), ("PG", "Procter & Gamble", "Consumer Staples"),
    ("KO", "Coca-Cola", "Consumer Staples"), ("PEP", "PepsiCo", "Consumer Staples"), ("PM", "Philip Morris", "Consumer Staples"),
    ("XOM", "Exxon Mobil", "Energy"), ("CVX", "Chevron", "Energy"), ("COP", "ConocoPhillips", "Energy"),
    ("NEE", "NextEra Energy", "Utilities"), ("SO", "Southern Company", "Utilities"), ("DUK", "Duke Energy", "Utilities"),
    ("PLD", "Prologis", "Real Estate"), ("AMT", "American Tower", "Real Estate"),
    ("LIN", "Linde", "Materials"), ("SHW", "Sherwin-Williams", "Materials"), ("FCX", "Freeport-McMoRan", "Materials"),
]


def main():
    syms = [INDEX[0]] + list(EXTRAS) + list(SECTOR_ETFS) + [s[0] for s in STOCKS]
    df = yf.download(syms, period="3y", auto_adjust=True, progress=False, threads=True)["Close"].sort_index()
    df = df[df[INDEX[0]].notna()]
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    close, skipped = {}, []
    for sym in syms:
        col = df[sym] if sym in df else pd.Series(dtype=float)
        vals = [None if pd.isna(v) else round(float(v), 4) for v in col.reindex(df.index)]
        recent = [v for v in vals[-253:] if v is not None]
        jumps = [abs(b / a - 1) for a, b in zip(recent, recent[1:]) if a]
        if sym != syms[0] and jumps and max(jumps) > 0.45:   # suspect data: unadjusted split/consolidation or bad ticks
            skipped.append(sym + " (suspect data: one-day move of {:.0%})".format(max(jumps)))
            continue
        if sum(v is not None for v in vals) < 120:
            skipped.append(sym)
            continue
        close[sym] = vals
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "index": {"symbol": INDEX[0], "name": INDEX[1]},
        "extras": {k: v for k, v in EXTRAS.items() if k in close},
        "sector_etfs": [{"symbol": k, "sector": v} for k, v in SECTOR_ETFS.items() if k in close],
        "stocks": [{"symbol": s, "code": s, "name": n, "sector": sec} for s, n, sec in STOCKS if s in close],
        "dates": dates, "close": close,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(dates)} days to {dates[-1]}; {len(data['stocks'])} stocks, {len(data['sector_etfs'])} sector ETFs, extras {list(data['extras'])}; skipped: {skipped or 'none'}")


if __name__ == "__main__":
    main()
