"""G-06 陽性対照 — ゲートが本当に何かを見ていることを確かめる。

構造ゲートが常に空リストを返すだけの飾りであっても、G-01 は通ってしまう。
ここでは故意に壊したコーパスを与え、ゲートが**落ちること**を検査する。
壊し方は G-01 が主張する不変条件の一つずつに対応させる。
"""
import pytest

from pipeline.gates import check_repairs, check_structure

pytestmark = pytest.mark.validation


def test_control_baseline_passes(corpus):
    """壊す前は合格していること(対照の前提)。"""
    assert check_structure(corpus) == []


def test_detects_dropped_unit(mutable):
    mutable["units"].pop(100)
    assert check_structure(mutable), "単位を落としても検出されない"


def test_detects_overlapping_assignment(mutable):
    """ある単位の行を別の単位へ複製する = 重複割当。"""
    src, dst = mutable["units"][10], mutable["units"][11]
    dst["greek"].append(dict(src["greek"][0]))
    v = check_structure(mutable)
    assert any("重複" in x for x in v), v


def test_detects_empty_translation(mutable):
    mutable["units"][500]["murray"] = "   "
    v = check_structure(mutable)
    assert any("Murray" in x for x in v), v


def test_detects_missing_greek_lines(mutable):
    mutable["units"][7]["greek"] = []
    v = check_structure(mutable)
    assert any("原典行が無い" in x for x in v), v


def test_detects_missing_book(mutable):
    mutable["units"] = [u for u in mutable["units"] if u["book"] != 12]
    v = check_structure(mutable)
    assert any("巻が" in x for x in v), v


def test_detects_filled_known_gap(mutable):
    """欠番を「親切に」埋めてしまう回帰を捕まえる。"""
    target = next(u for u in mutable["units"] if u["book"] == 10
                  and u["line_start"] <= 456 <= u["line_end"])
    target["greek"].append({"line": 456, "text": "(捏造)"})
    target["greek"].sort(key=lambda g: g["line"])
    v = check_structure(mutable)
    assert any("欠番" in x for x in v), v


def test_detects_broken_monotonicity(mutable):
    u = mutable["units"][3]
    u["greek"] = list(reversed(u["greek"]))
    v = check_structure(mutable)
    assert any("単調" in x for x in v), v


def test_detects_reversed_span(mutable):
    u = mutable["units"][20]
    u["line_start"], u["line_end"] = u["line_end"], u["line_start"]
    v = check_structure(mutable)
    assert any("逆転" in x for x in v), v


def test_detects_lost_repair_record(mutable):
    """出典欠陥の修復記録が消えた/変わったことを検出する。"""
    mutable["repairs"] = [r for r in mutable["repairs"] if r["kind"] != "out_of_range"]
    assert check_repairs(mutable), "修復記録が欠けても検出されない"


def test_detects_unrecorded_transposition(mutable):
    mutable["repairs"] = [r for r in mutable["repairs"] if r["kind"] != "transposed"]
    v = check_repairs(mutable)
    assert any("逆転" in x for x in v), v
