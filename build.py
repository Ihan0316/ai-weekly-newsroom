# -*- coding: utf-8 -*-
"""
데일리 다이제스트 — 하루치 상세 페이지 렌더러.
구성: 오늘의 뉴스(클릭→3D 모달로 크롤 원문) · 기초상식(정처기, 클릭형 정답/오답) · IT/개발/기획 용어.
공유 assets/site.css · site.js 사용.

usage: python build.py <day.json> [out.html]
"""
import json, sys, html, os

KIND_COLORS = {"IT": "#0071e3", "개발": "#1d9d57", "기획": "#c25e00"}

# 기사 Q&A 프록시(Cloudflare Worker 등) 엔드포인트. 비우면 질문 UI 숨김.
ASK_ENDPOINT = "https://ai-weekly-newsroom.aijnjj12.workers.dev"

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

def build_news(news):
    if not news:
        return '<p class="empty">오늘은 수집된 소식이 없습니다.</p>'
    out = []
    for i, it in enumerate(news):
        blurb = f'<p class="ni-blurb">{esc(it["blurb_kr"])}</p>' if it.get("blurb_kr") else ""
        thumb = (f'<img class="ni-thumb" src="{esc(it["image"])}" alt="" loading="lazy" '
                 f'onerror="this.remove()">') if it.get("image") else ""
        out.append(f'''
        <li>
          <button class="newsitem{(" has-thumb" if thumb else "")}" data-idx="{i}" type="button">
            <div class="ni-text">
              <span class="ni-src">{esc(it.get("source",""))}</span>
              <h3 class="ni-title">{esc(oneline(it["title_kr"]))}</h3>
              {blurb}
              <span class="ni-open">원문 보기 →</span>
            </div>
            {thumb}
          </button>
        </li>''')
    return f'<ul class="newslist">{"".join(out)}</ul>'

def news_payload(news):
    """모달에서 쓸 뉴스 데이터(본문 포함)를 JSON으로 임베드."""
    items = []
    for it in news:
        items.append({
            "title": oneline(it.get("title_kr", "")),
            "source": it.get("source", ""),
            "url": it.get("url", ""),
            "blurb": it.get("blurb_kr", ""),
            "content": it.get("content", []) or [],
            "audio": it.get("audio", ""),
            "image": it.get("image", ""),
            "comment": it.get("comment_kr", ""),   # 화면 미표시, 복사 시에만 사용
        })
    js = json.dumps(items, ensure_ascii=False)
    return js.replace("</", "<\\/")

def build_quiz(q):
    letters = "①②③④⑤"
    opts = "".join(
        f'<li class="qopt" data-i="{i}"><span class="ql">{letters[i]}</span>'
        f'<span class="qtext">{esc(o)}</span><span class="qmark"></span></li>'
        for i, o in enumerate(q["options"])
    )
    cat = esc(q.get("category", "정보처리기사"))
    ans = letters[q["answer"]]
    return f'''
      <div class="quiz" data-answer="{q["answer"]}">
        <div class="sectag">#{cat}</div>
        <p class="q-question">{esc(q["question"])}</p>
        <ol class="qopts">{opts}</ol>
        <p class="q-hint">보기를 클릭해 정답을 확인하세요.</p>
        <div class="q-explain" hidden><b>정답: {ans}</b><p>{esc(q["explain_kr"])}</p></div>
      </div>'''

def build_terms(terms):
    rows = []
    for t in terms:
        kind = t.get("kind", "IT")
        col = KIND_COLORS.get(kind, "#1f6feb")
        rows.append(f'''
        <li class="termrow">
          <span class="t-kind" style="background:{col}">{esc(kind)}</span>
          <span class="t-term">{esc(t["term"])}</span>
          <span class="t-mean">{esc(t["meaning_kr"])}</span>
        </li>''')
    return f'<ul class="terms">{"".join(rows)}</ul>'

