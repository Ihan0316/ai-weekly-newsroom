# -*- coding: utf-8 -*-
"""
주간 AI 뉴스 — 상세(호) 페이지 렌더러.
미니멀 에디토리얼 디자인. 공유 assets/site.css · site.js 사용 (index와 동일 시스템).
폼(섹션 구성)은 유지: 뉴스 3 · 실전 영어 10 · 개발자 은어 · 미니연습 · 핵심요약 · 메모.

usage: python build.py <digest.json> [out.html]
"""
import json, sys, html, os, re

def esc(s):
    return html.escape(html.unescape(str(s)))

def strip_check(s):
    s = str(s).lstrip()
    for p in ("✅", "✔️", "✔", "✓", "- ", "* "):
        if s.startswith(p):
            s = s[len(p):].lstrip()
    return s

def oneline(s):
    return " ".join(str(s).split("\n")).strip()

def week_num_from(d, fallback=""):
    m = re.search(r"(\d+)\s*\.\s*(\d+)", d.get("date_label", ""))
    return fallback

def build_stories(news):
    out = []
    for it in news:
        facts = "".join(f"<li>{esc(strip_check(b))}</li>" for b in it["bullets_kr"])
        out.append(f'''
      <article class="story tilt">
        <div class="snum">{it["n"]:02d}</div>
        <div class="sdate">{esc(it["date"])} · {esc(it["source"])}</div>
        <h2 class="stitle">{esc(oneline(it["title_kr"]))}</h2>
        <blockquote class="squote">“{esc(it["bubble_kr"])}”</blockquote>
        <ul class="sfacts">{facts}</ul>
        <div class="stake">{esc(it["star_kr"])}</div><br>
        <a class="ssrc" href="{esc(it["url"])}" target="_blank" rel="noopener">출처 · {esc(it["source"])} ↗</a>
      </article>''')
    return "\n".join(out)

def build_eng(expr):
    cells = []
    for it in expr:
        cells.append(f'''
        <div class="eng">
          <span class="enum">{it["n"]:02d}</span>
          <span><span class="en">{esc(it["term_en"])}</span><span class="ekr">{esc(it["meaning_kr"])}</span></span>
        </div>''')
    return "".join(cells)

def build_slang(rows):
    head = ("<tr><th>표현</th><th>일반 뜻</th><th>개발·AI 맥락</th>"
            "<th>언제 쓰나</th><th>업무 표현</th><th>예문</th></tr>")
    body = ""
    for r in rows:
        body += (f'<tr><td class="sterm">{esc(r["term"])}</td><td>{esc(r["general_kr"])}</td>'
                 f'<td>{esc(r["context_kr"])}</td><td>{esc(r["when_kr"])}</td>'
                 f'<td>{esc(r["work_kr"])}</td><td class="sex">{esc(r["example_en"])}</td></tr>')
    return f'<div class="slang-wrap"><table class="slang">{head}{body}</table></div>'

def build_trio(mp, summary, memo):
    summ = "".join(f"<li>{esc(strip_check(s))}</li>" for s in summary)
    return f'''
      <div class="tcard">
        <h4>미니 연습</h4>
        <p><b>1. 빈칸</b><br>{esc(mp["fill_blank"])}<br><span class="ans">→ {esc(mp["fill_answer"])}</span></p>
        <p><b>2. 영작</b><br>{esc(mp["kr_to_en"])}<br><span class="ans">→ {esc(mp["kr_to_en_answer"])}</span></p>
        <p><b>3. 말하기</b><br><span class="ans">{esc(mp["speaking"])}</span></p>
      </div>
      <div class="tcard">
        <h4>이번 주 핵심</h4>
        <ul>{summ}</ul>
      </div>
      <div class="tcard">
        <h4>메모</h4>
        <ul class="memo">
          <li>{esc(memo["official_date"])}</li>
          <li>출처 · {esc(memo["sources"])}</li>
          <li>반응 · {esc(memo["x_reaction"])}</li>
        </ul>
      </div>'''

def render(d, back_href=None, asset_prefix="../", week_label=None):
    a = asset_prefix
    back = (f'<div class="dnav"><a class="backlink" href="{esc(back_href)}">← 모든 호</a></div>') if back_href else ''
    wl = esc(week_label) if week_label else esc(d["date_label"])
    n = len(d["news"])
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>주간 AI 뉴스 · {esc(d["date_label"])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..600;1,9..144,400..600&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+KR:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{a}assets/site.css">
</head>
<body>
<div class="orbs"><span class="orb o1"></span><span class="orb o2"></span><span class="orb o3"></span></div>
{back}
<main class="reader">
  <div class="kicker">{wl} · 주간 AI 다이제스트</div>
  <h1 class="dhead">이번 주, AI 뉴스 <em>{n}</em></h1>
  <p class="dsub">{esc(d["official_date"])}</p>
  <div class="rule"></div>

  <section class="stories">{build_stories(d["news"])}</section>

  <section class="block">
    <h3 class="blockh"><span class="idx">A</span> 실전 영어 표현 10</h3>
    <div class="enggrid">{build_eng(d["english_expressions"])}</div>
  </section>

  <section class="block">
    <h3 class="blockh"><span class="idx">B</span> 개발자 은어 &amp; 관용 표현</h3>
    {build_slang(d["dev_slang"])}
  </section>

  <section class="trio">{build_trio(d["mini_practice"], d["summary_kr"], d["memo"])}</section>

  <div class="foot">
    <span class="fbrand">AI 뉴스룸</span> · 주간 AI 뉴스 다이제스트 · {esc(d["date_label"])}<br>
    뉴스 본문은 LLM 웹검색 자동 수집물입니다. 게시 전 출처 확인을 권장합니다.
  </div>
</main>
<script src="{a}assets/site.js"></script>
</body></html>'''

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "digest.json")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join("dist", "index.html")
    with open(src, "r", encoding="utf-8") as f:
        d = json.load(f)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    # 단독 실행 시 assets는 같은 폴더 기준
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(d, asset_prefix=""))
    print("built:", out)

if __name__ == "__main__":
    main()
