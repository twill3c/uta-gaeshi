"""発話導入定型からの話者抽出 — 「登場」を機械的に取るための経路。

素朴に名前の出現を数えると壊れる(実測: Atreus の 88%、Cronos の 97% が
「〜の子」= 父称で、その名の人物ではなく別人を指す)。

代わりに、ギリシャ語が**格で役割を符号化している**ことを使う。

    主格 → 話し手         (Τηλέμαχος)
    対格 → 話しかけられた相手 = その場にいる (Τηλέμαχον)
    属格 → 父称・所属。その人物の登場ではない  (Εὐπείθεος)

ここで作るのは**候補と測定値**であって確定した人物表ではない。異体・別名・同名別人の
解決は L3 の人手判断の表に委ねる。本モジュールは「機械だけでどこまで取れるか」を測る。
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# 発話導入に現れる動詞・分詞の語幹(付加記号除去後)。
SPEECH_STEMS = (
    "προσεφη", "προσεειπ", "ηυδα", "μετεφη", "μετεειπ",
    "προσηυδα", "ημειβ", "φωνησα", "εφατ", "εειπε",
)

# 格の語尾表。**必ず deaccent() 後の形(最終シグマは σ)で書く**。
# ς で書くと照合後の形と食い違い、その項は永久に当たらない(loop_002 / GEN-LOGIC)。
# 長い語尾から順に当てる。決められないものは "amb" に落とし、役割を与えない。
CASE_ENDINGS: tuple[tuple[str, str], ...] = (
    ("οιο", "gen"), ("αων", "gen"), ("εοσ", "gen"), ("ηοσ", "gen"),
    ("ευσ", "nom"),
    ("ηα", "acc"), ("εα", "acc"), ("ην", "acc"), ("αν", "acc"), ("ον", "acc"),
    ("αο", "gen"), ("εω", "gen"), ("ου", "gen"),
    ("οσ", "nom"), ("ωσ", "nom"),
    # -ησ / -ασ は 1 変化女性の属格とも男性の主格ともとれる。決めない。
    ("ησ", "amb"), ("ασ", "amb"),
    ("ωι", "dat"), ("ηι", "dat"), ("ει", "dat"),
    ("ευ", "voc"),
    ("η", "nom"), ("α", "nom"),
    ("ω", "dat"), ("ι", "dat"), ("ε", "voc"),
)

_COMB = re.compile(r"[\u0300-\u036f]")
_PUNCT = re.compile(r"[^\w ]", re.UNICODE)


def deaccent(token: str) -> str:
    s = unicodedata.normalize("NFD", token)
    s = _COMB.sub("", s)
    s = _PUNCT.sub("", s)
    return s.replace("ς", "σ")


def is_proper(token: str) -> bool:
    """先頭が大文字のギリシャ文字なら固有名詞候補とみなす。"""
    t = token.strip("\u201c\u201d«»()[]·,.;:")
    if len(t) < 4:
        return False
    first = unicodedata.normalize("NFD", t)[0]
    return first.isupper() and "GREEK" in unicodedata.name(first, "")


def case_of(token: str) -> str:
    d = deaccent(token).lower()
    for ending, case in CASE_ENDINGS:
        if d.endswith(ending):
            return case
    return "unknown"


def is_speech_line(text: str) -> bool:
    d = deaccent(text).lower()
    return any(stem in d for stem in SPEECH_STEMS)


def _patronymic_context(tokens: list[str], idx: int) -> bool:
    """属格の直後/近傍に「子」を表す語があれば父称構文とみなす。"""
    window = " ".join(deaccent(t).lower() for t in tokens[idx : idx + 3])
    return any(k in window for k in ("υιο", "υιε", "παισ", "παιδ", "τεκο"))


def analyse(corpus: dict) -> dict:
    speech_lines = []
    speakers: Counter[str] = Counter()
    addressees: Counter[str] = Counter()
    patronymics: Counter[str] = Counter()
    by_name: dict[str, list[dict]] = defaultdict(list)
    named = 0
    ambiguous: Counter[str] = Counter()

    for u in corpus["units"]:
        for g in u["greek"]:
            if not is_speech_line(g["text"]):
                continue
            tokens = g["text"].split()
            found = []
            for i, tok in enumerate(tokens):
                if not is_proper(tok):
                    continue
                case = case_of(tok)
                key = deaccent(tok).lower()
                role = {"nom": "speaker", "acc": "addressee"}.get(case)
                if case == "amb":
                    ambiguous[deaccent(tok).lower()] += 1
                if case == "gen":
                    role = "patronymic" if _patronymic_context(tokens, i) else "genitive"
                found.append({"token": tok, "key": key, "case": case, "role": role})
                if role == "speaker":
                    speakers[key] += 1
                elif role == "addressee":
                    addressees[key] += 1
                elif role == "patronymic":
                    patronymics[key] += 1
                if role in ("speaker", "addressee"):
                    by_name[key].append(
                        {"book": u["book"], "line": g["line"], "unit": u["id"], "role": role}
                    )
            if found:
                named += 1
            speech_lines.append(
                {"book": u["book"], "line": g["line"], "unit": u["id"], "names": found}
            )

    total = sum(1 for u in corpus["units"] for _ in u["greek"])
    return {
        "meta": {
            "total_lines": total,
            "speech_lines": len(speech_lines),
            "speech_share": round(len(speech_lines) / total, 4),
            "speech_lines_with_name": named,
            "named_share": round(named / len(speech_lines), 4) if speech_lines else 0.0,
            "distinct_speakers": len(speakers),
            "distinct_addressees": len(addressees),
            "patronymic_hits": sum(patronymics.values()),
            "ambiguous_case_hits": sum(ambiguous.values()),
            "unknown_case_hits": 0,
        },
        "speakers": [{"key": k, "count": c} for k, c in speakers.most_common()],
        "addressees": [{"key": k, "count": c} for k, c in addressees.most_common()],
        "patronymics": [{"key": k, "count": c} for k, c in patronymics.most_common()],
        "ambiguous": [{"key": k, "count": c} for k, c in ambiguous.most_common()],
        "occurrences": {k: v for k, v in by_name.items()},
        "speech_lines": speech_lines,
    }


def main() -> None:
    corpus = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    res = analyse(corpus)
    (DATA / "speakers.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    m = res["meta"]
    print(f"発話導入定型を含む行 {m['speech_lines']:,} / {m['total_lines']:,}"
          f" ({m['speech_share']*100:.1f}%)")
    print(f"  うち固有名詞を伴う行 {m['speech_lines_with_name']:,}"
          f" ({m['named_share']*100:.0f}%)")
    print(f"話者候補 {m['distinct_speakers']} / 受け手候補 {m['distinct_addressees']}"
          f" / 父称と判定 {m['patronymic_hits']} / 格が曖昧 {m['ambiguous_case_hits']}")
    print("\n話者候補 上位12:")
    for s in res["speakers"][:12]:
        print(f"  {s['count']:4d}  {s['key']}")


if __name__ == "__main__":
    main()
