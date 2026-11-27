"""DCE palm oil (p) and soybean oil (y) options: daily call and put volume and open interest, from Sina Finance.

Writes data/dce_options.json for the dce-report page (call/put ratios).
- Each run after the day session (15:00-21:00 Beijing time) takes a snapshot of every strike of the tracked option
  months (near month + next 01/05/09, same as the broker rankings): open interest, and volume for strikes that
  traded that day.
- Open interest is only available as today's figure, so its history builds up from the first run (27 Nov 2026).
- Volume history is backfilled once from Sina's per-strike daily bars.
The exchange's own site (dce.com.cn) sits behind a bot check, so it is not used.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_dce_positions import active_contracts  # same contract months as the broker rankings

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "dce_options.json"
KEEP = 260                      # trading days kept
HQ = "https://hq.sinajs.cn/list="
DAYLINE = "https://stock.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/FutureOptionAllService.getOptionDayline"
KLINE = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/InnerFuturesNewService.getDailyKLine"
H = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)"}
S = requests.Session()
S.headers.update(H)
CST = timezone(timedelta(hours=8))


def get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=40)
            if r.status_code == 200:
                return r
        except requests.RequestException as e:
            print(f"  retry {i + 1}: {e.__class__.__name__}")
        time.sleep(4 * (i + 1))
    return None


def underlying_price(code):
    r = get(KLINE, {"symbol": code})
    m = r and re.search(r"\((\[.*\])\)", r.text, re.S)
    if not m:
        return None
    rows = [x for x in json.loads(m.group(1)) if float(x.get("c") or 0) > 0]
    return float(rows[-1]["c"]) if rows else None


def chain(und, price):
    """{symbol: (strike, 'C'|'P', oi, vol, quote_datetime)} for strikes 60%-150% of the futures price."""
    syms = [f"P_OP_{und}{cp}{k}" for k in range(int(price * 0.6) // 100 * 100, int(price * 1.5), 100) for cp in "CP"]
    out = {}
    for i in range(0, len(syms), 80):
        r = get(HQ + ",".join(syms[i:i + 80]))
        if r is None:
            continue
        for m in re.finditer(r'hq_str_P_OP_(\w+?)([CP])(\d+)="([^"]+)"', r.content.decode("gbk", "replace")):
            f = m.group(4).split(",")
            di = [j for j, x in enumerate(f) if re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d", x)]
            if not di:
                continue
            try:
                oi = float(f[5] or 0)
                vol = float(f[di[0] + 9] or 0)
            except (ValueError, IndexError):
                continue
            out[m.group(1) + m.group(2) + m.group(3)] = (int(m.group(3)), m.group(2), oi, vol, f[di[0]])
        time.sleep(0.5)
    return out


def backfill_volume(syms):
    """{date: [call_vol, put_vol]} summed over the given strike symbols, from Sina daily bars."""
    tot = {}
    for s in syms:
        r = get(DAYLINE, {"symbol": s})
        m = r and re.search(r"\((\[.*\])\)", r.text, re.S)
        if m:
            for b in json.loads(m.group(1)):
                v = float(b.get("v") or 0)
                d = tot.setdefault(b["d"], [0, 0])
                d[0 if "C" in s[5:] else 1] += v
        time.sleep(0.6)
    return tot


def main():
    now = datetime.now(CST)
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"products": {}}
    snapshot_ok = now.weekday() < 5 and 15 <= now.hour < 21     # after the day session, before the night session
    for prod in ("p", "y"):
        P = data["products"].setdefault(prod, {"days": {}, "backfilled": []})
        months = [c.lower() for c in active_contracts(now.date(), prod)]
        snap = {"cv": 0, "pv": 0, "coi": 0, "poi": 0}
        day = None
        for und in months:
            px = underlying_price(und.upper())
            if not px:
                continue
            ch = chain(und, px)
            if not ch:
                continue
            print(f"  {und}: {len(ch)} option quotes")
            if und not in P["backfilled"]:            # one-off: volume history for this option month
                for d, (c, p_) in backfill_volume(list(ch)).items():
                    day_ = P["days"].setdefault(d, {})
                    day_["cv"] = day_.get("cv", 0) + c
                    day_["pv"] = day_.get("pv", 0) + p_
                P["backfilled"].append(und)
            if snapshot_ok:
                tdate = max(q[4][:10] for q in ch.values())
                day = tdate
                for strike, cp, oi, vol, ts in ch.values():
                    snap["coi" if cp == "C" else "poi"] += oi
                    if ts[:10] == tdate and ts[11:13] < "21":
                        snap["cv" if cp == "C" else "pv"] += vol
        if snapshot_ok and day:
            P["days"][day] = {**P["days"].get(day, {}), **snap}
            print(f"  {prod} {day}: calls vol {snap['cv']:.0f} OI {snap['coi']:.0f} · puts vol {snap['pv']:.0f} OI {snap['poi']:.0f}")
        P["months"] = months
        P["days"] = dict(sorted(P["days"].items())[-KEEP:])
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    data["note"] = "cv/pv = call/put volume, coi/poi = call/put open interest, summed over the tracked option months"
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB); snapshot {'taken' if snapshot_ok else 'skipped (outside 15:00-21:00 Beijing time)'}")


if __name__ == "__main__":
    main()
