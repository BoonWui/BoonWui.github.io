import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fetch_mpob as F  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "mpob_report_2026_09.html"


@pytest.fixture(scope="module")
def rep():
    return F.parse_report(FIX.read_text(encoding="utf-8", errors="ignore"))


def test_parse_saved_report(rep):
    assert rep["month"] == "2026-09"
    assert rep["cur"] == {"prod": 2_116_950, "stock": 3_510_554, "exp": 1_097_074, "imp": 58_064}
    assert rep["prev"] == {"prod": 1_817_499, "stock": 2_819_061, "exp": 1_275_349, "imp": 49_524}


def test_brackets_are_negative():
    assert F.to_int("(178,276)") == -178_276


def rows_to(month_rows):
    return [{"month": m, "production_t": p, "imports_t": i, "exports_t": e, "domestic_t": d, "end_stocks_t": s}
            for m, p, i, e, d, s in month_rows]


def test_adds_new_month_and_revises_previous(rep):
    rows = rows_to([("2026-07", 1_792_596, 49_566, 1_399_579, 358_515, 2_627_898),
                    ("2026-08", 1_817_499, 49_524, 1_275_099, 400_761, 2_819_061)])
    new, notes, blocking = F.apply(rows, rep)
    assert blocking == []
    assert [r["month"] for r in new] == ["2026-07", "2026-08", "2026-09"]
    assert new[1]["exports_t"] == 1_275_349 and new[1]["domestic_t"] == 400_511
    assert new[2]["domestic_t"] == 2_819_061 + 2_116_950 + 58_064 - 1_097_074 - 3_510_554
    assert any("revised" in n for n in notes)


def test_up_to_date_is_a_no_op(rep):
    rows = rows_to([("2026-07", 1_792_596, 49_566, 1_399_579, 358_515, 2_627_898),
                    ("2026-08", 1_817_499, 49_524, 1_275_099, 400_761, 2_819_061)])
    once, _, _ = F.apply(rows, rep)
    twice, notes, _ = F.apply(once, rep)
    assert twice == once and notes == []


def test_missing_month_is_an_error(rep):
    rows = rows_to([("2026-06", 1_638_796, 103_113, 1_215_850, 410_201, 2_543_830),
                    ("2026-07", 1_792_596, 49_566, 1_399_579, 358_515, 2_627_898)])
    with pytest.raises(ValueError):
        F.apply(rows, rep)


def test_layout_change_is_an_error():
    with pytest.raises(ValueError):
        F.parse_report("<html><h1>PERFORMANCE OF THE MALAYSIAN PALM OIL INDUSTRY, OCTOBER 2026</h1><table></table></html>")
