"""上流の版を刻印する。

件数を定数でゲートに書くと、上流が改訂されたときに「我々の回帰」と区別がつかない。
取得物の sha256 を固定しておけば、件数のずれが起きたときに次のどちらかを即断できる:

  * ハッシュ一致 + 件数ずれ → **我々の回帰**。直す
  * ハッシュ不一致        → **上流の改訂**。実測し直して刻印と期待値を更新する

刻印の更新は専用コミット(`chore: repin upstream`)で行い、ループログに理由を残す。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources.json"

# 実測日 2026-08-31 / PerseusDL/canonical-greekLit master
PINNED_SHA256 = {
    "grc": "e00253c0b383d6c94f949524f0ec1d4491f585ebaf66413e8615199af5fd2904",
    "murray": "dda5b206e332e56c570c1d92ea41e9a510339a454bc2ea90491788e34174a7e7",
    "butler": "4404a35bd6fc679db69dc7f6b4d5414bd576821b12615ff0d9bf3f3a19d5834d",
}


def upstream_drift() -> list[str]:
    """刻印と実物のずれを返す。空リスト = 上流は動いていない。"""
    if not SOURCES.exists():
        return ["data/sources.json が無い(python -m pipeline.fetch_tei 未実行)"]
    got = json.loads(SOURCES.read_text(encoding="utf-8"))["editions"]
    out = []
    for key, sha in PINNED_SHA256.items():
        actual = got.get(key, {}).get("sha256")
        if actual != sha:
            out.append(f"{key}: 刻印 {sha[:12]}… / 実物 {str(actual)[:12]}…")
    return out
