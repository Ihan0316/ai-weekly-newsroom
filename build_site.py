# -*- coding: utf-8 -*-
"""
데일리 다이제스트 사이트 생성기.
- index.html: 미니멀 에디토리얼 + Three.js 3D 히어로 + 카드 틸트 (데일리 피드)
- days/<id>.html: 하루치 상세 (뉴스 / 기초상식·정처기 / IT·개발·기획 용어) — build.render_day()
공유 assets/site.css · site.js (단일 디자인 소스).

usage: python build_site.py
"""
import json, os, glob, re, shutil, hashlib, sys
from build import render_day, esc

DAYS_DIR = os.path.join("data", "days")
OUT_DIR = "docs"
ASSETS_SRC = "assets"
SITE_BASE = "https://ihan0316.github.io/ai-weekly-newsroom/"   # GitHub Pages 루트(canonical·OG용)
THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"

INK = "#191711"; BONE = "#f6f4ec"; FAINT = "#ece3d2"; MUTED = "#7c7669"
ACCENT = "#c2532f"; ADEEP = "#9c3f20"; LINE = "#e2ddcf"

def parse_md(day_id):
    m = re.match(r"(\d+)-(\d+)-(\d+)", day_id)
    if m:
        return str(int(m.group(2))), str(int(m.group(3)))
    return "", "•"

def thumb_svg(day_id, rec):
    # 기사 이미지가 없을 때 쓰는 Apple-미니멀 플레이스홀더 (연그레이 + 큰 날짜)
    mo, da = parse_md(day_id)
    wd = rec.get("weekday", "")
    return f'''<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg">
      <rect width="480" height="300" fill="#f5f5f7"/>
      <text x="40" y="186" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="150" font-weight="700" fill="#1d1d1f" letter-spacing="-7">{da}</text>
      <text x="46" y="238" font-family="-apple-system,BlinkMacSystemFont,sans-serif" font-size="20" font-weight="500" fill="#6e6e73">{mo}월 · {wd}요일</text>
    </svg>'''

def card_image(rec):
    news = rec.get("news") or []
    if news and news[0].get("image"):
        return news[0]["image"].replace("../", "")   # index 기준 상대경로
    return None

def headline(rec):
    news = rec.get("news") or []
    if news:
        return " ".join(news[0]["title_kr"].split("\n"))
    if rec.get("quiz"):
        return " ".join(rec["quiz"]["question"].split("\n"))
    return "오늘의 읽을거리"

def meta_line(rec):
    nn = len(rec.get("news") or [])
    nt = len(rec.get("terms") or [])
    return f"뉴스 {nn} · 정처기 1 · 용어 {nt}"

def card(day_id, rec, hero=False):
    top = headline(rec)
    wd = rec.get("weekday", "")
    label = f'{rec["date_label"]}' + (f' ({wd})' if wd else '')
    href = f'days/{day_id}.html'
    img = card_image(rec)
    thumb = (f'<img src="{esc(img)}" alt="" loading="lazy">' if img else thumb_svg(day_id, rec))
    if hero:
        return f'''<div class="featured"><a class="card" href="{esc(href)}">
      <div class="thumb">{thumb}</div>
      <div class="cbody">
        <div class="eyebrow">오늘 · {esc(label)}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">{esc(meta_line(rec))}</p>
        <span class="clink">오늘 읽기 <span class="arr">→</span></span>
      </div></a></div>'''
    return f'''<a class="card" href="{esc(href)}">
      <div class="thumb">{thumb}</div>
      <div class="cbody">
        <div class="eyebrow">{esc(label)}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">{esc(meta_line(rec))}</p>
        <span class="clink">읽기 <span class="arr">→</span></span>
      </div></a>'''

PAGE_SIZE = 12   # 인덱스 피드 '지난 날' 초기 노출 카드 수 (나머지는 '더보기'로 점진 노출)

