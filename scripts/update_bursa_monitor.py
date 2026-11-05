"""Build bursa-monitor/data.json: daily closes for the FBM KLCI and large Bursa Malaysia companies by sector.

Source: Yahoo Finance via the yfinance library (prices adjusted for dividends and splits).
Palm oil prices for the plantation comparison come from palm-oil-monitor/data.json (World Bank).
Symbols with too little data (for example after a delisting) are skipped automatically.
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
# (Yahoo symbol, short code, company name, sector)
STOCKS = [
    ("1155.KL", "MAYBANK", "Malayan Banking", "Banks"),
    ("1295.KL", "PBBANK", "Public Bank", "Banks"),
    ("1023.KL", "CIMB", "CIMB Group", "Banks"),
    ("1066.KL", "RHBBANK", "RHB Bank", "Banks"),
    ("5819.KL", "HLBANK", "Hong Leong Bank", "Banks"),
    ("1015.KL", "AMBANK", "AMMB Holdings", "Banks"),
    ("5347.KL", "TENAGA", "Tenaga Nasional", "Utilities"),
    ("6742.KL", "YTLPOWR", "YTL Power International", "Utilities"),
    ("4677.KL", "YTL", "YTL Corporation", "Utilities"),
    ("6033.KL", "PETGAS", "Petronas Gas", "Utilities"),
    ("6947.KL", "CDB", "CelcomDigi", "Telecoms"),
    ("6012.KL", "MAXIS", "Maxis", "Telecoms"),
    ("6888.KL", "AXIATA", "Axiata Group", "Telecoms"),
    ("4863.KL", "TM", "Telekom Malaysia", "Telecoms"),
    ("5183.KL", "PCHEM", "Petronas Chemicals", "Energy & chemicals"),
    ("5681.KL", "PETDAG", "Petronas Dagangan", "Energy & chemicals"),
    ("7277.KL", "DIALOG", "Dialog Group", "Energy & chemicals"),
    ("3816.KL", "MISC", "MISC", "Energy & chemicals"),
    ("4707.KL", "NESTLE", "Nestlé Malaysia", "Consumer"),
    ("4065.KL", "PPB", "PPB Group", "Consumer"),
    ("7084.KL", "QL", "QL Resources", "Consumer"),
    ("5296.KL", "MRDIY", "MR D.I.Y. Group", "Consumer"),
    ("5326.KL", "99SMART", "99 Speed Mart Retail", "Consumer"),
    ("3182.KL", "GENTING", "Genting", "Consumer"),
    ("4715.KL", "GENM", "Genting Malaysia", "Consumer"),
    ("5225.KL", "IHH", "IHH Healthcare", "Healthcare"),
    ("5168.KL", "HARTA", "Hartalega", "Healthcare"),
    ("7113.KL", "TOPGLOV", "Top Glove", "Healthcare"),
    ("4197.KL", "SIME", "Sime Darby", "Industrials"),
    ("5398.KL", "GAMUDA", "Gamuda", "Industrials"),
    ("3336.KL", "IJM", "IJM Corporation", "Industrials"),
    ("8869.KL", "PMETAL", "Press Metal Aluminium", "Industrials"),
    ("0166.KL", "INARI", "Inari Amertron", "Technology"),
    ("0128.KL", "FRONTKN", "Frontken", "Technology"),
    ("0097.KL", "VITROX", "ViTrox", "Technology"),
    ("0138.KL", "MYEG", "MyEG Services", "Technology"),
    ("5211.KL", "SUNWAY", "Sunway", "Property"),
    ("8664.KL", "SPSETIA", "S P Setia", "Property"),
    ("5148.KL", "UEMS", "UEM Sunrise", "Property"),
    ("2445.KL", "KLK", "Kuala Lumpur Kepong", "Plantations"),
    ("5285.KL", "SDG", "SD Guthrie", "Plantations"),
    ("1961.KL", "IOI", "IOI Corporation", "Plantations"),
    ("2291.KL", "GENP", "Genting Plantations", "Plantations"),
    ("2089.KL", "UTDPLT", "United Plantations", "Plantations"),
    ("5126.KL", "SOP", "Sarawak Oil Palms", "Plantations"),
    ("5138.KL", "HSPLANT", "Hap Seng Plantations", "Plantations"),
    ("5012.KL", "TAANN", "Ta Ann Holdings", "Plantations"),
    ("9059.KL", "TSH", "TSH Resources", "Plantations"),
]


def main():
    syms = [INDEX[0]] + [s[0] for s in STOCKS]
    df = yf.download(syms, period="3y", auto_adjust=True, progress=False, threads=True)["Close"].sort_index()
    df = df[df[INDEX[0]].notna()]           # Bursa trading days only
    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    close, kept, skipped = {}, [], []
    for sym in syms:
        col = df[sym] if sym in df else pd.Series(dtype=float)
        vals = [None if pd.isna(v) else round(float(v), 4) for v in col.reindex(df.index)]
        if sum(v is not None for v in vals) < 120 or vals[-1] is None and all(v is None for v in vals[-10:]):
            skipped.append(sym)
            continue
        close[sym] = vals
    for s, c, n, sec in STOCKS:
        if s in close:
            kept.append({"symbol": s, "code": c, "name": n, "sector": sec})
    data = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "index": {"symbol": INDEX[0], "name": INDEX[1]},
        "stocks": kept, "dates": dates, "close": close,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(dates)} trading days to {dates[-1]}; {len(kept)} stocks kept; skipped: {skipped or 'none'}")


if __name__ == "__main__":
    main()
