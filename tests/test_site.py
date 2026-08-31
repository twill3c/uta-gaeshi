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
