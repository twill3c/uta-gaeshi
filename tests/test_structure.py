"""G-01 構造ゲート — 本物のコーパスが不変条件を満たすこと。"""
import pytest

from pipeline.gates import (
    BOOKS, GREEK_LINES, KNOWN_GAPS, UNITS, check_repairs, check_structure,
)

pytestmark = pytest.mark.validation


def test_g01_structure_clean(corpus):
    assert check_structure(corpus) == []


def test_g01_repairs_match_known_defects(corpus):
    assert check_repairs(corpus) == []


def test_meta_counts(corpus):
    m = corpus["meta"]
    assert m["books"] == BOOKS
    assert m["greek_lines"] == GREEK_LINES
    assert len(corpus["units"]) == UNITS


def test_units_partition_greek_lines(corpus):
    seen = set()
    for u in corpus["units"]:
        for g in u["greek"]:
            key = (u["book"], g["line"])
            assert key not in seen, f"{key} が重複割当"
            seen.add(key)
    assert len(seen) == GREEK_LINES


def test_known_gaps_are_absent_not_filled(corpus):
    """校訂で削除された行は埋めない。番号だけが欠けている状態を保つ。"""
    present = {(u["book"], g["line"]) for u in corpus["units"] for g in u["greek"]}
    for book, gaps in KNOWN_GAPS.items():
        for line in gaps:
            assert (book, line) not in present, f"{book}.{line} は欠番のはず"


def test_every_unit_has_both_editions(corpus):
    for u in corpus["units"]:
        assert u["greek"], f"{u['id']}: 原典行が無い"
        assert u["murray"].strip(), f"{u['id']}: Murray 訳が空"
        assert u["butler"], f"{u['id']}: Butler 訳の対応区間が無い"


def test_line_span_matches_greek_lines(corpus):
    for u in corpus["units"]:
        lines = [g["line"] for g in u["greek"]]
        assert min(lines) >= u["line_start"]
        assert max(lines) <= u["line_end"]
