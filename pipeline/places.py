"""地名の全数集計 — 既製の typed タグを使い、その欠陥ごと記録する。

人名と違い、地名は Perseus が <placeName key="..."> でタグ付けしている(英訳側のみ)。
ただし実測で三種の欠陥がある:

  1. 同一の地に二つの ID     (Ithaca が tgn,1007519 と tgn,7013803 に分裂)
  2. 典拠系統の混在         (Troy=perseus,Troy と Ilios=tgn,7002329 が別項目)
  3. 地名でないものが地名扱い (Cyclops=種族、North Wind=風)

さらに決定的なのは**欠落**である。航海の寄港地(Ogygia, Aeaea, Thrinacia …)は
本文に現れるのにタグが付いていない。稀だからではなく、指示対象が存在しないため。
→ オデュッセウスの航路は地図に描けない。描けない区間を明示することが企画の芯であり、
   ここではその欠落を**測定値として**出す。
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.parse_tei import BOOK_DIV, N_ATTR, TAG, WS, _body, load

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

PLACE = re.compile(r'<placeName\b([^>]*)>(.*?)</placeName>', re.S)
KEY_ATTR = re.compile(r'\bkey="([^"]*)"')
MILESTONE_N = re.compile(r'<milestone\b[^>]*\bunit="line"[^>]*/>', re.S)

# 本文に現れるのにタグが無い地名を測るための対象。
# 「同定不能」の主張はここの実測に立つので、対象は事前に固定して恣意を避ける。
VOYAGE_TOPONYMS = (
    "Ogygia", "Aeaea", "Scheria", "Thrinacia", "Aeolia",
    "Laestrygon", "Cimmer", "Lotus", "Erebus", "Ismarus",
)


def _line_at(seg: str, pos: int) -> int:
    """seg 内の位置 pos の直前にある行錨の番号を返す。"""
    last = 0
    for m in MILESTONE_N.finditer(seg):
        if m.start() > pos:
            break
        n = N_ATTR.search(m.group(0))
        if n:
            last = int(n.group(1))
    return last


def collect(edition: str) -> list[dict]:
    body = _body(load(edition))
    hits = list(BOOK_DIV.finditer(body))
    out = []
    for i, m in enumerate(hits):
        n = N_ATTR.search(m.group(0))
        if not n:
            continue
        book = int(n.group(1))
        seg = body[m.start() : hits[i + 1].start() if i + 1 < len(hits) else len(body)]
        for p in PLACE.finditer(seg):
            key = KEY_ATTR.search(p.group(1))
            surface = WS.sub(" ", TAG.sub("", p.group(2))).strip()
            out.append(
                {
                    "book": book,
                    "line": _line_at(seg, p.start()),
                    "key": key.group(1) if key else None,
                    "surface": surface,
                    "edition": edition,
                }
            )
    return out


def untagged_toponyms(edition: str) -> list[dict]:
    """本文に現れるがタグの付いていない地名を測る。"""
    body = _body(load(edition))
    tagged = {WS.sub(" ", TAG.sub("", m.group(2))).strip() for m in PLACE.finditer(body)}
    plain = WS.sub(" ", TAG.sub(" ", body))
    out = []
    for name in VOYAGE_TOPONYMS:
        occ = len(re.findall(name, plain))
        hit = sorted(t for t in tagged if name.lower() in t.lower())
        out.append({"name": name, "occurrences": occ, "tagged_as": hit})
    return out


def build() -> dict:
    murray = collect("murray")
    by_key: dict[str, dict] = {}
    surfaces: dict[str, Counter] = defaultdict(Counter)
    keys_per_surface: dict[str, set] = defaultdict(set)

    for r in murray:
        k = r["key"] or "(キー無し)"
        e = by_key.setdefault(k, {"key": k, "count": 0, "books": set(), "occurrences": []})
        e["count"] += 1
        e["books"].add(r["book"])
        e["occurrences"].append({"book": r["book"], "line": r["line"]})
        surfaces[k][r["surface"]] += 1
        keys_per_surface[r["surface"]].add(k)

    places = []
    for k, e in by_key.items():
        places.append(
            {
                "key": k,
                "authority": k.split(",")[0] if "," in k else None,
                "label": surfaces[k].most_common(1)[0][0],
                "surfaces": dict(surfaces[k]),
                "count": e["count"],
                "books": sorted(e["books"]),
                "occurrences": e["occurrences"],
            }
        )
    places.sort(key=lambda p: (-p["count"], p["key"]))

    split = {s: sorted(ks) for s, ks in keys_per_surface.items() if len(ks) > 1}
    untagged = untagged_toponyms("murray")

    return {
        "meta": {
            "occurrences": len(murray),
            "distinct_keys": len(by_key),
            "by_authority": dict(Counter(p["authority"] for p in places)),
            "surfaces_with_multiple_keys": len(split),
            "voyage_toponyms_checked": len(untagged),
            "voyage_toponyms_untagged": sum(1 for u in untagged if not u["tagged_as"]),
        },
        "places": places,
        "split_surfaces": split,
        "untagged_voyage_toponyms": untagged,
    }


def main() -> None:
    res = build()
    (DATA / "places.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    m = res["meta"]
    print(f"地名タグ {m['occurrences']} 箇所 / 異なりキー {m['distinct_keys']}")
    print(f"典拠の内訳 {m['by_authority']}")
    print(f"同一表記に複数キーが割り当たっているもの {m['surfaces_with_multiple_keys']} 件:")
    for s, ks in res["split_surfaces"].items():
        print(f"   {s}: {ks}")
    print(f"\n航海の寄港地 {m['voyage_toponyms_checked']} 件を検査 → "
          f"タグ無し {m['voyage_toponyms_untagged']} 件")
    for u in res["untagged_voyage_toponyms"]:
        state = f"タグ有り {u['tagged_as']}" if u["tagged_as"] else "タグ無し"
        print(f"   {u['name']:12s} 本文 {u['occurrences']:3d} 回  {state}")


if __name__ == "__main__":
    main()
