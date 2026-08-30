# データの権利表示

## 出典

本プロジェクトの構造化データは、Perseus Digital Library の TEI XML を出典とする。

| 版 | 内容 | 権利 |
|---|---|---|
| `tlg0012.tlg002.perseus-grc2` | ホメロス『オデュッセイア』ギリシャ語原典(A.T. Murray 校訂、Loeb 1919) | 原典はパブリックドメイン |
| `tlg0012.tlg002.perseus-eng3` | A.T. Murray 英訳(1919) | パブリックドメイン |
| `tlg0012.tlg002.perseus-eng4` | Samuel Butler 英訳(Power / Nagy 改訂) | パブリックドメイン |

TEI 符号化と校訂データ:
**Perseus Digital Library, Tufts University — Creative Commons Attribution-ShareAlike 3.0 United States**

## 本プロジェクトの派生物

`data/units.json` および以後の派生データ(和訳を含む)は上記の派生著作物にあたるため、
**CC BY-SA 3.0 US** で頒布する。継承条項に従い、再配布時は同ライセンスと
Perseus へのクレジットを維持すること。

コード(`pipeline/`, `tests/`, `harness/`)はリポジトリ直下の `LICENSE` に従う。

## 使えない翻訳

日本語の既存訳は以下の理由で本プロジェクトでは使用しない。

- 松平千秋訳・呉茂一訳 — 著作権存続中
- 土井晩翠訳(1941) — 日本ではパブリックドメイン(訳者 1952 年没)だが、
  青空文庫では『オヂュッセーア』が **2026-08-31 時点で「作業中」で未公開**であり、
  利用可能な電子テキストが存在しない(『イーリアス』のみ公開)

したがって和訳は自前で生成する。生成方法と測定値は `/about` で開示する。
