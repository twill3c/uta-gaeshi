"""和訳に対する較正ゲート G-02〜G-05。

いずれも **LLM に自分の訳を採点させない**。判定材料は原典の反復構造・人手の判断表・
数詞・文字種だけで、すべて機械的に決まる。訳の巧拙は測定対象ではない(SPEC §5)。

G-02 反復保存: 原典で同一の行を含む単位は、用語集が定める中核句を訳文に含む
G-03 固有名詞: 判断表で和名が確定した実体が原典側にあれば、訳文にその和名がある
G-04 数詞保存: 英訳側の数詞が訳文で保存されている
G-05 文字種衛生: 想定外の文字種(キリル文字・ハングル等)が混入していない
"""
from __future__ import annotations

import re
import unicodedata

# 英訳の数詞 → 訳文で受理する表記。
#
# **"one" は入れない。** 実測(2026-08-31、全 2,432 単位)では 384 単位(16%)に現れるが、
# 無作為 8 件の用法はすべて代名詞・副詞("one on either side" / "each one of you" /
# "if one would give")で、数詞用法は 0 件だった。ゲートに入れると 16% の単位に
# 恒常的な誤検出を出す。two(156 単位) / nine(20) / twenty(20) は同じ手順で
# 真の数詞であることを確認済み(HC-083 の手順)。
NUMERALS = {
    "two": ("二", "2", "ふた"), "three": ("三", "3"),
    "four": ("四", "4"), "five": ("五", "5"), "six": ("六", "6"),
    "seven": ("七", "7"), "eight": ("八", "8"), "nine": ("九", "9"),
    "ten": ("十", "10"), "twelve": ("十二", "12"), "twenty": ("二十", "20"),
    "fifty": ("五十", "50"), "hundred": ("百", "100"), "thousand": ("千", "1000"),
}

FOREIGN = {
    "キリル文字": re.compile(r"[\u0400-\u04FF]"),
    "ハングル": re.compile(r"[\uac00-\ud7af]"),
    "タイ文字": re.compile(r"[\u0e00-\u0e7f]"),
    # ラテン文字。英訳を下敷きにしていると、訳し残した語がそのまま混じる
    # (loop_006 で「老いた友よ」と書くつもりが「old友よ」になった)。
    # 字形が似ていないので目には入るが、それでも見落とす。
    # 昇格前に実測: 記録済み訳文 253 件中、含むもの 0 件。誤検出源にならない。
    "ラテン文字": re.compile(r"[A-Za-z]"),
}
_WS = re.compile(r"\s+")


def norm_ja(text: str) -> str:
    """全角半角と空白のゆれを吸収する。中核句の包含判定に使う。"""
    return _WS.sub("", unicodedata.normalize("NFKC", text))


def check_g02(unit: dict, ja: str, glossary: dict) -> list[str]:
    """反復保存。単位が含む反復行に対応する中核句が訳文にあること。"""
    v = []
    body = norm_ja(ja)
    for g in unit.get("formulas", []):
        entry = glossary["entries"].get(g)
        if not entry:
            continue
        core = norm_ja(entry["core"])
        if core and core not in body:
            v.append(f"G-02 中核句が訳文に無い: {entry['core']!r} (反復行 {g[:20]}…)")
    return v


def check_g03(unit: dict, ja: str, names: dict[str, str]) -> list[str]:
    """固有名詞。英訳側に現れた実体の和名が訳文にあること。

    英訳を手がかりにするのは、原典側が格変化して照合が難しいためであり、
    かつ英訳と原典は独立に付き合わせ済み(L3)だからである。
    """
    v = []
    for english, japanese in names.items():
        if re.search(rf"\b{re.escape(english)}\b", unit["murray"]):
            if japanese not in ja:
                v.append(f"G-03 固有名詞が訳文に無い: {english} → {japanese}")
    return v


def check_g04(unit: dict, ja: str) -> list[str]:
    """数詞保存。英訳側の数詞が訳文のどこかに現れること。"""
    v = []
    low = unit["murray"].lower()
    for word, accepted in NUMERALS.items():
        if re.search(rf"\b{word}\b", low):
            if not any(a in ja for a in accepted):
                v.append(f"G-04 数詞が保存されていない: {word} → {'/'.join(accepted)}")
    return v


def check_g05(ja: str) -> list[str]:
    """文字種衛生。字形が似た他言語文字の混入は目視で気づけない。"""
    return [f"G-05 {name}の混入" for name, pat in FOREIGN.items() if pat.search(ja)]


# G-14 の閾値。和訳/英訳の文字数比の実測分布(2026-08-31, n=318)から決めた:
#   中央 0.416 / 平均 0.417 / 標準偏差 0.055 → 平均 - 2σ = 0.307
# この線を下回る 7 件はすべて、作業画面での原文切り詰め(280字)を超えた単位だった。
# 訳文が短いこと自体は罪ではないが、**原文の尾部が落ちた場合の唯一の機械的な痕跡**である。
# 他のゲートは「訳文に何が入っているか」しか見ないため、名前も数詞も定型句も無い
# 尾部の欠落を捕まえられない(HC-086)。
# G-14 は**判定ではなく選別**である。2σ の裾には「本当の欠落」と
# 「完訳だが訳が詰まっている」が混ざる。発火したら原文全体を読み直し、
# 欠落でなければ訳を自然な密度に開いて通す。閾値を下げてはならない
# (本物の欠落を通す)し、上げてもならない(裾を見なくなる)。
#
# 実績: 発火 9 件のうち 7 件が真の訳し落とし、2 件が完訳だが簡潔すぎた例。
# 再較正(2026-08-31, n=594, 巻1-6): 中央 0.415 / 平均 0.418 / σ 0.049
#   → 平均 - 2σ = 0.319。現行値 0.31 とほぼ一致するため据え置く。
LENGTH_RATIO_MIN = 0.31


def check_g14(unit: dict, ja: str) -> list[str]:
    """分量整合。原文に対して訳文が極端に短くないこと。"""
    src = len(unit["murray"])
    if src == 0:
        return []
    ratio = len(ja) / src
    if ratio < LENGTH_RATIO_MIN:
        return [f"G-14 訳文が短すぎる: 英{src}字 → 和{len(ja)}字 "
                f"(比 {ratio:.2f} < {LENGTH_RATIO_MIN}). 原文の尾部を訳し落としていないか確かめる"]
    return []


def check_unit(unit: dict, ja: str, glossary: dict, names: dict[str, str]) -> list[str]:
    if not ja.strip():
        return ["訳文が空"]
    return (
        check_g02(unit, ja, glossary)
        + check_g03(unit, ja, names)
        + check_g04(unit, ja)
        + check_g05(ja)
        + check_g14(unit, ja)
    )
