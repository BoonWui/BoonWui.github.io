"""DCE palm oil (P) broker positions: daily top-20 member rankings + daily prices, from Sina Finance.

Writes data/dce_palm_positions.json for the dce-positions page. Contracts: the near month plus the
next 01 / 05 / 09 main months (e.g. P2612, P2701, P2705, P2709). Keeps the last WINDOW_DAYS calendar days.
Incremental: only trading days not yet stored are fetched, one page per contract per day, politely spaced.

Why Sina: the exchange's own data service (dce.com.cn) only answers a real browser that passes its bot
check, so it is not fetched here. Sina republishes the same DCE member rankings as plain pages.
"""
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
# product -> (output file, listed contract months). Run: python scripts/fetch_dce_positions.py p y
PRODUCTS = {"p": ("dce_palm_positions.json", list(range(1, 13))), "y": ("dce_soyoil_positions.json", [1, 3, 5, 7, 8, 9, 11, 12])}
OUT = ROOT / "data" / "dce_palm_positions.json"
WINDOW_DAYS = 185
PAUSE = 1.5           # seconds between Sina requests
MAX_FETCH = 700       # safety cap per run (a full backfill of 4 contracts is ~520 pages)

RANK_URL = "https://vip.stock.finance.sina.com.cn/q/view/vFutures_Positions_cjcc.php"
KLINE_URL = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/InnerFuturesNewService.getDailyKLine"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)", "Referer": "https://finance.sina.com.cn/"}
S = requests.Session()
S.headers.update(HEADERS)


# ---------- contracts ----------
def _add(y, m, k):
    t = y * 12 + (m - 1) + k
    return t // 12, t % 12 + 1


def _last_trading_day(y, m):
    """DCE: the 10th trading day of the delivery month (weekdays; holidays ignored)."""
    d, n = date(y, m, 1), 0
    while True:
        if d.weekday() < 5:
            n += 1
            if n == 10:
                return d
        d += timedelta(days=1)


def active_contracts(today=None, prod="p"):
    today = today or date.today()
    listed = PRODUCTS[prod][1]
    y, m = today.year, today.month
    # near month: the first month whose contract is still trading
    k = 0
    while _add(y, m, k)[1] not in listed or _last_trading_day(*_add(y, m, k)) < today:
        k += 1
    near = _add(y, m, k)
    out = [near]
    # the next three main months (01 / 05 / 09) after the near month
    j = 1
    while len(out) < 4:
        ym = _add(*near, j)
        if ym[1] in (1, 5, 9):
            out.append(ym)
        j += 1
    return [prod.upper() + "%02d%02d" % (yy % 100, mm) for yy, mm in out]


# ---------- Sina ----------
def get(url, params=None, tries=4):
    for i in range(tries):
        try:
            r = S.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} {url}")
        except requests.RequestException as e:
            print(f"  retry {i + 1}: {e.__class__.__name__}")
        time.sleep(5 * (i + 1))
    return None


def fetch_prices(code):
    """Daily OHLC, volume and open interest for one contract: [[date, o, h, l, c, vol, oi], ...]."""
    r = get(KLINE_URL, {"symbol": code})
    if r is None:
        return []
    m = re.search(r"\((\[.*\])\)", r.text, re.S)
    if not m:
        return []
    rows = []
    for k in json.loads(m.group(1)):
        try:
            rows.append([k["d"], float(k["o"]), float(k["h"]), float(k["l"]), float(k["c"]), int(float(k["v"])), int(float(k["p"]))])
        except (KeyError, ValueError):
            pass
    return rows


def _table(html, list_id):
    i = html.find(f'id="{list_id}"')
    if i < 0:
        return []
    j = html.find("</table>", i)
    out = []
    for tr in re.findall(r"<tr>(.*?)</tr>", html[i:j], re.S):
        tds = [re.sub(r"<[^>]+>", "", td).strip() for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(tds) == 4 and tds[0].isdigit():
            try:
                out.append([tds[1], int(tds[2].replace(",", "")), int(tds[3].replace(",", ""))])
            except ValueError:
                pass
    return out


def fetch_ranking(code, d):
    """Top-20 volume / long / short for one contract and day. None = request failed, {} = no ranking that day."""
    r = get(RANK_URL, {"t_breed": code, "t_date": d})
    if r is None:
        return None
    html = r.content.decode("gb18030", errors="replace")
    v, l, s = _table(html, "listdeal"), _table(html, "listbuy"), _table(html, "listsell")
    if not (v or l or s):
        return {}
    return {"v": v, "l": l, "s": s}


# ---------- main ----------
def main(prod="p"):
    global OUT
    OUT = ROOT / "data" / PRODUCTS[prod][0]
    today = date.today()
    start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"contracts": {}}
    old = data.get("contracts", {})
    codes = active_contracts(today, prod)
    print("Contracts:", ", ".join(codes))
    contracts, fetched, added = {}, 0, 0
    for code in codes:
        c = old.get(code, {"prices": [], "days": {}})
        prices = fetch_prices(code) or c.get("prices", [])
        time.sleep(PAUSE)
        prices = [p for p in prices if p[0] >= start]
        days = {d: v for d, v in c.get("days", {}).items() if d >= start}
        last_px = prices[-1][0] if prices else None
        recheck = (today - timedelta(days=7)).isoformat()   # Sina sometimes posts a day late: retry recent empty days
        todo = [p[0] for p in prices if p[5] > 0 and (p[0] not in days or (not days[p[0]] and p[0] >= recheck))]
        for d in todo:
            if fetched >= MAX_FETCH:
                break
            rk = fetch_ranking(code, d)
            fetched += 1
            time.sleep(PAUSE)
            if rk is None:
                continue
            if not rk and d >= recheck:
                days.pop(d, None)
                continue          # not posted yet: try again on the next runs for a week
            days[d] = rk          # {} = contract too thin to be ranked that day
            added += 1 if rk else 0
        contracts[code] = {"prices": prices, "days": dict(sorted(days.items()))}
        n = sum(1 for v in days.values() if v)
        print(f"  {code}: {len(prices)} price days, {n} ranking days")
    if contracts == old and OUT.exists():
        print("Nothing new; file left unchanged.")
        return
    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": "DCE member rankings and daily prices via Sina Finance",
        "window_days": WINDOW_DAYS,
        "contracts": contracts,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Fetched {fetched} ranking pages, {added} new ranking days. Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")
    if not any(c["prices"] for c in contracts.values()):
        sys.exit("No prices fetched")


if __name__ == "__main__":
    for prod in (sys.argv[1:] or ["p"]):
        main(prod)
