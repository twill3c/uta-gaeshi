"""構造ゲート G-01 と、その陽性対照 G-06 の判定本体。

ゲートは「違反の一覧」を返す純関数として書く。テストは本物のコーパスに対して
空であることを検査し(G-01)、故意に壊したコーパスに対して非空であることを検査する(G-06)。
同じ関数を両方向から叩くので、ゲートが実は何も見ていないという事故を防げる。
"""
from __future__ import annotations

BOOKS = 24
GREEK_LINES = 12107
UNITS = 2432

# 校訂で削除され、引用の安定のため番号だけが残っている行(実測)。
# 埋めてはならない。上流が変われば気づけるよう、期待値として固定する。
KNOWN_GAPS = {10: [456], 16: [101], 23: [49]}

# 出典の組版順が正準行番号順と食い違う箇所(校訂判断であって欠陥ではない)。
KNOWN_TRANSPOSITIONS = {3: 304, 14: 63}


def check_structure(corpus: dict) -> list[str]:
    """G-01。違反があれば人間可読の文字列で返す。空リスト = 合格。"""
    v: list[str] = []
    units = corpus["units"]

    books = sorted({u["book"] for u in units})
    if books != list(range(1, BOOKS + 1)):
        v.append(f"巻が 1..{BOOKS} の連番でない: {books}")

    if len(units) != UNITS:
        v.append(f"翻訳単位が {len(units)} 件(期待 {UNITS})")

    # 単位の健全性
    for u in units:
        if not u["greek"]:
            v.append(f"単位 {u['id']} に原典行が無い")
        if not u["murray"].strip():
            v.append(f"単位 {u['id']} の Murray 訳が空")
        if u["line_start"] > u["line_end"]:
            v.append(f"単位 {u['id']} の区間が逆転: {u['line_start']}..{u['line_end']}")

    # 分割性: 原典行を過不足なく、重複なく覆う
    seen: set[tuple[int, int]] = set()
    overlaps = 0
    for u in units:
        for g in u["greek"]:
            key = (u["book"], g["line"])
            if key in seen:
                overlaps += 1
            seen.add(key)
    if overlaps:
        v.append(f"原典行が複数の単位に重複割当: {overlaps} 件")
    if len(seen) != GREEK_LINES:
        v.append(f"被覆した原典行が {len(seen):,}(期待 {GREEK_LINES:,})")

    # 巻ごとの行番号: 一意かつ狭義単調、欠番は既知のものだけ
    for b in books:
        lines = [g["line"] for u in units if u["book"] == b for g in u["greek"]]
        if len(lines) != len(set(lines)):
            v.append(f"巻{b} の行番号に重複がある")
        if lines != sorted(lines):
            v.append(f"巻{b} の行番号が単調でない")
        if lines:
            gaps = sorted(set(range(1, max(lines) + 1)) - set(lines))
            if gaps != KNOWN_GAPS.get(b, []):
                v.append(f"巻{b} の欠番が {gaps}(既知 {KNOWN_GAPS.get(b, [])})")

    return v


def check_repairs(corpus: dict) -> list[str]:
    """出典欠陥の修復記録が、実測した既知の欠陥と一致することを検査する。"""
    v: list[str] = []
    reps = corpus.get("repairs", [])
    trans = {r["book"]: r["line"] for r in reps if r["kind"] == "transposed"}
    if trans != KNOWN_TRANSPOSITIONS:
        v.append(f"組版順の逆転が {trans}(既知 {KNOWN_TRANSPOSITIONS})")
    kinds = sorted(r["kind"] for r in reps)
    expected = ["duplicate_anchor", "out_of_range", "transposed", "transposed"]
    if kinds != expected:
        v.append(f"修復の種別が {kinds}(期待 {expected})")
    return v


def diagnose(corpus: dict) -> str:
    """G-01 が落ちたとき、上流の改訂か我々の回帰かを言い分ける。"""
    from pipeline.pins import upstream_drift

    violations = check_structure(corpus)
    if not violations:
        return "G-01 合格"
    drift = upstream_drift()
    cause = "上流が改訂された(刻印と実物が不一致)" if drift else "我々の回帰(上流は不動)"
    return f"G-01 不合格 — {cause}\n" + "\n".join(f"  - {x}" for x in violations + drift)
