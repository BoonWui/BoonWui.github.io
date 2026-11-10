"""Write the monthly palm oil market note after each MPOB release: market-notes/YYYY-MM.html + index.

The note is named after the month it is issued in (the month after the MPOB data month) and is written once:
later runs leave an existing note alone, so the archive shows what was known at the time (--force rewrites it).
It only describes the data (MPOB, World Bank, NOAA, Open-Meteo, EIA, Bank Negara) and the site's own nowcast;
it makes no price calls. Run after nowcast.py:  python scripts/write_market_note.py
"""
import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone

import add_mpob as A
import nowcast as N

ROOT = A.ROOT
OUT = ROOT / "market-notes"
MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
       "November", "December"]
BBL_PER_T = 7.33


def ml(m):
    y, mo = m.split("-")
    return f"{MON[int(mo) - 1]} {y}"


def kt(v):
    return f"{round(v / 1000):,}"


def mt(v):
    return f"{v / 1e6:.2f}"


def pct(a, b):
    return (a / b - 1) * 100


def sg(v, d=1):
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.{d}f}"


def load_json(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def gather():
    """Collect every number the note uses into one dict (also what the tests check)."""
    by = N.table(A.load())
    M = max(by)
    P, PP, Y = by[M], by[N.add(M, -1)], by.get(N.add(M, -12))
    hist = [by[m]["stock"] for m in by if m < M]
    log = N.load_log()
    L = next((x for x in log if x["month"] == M), None)
    nxt = next((x for x in log if x["month"] == N.add(M, 1)), None) or {"month": N.add(M, 1), **N.forecast(by, N.add(M, 1))}

    palm = load_json("palm-oil-monitor/data.json")
    pr = palm["prices"]
    pl, p1 = pr[-1], pr[-2]
    p12 = next((x for x in pr if x["month"] == N.add(pl["month"], -12)), None)
    oni = palm["oni"][-1]

    w = load_json("weather-monitor/data.json")
    last_full = N.add(datetime.now(timezone.utc).strftime("%Y-%m"), -1)

    def rain(country):
        vals = []
        for r in w["regions"]:
            if r["country"] == country and last_full in r["monthly"]:
                vals.append(r["monthly"][last_full] / r["normal"][int(last_full[5:]) - 1] * 100)
        return sum(vals) / len(vals) if vals else None

    e = load_json("energy-monitor/data.json")

    def last(key):
        return next((d, v) for d, v in zip(reversed(e["dates"]), reversed(e[key])) if v is not None)

    out = {
        "M": M, "P": P, "PP": PP, "Y": Y, "record": P["stock"] > max(hist), "L": L, "next": nxt,
        "price": pl, "price_prev": p1, "price_yago": p12, "oni": oni,
        "rain_month": last_full, "rain_my": rain("Malaysia"), "rain_id": rain("Indonesia"),
        "brent": last("brent"), "usdmyr": last("usdmyr"),
    }
    return out


def oni_label(a):
    return "a strong El Niño" if a >= 1.5 else "an El Niño" if a >= 0.5 else "La Niña" if a <= -0.5 else "neutral"


def biggest_miss(P, est):
    eff = [("production", P["prod"] - est["prod"], 1), ("imports", P["imp"] - est["imp"], 1),
           ("exports", P["exp"] - est["exp"], -1), ("domestic use", P["dom"] - est["dom"], -1)]
    return max(eff, key=lambda x: abs(x[1]))


def render(d, issued):
    M, P, PP, Y, L, nx = d["M"], d["P"], d["PP"], d["Y"], d["L"], d["next"]
    chg = P["stock"] - PP["stock"]
    pr, p1, p12 = d["price"], d["price_prev"], d["price_yago"]
    issue_m = N.add(M, 1)
    title = f"Palm oil market note, {ml(issue_m)}"
    lead = (f"Malaysian palm oil stocks {'rose' if chg >= 0 else 'fell'} {kt(abs(chg))}k tonnes to {mt(P['stock'])} million "
            f"at the end of {MON[int(M[5:]) - 1]}{', the highest since this data set starts in 2014' if d['record'] else ''}. "
            f"The site's model puts {MON[int(nx['month'][5:]) - 1]} stocks at {mt(nx['est']['stock'])} million "
            f"(likely {mt(nx['range80']['stock'][0])}–{mt(nx['range80']['stock'][1])}).")
    desc = re.sub(r"\s+", " ", lead)

    s = []
    s.append(f"<h2>MPOB: {ml(M)}</h2><ul>"
             f"<li><b>Stocks</b> {kt(P['stock'])}k t, {sg(chg / 1000, 0)}k t on the month ({sg(pct(P['stock'], PP['stock']))}%)"
             + (f" and {sg(pct(P['stock'], Y['stock']))}% on a year earlier" if Y else "") + ".</li>"
             f"<li><b>Production</b> {kt(P['prod'])}k t ({sg(pct(P['prod'], PP['prod']))}% m/m"
             + (f", {sg(pct(P['prod'], Y['prod']))}% y/y" if Y else "") + ").</li>"
             f"<li><b>Exports</b> {kt(P['exp'])}k t ({sg(pct(P['exp'], PP['exp']))}% m/m"
             + (f", {sg(pct(P['exp'], Y['exp']))}% y/y" if Y else "") + ").</li>"
             f"<li><b>Imports</b> {kt(P['imp'])}k t; <b>domestic use</b> {kt(P['dom'])}k t (worked out from the stock balance).</li></ul>")

    nb = []
    if L:
        miss = P["stock"] - L["est"]["stock"]
        lo, hi = L["range80"]["stock"]
        name, diff, sign = biggest_miss(P, L["est"])
        nb.append(f"The forecast saved before the release was {kt(L['est']['stock'])}k t. The actual figure was {kt(abs(miss))}k t "
                  f"{'below' if miss < 0 else 'above'} it, {'inside' if lo <= P['stock'] <= hi else 'outside'} the likely range of "
                  f"{kt(lo)}–{kt(hi)}k t. The biggest miss was {name}: {kt(abs(diff))}k t {'more' if diff > 0 else 'less'} than forecast.")
    e = nx["est"]
    nb.append(f"For {ml(nx['month'])} the model expects production of about {kt(e['prod'])}k t, exports of {kt(e['exp'])}k t "
              f"and stocks of {kt(e['stock'])}k t (likely {kt(nx['range80']['stock'][0])}–{kt(nx['range80']['stock'][1])}k t). "
              f"MPOB is due to publish around 10 {MON[int(N.add(nx['month'], 1)[5:]) - 1]}.")
    s.append("<h2>Against the nowcast</h2>" + "".join(f"<p>{x}</p>" for x in nb))

    pogo = pr["palm"] - pr["brent"] * BBL_PER_T
    s.append(f"<h2>Prices: {ml(pr['month'])} averages</h2><ul>"
             f"<li><b>Palm oil</b> ${round(pr['palm']):,}/t ({sg(pct(pr['palm'], p1['palm']))}% m/m"
             + (f", {sg(pct(pr['palm'], p12['palm']))}% y/y" if p12 else "") + ").</li>"
             f"<li><b>Soybean oil</b> ${round(pr['soy']):,}/t, so palm is ${abs(round(pr['palm'] - pr['soy'])):,}/t "
             f"{'below' if pr['palm'] < pr['soy'] else 'above'} soy.</li>"
             f"<li><b>Brent</b> ${pr['brent']:.1f}/bbl; palm is ${abs(round(pogo)):,}/t {'above' if pogo > 0 else 'below'} crude per tonne.</li></ul>")

    o = d["oni"]
    wl = [f"The El Niño index (ONI) is {sg(o['anom'], 2)}°C for {o['season']} {o['year']}, {oni_label(o['anom'])}. "
          "Dry spells usually show up in palm output 6–12 months later."]
    if d["rain_my"] is not None and d["rain_id"] is not None:
        wl.append(f"Rain in {ml(d['rain_month'])} was {round(d['rain_my'])}% of normal across the Malaysian palm belts and "
                  f"{round(d['rain_id'])}% across the Indonesian ones.")
    s.append("<h2>Weather</h2><p>" + " ".join(wl) + "</p>")

    (bd, bv), (fd, fv) = d["brent"], d["usdmyr"]
    s.append(f"<h2>Energy and the ringgit</h2><p>Brent was ${bv:.2f}/bbl on {bd} (EIA) and the ringgit {fv:.4f} per US dollar "
             f"on {fd} (Bank Negara noon rate).</p>")

    links = ('<div class="cta">Live numbers: <a href="../mpob-nowcast/">MPOB Nowcast</a> · '
             '<a href="../palm-oil-monitor/">Palm Oil Market Monitor</a> · <a href="../weather-monitor/">Weather Monitor</a> · '
             '<a href="../energy-monitor/">Veg Oil &amp; Energy Monitor</a> · <a href="./">All market notes</a></div>')
    srcs = ('<p class="foot">Written automatically from public data on the day MPOB published: MPOB (monthly release), '
            'World Bank Pink Sheet (monthly averages), NOAA (ONI), Open-Meteo (ERA5), EIA and Bank Negara Malaysia. '
            'It describes the data and makes no forecast of prices. For education only. <b>Not financial advice.</b></p>')
    return title, desc, page(title, desc, f"{issue_m}.html", issued,
                             f'<span class="meta">{issued:%d %B %Y} · MPOB {ml(M)} data</span><h1>{html.escape(title)}</h1>'
                             f'<p class="lede">{lead}</p>' + "".join(s) + links + srcs)


def page(title, desc, path, issued, body):
    t, dsc = html.escape(title), html.escape(desc)
    url = f"https://boonwui.github.io/market-notes/{path}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{t}</title>
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:site_name" content="BoonWui">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{dsc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://boonwui.github.io/assets/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#1f6f4a">
<meta name="description" content="{dsc}">
<meta property="article:published_time" content="{issued:%Y-%m-%d}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700;12..96,800&family=Source+Sans+3:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="../assets/app.css">
<link rel="stylesheet" href="../blog/blog.css">
<script src="../assets/site.js"></script>
</head>
<body>
<div class="app">
  <div class="top"><a href="./">← All market notes</a><a href="../">Portfolio</a></div>
  <p class="disclaimer" role="note"><b>Disclaimer:</b> Data may be delayed, incomplete or inaccurate. The nowcast is a simple model and can be well off. For education and research only. Use at your own risk. <b>Not financial advice.</b></p>
  <article class="post">
    {body}
  </article>
</div>
</body>
</html>
"""


def write_index():
    notes = []
    for f in sorted(OUT.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].html"), reverse=True):
        txt = f.read_text(encoding="utf-8")
        title = html.unescape(re.search(r"<title>(.*?)</title>", txt).group(1))
        desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', txt).group(1))
        date = re.search(r'article:published_time" content="([\d-]+)"', txt).group(1)
        notes.append((f.name, title, desc, date))
    items = "\n".join(
        f'      <article class="entry">\n        <span class="meta">{datetime.strptime(d, "%Y-%m-%d"):%d %B %Y}</span>\n'
        f'        <a href="{n}">{html.escape(t)}</a>\n        <p>{html.escape(s)}</p>\n      </article>' for n, t, s, d in notes)
    body = f"""<div class="list">
    <header>
      <h1>Palm market notes</h1>
      <p class="lede">A short note on the Malaysian palm oil market, written automatically from public data each month on the day MPOB publishes. It records what the data showed and how the site's nowcast did. Follow along with the <a href="../feed.xml">RSS feed</a>.</p>
    </header>
    <div>
{items}
    </div>
  </div>"""
    idx = page("Palm market notes", "Monthly notes on the Malaysian palm oil market, written automatically from public data on MPOB release day.",
               "", datetime.now(timezone.utc), "")
    idx = idx.replace('<a href="./">← All market notes</a>', '<a href="../">← BoonWui portfolio</a>').replace(
        '<a href="../">Portfolio</a>', '<a href="../blog/">Notes</a>').replace(
        'https://boonwui.github.io/market-notes/"', 'https://boonwui.github.io/market-notes/"')
    idx = re.sub(r'<meta property="article:published_time"[^>]*>\n', "", idx).replace('og:type" content="article"', 'og:type" content="website"')
    idx = idx.replace('<article class="post">\n    \n  </article>', body)
    (OUT / "index.html").write_text(idx, encoding="utf-8")
    return len(notes)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="rewrite this month's note if it exists")
    a = ap.parse_args(argv)
    d = gather()
    issued = datetime.now(timezone.utc)
    path = OUT / f"{N.add(d['M'], 1)}.html"
    OUT.mkdir(exist_ok=True)
    if path.exists() and not a.force:
        print(f"{path.name} already written; leaving it as it was.")
    else:
        title, desc, txt = render(d, issued)
        path.write_text(txt, encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}: {desc}")
    print(f"Index lists {write_index()} note(s).")
    add_to_sitemap(path.name, issued)
    return 0


def add_to_sitemap(name, issued):
    sm = ROOT / "sitemap.xml"
    url = f"https://boonwui.github.io/market-notes/{name}"
    s = sm.read_text(encoding="utf-8")
    if url not in s:
        s = s.replace("</urlset>", f"  <url><loc>{url}</loc><lastmod>{issued:%Y-%m-%d}</lastmod></url>\n</urlset>")
        sm.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