def build_index(days, ver="", build_v=""):
    latest_id, latest = days[0]
    rest = days[1:]
    hero_card = card(latest_id, latest, hero=True)
    rest_cards = [card(i, r) for i, r in rest]
    # 초기엔 PAGE_SIZE개만 노출, 나머지는 hidden → JS '더보기'가 점진 공개 (검색엔진/무JS는 noscript로 전부 노출)
    extra_n = max(0, len(rest_cards) - PAGE_SIZE)
    shown = rest_cards[:PAGE_SIZE]
    hidden = [c.replace('<a class="card"', '<a class="card" hidden', 1) for c in rest_cards[PAGE_SIZE:]]
    cards = "\n".join(shown + hidden)
    grid = f'<div class="grid">{cards}</div>' if rest else ''
    rest_h = '<div class="sec-label">지난 날</div>' if rest else ''
    more = (f'<div class="feed-more"><button class="more-btn" type="button" data-page="{PAGE_SIZE}">지난 날 더보기 ({extra_n})</button></div>'
            if extra_n else '')
    n = len(days)
    desc = "매일 IT·개발 뉴스, 정보처리기사 기초 문제, IT·개발·기획 용어를 한 장에 모은 데일리 다이제스트."
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>데일리 · 알아두면 좋은 것들</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_BASE}">
<meta property="og:type" content="website">
<meta property="og:title" content="데일리 · 알아두면 좋은 것들">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE_BASE}">
<link rel="stylesheet" href="assets/site.css{ver}">
<noscript><style>.grid .card[hidden]{{display:flex !important}} .feed-more{{display:none !important}}</style></noscript>
<meta name="site-build" content="{build_v}" data-src="build.json">
<script>
/* 모바일 직접 접속 시 오늘 뉴스로 자동 이동. 사이트 내부 이동('전체 보기' 등)·재방문은 제외 */
(function(){{try{{
  var mobile = window.matchMedia && window.matchMedia('(max-width:620px)').matches;
  var internal = document.referrer && document.referrer.indexOf(location.origin) === 0;
  if (mobile && !internal && !sessionStorage.getItem('rdrToday')) {{
    sessionStorage.setItem('rdrToday','1');
    location.replace('today.html');
  }}
}}catch(e){{}}}})();
</script>
</head>
<body>
<nav class="nav">
  <span class="brand">데일리<span class="dot">.</span></span>
  <span class="tag">알아두면 좋은 것들 — 뉴스·정처기·용어</span>
  <span class="spacer"></span>
  <span class="pill">{n} days</span>
</nav>
<div class="wrap">
  <section class="masthead">
    <div class="mh-copy">
      <div class="kicker">매일 한 장</div>
      <h1>매일, <em>알아두면</em> 좋은 것들.</h1>
      <p>그날의 IT·개발 뉴스, 정보처리기사 기초 문제, 그리고 IT·개발·기획 용어를 한 장에.</p>
    </div>
  </section>

  <div class="searchbar">
    <span class="search-ico" aria-hidden="true">🔎</span>
    <input id="news-search" class="search-input" type="search" autocomplete="off"
      data-index="search.json{ver}"
      placeholder="주제·키워드로 뉴스 검색 (제목·본문까지)" aria-label="뉴스 검색">
    <button id="search-clear" class="search-clear" type="button" hidden aria-label="검색어 지우기">✕</button>
  </div>
  <div class="search-results" id="search-results" hidden></div>

  <div class="feed" id="feed">
  {hero_card}
  {rest_h}
  {grid}
  {more}
  </div>

  <div class="foot">
    <span class="fbrand">데일리</span> · 자동 생성 MVP<br>
    뉴스 본문은 LLM 웹검색 자동 수집물입니다. 게시 전 출처 확인을 권장합니다.
  </div>
