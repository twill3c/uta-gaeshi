"""L6 — 公開物のゲート G-15〜G-17。

データ側の検査は 7 本あるが、いずれも**生成した HTML が繋がっているか**を見ない。
索引から本文へ飛べなければ三索引は成立しないので、そこを機械的に確かめる。
初回実行で壊れたアンカー 568 件を検出した(loop_010)。
"""
import re
from pathlib import Path

import pytest

from pipeline.sitegates import (
    OUT, check_attribution, check_links, check_no_external_fetch, pages,
)

pytestmark = pytest.mark.validation


@pytest.fixture(scope="module", autouse=True)
def built():
    if not (OUT / "index.html").exists():
        pytest.skip("out/ が無い。python -m pipeline.site を先に実行する")


def test_g15_all_internal_links_resolve():
    assert check_links() == []


def test_g16_no_external_resource_fetch():
    """SPEC N-01: 実行時の課金経路をゼロにする = 外部依存を持たない。"""
    assert check_no_external_fetch() == []


def test_g17_attribution_on_every_page():
    """SPEC N-03: 全ページに Perseus と、**版番号を含む**ライセンス表記を出す。

    版だけを間違えても「CC BY-SA がある」検査は通ってしまう。実際 3.0 US と
    誤表記したまま 12 ループ通過した(HC-091)。版まで検査する。
    """
    assert check_attribution() == []


def test_every_book_page_exists():
    for b in range(1, 25):
        assert (OUT / "book" / f"{b}.html").exists(), f"第{b}巻の頁が無い"


def test_canonical_line_anchors_exist():
    """引用形式(Od. 1.388)がそのまま解決できること。

    単位の先頭行だけに id を置くと、索引が指す個々の行に飛べない。
    """
    import json
    corpus = json.loads((Path(__file__).resolve().parents[1] / "data" / "units.json")
                        .read_text(encoding="utf-8"))
    for book in (1, 9, 24):
        text = (OUT / "book" / f"{book}.html").read_text(encoding="utf-8")
        ids = set(re.findall(r'\bid="(L\d+)"', text))
        want = {f'L{g["line"]}' for u in corpus["units"] if u["book"] == book
                for g in u["greek"]}
        assert want <= ids, f"第{book}巻: 欠けているアンカー {sorted(want - ids)[:5]}"


def test_untranslated_units_are_marked_not_hidden():
    """未訳を空にせず、そうと明示すること。

    もとは「第24巻は未訳だから印がある」と巻を決め打ちしていた。
    loop_031 で全24巻を訳し終えた瞬間、この検査は前提ごと落ちた
    (VERIF-GAP)。**実例を直書きすると、実例が消えたときに
    不変条件まで一緒に消える。** そこで台帳から導く形に書き直す。

    未訳がゼロでも空回りしないよう、裏側も検査する ——
    訳のある単位は、その訳が実際に頁へ出ていること。
    """
    from pipeline.translate import load_units
    import json

    ledger = Path(__file__).resolve().parents[1] / "data" / "translated.jsonl"
    done = {json.loads(l)["id"] for l in
            ledger.read_text(encoding="utf-8").splitlines() if l.strip()}
    units = load_units()
    pending = [u for u in units if u["id"] not in done]

    for u in pending:
        t = (OUT / "book" / f'{u["book"]}.html').read_text(encoding="utf-8")
        assert "まだ和訳していません" in t, f'{u["id"]}: 未訳なのに印が無い'
        assert "（未訳）" in t, f'{u["id"]}: 未訳なのに印が無い'

    # 未訳がゼロのときに素通りしないための裏側。
    assert units, "単位が空"
    for book in (1, 12, 24):
        t = (OUT / "book" / f"{book}.html").read_text(encoding="utf-8")
        if not any(u["book"] == book for u in pending):
            assert "まだ和訳していません" not in t, f"第{book}巻: 全訳済みなのに未訳の印が残っている"


def test_pages_declare_utf8_and_lang():
    for p in pages():
        t = p.read_text(encoding="utf-8")
        assert '<meta charset="utf-8">' in t, f"{p.name}: charset 宣言が無い"
        assert '<html lang="ja">' in t, f"{p.name}: lang 宣言が無い"


