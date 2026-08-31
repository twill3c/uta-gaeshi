"""L4 — 用語集の設計則と、和訳ゲートの陽性対照。"""
import json
import re
from pathlib import Path

import pytest

from pipeline.tgates import check_g02, check_g03, check_g04, check_g05, check_unit
from pipeline.translate import load_glossary, load_units, name_table, read_ledger

pytestmark = pytest.mark.validation
DATA = Path(__file__).resolve().parents[1] / "data"

# 活用しうる語尾。中核句がこれで終わると、文脈で語形が変わり G-02 が落ちる。
# 高精度な終止形だけを見る。り/れ/き/し/え/け は名詞語尾にも多く(誉れ・眠り)、
# 広く取ると正しい中核句を落とす(loop_004 / VERIF-FALSE)。
INFLECTING_END = re.compile(r"(る|う|ぐ|す|つ|ぬ|ぶ|む|た|だ|い)$")


@pytest.fixture(scope="module")
def glossary():
    return load_glossary()


@pytest.fixture(scope="module")
def units():
    return {u["id"]: u for u in load_units()}


def test_cores_are_inflection_stable(glossary):
    """中核句は活用しない部分に限る(loop_004 / SPEC-AMB)。

    最初の版は 94 件中 49 件が活用語尾で終わっており、1.80 で実際に落ちた。
    ホメロスの定型句の不変部分は形容辞であって節全体ではない。
    """
    bad = [
        (k, e["core"]) for k, e in glossary["entries"].items()
        if INFLECTING_END.search(e["core"])
    ]
    assert bad == [], f"活用語尾で終わる中核句: {[c for _, c in bad]}"


def test_cores_are_non_empty_and_distinctive(glossary):
    for k, e in glossary["entries"].items():
        assert e["core"].strip(), f"{k}: 中核句が空"
        assert len(e["core"]) >= 2, f"{k}: 中核句が短すぎる {e['core']!r}"


def test_glossary_covers_every_needed_formula(glossary):
    """用語集の穴は G-02 の判定漏れになる。穴が無いことを検査する。"""
    c = glossary["coverage"]
    assert c["unmatched"] == 0, f"未対応の反復行 {c['unmatched']} 件"
    assert c["authored"] == c["needed"]


def test_full_examples_contain_their_own_core(glossary):
    """訳例が自分の中核句を含むこと。含まなければ中核句の選び方が誤っている。"""
    from pipeline.tgates import norm_ja
    for k, e in glossary["entries"].items():
        assert norm_ja(e["core"]) in norm_ja(e["full"]), f"{k}: 訳例が中核句を含まない"


# ---- 陽性対照 ---------------------------------------------------------------

def test_g02_fires_when_core_missing(units, glossary):
    u = units["1.15"]
    core = glossary["entries"][u["formulas"][0]]["core"]
    assert check_g02(u, f"…{core}…", glossary) == []
    assert check_g02(u, "中核句を含まない訳文", glossary)


def test_g03_fires_when_name_missing(units):
    u = units["1.15"]  # Murray に Ithaca を含む
    assert check_g03(u, "イタケへの帰郷", {"Ithaca": "イタケ"}) == []
    assert check_g03(u, "その島への帰郷", {"Ithaca": "イタケ"})


def test_g04_fires_when_numeral_dropped(units):
    u = next(x for x in units.values() if re.search(r"\btwo\b", x["murray"].lower()))
    assert check_g04(u, "二人の侍女") == []
    assert check_g04(u, "侍女たち")


def test_g05_fires_on_foreign_script():
    assert check_g05("正常な日本語") == []
    assert check_g05("洞\u0441")           # text-hygiene:allow
    assert check_g05("\uac00")


def test_empty_translation_is_rejected(units, glossary):
    assert check_unit(units["1.1"], "   ", glossary, {}) == ["訳文が空"]


# ---- 台帳 -------------------------------------------------------------------

def test_ledger_records_are_well_formed():
    for uid, rec in read_ledger().items():
        assert rec["id"] == uid
        assert rec["ja"].strip(), f"{uid}: 訳文が空"
        assert 1 <= rec["book"] <= 24
        assert rec["line_start"] <= rec["line_end"]


def test_ledger_ids_exist_in_corpus(units):
    for uid in read_ledger():
        assert uid in units, f"台帳に存在しない単位 {uid}"


def test_g05_fires_on_stray_latin():
    """英訳を下敷きにすると訳し残しがそのまま混じる(loop_006 の「old友よ」)。

    G-05 は当初キリル・ハングル・タイ文字しか見ておらず、ラテン文字は素通りした。
    昇格前の実測: 記録済み訳文 253 件中、ラテン文字を含むもの 0 件(誤検出源にならない)。
    """
    assert check_g05("老いた友よ") == []
    assert check_g05("old友よ")


def test_no_latin_in_recorded_translations():
    import re as _re
    latin = _re.compile(r"[A-Za-z]")
    bad = [uid for uid, rec in read_ledger().items() if latin.search(rec["ja"])]
    assert bad == [], f"訳文にラテン文字が混入: {bad}"


def test_no_key_shadows_another_with_a_different_core():
    """短い鍵が長い鍵を覆い隠して、別の中核句を当ててはならない。

    照合は前方一致なので、`ὧδε δέ τις εἴπεσκε` は `ὧδε δέ τις εἴπεσκεν` にも当たる。
    最初の一致を採っていたため、第8巻(話者は神々)へ第2巻(驕り高ぶる若者たち)の
    中核句が付いていた(loop_014)。最長一致に直したうえで、
    **異なる中核句を持つ鍵どうしの覆い隠し自体を禁じる**。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "judgments"))
    from glossary_source import CORE  # noqa: E402

    bad = [
        (a, b) for a in CORE for b in CORE
        if a != b and b.startswith(a) and CORE[a][0] != CORE[b][0]
    ]
    assert bad == [], f"異なる中核句を持つ鍵が覆い隠し合っている: {bad}"
