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


def test_untranslated_books_are_marked_not_hidden():
    """未訳の巻を空にせず、そうと明示すること。"""
    t = (OUT / "book" / "24.html").read_text(encoding="utf-8")
    assert "まだ和訳していません" in t
    assert "（未訳）" in t


def test_pages_declare_utf8_and_lang():
    for p in pages():
        t = p.read_text(encoding="utf-8")
        assert '<meta charset="utf-8">' in t, f"{p.name}: charset 宣言が無い"
        assert '<html lang="ja">' in t, f"{p.name}: lang 宣言が無い"
