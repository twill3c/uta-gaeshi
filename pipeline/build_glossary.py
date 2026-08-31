"""判断表(glossary_source.py)を用語集 JSON へ組み立てる。

対応がつかなかった反復行は**黙って落とさず一覧に出す**。用語集の穴は
G-02 の判定漏れになるので、穴があること自体を見えるようにしておく。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(DATA / "judgments"))


def build(books: tuple[int, ...] | None = (1, 2)) -> dict:
    from glossary_source import CORE  # noqa: E402

    from pipeline.translate import load_units

    formulas = json.loads((DATA / "formulas.json").read_text(encoding="utf-8"))
    by_key = {g["key"]: g for g in formulas["repeated_lines"]}
    units = load_units()
    # 用語集は巻をまたいで累積する。一度入った項目は以後のすべての巻を拘束する。
    need = sorted({
        k for u in units if books is None or u["book"] in books for k in u["formulas"]
    })

    entries, unmatched = {}, []
    for key in need:
        sample = by_key[key]["sample"]
        for prefix, (core, full) in CORE.items():
            if sample.startswith(prefix):
                entries[key] = {
                    "sample": sample, "count": by_key[key]["count"],
                    "core": core, "full": full, "matched_on": prefix,
                }
                break
        else:
            unmatched.append({"key": key, "sample": sample, "count": by_key[key]["count"]})
    return {
        "authored_on": "2026-08-31", "author": "loop_004/loop_005",
        "policy": {
            "core": "反復行が現れるたび一字一句同じで訳文に現れる不変部分",
            "variable": "前後の助詞・接続は文脈に合わせてよい",
            "gate": "G-02 は中核句の包含で判定する",
        },
        "coverage": {"needed": len(need), "authored": len(entries),
                     "unmatched": len(unmatched)},
        "entries": entries, "unmatched": unmatched,
    }


def main() -> None:
    g = build()
    (DATA / "judgments" / "glossary.json").write_text(
        json.dumps(g, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")
    c = g["coverage"]
    print(f"用語集 {c['authored']}/{c['needed']} 件 (未対応 {c['unmatched']})")
    for u in g["unmatched"]:
        print(f"   未: {u['sample'][:56]}")


if __name__ == "__main__":
    main()
