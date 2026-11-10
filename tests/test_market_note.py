import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_feed as F  # noqa: E402
import write_market_note as W  # noqa: E402


def test_note_uses_latest_mpob_month_and_saved_forecasts():
    d = W.gather()
    assert d["M"] == max(r["month"] for r in W.A.load())
    assert d["next"]["month"] == W.N.add(d["M"], 1)
    title, desc, txt = W.render(d, datetime(2026, 11, 10, tzinfo=timezone.utc))
    assert title.startswith("Palm oil market note, ")
    assert "Not financial advice" in txt and "makes no forecast of prices" in txt
    assert f"{d['P']['stock'] / 1000:,.0f}k t" in txt


def test_biggest_miss_by_effect_on_stocks():
    P = {"prod": 2_154_000, "imp": 26_000, "exp": 1_709_000, "dom": 361_000}
    est = {"prod": 2_119_000, "imp": 52_000, "exp": 1_553_000, "dom": 382_000}
    assert W.biggest_miss(P, est)[0] == "exports"


def test_oni_labels():
    assert W.oni_label(2.46) == "a strong El Niño" and W.oni_label(0.7) == "an El Niño"
    assert W.oni_label(-0.8) == "La Niña" and W.oni_label(0.1) == "neutral"


def test_feed_is_valid_rss_with_notes_and_articles():
    items = F.collect()
    rss = ET.fromstring(F.render(items))
    links = [i.findtext("link") for i in rss.iter("item")]
    assert any("/market-notes/" in u for u in links) and any("/blog/" in u for u in links)
    assert len(links) == len(set(links))
