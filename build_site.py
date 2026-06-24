# -*- coding: utf-8 -*-
"""
데일리 다이제스트 사이트 생성기.
- index.html: 미니멀 에디토리얼 + Three.js 3D 히어로 + 카드 틸트 (데일리 피드)
- days/<id>.html: 하루치 상세 (뉴스 / 기초상식·정처기 / IT·개발·기획 용어) — build.render_day()
공유 assets/site.css · site.js (단일 디자인 소스).

usage: python build_site.py
"""
import json, os, glob, re, shutil, hashlib
from build import render_day, esc

DAYS_DIR = os.path.join("data", "days")
OUT_DIR = "docs"
ASSETS_SRC = "assets"
THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"

INK = "#191711"; BONE = "#f6f4ec"; FAINT = "#ece3d2"; MUTED = "#7c7669"
ACCENT = "#c2532f"; ADEEP = "#9c3f20"; LINE = "#e2ddcf"

def parse_md(day_id):
    m = re.match(r"(\d+)-(\d+)-(\d+)", day_id)
    if m:
        return str(int(m.group(2))), str(int(m.group(3)))
    return "", "•"

def thumb_svg(day_id, rec):
    mo, da = parse_md(day_id)
    wd = rec.get("weekday", "")
    top = headline(rec)
    top = (top[:26] + "…") if len(top) > 27 else top
    gid = "o" + day_id.replace("-", "")
    chips = ["뉴스", "정처기", "용어"]
    chipcols = [ACCENT, "#0a8f6b", "#1f6feb"]
    cx = 50
    chip_svg = ""
    for c, col in zip(chips, chipcols):
        w = 30 + len(c) * 13
        chip_svg += (f'<rect x="{cx}" y="150" width="{w}" height="24" rx="12" fill="{col}"/>'
                     f'<text x="{cx + w/2}" y="167" text-anchor="middle" font-family="\'Noto Serif KR\',sans-serif" font-size="13" fill="#fff">{c}</text>')
        cx += w + 8
    return f'''<svg viewBox="0 0 480 250" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="{gid}" cx="0.35" cy="0.3" r="0.75">
          <stop offset="0" stop-color="#ffffff"/><stop offset="0.55" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ADEEP}"/>
        </radialGradient>
        <filter id="b{gid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
      </defs>
      <rect width="480" height="250" fill="{BONE}"/>
      <circle cx="398" cy="74" r="60" fill="url(#{gid})" filter="url(#b{gid})" opacity="0.5"/>
      <circle cx="398" cy="74" r="44" fill="url(#{gid})" opacity="0.95"/>
      <text x="46" y="118" font-family="Fraunces,Georgia,serif" font-style="italic" font-size="92" font-weight="600" fill="{FAINT}">{da}</text>
      <text x="52" y="58" font-family="'JetBrains Mono',monospace" font-size="14" letter-spacing="2" fill="{ACCENT}">{mo}월 · {wd}요일</text>
      {chip_svg}
      <text x="52" y="210" font-family="'Noto Serif KR',serif" font-size="15" font-weight="600" fill="{INK}">{esc(top)}</text>
    </svg>'''

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
    if hero:
        return f'''<div class="featured"><a class="card tilt featured-tilt" href="{esc(href)}">
      <div class="thumb lift">{thumb_svg(day_id, rec)}</div>
      <div class="cbody">
        <div class="eyebrow">오늘 · {esc(label)}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">{esc(meta_line(rec))}</p>
        <span class="clink">오늘 읽기 <span class="arr">→</span></span>
      </div></a></div>'''
    return f'''<a class="card tilt" href="{esc(href)}">
      <div class="thumb">{thumb_svg(day_id, rec)}</div>
      <div class="cbody">
        <div class="eyebrow">{esc(label)}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">{esc(meta_line(rec))}</p>
        <span class="clink">읽기 <span class="arr">→</span></span>
      </div></a>'''

def build_index(days, ver=""):
    latest_id, latest = days[0]
    rest = days[1:]
    hero_card = card(latest_id, latest, hero=True)
    cards = "\n".join(card(i, r) for i, r in rest)
    grid = f'<div class="grid">{cards}</div>' if rest else ''
    rest_h = '<div class="sec-label">지난 날</div>' if rest else ''
    n = len(days)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>데일리 · 알아두면 좋은 것들</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..600;1,9..144,400..600&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+KR:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/site.css{ver}">
</head>
<body>
<div class="orbs"><span class="orb o1"></span><span class="orb o2"></span><span class="orb o3"></span></div>
<nav class="nav">
  <span class="brand">데일리<span class="dot">.</span></span>
  <span class="tag">알아두면 좋은 것들 — 뉴스·정처기·용어</span>
  <span class="spacer"></span>
  <span class="pill">{n} days</span>
</nav>
<div class="wrap">
  <section class="masthead">
    <div class="mh-copy">
      <div class="kicker">Daily · 매일 한 장</div>
      <h1>매일, <em>알아두면</em><br>좋은 것들.</h1>
      <p>그날의 IT·개발 뉴스 몇 개, 정보처리기사 기초 문제 하나, 그리고 IT·개발·기획 용어 몇 개.</p>
    </div>
    <div class="hero3d"><canvas id="scene"></canvas></div>
  </section>

  {hero_card}
  {rest_h}
  {grid}

  <div class="foot">
    <span class="fbrand">데일리</span> · 자동 생성 MVP<br>
    뉴스 본문은 LLM 웹검색 자동 수집물입니다. 게시 전 출처 확인을 권장합니다.
  </div>
</div>
<script src="{THREE_CDN}"></script>
<script src="assets/site.js{ver}"></script>
</body></html>'''

def main():
    files = glob.glob(os.path.join(DAYS_DIR, "*.json"))
    if not files:
        print("no days in", DAYS_DIR); return
    days = []
    for f in files:
        did = os.path.splitext(os.path.basename(f))[0]
        with open(f, "r", encoding="utf-8") as fh:
            days.append((did, json.load(fh)))
    days.sort(key=lambda x: x[0], reverse=True)  # 최신 날짜 먼저

    dst_assets = os.path.join(OUT_DIR, "assets")
    os.makedirs(dst_assets, exist_ok=True)
    h = hashlib.md5()
    for fn in sorted(os.listdir(ASSETS_SRC)):
        sp = os.path.join(ASSETS_SRC, fn)
        shutil.copy2(sp, os.path.join(dst_assets, fn))
        with open(sp, "rb") as fb:
            h.update(fb.read())
    ver = "?v=" + h.hexdigest()[:8]      # 에셋 변경 시 캐시 무효화
    open(os.path.join(OUT_DIR, ".nojekyll"), "w").close()

    os.makedirs(os.path.join(OUT_DIR, "days"), exist_ok=True)
    for did, rec in days:
        out = os.path.join(OUT_DIR, "days", did + ".html")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(render_day(rec, back_href="../index.html", asset_prefix="../", ver=ver))
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(days, ver))
    print("built index + %d days:" % len(days), ", ".join(d for d, _ in days))

if __name__ == "__main__":
    main()
