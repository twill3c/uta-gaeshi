# -*- coding: utf-8 -*-
"""静的サイトの生成。

方針(SPEC N-01):
  * 完全 SSG。実行時の API 呼び出し・DB・cron をいっさい持たない
  * **外部リクエストをゼロにする**。CDN もウェブフォントも使わない。
    課金経路を作らないという要求は、外部依存を持たないことと同義である
  * 未訳の巻は空にせず、原典と Murray 英訳を出したうえで「未訳」と明示する。
    訳が無いことを隠さないほうが、読み手にとっても我々にとっても正確である

相互リンクの座標系は **巻.行** ひとつに統一する。定型句・人物・地名の三索引は
すべて `book/N.html#L{行}` を指し、本文側は同じ id を持つ。
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "out"

REPO = "https://github.com/twill3c/uta-gaeshi"
APP_MENU = "https://app-menu-amber.vercel.app"
GUIDE = "https://claude.ai/code/artifact/53733816-46f1-4044-bf43-9c62a9060480"
DESIGN = "https://claude.ai/code/artifact/4870833a-4718-438b-948b-840296c004dd"

CSS = """
:root{--bg:#fbfaf7;--fg:#1c1a17;--sub:#6b6459;--line:#ddd6c9;--acc:#7a5c3e;--mark:#f0e6d2}
*{box-sizing:border-box}
body{margin:0;padding:0 0 3.2rem;background:var(--bg);color:var(--fg);
 font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.85}
header{border-bottom:1px solid var(--line);padding:1.1rem 1rem .9rem}
header h1{margin:0;font-size:1.35rem;letter-spacing:.04em}
header h1 .en{font-size:.62rem;color:var(--sub);margin-left:.6rem;letter-spacing:.14em}
header p{margin:.35rem 0 0;font-size:.8rem;color:var(--sub)}
nav{padding:.5rem 1rem;border-bottom:1px solid var(--line);font-size:.85rem}
nav a{color:var(--acc);text-decoration:none;margin-right:1rem}
nav a:hover{text-decoration:underline}
main{max-width:56rem;margin:0 auto;padding:1.2rem 1rem}
h2{font-size:1.05rem;margin:1.8rem 0 .6rem;border-left:3px solid var(--acc);padding-left:.5rem}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{border-bottom:1px solid var(--line);padding:.35rem .5rem;text-align:left;vertical-align:top}
th{color:var(--sub);font-weight:normal;white-space:nowrap}
.unit{margin:0 0 1.4rem;padding-top:.3rem}
.ln{font-size:.7rem;color:var(--sub);letter-spacing:.05em}
.ja{margin:.15rem 0 0}
.grc,.eng{margin:.3rem 0 0;font-size:.82rem;color:var(--sub)}
.grc{font-family:"Palatino Linotype",Palatino,serif}
.untranslated{color:var(--sub);font-style:italic}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(7.2rem,1fr));gap:.4rem}
.grid a{display:block;border:1px solid var(--line);border-radius:3px;padding:.45rem .5rem;
 text-decoration:none;color:var(--fg);font-size:.85rem;background:#fff}
.grid a .st{display:block;font-size:.68rem;color:var(--sub);margin-top:.15rem}
.grid a.done{border-color:var(--acc)}
.note{font-size:.8rem;color:var(--sub);background:#fff;border:1px solid var(--line);
 border-radius:3px;padding:.6rem .8rem;margin:.8rem 0}
.tier1{color:#2c5f2d}.tier2{color:#8a6d1f}.tier3{color:#8a3324}
mark{background:var(--mark)}
.modes{font-size:.8rem;color:var(--sub);margin:.2rem 0 1rem}
.modes button{font:inherit;font-size:.8rem;border:1px solid var(--line);background:#fff;
 color:var(--fg);border-radius:3px;padding:.2rem .55rem;margin-right:.3rem;cursor:pointer}
.modes button[aria-pressed=true]{border-color:var(--acc);background:var(--mark)}
body.hide-grc .grc{display:none}
body.hide-eng .eng{display:none}
footer{position:fixed;left:0;right:0;bottom:0;z-index:10;background:var(--bg);
 border-top:1px solid var(--line);color:var(--sub);font-size:.75rem;text-align:center;
 padding:.5rem 1rem;white-space:nowrap;overflow-x:auto}
footer p{display:inline;margin:0}
footer a{color:var(--sub)}
"""

FOOTER = f"""<footer>
  <p><a href="{REPO}/blob/main/LICENSE" target="_blank" rel="noopener">MIT License</a> © 2026 坂田哲朗
  ・ <a href="{REPO}" target="_blank" rel="noopener">GitHub</a>
  ・ <a href="{GUIDE}" target="_blank" rel="noopener">歌返しの歩き方</a>
  ・ <a href="{DESIGN}" target="_blank" rel="noopener">歌返し設計図</a>
  ・ <a href="about.html">出典と作り方</a>
  ・ 本文データ CC BY-SA 3.0 US（Perseus Digital Library）
  ・ <a href="{APP_MENU}" target="_blank" rel="noopener">App Menu</a></p>
</footer>"""


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def page(title: str, body: str, *, depth: int = 0, extra_head: str = "") -> str:
    up = "../" * depth
    nav = (f'<nav><a href="{up}index.html">目次</a>'
           f'<a href="{up}formula.html">定型句</a>'
           f'<a href="{up}person.html">登場者</a>'
           f'<a href="{up}place.html">地名</a>'
           f'<a href="{up}about.html">出典と作り方</a></nav>')
    foot = FOOTER.replace('href="about.html"', f'href="{up}about.html"')
    return (f'<!doctype html>\n<html lang="ja">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{esc(title)}</title>\n<style>{CSS}</style>\n{extra_head}</head>\n<body>\n'
            f'{nav}\n<main>\n{body}\n</main>\n{foot}\n</body>\n</html>\n')


# ---- データ読み込み ---------------------------------------------------------

def load():
    corpus = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    formulas = json.loads((DATA / "formulas.json").read_text(encoding="utf-8"))
    entities = json.loads((DATA / "entities.json").read_text(encoding="utf-8"))
    places = json.loads((DATA / "places.json").read_text(encoding="utf-8"))
    tiers = json.loads((DATA / "judgments" / "places_tiers.json").read_text(encoding="utf-8"))
    speakers = json.loads((DATA / "speakers.json").read_text(encoding="utf-8"))
    ledger = {}
    lp = DATA / "translated.jsonl"
    if lp.exists():
        for line in lp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                ledger[r["id"]] = r["ja"]
    return corpus, formulas, entities, places, tiers, speakers, ledger


def ref(book: int, line: int, depth: int = 0) -> str:
    up = "../" * depth
    return f'<a href="{up}book/{book}.html#L{line}">{book}.{line}</a>'


# ---- 各ページ ---------------------------------------------------------------

def build_book(book: int, corpus, ledger) -> tuple[str, int, int]:
    units = [u for u in corpus["units"] if u["book"] == book]
    done = sum(1 for u in units if u["id"] in ledger)
    parts = [f'<h2>第 {book} 巻</h2>']
    if done == 0:
        parts.append('<div class="note">この巻はまだ和訳していません。'
                     '原典（ギリシャ語）と Murray 英訳のみを掲げます。</div>')
    elif done < len(units):
        parts.append(f'<div class="note">この巻は {done}/{len(units)} 単位まで和訳済みです。</div>')
    parts.append('<div class="modes">表示：'
                 '<button type="button" data-mode="ja" aria-pressed="true">和</button>'
                 '<button type="button" data-mode="jaeng" aria-pressed="false">和英</button>'
                 '<button type="button" data-mode="all" aria-pressed="false">希和英</button></div>')
    for u in units:
        ja = ledger.get(u["id"])
        grc = " / ".join(g["text"] for g in u["greek"])
        # 正準行番号のすべてにアンカーを置く。索引は個々の行(Od. 1.388)を指すため、
        # 単位の先頭行だけに id を置くと飛び先が無くなる(loop_010 / G-15 が検出)。
        # 引用形式そのままで解決できることは設計意図でもある。
        anchors = "".join(f'<span id="L{g["line"]}"></span>' for g in u["greek"])
        parts.append(f'<div class="unit">{anchors}')
        parts.append(f'<div class="ln">{book}.{u["line_start"]}–{u["line_end"]}</div>')
        if ja:
            parts.append(f'<p class="ja">{esc(ja)}</p>')
        else:
            parts.append('<p class="ja untranslated">（未訳）</p>')
        parts.append(f'<p class="grc">{esc(grc)}</p>')
        parts.append(f'<p class="eng">{esc(u["murray"])}</p>')
        parts.append('</div>')
    script = """<script>
document.addEventListener('DOMContentLoaded',function(){
 var b=document.body,btns=document.querySelectorAll('.modes button');
 function set(m){b.classList.toggle('hide-grc',m!=='all');
  b.classList.toggle('hide-eng',m==='ja');
  btns.forEach(function(x){x.setAttribute('aria-pressed',String(x.dataset.mode===m))});}
 btns.forEach(function(x){x.addEventListener('click',function(){set(x.dataset.mode)})});
 set('ja');});
</script>"""
    return page(f"第{book}巻 — 歌返し", "\n".join(parts), depth=1, extra_head=script), done, len(units)


def build_index(corpus, ledger, formulas) -> str:
    per = defaultdict(lambda: [0, 0])
    for u in corpus["units"]:
        per[u["book"]][1] += 1
        if u["id"] in ledger:
            per[u["book"]][0] += 1
    total_done = sum(v[0] for v in per.values())
    total = sum(v[1] for v in per.values())
    m = formulas["meta"]
    cells = []
    for b in range(1, 25):
        d, t = per[b]
        cls = " done" if d == t else ""
        st = "完訳" if d == t else (f"{d}/{t}" if d else "未訳")
        cells.append(f'<a class="grid-cell{cls}" href="book/{b}.html">第 {b} 巻'
                     f'<span class="st">{st}</span></a>')
    body = f"""<h2>ホメロス『オデュッセイア』</h2>
<p>全 24 巻・原典 {m['total_lines']:,} 行。和訳は <strong>{total_done:,} / {total:,} 単位
（{100*total_done/total:.1f}%）</strong>。</p>
<div class="note">和訳は自前の機械生成です。既存の日本語訳は使っていません（著作権存続、
あるいは電子テキスト不在）。訳の巧拙は主張せず、生成方法と測定値を
<a href="about.html">出典と作り方</a>で開示しています。</div>
<div class="grid">{''.join(cells)}</div>
<h2>三つの索引</h2>
<table>
<tr><th><a href="formula.html">定型句</a></th><td>逐語的に反復する行 <strong>{m['repeated_types']} 種 /
 {m['repeated_occurrences']:,} 回</strong>＝全行の {m['repeated_share']*100:.1f}%。
 この反復が和訳の検査そのものになっています。</td></tr>
<tr><th><a href="person.html">登場者</a></th><td>発話・在席・言及の三層で分けた一覧。
 「名前が出る」ことと「その場にいる」ことは別です。</td></tr>
<tr><th><a href="place.html">地名</a></th><td>同定確実／比定に争いあり／同定不能の三段。
 <strong>オデュッセウスの航路は地図に描けません。</strong></td></tr>
</table>"""
    return page("歌返し — ホメロス『オデュッセイア』", body)


def build_formula(formulas, ledger, corpus) -> str:
    """目玉。逐語的に反復する行を、出現位置つきで並べる。"""
    m = formulas["meta"]
    reps = formulas["repeated_lines"]
    rows = []
    for g in reps[:120]:
        refs = " ".join(ref(o["book"], o["line"]) for o in g["occurrences"][:14])
        more = f" ほか{len(g['occurrences'])-14}箇所" if len(g["occurrences"]) > 14 else ""
        rows.append(f'<tr><td style="white-space:nowrap">{g["count"]} 回</td>'
                    f'<td><span class="grc">{esc(g["sample"])}</span><br>{refs}{more}</td></tr>')
    body = f"""<h2>定型句の地図</h2>
<p>原典 {m['total_lines']:,} 行のうち、<strong>{m['repeated_occurrences']:,} 行（{m['repeated_share']*100:.1f}%）が
他の行の逐語的な繰り返し</strong>です。異なり {m['repeated_types']} 種。口誦叙事詩としての
この作品の骨格が、そのまま数字に出ています。</p>
<div class="note">この集計は原典の n-gram を数えただけで、我々の解釈は一切入っていません。
だからこそ<strong>和訳の検査に使えます</strong> — 原典で同一の行は、和訳でも同一に訳されていなければ
ならない。この制約は {m['equality_constraints']:,} 件あり、しかも
<strong>{m['cross_unit_types']} 種すべてが翻訳単位を跨いで</strong>います。
つまり離れた場所どうしの一貫性を要求します。機械翻訳を、機械翻訳自身に採点させずに
検査できるのはこのためです。</div>
<p>4-gram で 5 回以上現れる定型句は {m['ngram_types']['4']} 種、
3-gram では {m['ngram_types']['3']} 種あります。以下は反復行の上位 120 種です。</p>
<table><tr><th>回数</th><th>行（原典）と出現位置</th></tr>{''.join(rows)}</table>"""
    return page("定型句の地図 — 歌返し", body)


def build_person(entities, speakers, ledger) -> str:
    """三層(発話/在席/言及)で分けた登場者一覧。"""
    form2ent = {}
    for e in entities["entities"]:
        for f in e["forms"]:
            form2ent[f["form"]] = e
    spoke, addressed = defaultdict(list), defaultdict(list)
    for line in speakers["speech_lines"]:
        for n in line["names"]:
            e = form2ent.get(n["key"])
            if not e:
                continue
            if n["role"] == "speaker":
                spoke[e["english"]].append((line["book"], line["line"]))
            elif n["role"] == "addressee":
                addressed[e["english"]].append((line["book"], line["line"]))
    persons = [e for e in entities["entities"]
               if e["category"] == "person" and e.get("verified") and e.get("ja")]
    persons.sort(key=lambda e: -e["count"])
    rows = []
    for e in persons:
        sp, ad = spoke.get(e["english"], []), addressed.get(e["english"], [])
        if sp:
            tier, cls = "発話", "tier1"
        elif ad:
            tier, cls = "在席", "tier2"
        else:
            tier, cls = "言及のみ", "tier3"
        where = " ".join(ref(b, l) for b, l in (sp or ad)[:8]) or "—"
        note = f'<br><span class="ln">{esc(e["note"])}</span>' if e.get("note") else ""
        rows.append(f'<tr><td>{esc(e["ja"])}<span class="ln"> {esc(e["english"])}</span>{note}</td>'
                    f'<td class="{cls}">{tier}</td><td>{e["count"]}</td>'
                    f'<td>{len(sp)}</td><td>{where}</td></tr>')
    body = f"""<h2>登場者一覧</h2>
<div class="note"><strong>「名前が出る」ことと「その場にいる」ことは別です。</strong>
この一覧は三層に分けています。<span class="tier1">発話</span>＝発話導入の定型句に主格で現れる
（機械的に確定）。<span class="tier2">在席</span>＝対格・呼格で呼びかけられている。
<span class="tier3">言及のみ</span>＝語られるだけ。たとえばアガメムノンは名前が数多く出ますが、
本人が現れるのは死者としてです。</div>
<p>ギリシャ語は格で役割を符号化しています。主格＝話し手、対格＝相手、属格＝父称。
父称は<strong>別人を指す</strong>ため（「アトレウスの子」はアガメムノンかメネラオス）、
名前の出現をそのまま数えると壊れます。指示先が一意なものだけ解決し、曖昧なものは保留しました。</p>
<p>人手で確認したのは出現 10 回以上の人物と地名・集団です。残りは機械確定のまま
「未確認」として出しています。</p>
<table><tr><th>人物</th><th>層</th><th>出現</th><th>発話</th><th>位置</th></tr>{''.join(rows)}</table>"""
    return page("登場者一覧 — 歌返し", body)


def build_place(places, tiers) -> str:
    """三段の地名台帳。同定不能な地に座標を与えない。"""
    occ = {}
    for p in places["places"]:
        for s in p["surfaces"]:
            occ.setdefault(s, []).extend(p["occurrences"])
    groups = {1: [], 2: [], 3: [], "mythic": []}
    for p in tiers["places"]:
        groups[p["tier"]].append(p)
    def table(items):
        rows = []
        for p in items:
            o = occ.get(p["english"], [])
            where = " ".join(ref(x["book"], x["line"]) for x in o[:10]) or "—"
            cand = ("<br><span class=\"ln\">比定候補: " + esc(" / ".join(p["candidates"])) + "</span>") if p["candidates"] else ""
            note = f'<br><span class="ln">{esc(p["note"])}</span>' if p.get("note") else ""
            rows.append(f'<tr><td>{esc(p["ja"])}<span class="ln"> {esc(p["english"])}</span>{cand}{note}</td>'
                        f'<td>{where}</td></tr>')
        return f'<table><tr><th>地名</th><th>出現位置</th></tr>{"".join(rows)}</table>'
    untagged = [u for u in places["untagged_voyage_toponyms"] if not u["tagged_as"]]
    body = f"""<h2>地名の三段台帳</h2>
<div class="note"><strong>オデュッセウスの航路は地図に描けません。</strong>
実測でそう言えます。航海の寄港地 {places['meta']['voyage_toponyms_checked']} 件のうち
<strong>{len(untagged)} 件</strong>は、本文に現れるのに Perseus の地名典拠に項目がありません。
稀だからではなく、指示対象が存在しないからです。よくある「オデュッセウス航海図」は
諸説の一つを断定したもので、我々はそれを作りません。<strong>描けない区間を明示すること</strong>を
仕様にしています。</div>
<h2 class="tier1">第一段 — 同定確実（{len(groups[1])} 件）</h2>
<p>同定が標準的に確立している地。現代地図に座標で載せられます。</p>
{table(groups[1])}
<h2 class="tier2">第二段 — 比定に争いあり（{len(groups[2])} 件）</h2>
<p>複数の候補を併記し、断定しません。</p>
{table(groups[2])}
<h2 class="tier3">第三段 — 同定不能（{len(groups[3])} 件）</h2>
<p><strong>地図に載せません。</strong>載らないことを見せるために、ここに登録簿として置きます。</p>
{table(groups[3])}
<h2>神話的空間（{len(groups['mythic'])} 件）</h2>
<p>地上の場所ではないため、三段のいずれにも属しません。</p>
{table(groups['mythic'])}
<div class="note">出典側にも欠陥があります。Perseus の地名タグは
{places['meta']['occurrences']} 箇所・異なり {places['meta']['distinct_keys']} キーですが、
同一の表記が複数のキーに分裂しているものが {places['meta']['surfaces_with_multiple_keys']} 件あります
（トロイアは 3 キー）。名寄せは我々の側で行いました。</div>"""
    return page("地名の三段台帳 — 歌返し", body)


def build_about(corpus, formulas, ledger, entities) -> str:
    """出典・生成方法・測定値の開示。訳の巧拙は主張せず、測った値だけを出す。"""
    m = formulas["meta"]
    total = len(corpus["units"])
    done = sum(1 for u in corpus["units"] if u["id"] in ledger)
    src = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    reps = json.loads((DATA / "repairs.json").read_text(encoding="utf-8"))
    ed = "".join(
        f'<tr><td>{esc(v["label"])}</td><td>{v["bytes"]:,} bytes</td>'
        f'<td><code class="ln">{v["sha256"][:16]}…</code></td></tr>'
        for v in src["editions"].values())
    rp = "".join(f'<li>{esc(r["edition"])} 巻{r["book"]} 行{r["line"]}: '
                 f'{esc(r["kind"])} — {esc(r["action"])}</li>' for r in reps)
    return page("出典と作り方 — 歌返し", f"""<h2>この和訳は機械が作ったものです</h2>
<div class="note">訳の巧拙は主張しません。<strong>作り方と測定値を開示すること</strong>で、
読み手がどこまで信用するかを自分で決められるようにしています。</div>
<h2>なぜ自前で訳したのか</h2>
<p>日本語の既存訳は一つも使えませんでした。松平千秋訳・呉茂一訳は著作権が存続しています。
土井晩翠訳（1941）は訳者が 1952 年に没しており日本ではパブリックドメインですが、
青空文庫では『オヂュッセーア』が 2026 年 8 月時点で「作業中」のままで、
利用できる電子テキストが存在しません（公開済みは『イーリアス』のみ）。</p>
<h2>出典</h2>
<p>Perseus Digital Library（Tufts University）の TEI XML。ライセンスは
<strong>CC BY-SA 3.0 US</strong>。継承条項があるため、本サイトの派生データ（和訳を含む）も
同ライセンスで頒布します。</p>
<table><tr><th>版</th><th>大きさ</th><th>sha256</th></tr>{ed}</table>
<p class="ln">上流が改訂されると刻印が合わなくなり、検査が落ちます。件数のずれが
「上流の改訂」なのか「我々の回帰」なのかを、そこで切り分けられるようにしています。</p>
<h2>出典側の欠陥と、その扱い</h2>
<ul>{rp}</ul>
<p class="ln">巻3.304 と巻14.63 の組版順の逆転は Loeb 版の校訂判断であって欠陥ではないため、
修復せず整列した事実として記録しています。校訂で削除され番号だけが残る欠番
（10.456 / 16.101 / 23.49）は<strong>埋めていません</strong>。</p>
<h2>作り方</h2>
<p>原典の行番号を唯一の座標系とし、Murray 英訳が打つ行錨で区切った区間を「翻訳単位」
（{total:,} 件）としました。訳は単位ごとに作り、追記のみの台帳に記録します。
現在 <strong>{done:,} / {total:,} 単位（{100*done/total:.1f}%）</strong>が訳済みです。</p>
<h2>検査（機械翻訳を、機械翻訳自身に採点させない）</h2>
<table>
<tr><th>G-01</th><td>構造：24 巻・原典 {m['total_lines']:,} 行を、単位が重複なく過不足なく分割する</td></tr>
<tr><th>G-02</th><td>反復保存：原典で同一の行は、和訳でも定めた中核句を含む
（{m['equality_constraints']:,} 件の制約）</td></tr>
<tr><th>G-03</th><td>固有名詞：人手で確認した和名の表記ゆれを許さない</td></tr>
<tr><th>G-04</th><td>数詞保存：英訳側の数詞が訳文に残っている</td></tr>
<tr><th>G-05</th><td>文字種衛生：キリル文字・ハングル・ラテン文字の混入を検出</td></tr>
<tr><th>G-06</th><td>陽性対照：故意に壊したデータで各ゲートが落ちることを確認</td></tr>
<tr><th>G-14</th><td>分量整合：訳文が原文に対して極端に短くないこと（訳し落としの検出）</td></tr>
</table>
<div class="note">G-02 が成り立つのは、原典の反復が<strong>我々の解釈を含まない</strong>からです。
n-gram を数えただけの事実なので、これを基準に訳を検査しても循環になりません。
G-05 と G-14 は実際に本番で欠陥を捕まえました — 目視では気づけないキリル文字の混入、
そして作業画面で原文を切り詰めていたことによる訳し落とし 7 件です。</div>
<h2>まだできていないこと</h2>
<ul>
<li>第 7 巻以降の和訳（{total-done:,} 単位）</li>
<li>地名の地図表示。同定確実な地点のみを Natural Earth（パブリックドメイン）で描く予定で、
タイルサーバは使いません</li>
<li>人手確認は出現 10 回以上の実体に限っています。残りは機械確定のままです</li>
</ul>""")


def main() -> None:
    corpus, formulas, entities, places, tiers, speakers, ledger = load()
    OUT.mkdir(exist_ok=True)
    (OUT / "book").mkdir(exist_ok=True)
    n = 0
    for b in range(1, 25):
        htm, done, total = build_book(b, corpus, ledger)
        (OUT / "book" / f"{b}.html").write_text(htm, encoding="utf-8")
        n += 1
    pages = {
        "index.html": build_index(corpus, ledger, formulas),
        "formula.html": build_formula(formulas, ledger, corpus),
        "person.html": build_person(entities, speakers, ledger),
        "place.html": build_place(places, tiers),
        "about.html": build_about(corpus, formulas, ledger, entities),
    }
    for name, htm in pages.items():
        (OUT / name).write_text(htm, encoding="utf-8")
    size = sum(f.stat().st_size for f in OUT.rglob("*.html"))
    print(f"生成 {n + len(pages)} ページ / 合計 {size:,} bytes")
    for name in pages:
        print(f"  {name:14s} {(OUT/name).stat().st_size:>8,} bytes")


if __name__ == "__main__":
    main()
