"""Perseus canonical-greekLit から『オデュッセイア』の TEI XML を取得する。

出典: PerseusDL/canonical-greekLit (CC BY-SA 4.0 International)
  tlg0012.tlg002.perseus-grc2 … ギリシャ語原典(Murray 校訂 Loeb 1919)
  tlg0012.tlg002.perseus-eng3 … A.T. Murray 英訳 1919
  tlg0012.tlg002.perseus-eng4 … Samuel Butler 英訳(Power/Nagy 改訂)

取得物は data/raw/(git 管理外)へ置き、sha256 を data/sources.json に刻む。
再取得時にハッシュが変われば、それは上流の改訂であって我々の測定値のずれではない
--- どちらであるかを常に切り分けられるようにするための刻印である。
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SOURCES = ROOT / "data" / "sources.json"

BASE = (
    "https://raw.githubusercontent.com/PerseusDL/canonical-greekLit"
    "/master/data/tlg0012/tlg002/"
)

EDITIONS = {
    "grc": {
        "file": "tlg0012.tlg002.perseus-grc2.xml",
        "lang": "grc",
        "label": "ギリシャ語原典(Murray 校訂 Loeb 1919)",
        "role": "原典",
    },
    "murray": {
        "file": "tlg0012.tlg002.perseus-eng3.xml",
        "lang": "eng",
        "label": "A.T. Murray 英訳 1919",
        "role": "対訳(主)",
    },
    "butler": {
        "file": "tlg0012.tlg002.perseus-eng4.xml",
        "lang": "eng",
        "label": "Samuel Butler 英訳(Power/Nagy 改訂)",
        "role": "対訳(照合用)",
    },
}

# 権利は**取得元リポジトリの license.md と README** にある。TEI ヘッダには
# <licence> 要素が一つも無い(取得物を見るだけでは分からない構造)。
# 初回にウェブサイト側の規約(3.0 US)を読んで 12 ループ誤表記した(HC-091)。
LICENSE = "CC BY-SA 4.0 International"
# 出典 README が課す追加義務。継承だけでなく還元も求めている。
OBLIGATION = "改変は Perseus へ提供すること (You must offer Perseus any modifications you make)"
ATTRIBUTION = "Perseus Digital Library, Tufts University"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(key: str, *, force: bool = False) -> Path:
    spec = EDITIONS[key]
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / spec["file"]
    if dest.exists() and not force:
        return dest
    url = BASE + spec["file"]
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (固定 https)
        data = r.read()
    dest.write_bytes(data)
    return dest


def fetch_all(*, force: bool = False) -> dict:
    manifest = {
        "source": "PerseusDL/canonical-greekLit",
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "base_url": BASE,
        "editions": {},
    }
    for key, spec in EDITIONS.items():
        path = fetch(key, force=force)
        raw = path.read_bytes()
        manifest["editions"][key] = {
            "file": spec["file"],
            "lang": spec["lang"],
            "label": spec["label"],
            "role": spec["role"],
            "bytes": len(raw),
            "sha256": sha256(raw),
        }
    SOURCES.parent.mkdir(parents=True, exist_ok=True)
    SOURCES.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    m = fetch_all()
    for k, v in m["editions"].items():
        print(f"{k:8s} {v['bytes']:>9,d} bytes  {v['sha256'][:16]}…  {v['label']}")
