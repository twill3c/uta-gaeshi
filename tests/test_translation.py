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


def test_no_duplicate_keys_in_glossary_source():
    """判断表に同じ鍵を二度書いてはならない。

    Python の dict リテラルは同一鍵を**エラーにせず後勝ちで捨てる**。
    第9巻で `πάντα κατὰ μοῖραν` を書いたとき、同じ鍵の第3巻の項
    (白い帆を張り)が黙って消え、既訳の 4.780 / 8.50 が後から落ちた
    (loop_015)。覆い隠し検査は CORE が dict になった後を見るので、
    **この故障だけは原理的に見えない**。ソースを AST で読む必要がある。
    """
    import ast
    from pathlib import Path as _P

    src = _P(__file__).resolve().parents[1] / "data" / "judgments" / "glossary_source.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    dup = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        seen = set()
        for k in node.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                if k.value in seen:
                    dup.append((k.lineno, k.value))
                seen.add(k.value)
    assert dup == [], f"判断表に重複した鍵がある(後勝ちで黙って消える): {dup}"


def test_no_unreviewed_key_line_collision():
    """一つの鍵が二つ以上の別の反復行に当たるなら、人が見た記録が要る。

    loop_014 の覆い隠し検査は**鍵どうし**を見る。だが鍵が一つしか無くても、
    新しい本文行がその鍵で始まれば中核句を継承してしまう。第10巻のキルケの鍵
    `ὣς ἐφάμην, ἡ δʼ αὐτίκʼ` が第11巻の「尊い母」の行に当たり、死んだ母に
    「女神のうちにも輝かしい方」を強制していた(loop_017)。

    **判定は全24巻の本文に対して行う。** 訳した巻だけを見ると、罠は次の巻を
    足すまで潜伏する —— 実際、第10巻の時点では衝突は存在しなかった。
    """
    import collections
    import json
    from pathlib import Path as _P

    from pipeline.build_glossary import build

    root = _P(__file__).resolve().parents[1]
    reviewed = {
        c["key"] for c in json.loads(
            (root / "data" / "judgments" / "key_collisions.json").read_text(encoding="utf-8")
        )["collisions"]
    }
    by = collections.defaultdict(set)
    for v in build(books=None)["entries"].values():
        by[v["matched_on"]].add(v["sample"])

    unreviewed = sorted(k for k, lines in by.items() if len(lines) > 1 and k not in reviewed)
    assert unreviewed == [], f"未検討の鍵と本文行の衝突: {unreviewed}"


# 予測表の band を刻印する。loop_020 で登録した時点の値。
PREDICTION_BANDS_SHA256 = "d48dd9d1b6d7c60470f959b6905c1c918e8279fda3bbb807371177b6b808756c"


def test_coverage_predictions_are_frozen():
    """事前登録した充足率の予測を書き換えてはならない。

    loop_019 で n=1 の説明を一般則として成果物に書き、loop_020 でも
    「イタケの場面が続くから高いまま」と述べて外した。仮説は事後には
    いくらでも当てはめられる。そこで残り 10 巻の band を訳す前に固定した。

    **規範だけでは守れないので刻印する。** 実測値はこのファイルではなく
    追記のみのループログに記録し、予測表そのものは動かさない。
    band を変えたいなら、それは新しい予測であって、別表として登録し直すこと。
    """
    import hashlib
    import json
    from pathlib import Path as _P

    src = _P(__file__).resolve().parents[1] / "data" / "judgments" / "coverage_predictions.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    bands = {str(p["book"]): p["band"] for p in d["predictions"]}
    got = hashlib.sha256(
        json.dumps(bands, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert got == PREDICTION_BANDS_SHA256, (
        f"予測表の band が変わっている。事後の書き換えは禁止: {bands}"
    )


def test_only_registered_gate_exceptions_remain():
    """台帳の再検査で落ちてよいのは、判断表に記名した誤検出だけ。

    loop_020 で 14.305 が G-14 に落ちた。錨と行の境界がずれる単位では
    G-02 を満たすと隣の単位の分母だけが残るという構造的な誤検出で、
    訳し落としではない。**だが赤を残したまま慣れるのが一番危ない。**
    常時1件落ちている状態を放置すると、二件目の本物に気づかなくなる。

    そこで誤検出は `data/judgments/gate_exceptions.json` に機構つきで
    記名し、**未登録の違反が一件でもあればここで落ちる**ようにした。
    閾値は下げない。訳文も水増ししない。
    """
    import json
    from pathlib import Path as _P

    from pipeline.translate import recheck

    root = _P(__file__).resolve().parents[1]
    registered = {
        e["unit"] for e in json.loads(
            (root / "data" / "judgments" / "gate_exceptions.json").read_text(encoding="utf-8")
        )["exceptions"]
    }
    failing = {d["id"] for d in recheck()["detail"] if d.get("violations")}
    assert failing <= registered, f"未登録のゲート違反: {sorted(failing - registered)}"
