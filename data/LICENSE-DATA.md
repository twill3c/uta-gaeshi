# データの権利表示

## 出典

本プロジェクトの構造化データは、Perseus Digital Library の TEI XML を出典とする。

| 版 | 内容 | 権利 |
|---|---|---|
| `tlg0012.tlg002.perseus-grc2` | ホメロス『オデュッセイア』ギリシャ語原典(A.T. Murray 校訂、Loeb 1919) | 原典はパブリックドメイン |
| `tlg0012.tlg002.perseus-eng3` | A.T. Murray 英訳(1919) | パブリックドメイン |
| `tlg0012.tlg002.perseus-eng4` | Samuel Butler 英訳(Power / Nagy 改訂) | パブリックドメイン |

TEI 符号化と校訂データ:
**Perseus Digital Library, Tufts University — Creative Commons Attribution-ShareAlike 4.0 International(CC BY-SA 4.0)**

取得元は <https://github.com/PerseusDL/canonical-greekLit> であり、権利は取得物(TEI ファイル)
自体には書かれておらず、**リポジトリの `license.md` と README にのみある**。

### 表記の訂正(2026-08-31)

本ファイルおよびサイトは、これを長らく「**CC BY-SA 3.0 United States**」と表記していた。
**版も適用域も誤り**である。原因は、Perseus の*ウェブサイト*の規約を読んだ一方で、
ファイルは *GitHub リポジトリ*から取得していたこと。両者のライセンスは実際に異なる。
サイト(`/about`)は 2026-08-31 に訂正したが、本ファイルの訂正は 2026-09-02 まで漏れていた。

## 本プロジェクトの派生物

`data/units.json` および以後の派生データ(和訳を含む)は上記の派生著作物にあたるため、
**CC BY-SA 4.0 International** で頒布する。継承条項に従い、再配布時は同ライセンスと
Perseus へのクレジットを維持すること。

コード(`pipeline/`, `tests/`, `harness/`)はリポジトリ直下の `LICENSE` に従う(MIT)。

## 継承のほかに課されるもの — 改変の還元(未履行)

出典の README は継承に加えてこう定めている ——
**「You must offer Perseus any modifications you make」**(改変を行った場合は Perseus に提供すること)。

本プロジェクトは出典データに対して**修復を 2 件**行っている(`data/repairs.json` に機械可読な形で記録)。

| 版 | 位置 | 種別 | 施した処置 |
|---|---|---|---|
| murray | 巻 6 行 320 | `duplicate_anchor` | 本文を直前の錨へ統合 |
| murray | 巻 16 行 580 | `out_of_range` | 錨を除去し本文を直前の錨へ引き継ぎ |

**この還元はまだ Perseus へ提供していない。未履行であることをここに明記する。**

なお `grc` 巻 3 行 304 と巻 14 行 63 の組版順の逆転は Loeb 版の校訂判断であって欠陥ではないため、
修復せず「正準行番号順に整列した事実」として記録している(改変にあたらない)。

## 帰属表示の文例

> 原文: Homer, *Odyssea*, ed. A. T. Murray (Loeb, 1919).
> Perseus Digital Library, Tufts University. CC BY-SA 4.0.
> 日本語訳: uta-gaeshi プロジェクト(機械翻訳)。CC BY-SA 4.0.

## 使えない翻訳

日本語の既存訳は以下の理由で本プロジェクトでは使用しない。

- 松平千秋訳・呉茂一訳 — 著作権存続中
- 土井晩翠訳(1941) — 日本ではパブリックドメイン(訳者 1952 年没)だが、
  青空文庫では『オヂュッセーア』が **2026-08-31 時点で「作業中」で未公開**であり、
  利用可能な電子テキストが存在しない(『イーリアス』のみ公開)

したがって和訳は自前で生成する。生成方法と測定値は `/about` で開示する。
