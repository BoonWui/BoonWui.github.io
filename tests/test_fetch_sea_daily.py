import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_sea_daily as F  # noqa: E402

PAGE = (Path(__file__).parent / "fixtures" / "sea_home_2026-11-06.html").read_text(encoding="utf-8", errors="ignore")


def test_parse_saved_page():
    r = F.parse(PAGE)
    assert r["date"] == "2026-11-06"
    assert r["cpo_cf_mumbai_usd"] == 1165 and r["cpo_fob_id_usd"] == 1115 and r["rbd_fob_usd"] == 1055
    assert r["cpo_kandla_inr"] == 124400 and r["rbd_local_inr"] == 135000
    assert r["soy_cif_mumbai_usd"] == 1285 and r["sun_cif_mumbai_usd"] == 1420


def test_not_quoted_is_none():
    page = PAGE.replace("US $/ MT 1420</td>", "US $/ MT NQ</td>")
    assert F.parse(page)["sun_cif_mumbai_usd"] is None


def test_layout_change_is_an_error():
    with pytest.raises(ValueError):
        F.parse(PAGE.replace("Crude Palm Oil (CPO) C&amp;F Mumbai", "Something else"))
    with pytest.raises(ValueError):
        F.parse("<html>no quotes</html>")
