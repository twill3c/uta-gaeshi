"""G-06 陽性対照(L2) — 測定のゲートが本当に何かを見ていることを確かめる。

L1 と同じ構え: 本物では空、故意に壊すと非空。不変量を足したら対照も足す。
"""
import copy
import json
from pathlib import Path

import pytest

from pipeline.formulas import build as build_formulas
from pipeline.gates import check_formulas, check_places, check_speakers
from pipeline.speakers import analyse

pytestmark = pytest.mark.validation
DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def formulas(corpus):
    return build_formulas(corpus)


@pytest.fixture(scope="module")
def speakers(corpus):
    return analyse(corpus)


@pytest.fixture(scope="module")
def places():
    p = DATA / "places.json"
    if not p.exists():
        pytest.skip("data/places.json が無い")
    return json.loads(p.read_text(encoding="utf-8"))


def test_baselines_pass(formulas, speakers, places):
    assert check_formulas(formulas) == []
    assert check_speakers(speakers) == []
    assert check_places(places) == []


def test_detects_singleton_in_repeated_groups(formulas):
    f = copy.deepcopy(formulas)
    f["repeated_lines"][0]["count"] = 1
    assert check_formulas(f)


def test_detects_occurrence_count_mismatch(formulas):
    f = copy.deepcopy(formulas)
    f["repeated_lines"][5]["occurrences"].pop()
    assert check_formulas(f)


def test_detects_broken_constraint_derivation(formulas):
    f = copy.deepcopy(formulas)
    f["meta"]["equality_constraints"] += 1
    v = check_formulas(f)
    assert any("強制等値制約" in x for x in v), v


def test_detects_genitive_promoted_to_speaker(speakers):
    """loop_002 で実際に起きた誤判定の再発を捕まえる。"""
    s = copy.deepcopy(speakers)
    for line in s["speech_lines"]:
        for n in line["names"]:
            if n["case"] == "gen":
                n["role"] = "speaker"
                break
        else:
            continue
        break
    v = check_speakers(s)
    assert any("役割 speaker なのに格 gen" in x for x in v), v


def test_detects_role_given_to_ambiguous_case(speakers):
    s = copy.deepcopy(speakers)
    for line in s["speech_lines"]:
        for n in line["names"]:
            if n["case"] == "amb":
                n["role"] = "speaker"
                break
        else:
            continue
        break
    assert check_speakers(s)


def test_detects_place_count_mismatch(places):
    p = copy.deepcopy(places)
    p["places"][0]["occurrences"].pop()
    v = check_places(p)
    assert any("count と出現数が不一致" in x for x in v), v


def test_detects_out_of_range_book(places):
    p = copy.deepcopy(places)
    p["places"][0]["occurrences"][0]["book"] = 99
    assert check_places(p)


def test_detects_dropped_place(places):
    p = copy.deepcopy(places)
    p["places"].pop()
    assert check_places(p)
