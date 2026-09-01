"""定型句に対応する英語を、Murray の訳文から**機械的に**取り出す。

Murray の英訳は行ごとに対応していない。約 5 行ごとの錨で区切られた散文で、
文の切れ目と行の切れ目は一致しない(第23巻 100-102 行がその例で、
一度目は単位 23.100 に丸ごと入るのに、二度目は 23.165 と 23.170 に割れる)。
だから「この行の英訳」を取り出す一般の方法は無い。

そこで**反復そのものを使う**。ある行が n 箇所に現れるなら、その行を含む
n 個の単位の英訳には、その行の訳語が n 個すべてに現れているはずである。
逆にそれ以外の語は、単位ごとに違う。よって

    その行を含むすべての単位の英訳に共通して現れる、最長の連続部分

を取れば、判断を一切持ち込まずに候補が得られる。定型句の検出が n-gram を
数えただけであるのと同じ性質で、**我々の解釈は入っていない**。

ただしこれは「その行の訳である」ことを保証しない。**保証するのは
「すべての単位に共通して現れる Murray の語の最長の連なりである」ことだけ**で、
とくに 2 箇所しか現れない行では偶然の重なりでありうる。頁にはそう書く。

篩は二つだけ置く。どちらも短すぎる断片を出さないためのもので、
意味の判定はしない。

- 12 字未満は出さない
- 機能語だけの連なりは出さない(内容語が 1 語も無いもの)

最初は内容語 2 語以上を要求したが、`spoke to one`(=互いに語り合って)や
`and addressed`(=翼ある言葉をかけ)といった**正しい抽出まで落ちた**ので緩めた。
篩は強いほどよいのではなく、落とすべきものだけ落とすのがよい。
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

MIN_CHARS = 12

# 内容語かどうかの判定にだけ使う。意味は見ない。
STOP = set(
    "the a an and or but of to in on at by for with from as is was were be been "
    "am are that this these those he she it they them him her his hers its their "
    "our your my me we you i not no nor so then when while had has have do did "
    "does there here all any some".split()
)


def _lcs(a: str, b: str) -> str:
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size]


def _trim_to_words(s: str) -> str:
    """語の途中で切れた両端を落とす。`oon as early Dawn` の `oon` を作らない。"""
    i = 0
    while i < len(s) and not s[i].isspace():
        i += 1
    j = len(s)
    while j > 0 and not s[j - 1].isspace():
        j -= 1
    return s[i:j].strip(" ,;:.—-") if j > i else ""


def _has_content_word(s: str) -> bool:
    words = re.findall(r"[A-Za-z']+", s.lower())
    return any(w not in STOP for w in words)


def common_english(murray_texts: list[str]) -> str:
    """すべての英訳に共通して現れる最長の連続部分。無ければ空文字。"""
    if len(murray_texts) < 2:
        return ""
    cur = murray_texts[0]
    for t in murray_texts[1:]:
        cur = _lcs(cur, t)
        if len(cur) < MIN_CHARS - 2:  # 早期打ち切り。刈り込み前なので少し緩く見る
            return ""
    cur = _trim_to_words(cur)
    if len(cur) < MIN_CHARS or not _has_content_word(cur):
        return ""
    return cur


def build() -> dict:
    from pipeline.translate import load_units

    units = {u["id"]: u for u in load_units()}
    formulas = json.loads((DATA / "formulas.json").read_text(encoding="utf-8"))["repeated_lines"]

    entries, by_count = {}, {"2": [0, 0], "3-4": [0, 0], "5+": [0, 0]}
    for g in formulas:
        texts = [units[uid]["murray"] for uid in g["units"] if uid in units]
        en = common_english(texts)
        bucket = "2" if g["count"] == 2 else ("3-4" if g["count"] <= 4 else "5+")
        by_count[bucket][1] += 1
        if en:
            entries[g["key"]] = en
            by_count[bucket][0] += 1

    lens = [len(v) for v in entries.values()]
    return {
        "method": (
            "その行を含むすべての単位の Murray 英訳に共通して現れる最長の連続部分。"
            "刈り込みは語境界のみ。12字未満と、内容語を含まないものは出さない。"
        ),
        "guarantees": (
            "**すべての単位に共通して現れる Murray の語の連なりである**ことだけを保証する。"
            "その行の訳であることは保証しない。とくに 2 箇所しか現れない行では偶然の重なりでありうる。"
        ),
        "min_chars": MIN_CHARS,
        "coverage": {
            "total": len(formulas),
            "with_english": len(entries),
            "share": round(len(entries) / len(formulas), 4),
            "by_count": {k: {"got": v[0], "total": v[1]} for k, v in by_count.items()},
            "mean_chars": round(sum(lens) / len(lens), 1) if lens else 0,
        },
        "entries": entries,
    }


def main() -> None:
    out = build()
    path = DATA / "formula_en.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    c = out["coverage"]
    print(f"定型句の英語 {c['with_english']}/{c['total']} 件 ({c['share']*100:.0f}%) "
          f"平均 {c['mean_chars']} 字 → {path.name}")
    for k, v in c["by_count"].items():
        print(f"  出現{k}回: {v['got']}/{v['total']}")


if __name__ == "__main__":
    main()
