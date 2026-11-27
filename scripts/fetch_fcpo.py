"""Bursa Malaysia Derivatives crude palm oil futures (FCPO): daily OHLC and volume, from Sina Finance.

Writes data/bmd_fcpo.json for the bmd-fcpo page. Sina's FCPO series follows the benchmark third-month
contract (e.g. Feb 2027 in late November 2026); its closes are within a few ringgit of Bursa's.
Bursa's own website sits behind a Cloudflare bot check, so it is not fetched.
"""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bmd_fcpo.json"
URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/GlobalFuturesService.getGlobalFuturesDailyKLine"
UA = {"User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)", "Referer": "https://finance.sina.com.cn/"}


def fetch():
    for i in range(5):
        try:
            r = requests.get(URL, params={"symbol": "FCPO"}, headers=UA, timeout=60)
            m = re.search(r"\((\[.*\])\)", r.text, re.S)
            if r.status_code == 200 and m:
                return json.loads(m.group(1))
            print(f"  HTTP {r.status_code}")
        except requests.RequestException as e:
            print(f"  retry {i + 1}: {e.__class__.__name__}")
        time.sleep(8 * (i + 1))
    raise SystemExit("could not fetch FCPO from Sina")


def main():
    bars = []
    for k in fetch():
        try:
            o, h, l, c = (round(float(k[x])) for x in ("open", "high", "low", "close"))
            if c > 0:
                bars.append([k["date"], o, h, l, c, int(float(k.get("volume") or 0))])
        except (KeyError, ValueError):
            pass
    if len(bars) < 250:
        raise SystemExit(f"only {len(bars)} bars; not overwriting")
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("bars") == bars:
        print("Nothing new; file left unchanged.")
        return
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": "Bursa Malaysia Derivatives FCPO (third-month benchmark) via Sina Finance",
        "bars": bars,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"{len(bars)} days, last {bars[-1]}. Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
