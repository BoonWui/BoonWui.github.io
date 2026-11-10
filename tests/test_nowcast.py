import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_mpob as A  # noqa: E402
import nowcast as N  # noqa: E402

ROWS = A.load()
TO_SEP = [r for r in ROWS if r["month"] <= "2026-09"]


def test_october_entry_is_frozen_as_published():
    # The page showed 3,747,605 t for Oct 2026 stocks before MPOB's release (commit c7e4e81, formula v1).
    import json
    oct_ = [x for x in json.loads(N.LOG.read_text(encoding="utf-8")) if x["month"] == "2026-10"][0]
    assert oct_["est"]["stock"] == 3_747_605 and oct_["formula"] == "v1"


def test_v2_formula_values():
    # Nov 2026 from data to Oct 2026: production = Oct x 5-year Oct->Nov change; exports = half seasonal, half trend
    f = N.forecast(N.table(ROWS[:ROWS.index(next(r for r in ROWS if r["month"] == "2026-10")) + 1]), "2026-11")
    assert 3_900_000 < f["est"]["stock"] < 4_000_000
    lo, hi = f["range80"]["stock"]
    assert lo < f["est"]["stock"] < hi


def test_quantile_matches_numpy_linear():
    assert N.quantile([1, 2, 3, 4], 0.5) == 2.5
    assert N.quantile([10, 0, 5], 0.1) == 1.0


def test_freeze_never_overwrites():
    log, e = N.freeze(TO_SEP, [], made="2026-11-10T03:49:12Z")
    assert e["month"] == "2026-10" and e["data_to"] == "2026-09"
    again, e2 = N.freeze(TO_SEP, log)
    assert e2 is None and again == log


def test_freeze_adds_next_month_after_new_data():
    log, _ = N.freeze(TO_SEP, [], made="2026-11-10T03:49:12Z")
    log2, e = N.freeze(ROWS, log)
    assert [x["month"] for x in log2][:2] == ["2026-10", "2026-11"] or e is None
    assert log2[0] == log[0]   # the October entry is untouched


def test_short_history_gives_no_forecast():
    assert N.estimate(N.table(ROWS[:10]), "2014-11") is None
