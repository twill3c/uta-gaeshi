"""名寄せの機械化 — 二経路の一致だけを自動確定とし、不一致を人手判断へ回す。

ギリシャ語の固有名詞は格変化するため、同一人物が多数の表層形を持つ
(Ὀδυσσεύς / Ὀδυσσῆος / Ὀδυσσῆα / Ὀδυσεύς …)。一方 Murray の英訳では
名前は無変化で現れる。この非対称を使って、独立な二経路を作る:

  経路 A: ギリシャ語の語幹前方一致クラスタ(形態の証拠)
  経路 B: 同一単位に現れる英訳固有名詞との共起(対訳の証拠)

A と B が同じ人物を指していれば自動確定してよい。食い違えば人手判断に回す。
どちらか一方だけで決めると、それは我々の規則が根拠になってしまう(循環)。

注意: 一致率そのものが測定対象(G-08)であって、前提ではない。
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.speakers import deaccent, is_proper

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

MIN_STEM = 4          # 語幹クラスタの最短前方一致長
MIN_COUNT = 3         # これ未満の表層形は雑音として扱う(数は残す)
CONFIDENT = 0.8       # 被覆率がこれ未満なら機械では決めず保留にする

# 英訳側で固有名詞と紛れる語。文頭大文字と人名を切り分けるために除く。
ENGLISH_STOP = set("""
The And But For Now Then There Thus So When Yet Him His Her She They Not Nay Come Let
Son Lord King Queen Father Mother Sir Hear Tell Would Should Could Have Was Were With
That This These Those Who What Where Why How All One Two Three Down Over Into Upon Out
Off Above Round Here Hither Thence Thither Never Ever Even Still Only Also Such Some
Many Much Most More Less Least Nor Neither Either Both Each Every Any None Other
Another Same Ah Alas Behold Lo Yea Verily Truly Indeed Surely Beside Beyond Before
After Since Until While Because Although Though Whether Unless Except Save Besides
Moreover However Therefore Wherefore Hence Whence Whither Whom Whose Which Whatever
Whoever Wherever Whenever Nevertheless Meanwhile Straightway Forthwith Howbeit
""".split())

ENG_TOKEN = re.compile(r'(?:^|[^.!?"\u201c]\s+)([A-Z][a-z\u00e9\u00eb]{2,})\b')


def greek_names(corpus: dict) -> dict[str, list[dict]]:
    """正規化した希語固有名詞 → 出現位置。"""
    out: dict[str, list[dict]] = defaultdict(list)
    for u in corpus["units"]:
        for g in u["greek"]:
            for tok in g["text"].split():
                if not is_proper(tok):
                    continue
                key = deaccent(tok).lower()
                if len(key) < MIN_STEM:
                    continue
                out[key].append({"book": u["book"], "line": g["line"], "unit": u["id"]})
    return out


def english_names(corpus: dict) -> dict[str, set[str]]:
    """単位 ID → その単位の Murray 訳に現れる英語固有名詞の集合。"""
    out: dict[str, set[str]] = {}
    for u in corpus["units"]:
        toks = {m.group(1) for m in ENG_TOKEN.finditer(u["murray"])}
        out[u["id"]] = {t for t in toks if t not in ENGLISH_STOP}
    return out


def align_by_form(corpus: dict) -> dict:
    """**英訳側を同一性の鍵にする。** 語幹を鍵にした版は二重に壊れていた:

      * 前方一致は別人を併合する (ευρυ ← Εὐρύκλεια / Εὐρύμαχος / Εὐρύλοχος)
      * 補充形は前方一致で繋がらない (Ζεύς / Διός / Ζηνός は同一人物)

    英語の固有名詞は無変化なので、そちらを鍵に据え、希語の表層形を証拠として
    ぶら下げる。希語の語形は依然として独立な経路であり、鍵が変わっただけで
    二経路の照合という構図は保たれる。各表層形について:

      共起票 = その表層形が現れた単位の Murray 訳に現れる英語固有名詞
      被覆率 = 最有力の英語名を含む単位の割合 → その対応の信頼度

    被覆率が低い表層形は「機械では決まらなかった」として保留に落とす。
    決めないことを選べるのが、閾値を後から動かせる設計の条件である。
    """
    gnames = greek_names(corpus)
    enames = english_names(corpus)

    forms = []
    for key, occ in gnames.items():
        if len(occ) < MIN_COUNT:
            continue
        units = {o["unit"] for o in occ}
        votes: Counter[str] = Counter()
        for uid in units:
            for e in enames.get(uid, ()):
                votes[e] += 1
        best, n = votes.most_common(1)[0] if votes else (None, 0)
        forms.append(
            {
                "form": key,
                "count": len(occ),
                "units": len(units),
                "english": best,
                "coverage": round(n / len(units), 3) if units else 0.0,
                "runners_up": votes.most_common(4)[1:],
                "books": sorted({o["book"] for o in occ}),
                "occurrences": occ,
            }
        )

    confident = [f for f in forms if f["coverage"] >= CONFIDENT]
    held = [f for f in forms if f["coverage"] < CONFIDENT]

    groups: dict[str, dict] = {}
    for f in confident:
        g = groups.setdefault(
            f["english"], {"english": f["english"], "forms": [], "count": 0, "books": set()}
        )
        g["forms"].append(
            {"form": f["form"], "count": f["count"], "coverage": f["coverage"]}
        )
        g["count"] += f["count"]
        g["books"].update(f["books"])
    for g in groups.values():
        g["books"] = sorted(g["books"])
        g["forms"].sort(key=lambda x: -x["count"])

    entities = sorted(groups.values(), key=lambda g: -g["count"])
    return {
        "meta": {
            "surface_forms": len(forms),
            "confident_forms": len(confident),
            "held_forms": len(held),
            "confident_share": round(len(confident) / len(forms), 3) if forms else 0.0,
            "entities": len(entities),
            "threshold": CONFIDENT,
        },
        "entities": entities,
        "held": sorted(held, key=lambda f: -f["count"]),
    }


def main() -> None:
    corpus = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    res = align_by_form(corpus)
    (DATA / "align.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    m = res["meta"]
    print(f"希語の表層形 {m['surface_forms']} 件(出現 {MIN_COUNT} 回以上)")
    print(f"  被覆率 >= {m['threshold']} で確定 {m['confident_forms']}"
          f" ({m['confident_share']*100:.0f}%) / 保留 {m['held_forms']}")
    print(f"  確定分が束ねた実体 {m['entities']} 件")
    print(chr(10) + "上位18(英訳名 / 出現 / 希語表層形の数 / 巻数):")
    for e in res["entities"][:18]:
        forms = " ".join(f["form"] for f in e["forms"][:3])
        print(f"  {e['english']:14s} {e['count']:4d}  形{len(e['forms']):2d}  {len(e['books']):2d}巻  {forms}")


if __name__ == "__main__":
    main()
