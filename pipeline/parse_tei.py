"""TEI XML を「翻訳単位」へ構造化する。

設計の要:
  * 原典 grc は <l n="..."> で全 12,107 行に正準行番号を持つ。これが唯一の座標系。
  * 英訳は散文だが <milestone unit="line" n="..."/> で原典行番号に錨を打つ。
    Murray(eng3) は 2,434 錨、Butler(eng4) は 1,045 錨。
  * よって「翻訳単位」= Murray の錨で区切られた原典行の区間、と定義する。
    単位は原典行を過不足なく分割する(G-01 で検査)。

注意(実測で二度踏んだ罠):
  div の属性順が版で異なる。grc は <div n="1" type="textpart" subtype="book">、
  eng は <div type="textpart" subtype="book" n="1">。属性順に依存する正規表現は壊れる。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.fetch_tei import EDITIONS, RAW

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BOOK_DIV = re.compile(r'<div\b[^>]*\bsubtype="book"[^>]*>')
N_ATTR = re.compile(r'\bn="([^"]+)"')
LINE_EL = re.compile(r'<l\b[^>]*\bn="(\d+)"[^>]*>(.*?)</l>', re.S)
MILESTONE = re.compile(r'<milestone\b[^>]*\bunit="line"[^>]*/>')
# 読みの本文に含めない要素(注釈・書誌)。中身ごと落とす。
DROP_EL = re.compile(r"<(note|bibl|head)\b[^>]*>.*?</\1>", re.S)
SELF_CLOSED_DROP = re.compile(r"<(note|bibl|head)\b[^>]*/>")
TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def _body(xml: str) -> str:
    return xml[xml.index("<text") :]


def _books(body: str):
    """(book_number, segment) を文書順に返す。属性順に依存しない。"""
    hits = list(BOOK_DIV.finditer(body))
    out = []
    for i, m in enumerate(hits):
        n = N_ATTR.search(m.group(0))
        if not n:
            continue
        end = hits[i + 1].start() if i + 1 < len(hits) else len(body)
        out.append((int(n.group(1)), body[m.start() : end]))
    return out


def _clean(fragment: str) -> str:
    s = DROP_EL.sub(" ", fragment)
    s = SELF_CLOSED_DROP.sub(" ", s)
    s = TAG.sub(" ", s)
    return WS.sub(" ", s).strip()


def load(key: str) -> str:
    path = RAW / EDITIONS[key]["file"]
    if not path.exists():
        raise FileNotFoundError(f"{path} が無い。先に python -m pipeline.fetch_tei を実行する")
    return path.read_text(encoding="utf-8")


def parse_greek() -> list[dict]:
    """原典を行単位で返す。[{book, line, text}] × 12,107 を期待。"""
    out = []
    for bn, seg in _books(_body(load("grc"))):
        for m in LINE_EL.finditer(seg):
            text = _clean(m.group(2))
            out.append({"book": bn, "line": int(m.group(1)), "text": text})
    return out


def parse_anchors(key: str) -> list[dict]:
    """英訳を錨で区切った断片として返す。[{book, line, text}]。line は区間の開始行。"""
    out = []
    for bn, seg in _books(_body(load(key))):
        hits = list(MILESTONE.finditer(seg))
        for i, m in enumerate(hits):
            n = N_ATTR.search(m.group(0))
            if not n:
                continue
            end = hits[i + 1].start() if i + 1 < len(hits) else len(seg)
            text = _clean(seg[m.end() : end])
            out.append({"book": bn, "line": int(n.group(1)), "text": text})
    return out



def repair_anchors(anchors: list[dict], last_line: int, book: int, edition: str):
    """錨列の欠陥を修復する。修復は必ず記録し、英訳本文は決して捨てない。

    Perseus の Murray(eng3) には実測で 2 件の欠陥がある(loop_001 / DATA-QUAL):
      * 巻 6: 同一行番号の錨が重複する
      * 巻 16: 巻の最終行 481 を超える錨 580 が存在する

    修復規則:
      1. 行番号が重複する錨は 1 本に統合し、本文を文書順に連結する
      2. 巻の範囲外を指す錨は落とす。ただしその本文は直前の錨へ引き継ぐ
         (落とすだけでは英訳が静かに消える)
      3. 修復後に単調でなければ、それは未知の欠陥なので例外で止める
    """
    repairs: list[dict] = []
    merged: list[dict] = []
    for a in anchors:
        if merged and a["line"] == merged[-1]["line"]:
            merged[-1]["text"] = (merged[-1]["text"] + " " + a["text"]).strip()
            repairs.append(
                {"edition": edition, "book": book, "line": a["line"],
                 "kind": "duplicate_anchor", "action": "本文を直前の錨へ統合"}
            )
        else:
            merged.append(dict(a))

    kept: list[dict] = []
    for a in merged:
        if a["line"] > last_line:
            if kept:
                kept[-1]["text"] = (kept[-1]["text"] + " " + a["text"]).strip()
            repairs.append(
                {"edition": edition, "book": book, "line": a["line"],
                 "kind": "out_of_range", "last_line": last_line,
                 "action": "錨を除去し本文を直前の錨へ引き継ぎ"}
            )
        else:
            kept.append(a)

    lines = [a["line"] for a in kept]
    if lines != sorted(lines) or len(lines) != len(set(lines)):
        raise ValueError(
            f"{edition} 巻{book}: 修復後も錨が単調でない {lines}"
        )
    return kept, repairs


def build_units() -> dict:
    greek = parse_greek()
    murray = parse_anchors("murray")
    butler = parse_anchors("butler")

    by_book: dict[int, list[dict]] = {}
    for g in greek:
        by_book.setdefault(g["book"], []).append(g)

    # 出典の組版順が正準行番号順と食い違う箇所がある(実測: 巻14 の 63/64)。
    # これは欠陥ではなく校訂判断なので修復せず、正準順に整列した事実として残す。
    transpositions: list[dict] = []
    for bn, lines in by_book.items():
        order = [l["line"] for l in lines]
        if order != sorted(order):
            flips = [
                {"edition": "grc", "book": bn, "line": order[i],
                 "kind": "transposed", "after": order[i - 1],
                 "action": "正準行番号順に整列(出典の組版順は逆)"}
                for i in range(1, len(order)) if order[i] < order[i - 1]
            ]
            transpositions.extend(flips)
            lines.sort(key=lambda l: l["line"])

    def spans(anchors, book_lines):
        """錨列を [start, end] の区間へ。末尾の錨は巻の最終行まで伸ばす。"""
        last = max(l["line"] for l in book_lines) if book_lines else 0
        res = []
        for i, a in enumerate(anchors):
            end = anchors[i + 1]["line"] - 1 if i + 1 < len(anchors) else last
            res.append((a["line"], max(end, a["line"]), a["text"]))
        return res

    units = []
    repairs: list[dict] = list(transpositions)
    for bn in sorted(by_book):
        lines = by_book[bn]
        last = max(l["line"] for l in lines)
        m_anchors, r1 = repair_anchors(
            [a for a in murray if a["book"] == bn], last, bn, "murray")
        b_anchors, r2 = repair_anchors(
            [a for a in butler if a["book"] == bn], last, bn, "butler")
        repairs.extend(r1); repairs.extend(r2)
        b_spans = spans(b_anchors, lines)
        for start, end, text in spans(m_anchors, lines):
            g = [l for l in lines if start <= l["line"] <= end]
            overlap = [
                {"line_start": s, "line_end": e, "text": t}
                for s, e, t in b_spans
                if not (e < start or s > end)
            ]
            units.append(
                {
                    "id": f"{bn}.{start}",
                    "book": bn,
                    "line_start": start,
                    "line_end": end,
                    "greek": [{"line": l["line"], "text": l["text"]} for l in g],
                    "murray": text,
                    "butler": overlap,
                }
            )

    meta = {
        "work": "Homer, Odyssey (Ὀδύσσεια)",
        "source": "PerseusDL/canonical-greekLit",
        "license": "CC BY-SA 4.0 International",
        "attribution": "Perseus Digital Library, Tufts University",
        "books": len(by_book),
        "greek_lines": len(greek),
        "units": len(units),
        "murray_anchors": len(murray),
        "butler_anchors": len(butler),
        "repairs": len(repairs),
    }
    return {"meta": meta, "units": units, "repairs": repairs}


def main() -> None:
    corpus = build_units()
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "units.json").write_text(
        json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    m = corpus["meta"]
    print(f"巻 {m['books']} / 原典行 {m['greek_lines']:,} / 翻訳単位 {m['units']:,}")
    print(f"錨 Murray {m['murray_anchors']:,} / Butler {m['butler_anchors']:,}")
    (DATA / "repairs.json").write_text(
        json.dumps(corpus["repairs"], ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    print(f"出典欠陥の修復 {m['repairs']} 件 → data/repairs.json")
    for r in corpus["repairs"]:
        print(f"  {r['edition']} 巻{r['book']} 行{r['line']}: {r['kind']} — {r['action']}")
    size = (DATA / "units.json").stat().st_size
    print(f"data/units.json {size:,} bytes")


if __name__ == "__main__":
    main()
