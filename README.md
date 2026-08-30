# uta-gaeshi(歌返し)

ホメロス『オデュッセイア』全 24 巻・原典 12,107 行を、行番号に固定した日本語で読む。

**同じ行が返ってくる** — 全行の 17.8%(808 種・2,155 回)が他の行の逐語的な繰り返しであることが、
口誦叙事詩としてのこの作品の骨格である。本プロジェクトはそれを全数で示し、同時に
「原典で同一の行は和訳でも同一であるべき」という**非循環の検査**として使う。

和訳は自前の機械生成である。既存の日本語訳は使えない(`data/LICENSE-DATA.md`)。
訳の巧拙は主張せず、生成方法と測定値を開示する。

## 状態

| ループ | 内容 | 状態 |
|---|---|---|
| L1 | TEI 取得・構造化・G-01 / G-06 | 完了 |
| L2 | 定型句・話者・地名の全数測定 | 未着手 |
| L3 | 名寄せ表と用語集の確定 | 未着手 |
| L4 | 全 2,432 単位の和訳 | 未着手 |
| L5 | 較正ゲートの測定 | 未着手 |
| L6 | 公開 | 未着手 |

## 使い方

```bash
python -m pipeline.fetch_tei    # 出典 TEI を取得し sha256 を data/sources.json に刻む
python -m pipeline.parse_tei    # 翻訳単位 data/units.json を構築
python -m pytest -q             # G-01 構造ゲートと G-06 陽性対照
```

`data/raw/` は git 管理外(再取得可能)。上流が改訂されると `tests/test_pins.py` だけが落ちる。
そのときは実測し直して `pipeline/pins.py` と `pipeline/gates.py` を更新する。

## 出典と権利

Perseus Digital Library, Tufts University(CC BY-SA 3.0 US)。
派生データも同ライセンスで頒布する。詳細は `data/LICENSE-DATA.md`。