</div>
<script src="assets/site.js{ver}"></script>
</body></html>'''

def validate_day(rec):
    """렌더에 필요한 최소 스키마 검증. 불량 day 1개가 전체 빌드를 중단시키지 않도록 사전 차단.
    반환: 문제 사유(str) 또는 None(정상)."""
    if not isinstance(rec, dict):
        return "레코드가 dict 아님"
    if not rec.get("date_label"):
        return "date_label 없음"
    q = rec.get("quiz")
    if not isinstance(q, dict):
        return "quiz 없음/형식오류"
    opts = q.get("options")
    if not isinstance(opts, list) or not (1 <= len(opts) <= 5):
        return "quiz.options 개수 오류"
    try:
        ans = int(q.get("answer"))
    except (TypeError, ValueError):
        return "quiz.answer 정수 아님"
    if not (0 <= ans < len(opts)):
        return "quiz.answer 범위 초과"
    for k in ("question", "explain_kr"):
        if not q.get(k):
            return "quiz.%s 없음" % k
    for it in rec.get("news", []):
        if not it.get("title_kr"):
            return "news 항목 title_kr 없음"
    return None

def main():
    files = glob.glob(os.path.join(DAYS_DIR, "*.json"))
    if not files:
        print("no days in", DAYS_DIR); sys.exit(1)
    days = []
    skipped = []
    for f in files:
        did = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, "r", encoding="utf-8") as fh:
                rec = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            skipped.append((did, "로드 실패: %s" % e)); continue
        reason = validate_day(rec)
        if reason:
            skipped.append((did, reason)); continue
        days.append((did, rec))
    if skipped:
        for did, why in skipped:
            print("SKIP", did, "—", why, file=sys.stderr)
    if not days:
        print("유효한 day 없음 — 중단", file=sys.stderr); sys.exit(1)
    days.sort(key=lambda x: x[0], reverse=True)  # 최신 날짜 먼저

    dst_assets = os.path.join(OUT_DIR, "assets")
    os.makedirs(dst_assets, exist_ok=True)
    h = hashlib.md5()
    for fn in sorted(os.listdir(ASSETS_SRC)):
        sp = os.path.join(ASSETS_SRC, fn)
        if not os.path.isfile(sp):   # 하위 폴더(assets/fonts/ 등)는 건너뜀 — copy2/open 크래시 방지
            continue
        shutil.copy2(sp, os.path.join(dst_assets, fn))
        with open(sp, "rb") as fb:
            h.update(fb.read())
    ver = "?v=" + h.hexdigest()[:8]      # 에셋 변경 시 캐시 무효화
    open(os.path.join(OUT_DIR, ".nojekyll"), "w").close()

    # 기사 이미지 연결: url 해시로 docs/images/<hash>.* 존재 시 주입
    n_img = 0
    for _did, rec in days:
        for it in rec.get("news", []):
            u = (it.get("url") or "").strip()
            if not u:
                continue
            h = hashlib.md5(u.encode("utf-8")).hexdigest()[:12]
            imgs = glob.glob(os.path.join(OUT_DIR, "images", h + ".*"))
            if imgs:
                it["image"] = "../images/" + os.path.basename(imgs[0]); n_img += 1
    print("images linked:", n_img)

    # 빌드 버전(콘텐츠 변경 시마다 달라짐) → 클라이언트가 자동 갱신 감지에 사용
    build_v = hashlib.md5(json.dumps([r for _, r in days], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    with open(os.path.join(OUT_DIR, "build.json"), "w", encoding="utf-8") as fh:
        json.dump({"v": build_v}, fh, ensure_ascii=False)

    os.makedirs(os.path.join(OUT_DIR, "days"), exist_ok=True)
    for did, rec in days:
        out = os.path.join(OUT_DIR, "days", did + ".html")
        canonical = SITE_BASE + "days/" + did + ".html"
        news0 = (rec.get("news") or [{}])[0]
        img = news0.get("image", "")
        if img.startswith("http"):
            og_image = img
        elif img:
            og_image = SITE_BASE + img.replace("../", "")   # ../images/x.png → 절대 URL
        else:
            og_image = ""
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(render_day(rec, back_href="../index.html", asset_prefix="../",
                                ver=ver, build_v=build_v, canonical=canonical, og_image=og_image))
    # 클라이언트 검색 인덱스(전체 뉴스, 본문 포함) → docs/search.json (지연 로드)
    search = []
    for did, rec in days:
        for i, it in enumerate(rec.get("news", [])):
            img = it.get("image", "")
            body = " ".join((b.get("text") or "") for b in (it.get("content") or []))
            search.append({
                "t": " ".join((it.get("title_kr") or "").split("\n")),
                "b": it.get("blurb_kr", ""),
                "s": it.get("source", ""),
                "c": body,
                "d": rec.get("date_label", ""),
                "wd": rec.get("weekday", ""),
                "id": did, "n": i,
                "img": img.replace("../", "") if img else "",
            })
    with open(os.path.join(OUT_DIR, "search.json"), "w", encoding="utf-8") as fh:
        json.dump(search, fh, ensure_ascii=False)

    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(days, ver, build_v))

    # /today.html : 항상 최신(오늘) 날짜 상세로 바로 이동하는 고정 주소(북마크용)
    latest = days[0][0]
    today_html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8">'
                  '<meta http-equiv="refresh" content="0; url=days/%s.html">'
                  '<meta name="viewport" content="width=device-width,initial-scale=1">'
                  '<title>오늘의 다이제스트…</title><link rel="canonical" href="days/%s.html">'
                  '<script>location.replace("days/%s.html"+location.search);</script>'
                  '<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f1efe7;'
                  'color:#6a6353;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}</style>'
                  '</head><body><p>오늘의 다이제스트로 이동 중… <a href="days/%s.html">바로가기</a></p></body></html>'
                  ) % (latest, latest, latest, latest)
    with open(os.path.join(OUT_DIR, "today.html"), "w", encoding="utf-8") as fh:
        fh.write(today_html)
    print("built index + %d days:" % len(days), ", ".join(d for d, _ in days))

if __name__ == "__main__":
    main()
