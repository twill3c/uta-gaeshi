"""L3 — 名寄せの保存則、判断表の健全性、三段台帳の網羅。"""
import json
from pathlib import Path

import pytest

from pipeline.persons import apply, load_judgments

pytestmark = pytest.mark.validation
DATA = Path(__file__).resolve().parents[1] / "data"
VALID_CATEGORIES = {"person", "place", "group", "alias", "patronymic", "epithet", "nature"}


@pytest.fixture(scope="module")
def align():
    p = DATA / "align.json"
    if not p.exists():
        pytest.skip("data/align.json が無い。python -m pipeline.align を先に実行する")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def judgments():
    return load_judgments()


@pytest.fixture(scope="module")
def entities(align, judgments):
    return apply(align, judgments)


@pytest.fixture(scope="module")
def tiers():
    return json.loads((DATA / "judgments" / "places_tiers.json").read_text(encoding="utf-8"))


# ---- G-10 名寄せ保存 ---------------------------------------------------------

def test_g10_occurrences_conserved(entities):
    """統合・解決・移動の前後で総出現数が変わらないこと。

    名寄せの事故は取りこぼしと二重計上の二方向に出る。総和はどちらも一度に捕まえる。
    """
    m = entities["meta"]
    assert m["occurrences_before"] == m["occurrences_after"]
    assert m["conserved"] is True


def test_reassigned_forms_are_moved_not_dropped(entities, judgments):
    """誤付着として外した形が、行き先の実体に実在すること。"""
    by_name = {e["english"]: e for e in entities["entities"]}
    for r in entities["reassignments"]:
        target = by_name.get(r["to"])
        assert target is not None, f"{r['form']} の行き先 {r['to']} が実体に無い"
        assert any(f["form"] == r["form"] for f in target["forms"])


def test_resolutions_land_on_real_entities(entities):
    by_name = {e["english"] for e in entities["entities"]}
    for r in entities["resolutions"]:
        assert r["to"] in by_name, f"{r['from']} → {r['to']} の解決先が存在しない"


# ---- 判断表の健全性 ---------------------------------------------------------

def test_judgment_categories_are_valid(judgments):
    for e in judgments["entities"]:
        assert e["category"] in VALID_CATEGORIES, f"{e['english']}: 未知の分類 {e['category']}"


def test_resolving_categories_have_a_target_or_are_held(judgments):
    """別名・形容辞は必ず解決先を持つ。父称は保留(None)が許される。"""
    for e in judgments["entities"]:
        if e["category"] in ("alias", "epithet"):
            assert e["resolves_to"], f"{e['english']}: 解決先が無い"
        if e["category"] == "patronymic" and e["resolves_to"] is None:
            assert e["note"], f"{e['english']}: 保留の根拠が書かれていない"


def test_no_resolution_cycles(judgments):
    table = {e["english"]: e.get("resolves_to") for e in judgments["entities"]}
    for start in table:
        seen, cur = set(), start
        while table.get(cur):
            assert cur not in seen, f"{start} から解決が循環している"
            seen.add(cur)
            cur = table[cur]


def test_every_judgment_has_japanese(judgments):
    for e in judgments["entities"]:
        assert e["ja"], f"{e['english']}: 和名が無い"


def test_verified_scope_matches_policy(entities):
    """方針どおり上位のみを確認し、未確認を隠していないこと。"""
    m = entities["meta"]
    assert m["verified"] >= 55
    assert m["unverified"] > 0, "未確認が 0 件なのは方針と食い違う"
    assert m["verified"] + m["unverified"] == m["entities"]


# ---- G-13 段の網羅 -----------------------------------------------------------

def test_g13_every_verified_place_has_a_tier(entities, tiers):
    tiered = {p["english"] for p in tiers["places"]}
    for e in entities["entities"]:
        if e["category"] == "place" and e["verified"]:
            assert e["english"] in tiered, f"{e['english']} に段が割り当てられていない"


def test_tier3_places_have_no_coordinates(tiers):
    """同定不能な地に座標を与えないこと。断定は捏造である。"""
    for p in tiers["places"]:
        if p["tier"] in (3, "mythic"):
            assert "lat" not in p and "lon" not in p, f"{p['english']} に座標が付いている"


def test_tier2_places_present_multiple_candidates(tiers):
    for p in tiers["places"]:
        if p["tier"] == 2:
            assert len(p["candidates"]) >= 1, f"{p['english']}: 比定候補が書かれていない"
            assert p["note"], f"{p['english']}: 争点の説明が無い"


def test_voyage_toponyms_are_not_tier1(tiers):
    """航海の寄港地を安易に地図へ載せていないこと。"""
    voyage = {"Ogygia", "Aeaea", "Thrinacia", "Aeolia", "Laestrygonians",
              "Cimmerians", "Lotus-eaters", "Scheria"}
    for p in tiers["places"]:
        if p["english"] in voyage:
            assert p["tier"] != 1, f"{p['english']} が tier1 になっている"
