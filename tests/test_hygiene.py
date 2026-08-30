"""文字種衛生(G-05) — 字形の似た他言語文字の混入を捕まえる。

loop_003 で docstring に 'crude' のつもりでキリル文字混じりの文字列を書いた。
目視では気づけない種類の事故なので、走査を検査に置く。
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
ALLOW = "text-hygiene:allow"
pytestmark = pytest.mark.unit


def _sources():
    for pattern in ("*.py", "*.md", "*.json"):
        for f in ROOT.rglob(pattern):
            parts = set(f.parts)
            if parts & {".git", "__pycache__", ".pytest_cache", "raw"}:
                continue
            if f.name == "text_hygiene.py":
                continue  # 検出器自身のフィクスチャ
            yield f


def test_no_cyrillic_in_sources():
    hits = []
    for f in _sources():
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if CYRILLIC.search(line) and ALLOW not in line:
                hits.append(f"{f.relative_to(ROOT)}:{i}")
    assert hits == [], f"キリル文字の混入: {hits}"


def test_detector_actually_detects():
    """陽性対照: 検出器が本当に反応すること。"""
    assert CYRILLIC.search("измерение")  # text-hygiene:allow
    assert not CYRILLIC.search("crude 素朴 Ὀδυσσεύς")
