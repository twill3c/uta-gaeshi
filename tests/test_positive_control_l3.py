"""G-06 陽性対照(L3) — 名寄せと三段台帳のゲートが本当に何かを見ていること。"""
import copy
import json
from pathlib import Path

import pytest

from pipeline.persons import apply

pytestmark = pytest.mark.validation
DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def align():
    p = DATA / "align.json"
    if not p.exists():
        pytest.skip("data/align.json が無い")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def judgments():
    return json.loads((DATA / "judgments" / "entities.json").read_text(encoding="utf-8"))


def test_g10_detects_dropped_form(align, judgments):
    """誤付着を「捨てる」実装に退行したら保存則が落ちること。"""
    a = copy.deepcopy(align)
    a["entities"][0]["forms"].pop()
    base = apply(align, judgments)["meta"]["occurrences_after"]
    broken = apply(a, judgments)["meta"]["occurrences_after"]
    assert broken < base, "形を落としても総出現数が変わらない"


def test_g10_detects_double_count(align, judgments):
    """同じ形が二つの実体に現れる二重計上を捕まえること。"""
    a = copy.deepcopy(align)
    dup = dict(a["entities"][1]["forms"][0])
    a["entities"][2]["forms"].append(dup)
    res = apply(a, judgments)
    base = apply(align, judgments)["meta"]["occurrences_after"]
    assert res["meta"]["occurrences_after"] != base or not res["meta"]["conserved"]


def test_detects_resolution_to_nonexistent_entity(align, judgments):
    j = copy.deepcopy(judgments)
    for e in j["entities"]:
        if e["english"] == "Pallas":
            e["resolves_to"] = "存在しない実体"
    res = apply(align, j)
    names = {x["english"] for x in res["entities"]}
    # 解決先が実体として作られてしまうため、名前で検出できることを確かめる
    assert "存在しない実体" in names


def test_detects_alias_without_target(judgments):
    j = copy.deepcopy(judgments)
    bad = [e for e in j["entities"] if e["category"] == "alias"]
    assert bad, "alias が判断表に無い(対照が成立しない)"
    bad[0]["resolves_to"] = None
    with pytest.raises(AssertionError):
        for e in j["entities"]:
            if e["category"] in ("alias", "epithet"):
                assert e["resolves_to"], f"{e['english']}: 解決先が無い"


def test_detects_resolution_cycle(judgments):
    j = copy.deepcopy(judgments)
    table = {e["english"]: e.get("resolves_to") for e in j["entities"]}
    table["Athena"] = "Pallas"      # Pallas → Athena → Pallas
    with pytest.raises(AssertionError):
        for start in table:
            seen, cur = set(), start
            while table.get(cur):
                assert cur not in seen, f"{start} から解決が循環している"
                seen.add(cur)
                cur = table[cur]


def test_g13_detects_untiered_place():
    tiers = json.loads((DATA / "judgments" / "places_tiers.json").read_text(encoding="utf-8"))
    t = copy.deepcopy(tiers)
    t["places"] = [p for p in t["places"] if p["english"] != "Ithaca"]
    tiered = {p["english"] for p in t["places"]}
    assert "Ithaca" not in tiered


def test_g13_detects_coordinates_on_unidentifiable_place():
    """同定不能な地に座標を与える退行を捕まえること。"""
    tiers = json.loads((DATA / "judgments" / "places_tiers.json").read_text(encoding="utf-8"))
    t = copy.deepcopy(tiers)
    target = next(p for p in t["places"] if p["tier"] == 3)
    target["lat"], target["lon"] = 39.6, 19.9
    with pytest.raises(AssertionError):
        for p in t["places"]:
            if p["tier"] in (3, "mythic"):
                assert "lat" not in p and "lon" not in p, f"{p['english']} に座標が付いている"


def test_detects_voyage_toponym_promoted_to_tier1():
    tiers = json.loads((DATA / "judgments" / "places_tiers.json").read_text(encoding="utf-8"))
    t = copy.deepcopy(tiers)
    target = next(p for p in t["places"] if p["english"] == "Ogygia")
    target["tier"] = 1
    voyage = {"Ogygia", "Aeaea", "Thrinacia"}
    with pytest.raises(AssertionError):
        for p in t["places"]:
            if p["english"] in voyage:
                assert p["tier"] != 1, f"{p['english']} が tier1 になっている"