# ---- 定型句の英語・和訳併記 / 登場者の説明 (loop_033) ----------------------

def _root():
    return Path(__file__).resolve().parents[1]


def test_formula_page_shows_english_and_japanese():
    """定型句の地図は、原典だけでなく英語と和訳(中核句)を併記すること。"""
    t = (OUT / "formula.html").read_text(encoding="utf-8")
    assert t.count('class="t-ja"') >= 100, "和訳(中核句)の併記が足りない"
    assert t.count('class="t-en"') >= 100, "英語の併記が足りない"
    # 代表例。Murray 自身の語であることの確認も兼ねる。
    # 先頭の Son が落ちているのは、共通部分が語の途中から始まるため
    # 刈り込みで捨てているからで、これは意図した挙動。
    assert "of Laertes, sprung from Zeus, Odysseus of many" in t
    assert "思慮深いテレマコス" in t


def test_formula_english_is_substring_of_every_source_unit():
    """**併記した英語は、その行を含むすべての単位の英訳に実在すること。**

    この欄の主張は「Murray の語である」ことだけである。取り出し方の都合で
    元文に無い文字列が出れば、それは主張が嘘になる。全数で確かめる。
    """
    import json as _json
    from pipeline.translate import load_units

    root = _root()
    fen = _json.loads((root / "data" / "formula_en.json").read_text(encoding="utf-8"))
    formulas = _json.loads(
        (root / "data" / "formulas.json").read_text(encoding="utf-8"))["repeated_lines"]
    units = {u["id"]: u for u in load_units()}

    bad = []
    for g in formulas:
        en = fen["entries"].get(g["key"])
        if not en:
            continue
        for uid in g["units"]:
            if uid in units and en not in units[uid]["murray"]:
                bad.append((g["key"][:30], uid))
    assert bad == [], f"元の英訳に存在しない文字列: {bad[:5]}"


def test_formula_english_coverage_holds():
    """取得率が黙って落ちないようにする。実測 95% に対し 85% を床にする。"""
    import json as _json
    fen = _json.loads((_root() / "data" / "formula_en.json").read_text(encoding="utf-8"))
    share = fen["coverage"]["share"]
    assert share >= 0.85, f"定型句の英語の取得率が落ちた: {share:.0%}"


def test_every_listed_person_has_a_description():
    """登場者一覧に出る全員に説明があること。表とコードの取り違えも防ぐ。"""
    import json as _json
    root = _root()
    ents = _json.loads((root / "data" / "entities.json").read_text(encoding="utf-8"))
    notes = _json.loads(
        (root / "data" / "judgments" / "person_notes.json").read_text(encoding="utf-8"))
    listed = {e["english"] for e in ents["entities"]
              if e["category"] == "person" and e.get("verified") and e.get("ja")}
    described = {p["english"] for p in notes["persons"] if p.get("note")}
    assert listed - described == set(), f"説明の無い登場者: {sorted(listed - described)}"
    assert described - listed == set(), f"一覧に出ないのに説明がある: {sorted(described - listed)}"

    t = (OUT / "person.html").read_text(encoding="utf-8")
    for p in notes["persons"]:
        assert p["note"][:12] in t, f'{p["ja"]}: 説明が頁に出ていない'


def test_speaks_untagged_claims_point_at_real_lines():
    """「実際には語っている」の根拠位置が本文に実在すること。

    ここは機械判定に逆らう主張なので、位置が実在しなければ言いっぱなしになる。
    """
    import json as _json
    from pipeline.translate import load_units

    notes = _json.loads(
        (_root() / "data" / "judgments" / "person_notes.json").read_text(encoding="utf-8"))
    lines = {(u["book"], g["line"]) for u in load_units() for g in u["greek"]}
    bad = []
    for p in notes["persons"]:
        su = p.get("speaks_untagged")
        if not su:
            continue
        assert su.get("why"), f'{p["ja"]}: 原因が書かれていない'
        for r in su["refs"]:
            b, l = r.split(".")
            if (int(b), int(l)) not in lines:
                bad.append((p["ja"], r))
    assert bad == [], f"本文に無い位置を根拠にしている: {bad}"
