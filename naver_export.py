# -*- coding: utf-8 -*-
"""
naver_export.py — 하루치 day JSON을 네이버 블로그 붙여넣기용 텍스트로 변환.

반자동 발행용: 완전자동(무인) 발행은 네이버 이용약관상 자동화 도구 금지 +
글쓰기 오픈API 폐지(2020-05-06)로 불가/계정 제재 리스크. 대신 이 스크립트가
매일 '네이버 에디터에 그대로 붙는 텍스트'를 만들어 두면 사용자가 30초 복붙+발행.

출력:
  naver/<YYYY-MM-DD>.txt   ← 제목 1줄 + 본문 (복붙용, 일반 텍스트)

저작권 주의: 뉴스 content 전문은 자동 크롤 원문이라 그대로 재게시 안 함.
기본은 본인 요약(blurb_kr) + 소제목 개요 + 원문 링크. --full 주면 본문 문단도 포함.

사용:
  python naver_export.py               # data/days 최신 날짜
  python naver_export.py 2026-07-02    # 특정 날짜
  python naver_export.py --full        # 뉴스 본문 문단까지 포함
"""
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.abspath(__file__))
DAYS_DIR = os.path.join(ROOT, "data", "days")
OUT_DIR = os.path.join(ROOT, "naver")
DOCS_NAVER = os.path.join(ROOT, "docs", "naver")
LIVE_URL = "https://ihan0316.github.io/ai-weekly-newsroom/"

CIRC = ["①", "②", "③", "④", "⑤", "⑥"]
RULE = "━━━━━━━━━━━━━━━━━━━━"


def latest_date():
    files = [f[:-5] for f in os.listdir(DAYS_DIR) if f.endswith(".json")]
    if not files:
        raise SystemExit("data/days 에 JSON 없음")
    return sorted(files)[-1]


def load_day(date):
    path = os.path.join(DAYS_DIR, date + ".json")
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def render(day, date, full=False):
    label = day.get("date_label", date)
    weekday = day.get("weekday", "")
    title = "🤖 AI 데일리 다이제스트 | {} ({})".format(label, weekday)

    L = []
    L.append("오늘의 AI·개발 소식 {}건 + 정보처리기사 퀴즈 + IT 용어 {}개 정리했습니다.".format(
        len(day.get("news", [])), len(day.get("terms", []))))
    L.append("")

    # 뉴스
    L.append(RULE)
    L.append("📰 오늘의 뉴스")
    L.append(RULE)
    for i, n in enumerate(day.get("news", []), 1):
        L.append("")
        L.append("{}. {}".format(i, n.get("title_kr", "").strip()))
        L.append("출처: {}".format(n.get("source", "")))
        blurb = n.get("blurb_kr", "").strip()
        if blurb:
            L.append(blurb)
        # 소제목 개요 (t=='h')
        heads = [c["text"].strip() for c in n.get("content", []) if c.get("t") == "h" and c.get("text")]
        if full:
            for c in n.get("content", []):
                t = c.get("text", "").strip()
                if not t:
                    continue
                L.append("▸ " + t if c.get("t") == "h" else t)
        elif heads:
            L.append("주요 내용: " + " / ".join(heads))
        L.append("🔗 원문 보기: {}".format(n.get("url", "")))

    # 퀴즈
    q = day.get("quiz")
    if q:
        L.append("")
        L.append(RULE)
        L.append("🧠 오늘의 퀴즈 (정보처리기사)")
        L.append(RULE)
        cat = q.get("category", "")
        L.append("[{}] {}".format(cat, q.get("question", "").strip()) if cat else q.get("question", "").strip())
        for j, opt in enumerate(q.get("options", [])):
            L.append("{} {}".format(CIRC[j] if j < len(CIRC) else str(j + 1), opt))
        ans = q.get("answer")
        if isinstance(ans, int):
            L.append("")
            L.append("정답: {}번".format(ans + 1))
        exp = q.get("explain_kr", "").strip()
        if exp:
            L.append("해설: " + exp)

    # 용어
    terms = day.get("terms", [])
    if terms:
        L.append("")
        L.append(RULE)
        L.append("📖 오늘의 IT 용어")
        L.append(RULE)
        for t in terms:
            kind = t.get("kind", "")
            head = "• {} ({})".format(t.get("term", ""), kind) if kind else "• {}".format(t.get("term", ""))
            L.append("")
            L.append(head)
            L.append("  " + t.get("meaning_kr", "").strip())

    # 푸터
    L.append("")
    L.append("---")
    L.append("※ 뉴스는 자동 수집·요약본입니다. 정확한 내용은 원문 링크를 확인하세요.")
    L.append("🌐 전체 보기(뉴스 원문·음성·검색): {}".format(LIVE_URL))
    L.append("#AI #인공지능 #개발 #IT용어 #정보처리기사 #개발자 #데일리뉴스")

    return title, "\n".join(L)


