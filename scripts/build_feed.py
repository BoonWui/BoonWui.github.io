"""Build feed.xml (RSS 2.0): the monthly palm market notes and the articles in blog/.

Run after write_market_note.py (the update-mpob workflow does), or after adding an article to blog/index.html.
Dates come from each page's article:published_time, then sitemap.xml, then today.
    python scripts/build_feed.py
"""
import html
import re
import sys
from datetime import datetime, timezone
from email.utils import format_datetime

import add_mpob as A

ROOT = A.ROOT
SITE = "https://boonwui.github.io/"
MAX_ITEMS = 50


def meta(txt, pattern):
    m = re.search(pattern, txt)
    return html.unescape(m.group(1)) if m else None


def lastmods():
    sm = ROOT / "sitemap.xml"
    if not sm.exists():
        return {}
    return dict(re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([\d-]+)</lastmod>", sm.read_text(encoding="utf-8")))


def item(path, lm):
    """(date, title, url, description) for one page, read from its own head."""
    txt = (ROOT / path).read_text(encoding="utf-8")
    url = SITE + path
    title = meta(txt, r'<meta property="og:title" content="(.*?)">') or meta(txt, r"<title>(.*?)</title>")
    desc = meta(txt, r'<meta name="description" content="(.*?)">') or ""
    date = meta(txt, r'article:published_time" content="([\d-]+)"') or lm.get(url) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc), title, url, desc


def collect():
    lm = lastmods()
    paths = [f"market-notes/{f.name}" for f in (ROOT / "market-notes").glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].html")]
    blog = (ROOT / "blog" / "index.html").read_text(encoding="utf-8")
    paths += [f"blog/{h}" for h in dict.fromkeys(re.findall(r'<article class="entry">\s*<span class="meta">[^<]*</span>\s*<a href="([^"/]+\.html)"', blog))]
    items = [item(p, lm) for p in paths if (ROOT / p).exists()]
    return sorted(items, key=lambda x: (x[0], x[2]), reverse=True)[:MAX_ITEMS]


def render(items):
    esc = html.escape
    body = "\n".join(
        f"    <item>\n      <title>{esc(t)}</title>\n      <link>{u}</link>\n      <guid isPermaLink=\"true\">{u}</guid>\n"
        f"      <pubDate>{format_datetime(d)}</pubDate>\n      <description>{esc(s)}</description>\n    </item>"
        for d, t, u, s in items)
    built = format_datetime(items[0][0]) if items else format_datetime(datetime.now(timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>BoonWui: palm oil notes</title>
    <link>{SITE}</link>
    <atom:link href="{SITE}feed.xml" rel="self" type="application/rss+xml"/>
    <description>Monthly palm oil market notes written on MPOB release day, and articles on palm oil markets, trading models and the code behind them. Not financial advice.</description>
    <language>en</language>
    <lastBuildDate>{built}</lastBuildDate>
{body}
  </channel>
</rss>
"""


def main():
    items = collect()
    (ROOT / "feed.xml").write_text(render(items), encoding="utf-8")
    print(f"feed.xml: {len(items)} items, newest: {items[0][1] if items else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
