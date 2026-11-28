"""Build data/etf_trend.json for the ETF Trend Allocator page.

Month-end total-return closes (dividends reinvested, via yfinance auto_adjust)
for a fixed set of liquid ETFs, plus the latest daily close and the last
~260 daily closes so the page can show a mid-month signal preview and
daily volatility.
"""
import json
import datetime as dt
from pathlib import Path

import yfinance as yf

TICKERS = {
    "SPY": "US large caps (S&P 500)",
    "QQQ": "US tech (Nasdaq 100)",
    "IWM": "US small caps (Russell 2000)",
    "EFA": "Developed markets ex-US",
    "EEM": "Emerging markets",
    "TLT": "US Treasuries 20y+",
    "IEF": "US Treasuries 7-10y",
    "GLD": "Gold",
    "DBC": "Broad commodities",
    "VNQ": "US real estate (REITs)",
    "SHY": "US Treasuries 1-3y (cash)",
}

OUT = Path(__file__).resolve().parent.parent / "data" / "etf_trend.json"


def main():
    raw = yf.download(list(TICKERS), period="max", interval="1d",
                      auto_adjust=True, progress=False, group_by="ticker", threads=True)
    monthly, daily, last = {}, {}, {}
    for t in TICKERS:
        s = raw[t]["Close"].dropna()
        if s.empty:
            raise SystemExit(f"no data for {t}")
        try:
            m = s.resample("ME").last().dropna()
        except ValueError:  # pandas < 2.2
            m = s.resample("M").last().dropna()
        monthly[t] = [[d.strftime("%Y-%m"), round(float(v), 4)] for d, v in m.items()]
        tail = s.iloc[-260:]
        daily[t] = [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in tail.items()]
        last[t] = [s.index[-1].strftime("%Y-%m-%d"), round(float(s.iloc[-1]), 4)]
    data = {
        "updated": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "Yahoo Finance via yfinance, adjusted for dividends and splits",
        "names": TICKERS,
        "monthly": monthly,
        "daily": daily,
        "last": last,
    }
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, {t: len(v) for t, v in monthly.items()})


if __name__ == "__main__":
    main()