PAGE_TMPL = u"""<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>네이버 복사 · AI 데일리 다이제스트</title>
<style>
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",sans-serif;
background:#0f1115;color:#e8eaed;line-height:1.6}
.wrap{max-width:720px;margin:0 auto;padding:20px 16px 80px}
h1{font-size:18px;margin:8px 0 4px}
.meta{font-size:13px;color:#9aa0a6;margin-bottom:16px}
.bar{position:sticky;top:0;display:flex;gap:8px;padding:12px 0;background:#0f1115;z-index:2}
button{flex:1;padding:14px 10px;border:0;border-radius:12px;font-size:15px;font-weight:700;
cursor:pointer;background:#03c75a;color:#fff}
button.sec{background:#2a2d34;color:#e8eaed}
button:active{transform:scale(.98)}
.card{background:#171a1f;border:1px solid #24272e;border-radius:14px;padding:14px;margin:12px 0}
.card h2{font-size:13px;color:#9aa0a6;margin:0 0 8px;font-weight:600}
pre{white-space:pre-wrap;word-break:break-word;margin:0;font:inherit;font-size:14.5px}
.hint{font-size:12.5px;color:#9aa0a6;margin-top:10px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#03c75a;color:#fff;
padding:10px 18px;border-radius:999px;font-size:14px;opacity:0;transition:.2s;pointer-events:none}
.toast.on{opacity:1}
</style></head><body><div class="wrap">
<h1>📋 네이버 블로그 복붙용</h1>
<div class="meta">__DATE__ · 아래 버튼으로 제목/본문 복사 → 네이버 글쓰기에 붙여넣기</div>
<div class="bar">
<button onclick="cp('t')">① 제목 복사</button>
<button class="sec" onclick="cp('b')">② 본문 복사</button>
</div>
<div class="card"><h2>제목</h2><pre id="t">__TITLE__</pre></div>
<div class="card"><h2>본문</h2><pre id="b">__BODY__</pre></div>
<div class="hint">팁: 제목 복사 → 네이버 제목칸 붙여넣기 → 본문 복사 → 본문칸 붙여넣기 → 발행.
자동 발행은 네이버 정책상 계정 제재 위험이 있어 발행 버튼만 직접 누르는 방식입니다.</div>
</div>
<div class="toast" id="toast">복사됨</div>
<script>
function cp(id){var el=document.getElementById(id);var t=el.innerText;
function ok(){var x=document.getElementById('toast');x.classList.add('on');setTimeout(function(){x.classList.remove('on')},1200)}
if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t).then(ok,function(){sel(el)})}
else{sel(el)}}
function sel(el){var r=document.createRange();r.selectNodeContents(el);var s=getSelection();s.removeAllRanges();s.addRange(r);try{document.execCommand('copy');document.getElementById('toast').classList.add('on');setTimeout(function(){document.getElementById('toast').classList.remove('on')},1200)}catch(e){}}
</script></body></html>"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_copy_page(date, label, weekday, title, body):
    os.makedirs(DOCS_NAVER, exist_ok=True)
    datestr = "{} ({})".format(label, weekday) if weekday else label
    html = (PAGE_TMPL
            .replace("__DATE__", esc(datestr))
            .replace("__TITLE__", esc(title))
            .replace("__BODY__", esc(body)))
    with io.open(os.path.join(DOCS_NAVER, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    # 데이터도 별도 저장(향후 자동화 확장용)
    with io.open(os.path.join(DOCS_NAVER, "latest.json"), "w", encoding="utf-8") as f:
        json.dump({"date": date, "title": title, "body": body}, f, ensure_ascii=False)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    full = "--full" in sys.argv
    date = args[0] if args else latest_date()

    day = load_day(date)
    title, body = render(day, date, full=full)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, date + ".txt")
    with io.open(out, "w", encoding="utf-8") as f:
        f.write("제목: " + title + "\n\n")
        f.write(body + "\n")

    write_copy_page(date, day.get("date_label", date), day.get("weekday", ""), title, body)

    print("생성:", os.path.relpath(out, ROOT))
    print("복사페이지:", os.path.relpath(os.path.join(DOCS_NAVER, "index.html"), ROOT))
    print("제목:", title)
    print("본문 {}자".format(len(body)))


if __name__ == "__main__":
    main()
