"""L2 の測定値と不変量。

数値は上流の刻印(pipeline/pins.py)とセットでのみ意味を持つ。
test_pins.py が通っているのに本ファイルが落ちたなら、それは我々の回帰である。
"""
import json
from pathlib import Path

import pytest

from pipeline.formulas import build as build_formulas
from pipeline.formulas import normalize
from pipeline.speakers import CASE_ENDINGS, analyse, case_of, deaccent, is_speech_line

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
        pytest.skip("data/places.json が無い。python -m pipeline.places を先に実行する")
    return json.loads(p.read_text(encoding="utf-8"))


# ---- 目玉: 反復 -------------------------------------------------------------

def test_repetition_headline(formulas):
    """実測 2026-08-31: 808 種 / 2,155 回 = 全行の 17.8%。"""
    m = formulas["meta"]
    assert m["repeated_types"] == 808
    assert m["repeated_occurrences"] == 2155
    assert m["repeated_share"] == pytest.approx(0.178, abs=0.001)


def test_every_repeated_group_is_actually_repeated(formulas):
    for g in formulas["repeated_lines"]:
        assert g["count"] >= 2
        assert len(g["occurrences"]) == g["count"]


def test_equality_constraints_derivation(formulas):
    """強制等値制約の数 = 出現数 - 種類数(各群で 1 本を基準に残りを縛る)。"""
    m = formulas["meta"]
    assert m["equality_constraints"] == m["repeated_occurrences"] - m["repeated_types"]
    assert m["equality_constraints"] == 1347


def test_repeated_groups_span_multiple_units(formulas):
    """単位内に閉じた反復はオラクルとして弱い。全群が単位を跨ぐことを確かめる。"""
    m = formulas["meta"]
    assert m["cross_unit_types"] == m["repeated_types"]


def test_normalization_is_conservative():
    """異体を統合しない。統合すると制約の根拠が我々の規則に移りオラクルが弱る。"""
    assert normalize("Ὀδυσσεύς") != normalize("Ὀδυσεύς")
    # 落とすのは付加記号・句読点・大小文字だけ
    assert normalize("Ὀδυσσεύς") == normalize("ὀδυσσεύς,")


# ---- 話者 -------------------------------------------------------------------

def test_case_endings_are_written_in_normalized_form():
    """語尾表は必ず deaccent() 後の形で書く。

    ς で書くと照合形(σ)と食い違い、その項は永久に当たらない。
    loop_002 で属格 4 項すべてが死に、属格を話者と誤判定した。直接の回帰ガード。
    """
    for ending, _ in CASE_ENDINGS:
        assert "ς" not in ending, f"語尾 {ending!r} が最終シグマで書かれている"
        assert deaccent(ending) == ending, f"語尾 {ending!r} が正規化形でない"


def test_genitive_is_not_a_speaker():
    """父称の属格を話者と取り違えないこと(Εὐπείθεος は話者ではない)。"""
    assert case_of("Εὐπείθεος") == "gen"
    assert case_of("Ἀλκινόοιο") == "gen"


def test_accusative_is_addressee_not_speaker():
    assert case_of("Ὀδυσσῆα") == "acc"
    assert case_of("Τηλέμαχον") == "acc"


def test_nominative_is_speaker():
    assert case_of("Ὀδυσσεύς") == "nom"
    assert case_of("Τηλέμαχος") == "nom"


def test_speech_detection_does_not_cross_word_boundaries():
    """語境界を跨いだ偽陽性を作らないこと(deaccent が空白を保つ)。"""
    assert " " in deaccent("τὸν δʼ αὖτε προσέειπε")
    assert is_speech_line("τὸν δʼ αὖτε προσέειπε")
    assert not is_speech_line("ἄνδρα μοι ἔννεπε μοῦσα")


def test_speaker_headline(speakers):
    """実測 2026-08-31: 発話導入定型 611 行、うち固有名詞を伴う 364 行(60%)。"""
    m = speakers["meta"]
    assert m["speech_lines"] == 611
    assert m["speech_lines_with_name"] == 364
    assert m["named_share"] == pytest.approx(0.596, abs=0.005)


def test_roles_are_consistent_with_case(speakers):
    for line in speakers["speech_lines"]:
        for n in line["names"]:
            if n["role"] == "speaker":
                assert n["case"] == "nom"
            elif n["role"] == "addressee":
                assert n["case"] == "acc"
            elif n["role"] in ("patronymic", "genitive"):
                assert n["case"] == "gen"
            elif n["role"] is None:
                assert n["case"] not in ("nom", "acc")


def test_ambiguous_endings_get_no_role(speakers):
    """決められない格に役割を与えない。無理な判定より測れる欠測のほうがよい。"""
    for line in speakers["speech_lines"]:
        for n in line["names"]:
            if n["case"] == "amb":
                assert n["role"] is None


# ---- 地名 -------------------------------------------------------------------

def test_place_headline(places):
    """実測 2026-08-31: タグ 418 箇所 / 異なりキー 70(tgn 49 + perseus 21)。"""
    m = places["meta"]
    assert m["occurrences"] == 418
    assert m["distinct_keys"] == 70
    assert m["by_authority"] == {"tgn": 49, "perseus": 21}


def test_split_surfaces_are_detected(places):
    """同一表記が複数キーに分裂している欠陥を検出していること。"""
    split = places["split_surfaces"]
    assert set(split) == {"Troy", "Ithaca", "Pylos", "Olympus", "Elis"}
    assert len(split["Troy"]) == 3


def test_voyage_toponyms_are_untagged(places):
    """航海の寄港地は典拠データに存在しない。これが「航路は描けない」の根拠。"""
    m = places["meta"]
    assert m["voyage_toponyms_untagged"] == 9
    tagged = [u["name"] for u in places["untagged_voyage_toponyms"] if u["tagged_as"]]
    assert tagged == ["Scheria"]


def test_every_place_occurrence_has_a_position(places):
    for p in places["places"]:
        assert p["occurrences"], f"{p['key']} に出現位置が無い"
        for o in p["occurrences"]:
            assert 1 <= o["book"] <= 24
