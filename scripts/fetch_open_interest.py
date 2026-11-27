"""Daily total open interest for Chinese vegetable oil futures, written to data/open_interest.json.

Total open interest = the sum over every listed contract month. Each month's daily bars come from Sina Finance
(InnerFuturesNewService.getDailyKLine, field "p" = open interest, "v" = volume):
  P  = Dalian palm olein (DCE)        Y  = Dalian soybean oil (DCE)        OI = Zhengzhou rapeseed oil (ZCE)
Weekly open interest for CBOT soybean oil/soybeans/soymeal and ICE gasoil is read by the page from
data/cftc_managed_money.json (CFTC and ICE Commitments of Traders). Bursa Malaysia does not publish FCPO total
open interest free of charge, so it is not included.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "open_interest.json"
KLINE = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/InnerFuturesNewService.getDailyKLine"
H = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)"}
PRODUCTS = {"P": ("Dalian palm olein", "DCE"), "Y": ("Dalian soybean oil", "DCE"), "OI": ("Zhengzhou rapeseed oil", "ZCE")}
KEEP = 260          # trading days kept
S = requests.Session()
S.headers.update(H)


def bars(symbol, tries=3):
    for k in range(tries):
        try:
            t = S.get(KLINE, params={"symbol": symbol}, timeout=40).text
            m = re.search(r"\((\[.*\]|null)\)", t, re.S)
            return json.loads(m.group(1)) or [] if m else []
        except Exception:
            time.sleep(8 * (k + 1))
    return []


def months_ahead(n=25, back=12):
    """Contract months from `back` months ago (expired ones, so older totals are complete) to a year ahead."""
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month - back
    while m < 1:
        y, m = y - 1, m + 12
    out = []
    for _ in range(n):
        out.append(f"{y % 100:02d}{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"products": {}}
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "source": "Sina Finance daily bars, summed over every listed contract month", "products": {}}
    for prod, (name, exch) in PRODUCTS.items():
        tot, vol, latest = {}, {}, {}
        for ym in months_ahead():
            sym = prod + ym
            rows = bars(sym)
            time.sleep(2.5)
            if not rows:
                continue
            for r in rows[-KEEP:]:
                d, oi, v = r["d"], float(r.get("p") or 0), float(r.get("v") or 0)
                tot[d] = tot.get(d, 0) + oi
                vol[d] = vol.get(d, 0) + v
            last = rows[-1]
            latest[sym] = {"d": last["d"], "oi": int(float(last.get("p") or 0)), "v": int(float(last.get("v") or 0)), "c": float(last.get("c") or 0)}
        if not tot:
            print(name, "not read; keeping the previous data")
            if prod in old.get("products", {}):
                out["products"][prod] = old["products"][prod]
            continue
        newest = max(x["d"] for x in latest.values())
        live = {k: v for k, v in latest.items() if v["d"] == newest and v["oi"] > 0}
        dates = sorted(tot)[-KEEP:]
        # drop the oldest days where expired months (no longer listed) would be missing from the sum
        cut = (datetime.fromisoformat(newest).toordinal() - 345)
        dates = [d for d in dates if datetime.fromisoformat(d).toordinal() >= cut]
        out["products"][prod] = {"name": name, "exchange": exch, "unit": "lots",
                                 "rows": [[d, int(tot[d]), int(vol[d])] for d in dates],
                                 "contracts": dict(sorted(live.items(), key=lambda kv: -kv[1]["oi"])),
                                 "main": max(live, key=lambda k: live[k]["oi"]) if live else None}
        print(name, newest, int(tot[newest]), "lots in", len(live), "months")
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")


if __name__ == "__main__":
    main()
