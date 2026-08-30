"""判断表を機械の名寄せ結果に適用し、保存則で検算する。

機械(align.py)は英訳を鍵に 280 表層形中 245 を自動確定した。本モジュールは
そこへ人手の判断表(data/judgments/entities.json)を重ね、次を行う:

  * 別名・父称・形容辞の解決 (Pallas→Athena, Κρονίων→Zeus, Γερήνιος→Nestor)
  * 共起投票の誤付着の除去。ただし**捨てずに正しい実体へ移す**
  * 人手確認の有無を実体ごとに旗として残す

**G-10 名寄せ保存**: 統合・解決・移動の前後で総出現数が変わってはならない。
名寄せの事故は「取りこぼし」と「二重計上」の二方向に出るが、総和を見れば
どちらも一度に捕まる。表を書き換えたら必ずこのゲートを通す。

指示先が一意でない父称(Ἀτρεΐδης)は解決しない。決めないことを選べるのが、
後から判断を足せる設計の条件である。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JUDGMENTS = DATA / "judgments" / "entities.json"


def load_judgments() -> dict:
    return json.loads(JUDGMENTS.read_text(encoding="utf-8"))


def apply(align: dict, judgments: dict) -> dict:
    table = {e["english"]: e for e in judgments["entities"]}
    reassign = judgments.get("reassign", {})

    # 表層形 → 実体 に展開し直す。
    # **before は展開前の生の合計から取る。** 辞書の鍵に潰した後の合計を使うと、
    # 同じ形が二実体に割り当たったとき before と after が同時に縮んで総和が一致し、
    # 二重計上を保存則がすり抜ける(loop_003 / VERIF-GAP、陽性対照が暴いた)。
    before = sum(f["count"] for ent in align["entities"] for f in ent["forms"])

    forms: dict[str, dict] = {}
    duplicates: list[dict] = []
    for ent in align["entities"]:
        for f in ent["forms"]:
            prev = forms.get(f["form"])
            if prev is not None:
                duplicates.append(
                    {"form": f["form"], "entities": [prev["english"], ent["english"]],
                     "count": f["count"]}
                )
            forms[f["form"]] = {"english": ent["english"], "count": f["count"]}

    # 1) 誤付着の除去と移動
    moved = []
    for form, spec in reassign.items():
        if form in forms:
            moved.append({"form": form, "from": forms[form]["english"],
                          "to": spec["to"], "count": forms[form]["count"],
                          "why": spec["why"]})
            forms[form]["english"] = spec["to"]

    # 2) 別名・父称・形容辞の解決
    resolved = []
    for form, f in forms.items():
        j = table.get(f["english"])
        if j and j.get("resolves_to"):
            resolved.append({"form": form, "from": f["english"],
                             "to": j["resolves_to"], "count": f["count"],
                             "kind": j["category"]})
            f["english"] = j["resolves_to"]

    # 3) 実体へ束ね直す
    entities: dict[str, dict] = {}
    for form, f in forms.items():
        e = entities.setdefault(
            f["english"],
            {"english": f["english"], "forms": [], "count": 0},
        )
        e["forms"].append({"form": form, "count": f["count"]})
        e["count"] += f["count"]

    for name, e in entities.items():
        j = table.get(name, {})
        e["ja"] = j.get("ja")
        e["category"] = j.get("category", "unclassified")
        e["verified"] = bool(j.get("verified"))
        e["note"] = j.get("note", "")
        e["forms"].sort(key=lambda x: -x["count"])

    after = sum(e["count"] for e in entities.values())
    held = align["held"]

    ordered = sorted(entities.values(), key=lambda e: -e["count"])
    return {
        "meta": {
            "occurrences_before": before,
            "occurrences_after": after,
            "conserved": before == after and not duplicates,
            "duplicate_forms": len(duplicates),
            "entities": len(ordered),
            "verified": sum(1 for e in ordered if e["verified"]),
            "unverified": sum(1 for e in ordered if not e["verified"]),
            "reassigned_forms": len(moved),
            "resolved_forms": len(resolved),
            "held_forms": len(held),
            "held_occurrences": sum(f["count"] for f in held),
        },
        "entities": ordered,
        "duplicates": duplicates,
        "reassignments": moved,
        "resolutions": resolved,
    }


def main() -> None:
    align = json.loads((DATA / "align.json").read_text(encoding="utf-8"))
    res = apply(align, load_judgments())
    (DATA / "entities.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8"
    )
    m = res["meta"]
    print(f"実体 {m['entities']} 件(確認済 {m['verified']} / 未確認 {m['unverified']})")
    print(f"誤付着の移動 {m['reassigned_forms']} 形 / 別名・父称の解決 {m['resolved_forms']} 形")
    print(f"保留 {m['held_forms']} 形({m['held_occurrences']} 出現)")
    print(f"G-10 保存則: {m['occurrences_before']} → {m['occurrences_after']}"
          f" / 形の二重割当 {m['duplicate_forms']}"
          f"  {'合格' if m['conserved'] else '不合格'}")
    print(chr(10) + "解決の内訳:")
    for r in res["resolutions"]:
        print(f"   {r['form']:14s} {r['from']:10s} → {r['to']:10s} ({r['count']}回, {r['kind']})")


if __name__ == "__main__":
    main()
