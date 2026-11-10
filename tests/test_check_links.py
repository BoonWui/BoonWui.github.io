import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_links as C  # noqa: E402


def test_parser_skips_mail_anchor_and_preconnect():
    p = C.Links()
    p.feed('<a href="/about/">a</a><a href="mailto:x@y.z">m</a><a href="#top">t</a>'
           '<link rel="preconnect" href="https://fonts.gstatic.com"><img src="assets/i.png"><script src="x.js"></script>')
    assert p.urls == ["/about/", "assets/i.png", "x.js"]


def test_internal_must_load():
    assert C.broken(404, True) and C.broken(403, True) and not C.broken(200, True)


def test_external_only_clear_failures():
    assert C.broken(404, False) and C.broken(410, False) and C.broken("no such site", False)
    assert not C.broken(403, False) and not C.broken(429, False) and not C.broken(503, False)
    assert not C.broken("ReadTimeout", False)


def test_page_detection():
    assert C.is_page("https://boonwui.github.io/blog/") and C.is_page("https://boonwui.github.io/a.html")
    assert not C.is_page("https://boonwui.github.io/assets/app.css")
