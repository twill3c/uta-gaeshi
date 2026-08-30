"""定型句の全数集計 — 本プロジェクトの目玉、かつ和訳検査の非循環オラクル。

口誦叙事詩としての『オデュッセイア』の骨格は反復にある。原典の n-gram 集計は
完全に決定論的で、LLM の判断を一切含まない。したがってここで得た反復構造は
和訳を検査するオラクルとして使える(**循環の禁止**):

    原典で逐語的に同一の行は、和訳でも同一に訳されていなければならない。

正規化の方針は**保守側**に倒す。異体(Ὀδυσσεύς / Ὀδυσεύς の σ の数など)は
別物として扱い、統合しない。統合すれば反復は増えて主張は派手になるが、
「同一の行」という制約の根拠が我々の正規化規則に移ってしまい、オラクルが弱くなる。
落とすのは付加記号・句読点・大小文字だけにとどめる。
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

NGRAM_SIZES = (3, 4, 5)
NGRAM_MIN_COUNT = 5

_PUNCT = re.compile(r"[^\w ]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """付加記号・句読点・大小文字のみを落とす。異体は統合しない。"""
    s = unicodedata.normalize("NFD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = _PUNCT.sub("", s)
    return _WS.sub(" ", s).strip().lower()


def iter_lines(corpus: dict):
    """(book, line, text, unit_id) を正準順に返す。"""
    for u in corpus["units"]:
        for g in u["greek"]:
            yield u["book"], g["line"], g["text"], u["id"]


def repeated_lines(corpus: dict) -> list[dict]:
    """逐語的に同一の行の群。和訳の強制等値制約そのもの。"""
    groups: dict[str, list[dict]] = defaultdict(list)
    sample: dict[str, str] = {}
    for book, line, text, uid in iter_lines(corpus):
        key = normalize(text)
        if not key:
            continue
        groups[key].append({"book": book, "line": line, "unit": uid})
        sample.setdefault(key, text)
    out = []
    for key, occ in groups.items():
        if len(occ) < 2:
            continue
        out.append(
            {
                "key": key,
                "sample": sample[key],
                "count": len(occ),
                "units": sorted({o["unit"] for o in occ}),
                "occurrences": occ,
            }
        )
    out.sort(key=lambda g: (-g["count"], g["key"]))
    return out


def ngram_formulas(corpus: dict, n: int, min_count: int = NGRAM_MIN_COUNT) -> list[dict]:
    """行を跨がない n-gram の反復。行全体の一致より細かい定型を拾う。"""
    counts: Counter[str] = Counter()
    where: dict[str, list[dict]] = defaultdict(list)
    for book, line, text, _ in iter_lines(corpus):
        words = normalize(text).split()
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i : i + n])
            counts[gram] += 1
            where[gram].append({"book": book, "line": line})
    out = [
        {"gram": g, "n": n, "count": c, "occurrences": where[g]}
        for g, c in counts.items()
        if c >= min_count
    ]
    out.sort(key=lambda x: (-x["count"], x["gram"]))
    return out


def build(corpus: dict) -> dict:
    reps = repeated_lines(corpus)
    total_lines = sum(1 for _ in iter_lines(corpus))
    rep_occ = sum(g["count"] for g in reps)
    ngrams = {str(n): ngram_formulas(corpus, n) for n in NGRAM_SIZES}

    # 反復行が同一単位内に閉じているか、単位を跨ぐか。
    # 跨ぐものだけが「離れた場所で同じ訳語を要求する」制約になる。
    cross = sum(1 for g in reps if len(g["units"]) > 1)

    return {
        "meta": {
            "total_lines": total_lines,
            "repeated_types": len(reps),
            "repeated_occurrences": rep_occ,
            "repeated_share": round(rep_occ / total_lines, 4),
            "cross_unit_types": cross,
            "equality_constraints": rep_occ - len(reps),
            "ngram_min_count": NGRAM_MIN_COUNT,
            "ngram_types": {n: len(v) for n, v in ngrams.items()},
        },
        "repeated_lines": reps,
        "ngrams": ngrams,
    }


def main() -> None:
    corpus = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    res = build(corpus)
    (DATA / "formulas.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    m = res["meta"]
    print(f"原典行 {m['total_lines']:,}")
    print(f"逐語反復する行  {m['repeated_types']:,} 種 / {m['repeated_occurrences']:,} 回"
          f"  = 全行の {m['repeated_share']*100:.1f}%")
    print(f"  うち単位を跨ぐ群 {m['cross_unit_types']:,} 種")
    print(f"  和訳の強制等値制約 {m['equality_constraints']:,} 件")
    for n, c in m["ngram_types"].items():
        print(f"{n}-gram(5回以上) {c:,} 種")


if __name__ == "__main__":
    main()
