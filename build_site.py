# -*- coding: utf-8 -*-
"""
멀티 주차 뉴스룸 사이트 생성기.
- index.html: 미니멀 에디토리얼 + Three.js 3D 히어로 + 카드 틸트
- issues/<id>.html: 동일 디자인 시스템의 상세(호) — build.render()
공유 assets/site.css · site.js (단일 디자인 소스 → index/상세 일관).

usage: python build_site.py
"""
import json, os, glob, re, shutil
from build import render, esc

ISSUES_DIR = os.path.join("data", "issues")
OUT_DIR = "docs"          # GitHub Pages: main 브랜치 /docs 서빙
ASSETS_SRC = "assets"
THREE_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"

# palette (site.css 토큰과 일치)
INK = "#191711"; BONE = "#f6f4ec"; FAINT = "#ece3d2"; MUTED = "#7c7669"
ACCENT = "#c2532f"; ADEEP = "#9c3f20"; WASH = "#f5e7df"; LINE = "#e2ddcf"

def week_num(week_id):
    m = re.search(r"w(\d+)", week_id)
    return m.group(1) if m else "•"

def thumb_svg(issue):
    wn = week_num(issue["id"])
    top = " ".join(issue["digest"]["news"][0]["title_kr"].split("\n"))
    top = (top[:26] + "…") if len(top) > 27 else top
    gid = "o" + issue["id"].replace("-", "")
    ticks = "".join(f'<rect x="{56 + i*16}" y="206" width="9" height="9" rx="2" fill="{ACCENT}" transform="rotate(45 {60+i*16} 210)"/>' for i in range(3))
    return f'''<svg viewBox="0 0 480 250" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="{gid}" cx="0.35" cy="0.3" r="0.75">
          <stop offset="0" stop-color="#ffffff"/><stop offset="0.55" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ADEEP}"/>
        </radialGradient>
        <filter id="b{gid}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>
      </defs>
      <rect width="480" height="250" fill="{BONE}"/>
      <circle cx="392" cy="74" r="64" fill="url(#{gid})" filter="url(#b{gid})" opacity="0.5"/>
      <circle cx="392" cy="74" r="46" fill="url(#{gid})" opacity="0.95"/>
      <text x="46" y="150" font-family="Fraunces,Georgia,serif" font-style="italic" font-size="116" font-weight="600" fill="{FAINT}">{wn}</text>
      <text x="52" y="60" font-family="'JetBrains Mono',monospace" font-size="14" letter-spacing="3" fill="{ACCENT}">WEEK {wn}</text>
      <line x1="52" y1="180" x2="428" y2="180" stroke="{LINE}" stroke-width="1.5"/>
      <text x="52" y="200" font-family="'Noto Serif KR',serif" font-size="15" font-weight="600" fill="{INK}">{esc(top)}</text>
      {ticks}
    </svg>'''

def card(issue, hero=False):
    d = issue["digest"]
    top = " ".join(d["news"][0]["title_kr"].split("\n"))
    srcs = " · ".join(n["source"].split(" / ")[0] for n in d["news"])
    href = f'issues/{issue["id"]}.html'
    if hero:
        return f'''<div class="featured"><a class="card tilt featured-tilt" href="{esc(href)}">
      <div class="thumb lift">{thumb_svg(issue)}</div>
      <div class="cbody">
        <div class="eyebrow">최신 호 · {esc(d["date_label"])}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">AI 주요 뉴스 3건 · {esc(srcs)}</p>
        <span class="clink">이번 호 읽기 <span class="arr">→</span></span>
      </div></a></div>'''
    return f'''<a class="card tilt" href="{esc(href)}">
      <div class="thumb">{thumb_svg(issue)}</div>
      <div class="cbody">
        <div class="eyebrow">{esc(d["date_label"])}</div>
        <h3 class="ctitle">{esc(top)}</h3>
        <p class="cmeta">뉴스 3건 · {esc(srcs)}</p>
        <span class="clink">읽기 <span class="arr">→</span></span>
      </div></a>'''

def build_index(issues):
    latest = issues[0]
    rest = issues[1:]
    hero_card = card(latest, hero=True)
    cards = "\n".join(card(it) for it in rest)
    grid = f'<div class="grid">{cards}</div>' if rest else ''
    rest_h = '<div class="sec-label">지난 호</div>' if rest else ''
    n_issue = len(issues)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 뉴스룸 · 주간 AI 뉴스 다이제스트</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400..600;1,9..144,400..600&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Noto+Serif+KR:wght@500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="assets/site.css">
</head>
<body>
<div class="orbs"><span class="orb o1"></span><span class="orb o2"></span><span class="orb o3"></span></div>
<nav class="nav">
  <span class="brand">AI 뉴스룸<span class="dot">.</span></span>
  <span class="tag">주간 AI 뉴스 다이제스트</span>
  <span class="spacer"></span>
  <span class="pill">{n_issue} issues</span>
</nav>
<div class="wrap">
  <section class="masthead">
    <div class="mh-copy">
      <div class="kicker">Weekly · AI Newsroom</div>
      <h1>이번 주, AI는<br><em>이렇게</em> 움직였다.</h1>
      <p>매주 가장 중요한 AI 뉴스 3가지. 카드를 누르면 그 주의 다이제스트로 들어갑니다.</p>
    </div>
    <div class="hero3d"><canvas id="scene"></canvas></div>
  </section>

  {hero_card}
  {rest_h}
  {grid}

  <div class="foot">
    <span class="fbrand">AI 뉴스룸</span> · 자동 생성 MVP<br>
    뉴스 본문은 LLM 웹검색 자동 수집물입니다. 게시 전 출처 확인을 권장합니다.
  </div>
</div>
<script src="{THREE_CDN}"></script>
<script src="assets/site.js"></script>
</body></html>'''

def main():
    files = glob.glob(os.path.join(ISSUES_DIR, "*.json"))
    if not files:
        print("no issues in", ISSUES_DIR); return
    issues = []
    for f in files:
        wid = os.path.splitext(os.path.basename(f))[0]
        with open(f, "r", encoding="utf-8") as fh:
            issues.append({"id": wid, "digest": json.load(fh)})
    issues.sort(key=lambda x: x["id"], reverse=True)

    # assets 복사
    dst_assets = os.path.join(OUT_DIR, "assets")
    os.makedirs(dst_assets, exist_ok=True)
    for fn in os.listdir(ASSETS_SRC):
        shutil.copy2(os.path.join(ASSETS_SRC, fn), os.path.join(dst_assets, fn))

    # GitHub Pages가 Jekyll로 처리하지 않도록
    open(os.path.join(OUT_DIR, ".nojekyll"), "w").close()

    os.makedirs(os.path.join(OUT_DIR, "issues"), exist_ok=True)
    for it in issues:
        out = os.path.join(OUT_DIR, "issues", it["id"] + ".html")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(render(it["digest"], back_href="../index.html", asset_prefix="../",
                            week_label="WEEK " + week_num(it["id"]) + " · " + it["digest"]["date_label"]))
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(build_index(issues))
    print("built index + %d issues:" % len(issues), ", ".join(i["id"] for i in issues))

if __name__ == "__main__":
    main()
