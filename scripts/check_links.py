"""Crawl the live site and report broken links. Used by check_health.py; can also run alone:
    python scripts/check_links.py

- Internal (boonwui.github.io): every page reachable from the home page and sitemap.xml is fetched, and every
  link, script, stylesheet and image on it is checked. Anything that does not load is broken.
- External: each linked URL is requested once. Only clear failures count as broken (404/410 "page gone", or the
  site does not exist). Many sites block automated checks (403, 429) or are slow; those are not reported,
  so the morning email does not cry wolf.
Links built by JavaScript at run time (e.g. stock pages) are not seen; the data checks cover those files.
"""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

import requests

SITE = "https://boonwui.github.io/"
HOST = urlparse(SITE).netloc
UA = {"User-Agent": "Mozilla/5.0 (compatible; boonwui-link-check; +https://github.com/BoonWui/BoonWui.github.io)"}
MAX_PAGES = 300
SKIP = ("mailto:", "tel:", "javascript:", "data:", "#")
# Hosts that only answer real browsers or need a login; checking them gives false alarms.
SKIP_HOSTS = {"www.linkedin.com", "linkedin.com", "fonts.googleapis.com", "fonts.gstatic.com"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("link", "a") and a.get("rel") in ("preconnect", "dns-prefetch"):
            return
        for k in ("href", "src"):
            v = (a.get(k) or "").strip()
            if v and not v.startswith(SKIP):
                self.urls.append(v)


def internal(u):
    return urlparse(u).netloc == HOST


def is_page(u):
    path = urlparse(u).path
    return path.endswith("/") or path.endswith(".html")


def crawl(session, start=SITE):
    """Return (link -> set of pages it appears on, internal results {url: status})."""
    seen_from, status = {}, {}
    todo = [start]
    try:
        sm = session.get(urljoin(start, "sitemap.xml"), timeout=30)
        if sm.ok:
            todo += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm.text)
    except requests.RequestException:
        pass
    done = set()
    while todo and len(done) < MAX_PAGES:
        page = urldefrag(todo.pop())[0]
        if page in done or not internal(page):
            continue
        done.add(page)
        try:
            r = session.get(page, timeout=30)
            status[page] = r.status_code
        except requests.RequestException as e:
            status[page] = type(e).__name__
            continue
        if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
            continue
        p = Links()
        p.feed(r.text)
        for raw in p.urls:
            u = urldefrag(urljoin(page, raw))[0]
            if urlparse(u).scheme not in ("http", "https"):
                continue
            seen_from.setdefault(u, set()).add(page)
            if internal(u) and is_page(u) and u not in done:
                todo.append(u)
    return seen_from, status


def check_one(session, u):
    try:
        r = session.head(u, timeout=20, allow_redirects=True)
        if r.status_code in (405, 403, 400) or r.status_code >= 500:   # some servers refuse HEAD; ask properly
            r = session.get(u, timeout=20, allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except requests.exceptions.ConnectionError as e:
        return "no such site" if "Name or service not known" in str(e) or "getaddrinfo" in str(e) or "NameResolution" in str(e) else "connection failed"
    except requests.RequestException as e:
        return type(e).__name__


def broken(code, is_internal):
    if is_internal:
        return code != 200
    return code in (404, 410, "no such site")


def find_broken(site=SITE):
    """Return (pages_checked, links_checked, [(url, code, [pages])])."""
    s = requests.Session()
    s.headers.update(UA)
    seen_from, status = crawl(s, site)
    todo = [u for u in seen_from if u not in status and urlparse(u).netloc not in SKIP_HOSTS]
    with ThreadPoolExecutor(8) as ex:
        for u, code in zip(todo, ex.map(lambda u: check_one(s, u), todo)):
            status[u] = code
    bad = sorted((u, status[u], sorted(seen_from.get(u, {site}))) for u in status
                 if broken(status[u], internal(u)))
    pages = sum(1 for u in status if internal(u) and is_page(u))
    return pages, len(status), bad


def short(u):
    return u.replace(SITE, "/")


def main():
    pages, n, bad = find_broken()
    print(f"Checked {pages} pages and {n} links.")
    for u, code, on in bad:
        print(f"BROKEN {code}: {u}\n    on {', '.join(short(p) for p in on[:5])}{' …' if len(on) > 5 else ''}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