MODAL = '''
<div class="modal-overlay" id="news-modal" hidden>
  <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <button class="modal-close" type="button" aria-label="닫기">✕</button>
    <div class="modal-src"></div>
    <h2 class="modal-title" id="modal-title"></h2>
    <div class="modal-tools">
      <button class="tts-toggle" type="button" hidden aria-label="본문 읽어주기">
        <span class="tts-ico">🔊</span><span class="tts-label">본문 듣기</span>
      </button>
      <button class="np-copy" type="button" data-part="title" aria-label="네이버 제목 복사">
        <span class="np-ico">📋</span><span>제목</span>
      </button>
      <button class="np-copy" type="button" data-part="body" aria-label="네이버 본문 복사">
        <span class="np-ico">📝</span><span>본문</span>
      </button>
    </div>
    <img class="modal-hero" alt="" hidden>
    <div class="modal-body"></div>
    <a class="modal-orig" target="_blank" rel="noopener">원문 사이트에서 보기 ↗</a>
    <div class="np-toast" role="status" aria-live="polite" hidden>복사됨</div>
  </div>
</div>
<div class="ask-panel" hidden role="dialog" aria-label="기사 질문">
  <div class="ask-head"><span>이 기사에 질문</span><button class="ask-x" type="button" aria-label="질문 패널 닫기">✕</button></div>
  <div class="ask-thread"></div>
  <div class="ask-foot">
    <div class="ask-quote" hidden></div>
    <div class="ask-row">
      <input class="ask-input" type="text" maxlength="500" autocomplete="off"
        placeholder="이 기사에서 궁금한 점" aria-label="질문 입력">
      <button class="ask-send" type="button">질문</button>
    </div>
    <div class="ask-count"></div>
  </div>
</div>
<div class="sel-ask" hidden><button class="sel-ask-btn" type="button">🤔 질문</button></div>'''

def day_desc(d):
    """공유·검색용 요약: 첫 기사 blurb → 제목 → 기본 문구."""
    news = d.get("news") or []
    if news and news[0].get("blurb_kr"):
        return oneline(news[0]["blurb_kr"])[:155]
    if news and news[0].get("title_kr"):
        return oneline(news[0]["title_kr"])[:155]
    return "그날의 IT·개발 뉴스, 정보처리기사 기초 문제, IT·개발·기획 용어를 한 장에."

def render_day(d, back_href=None, asset_prefix="../", ver="", build_v="", canonical="", og_image=""):
    a = asset_prefix
    back = (f'<div class="dnav"><a class="backlink" href="{esc(back_href)}">← 전체 보기</a></div>') if back_href else ''
    wd = d.get("weekday", "")
    label = f'{esc(d["date_label"])}' + (f' ({esc(wd)})' if wd else '')
    news = d.get("news", [])
    desc = esc(day_desc(d))
    og_title = esc(f'{d["date_label"]} · 데일리 다이제스트')
    canon = f'<link rel="canonical" href="{esc(canonical)}">' if canonical else ''
    og_url = f'<meta property="og:url" content="{esc(canonical)}">' if canonical else ''
    og_img = f'<meta property="og:image" content="{esc(og_image)}">' if og_image else ''
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>데일리 다이제스트 · {esc(d["date_label"])}</title>
<meta name="description" content="{desc}">
{canon}
<meta property="og:type" content="article">
<meta property="og:title" content="{og_title}">
<meta property="og:description" content="{desc}">
{og_url}
{og_img}
<link rel="stylesheet" href="{a}assets/site.css{ver}">
<meta name="site-build" content="{build_v}" data-src="{a}build.json">
<meta name="ask-endpoint" content="{ASK_ENDPOINT}">
</head>
<body>
{back}
<main class="reader">
  <div class="kicker">{label} · 데일리 다이제스트</div>
  <h1 class="dhead">오늘 <em>읽을거리</em></h1>
  <p class="dsub">뉴스 · 기초상식(정처기) · IT·개발·기획 용어</p>
  <div class="rule"></div>

  <section class="daystack">
    <article class="daysec sec-news">
      <div class="secnum">01</div>
      <span class="seclabel">오늘의 뉴스</span>
      {build_news(news)}
    </article>

    <article class="daysec sec-quiz">
      <div class="secnum">02</div>
      <span class="seclabel">기초상식 · 정처기</span>
      {build_quiz(d["quiz"])}
    </article>

    <article class="daysec sec-terms">
      <div class="secnum">03</div>
      <span class="seclabel">IT · 개발 · 기획 용어</span>
      {build_terms(d.get("terms", []))}
    </article>
  </section>

  <div class="foot">
    <span class="fbrand">데일리</span> · 읽을거리 · {esc(d["date_label"])}<br>
    뉴스 본문은 yozm.wishket · GeekNews(news.hada.io) 등에서 수집·요약한 것입니다. 정확한 내용은 원문을 확인하세요.
  </div>
</main>
{MODAL}
<script id="news-data" type="application/json">{news_payload(news)}</script>
<script src="{a}assets/site.js{ver}"></script>
</body></html>'''

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "days", "sample.json")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join("docs", "day.html")
    with open(src, "r", encoding="utf-8") as f:
        d = json.load(f)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render_day(d, asset_prefix=""))
    print("built:", out)

if __name__ == "__main__":
    main()
