# -*- coding: utf-8 -*-
"""公開物に対するゲート G-15〜G-17。

L2 以降ずっと積み上げてきた検査は、いずれも**データ**を見るものだった。
生成した HTML が実際に繋がっているかは、一度も検査していない。
索引から本文へ飛べなければ三索引は成立しないので、そこを機械的に確かめる。

G-15 リンク整合性: 内部リンクの飛び先ファイルとアンカーが実在する
G-16 外部依存ゼロ: 外部ホストへのリクエストを一切含まない(SPEC N-01)
G-17 権利表示: 全ページに Perseus のクレジットと CC BY-SA の表示がある(N-03)
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

HREF = re.compile(r'href="([^"]+)"')
SRC = re.compile(r'(?:src|href)="(https?://[^"]+)"')
ID = re.compile(r'\bid="([^"]+)"')
# 外部ホストを指してよいのはフッタの出典・リポジトリ・App Menu のリンクだけ。
# これらは <a href> であってリクエストを発生させない(クリックして初めて遷移する)。
FETCHING = re.compile(r'<(?:script|link|img|iframe|source|video|audio)\b[^>]*'
                      r'(?:src|href)="(https?://[^"]+)"', re.I)


def pages() -> list[Path]:
    return sorted(OUT.rglob("*.html"))


def check_links() -> list[str]:
    """G-15。内部リンクの飛び先ファイルとアンカーが実在すること。"""
    ids: dict[Path, set[str]] = {p: set(ID.findall(p.read_text(encoding="utf-8")))
                                for p in pages()}
    v = []
    for p in pages():
        text = p.read_text(encoding="utf-8")
        for href in HREF.findall(text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            path, _, frag = href.partition("#")
            target = (p.parent / path).resolve() if path else p
            if not target.exists():
                v.append(f"{p.relative_to(OUT)}: 飛び先が無い {href}")
                continue
            if frag and frag not in ids.get(target, set()):
                v.append(f"{p.relative_to(OUT)}: アンカーが無い {href}")
    return v


def check_no_external_fetch() -> list[str]:
    """G-16。外部ホストからリソースを取得しないこと(SPEC N-01)。"""
    v = []
    for p in pages():
        for url in FETCHING.findall(p.read_text(encoding="utf-8")):
            v.append(f"{p.relative_to(OUT)}: 外部リソースの取得 {url}")
    return v


def check_attribution() -> list[str]:
    """G-17。全ページに出典と継承ライセンスの表示があること(SPEC N-03)。"""
    v = []
    for p in pages():
        t = p.read_text(encoding="utf-8")
        if "Perseus" not in t:
            v.append(f"{p.relative_to(OUT)}: Perseus のクレジットが無い")
        if "CC BY-SA" not in t:
            v.append(f"{p.relative_to(OUT)}: CC BY-SA の表示が無い")
    return v


def main() -> None:
    for name, fn in (("G-15 リンク整合性", check_links),
                     ("G-16 外部依存ゼロ", check_no_external_fetch),
                     ("G-17 権利表示", check_attribution)):
        v = fn()
        print(f"{name}: {'合格' if not v else f'{len(v)} 件の違反'}")
        for x in v[:12]:
            print(f"   {x}")
        if len(v) > 12:
            print(f"   … ほか {len(v)-12} 件")


if __name__ == "__main__":
    main()
