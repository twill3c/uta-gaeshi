"""和訳の台帳と較正ゲート。

全 2,432 単位は一度の作業では終わらない。**再開可能な追記台帳**を軸に据え、
一度訳した単位を二度と訳し直さないことを設計の前提にする。

方針(loop_004 で確定、data/judgments/policy.json):
  * 文体は平明な現代語散文
  * 定型句は**中核句を一字一句同一に固定し、前後の助詞・接続だけ文脈に合わせる**。
    G-02 は中核句の包含で判定する。完全一致にすると日本語が壊れ、訳し分けを許すと
    原典の反復構造が訳文から消えて目玉のオラクルが成立しない。その中間を取る。

用語集は訳しながら育つが、**一度入った項目は以後拘束する**。第1巻に現れる反復行
94 種はすべて他巻へ波及するため、第1巻を訳した時点で残り 23 巻の骨格が決まる。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEDGER = DATA / "translated.jsonl"
GLOSSARY = DATA / "judgments" / "glossary.json"


def load_units() -> list[dict]:
    """単位に、その単位が含む反復行の鍵を注釈して返す。

    G-02 はこの注釈を見て「この単位は用語集のどの中核句を含むべきか」を判定する。
    注釈は formulas.json(決定論的な全数集計)から引くので、判定材料に我々の解釈は入らない。
    """
    units = json.loads((DATA / "units.json").read_text(encoding="utf-8"))["units"]
    fpath = DATA / "formulas.json"
    if fpath.exists():
        formulas = json.loads(fpath.read_text(encoding="utf-8"))["repeated_lines"]
        by_unit: dict[str, list[str]] = {}
        for g in formulas:
            for o in g["occurrences"]:
                by_unit.setdefault(o["unit"], []).append(g["key"])
        for u in units:
            u["formulas"] = by_unit.get(u["id"], [])
    else:
        for u in units:
            u["formulas"] = []
    return units


def load_glossary() -> dict:
    if not GLOSSARY.exists():
        return {"entries": {}}
    return json.loads(GLOSSARY.read_text(encoding="utf-8"))


def read_ledger() -> dict[str, dict]:
    """追記台帳を読む。同一 id が複数あれば最後の行を採る(訂正を許す)。"""
    out: dict[str, dict] = {}
    if not LEDGER.exists():
        return out
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


def append(records: list[dict]) -> int:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + chr(10))
    return len(records)


def pending(book: int | None = None) -> list[dict]:
    done = read_ledger()
    return [
        u for u in load_units()
        if u["id"] not in done and (book is None or u["book"] == book)
    ]


def progress() -> dict:
    units = load_units()
    done = read_ledger()
    per: dict[int, dict] = {}
    for u in units:
        e = per.setdefault(u["book"], {"total": 0, "done": 0})
        e["total"] += 1
        if u["id"] in done:
            e["done"] += 1
    return {
        "total": len(units),
        "done": len(done),
        "share": round(len(done) / len(units), 4) if units else 0.0,
        "per_book": per,
    }


def main() -> None:
    p = progress()
    print(f"和訳済み {p['done']:,} / {p['total']:,} 単位 ({p['share']*100:.1f}%)")
    g = load_glossary()
    print(f"用語集 {len(g['entries'])} 項目")
    for b in sorted(p["per_book"]):
        e = p["per_book"][b]
        if e["done"]:
            print(f"  巻{b:2d}: {e['done']:3d}/{e['total']:3d}")


if __name__ == "__main__":
    main()


def name_table() -> dict[str, str]:
    """G-03 が使う 英訳名 → 和名。人手確認済みの実体だけを対象にする。

    未確認の実体を混ぜると、機械の誤りをゲートが要求してしまう。
    確認済みに限ることで、ゲートが要求する内容の出所が必ず人手判断になる。
    """
    path = DATA / "entities.json"
    if not path.exists():
        return {}
    ents = json.loads(path.read_text(encoding="utf-8"))["entities"]
    return {
        e["english"]: e["ja"]
        for e in ents
        if e.get("verified") and e.get("ja") and e["category"] in ("person", "place", "group")
    }


def record_batch(translations: dict[str, str]) -> dict:
    """訳文を検査して台帳へ追記する。

    違反があっても記録は行い、違反内容を台帳に残す。落ちた訳を握り潰すと
    合格率が実態より高く出る。**測れる不合格のほうが、見えない不合格よりよい。**
    """
    from pipeline.tgates import check_unit

    units = {u["id"]: u for u in load_units()}
    glossary = load_glossary()
    names = name_table()

    records, violations = [], []
    for uid, ja in translations.items():
        u = units[uid]
        v = check_unit(u, ja, glossary, names)
        records.append({"id": uid, "book": u["book"], "line_start": u["line_start"],
                        "line_end": u["line_end"], "ja": ja, "violations": v})
        if v:
            violations.append({"id": uid, "violations": v})
    append(records)
    return {"recorded": len(records), "with_violations": len(violations),
            "detail": violations}


def recheck() -> dict:
    """台帳の全訳文を現在の用語集・和名表で検査し直す。

    用語集や判断表を改訂したら必ず通す。過去の訳が新しい規則に合わなくなることは
    起こりうるので、**改訂のたびに全件を測り直す**のが前提。
    """
    from pipeline.tgates import check_unit

    units = {u["id"]: u for u in load_units()}
    glossary = load_glossary()
    names = name_table()
    ledger = read_ledger()

    failed = []
    for uid, rec in ledger.items():
        v = check_unit(units[uid], rec["ja"], glossary, names)
        if v:
            failed.append({"id": uid, "violations": v})
    return {
        "checked": len(ledger),
        "passed": len(ledger) - len(failed),
        "failed": len(failed),
        "rate": round((len(ledger) - len(failed)) / len(ledger), 4) if ledger else 0.0,
        "detail": failed,
    }


def show_pending(book: int, limit: int = 14) -> None:
    """未訳の単位を**全文で**出す。

    切り詰めた表示のまま訳すと、原文の尾部が黙って落ちる(loop_007 / HC-086)。
    第4巻では 169 単位中 122 単位が 280 字の表示窓を超えており、
    そのうち 7 件で実際に訳し落としが起きた。**表示を切らないことが唯一の予防である。**
    """
    glossary = load_glossary()["entries"]
    done = read_ledger()
    todo = [u for u in load_units() if u["book"] == book and u["id"] not in done]
    print(f"第{book}巻 未訳 {len(todo)} 単位")
    for u in todo[:limit]:
        cores = [glossary[k]["core"] for k in u["formulas"] if k in glossary]
        head = f"### {u['id']}  英{len(u['murray'])}字"
        print(head + (f"  中核句: {cores}" if cores else ""))
        print(u["murray"])
        print()
