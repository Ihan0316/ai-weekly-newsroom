# -*- coding: utf-8 -*-
"""
무인 데일리 파이프라인 (GitHub Actions용). LLM 단계는 Google Gemini(무료 티어) 사용.
오늘 날짜의 뉴스 3건을 골라 본문 추출·퀴즈/용어 생성 → data/days/<오늘>.json 작성 →
fetch_images.py / build_site.py 실행. (git 커밋·푸시는 워크플로우가 담당.)

env: GEMINI_API_KEY 필요. TZ=Asia/Seoul 권장(오늘 날짜 기준).
"""
import os, sys, json, re, glob, time, datetime, subprocess
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (MODEL, KEY)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = os.path.join(HERE, "data", "days")
WD = ["월", "화", "수", "목", "금", "토", "일"]

def gemini(prompt, schema=None, max_tokens=8192, temp=0.4):
    # thinkingBudget 0: 2.5 Flash의 추론 토큰이 출력 예산을 먹어 JSON이 잘리는 것 방지
    cfg = {"temperature": temp, "maxOutputTokens": max_tokens, "responseMimeType": "application/json",
           "thinkingConfig": {"thinkingBudget": 0}}
    if schema:
        cfg["responseSchema"] = schema
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg}
    data = json.dumps(body).encode("utf-8")
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(API, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                j = json.loads(r.read().decode("utf-8", "ignore"))
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(txt)
        except Exception as e:
            last = e
            sys.stderr.write("gemini retry %d: %s\n" % (attempt, e))
            time.sleep(6)
    raise RuntimeError("gemini failed: %s" % last)

def fetch(url, maxbytes=500000):
    # r.jina.ai 프록시 폴백 제거(2026-07-10): 현재 CAPTCHA 페이지를 200으로 반환해
    # 본문 추출을 오염시킴. 뉴스 목록은 RSS/Atom 피드 기반이라 403 우회 자체가 불필요.
    last = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": "text/html,application/xml,*/*", "Accept-Language": "ko,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read(maxbytes).decode("utf-8", "ignore")
        except Exception as e:
            last = e
            sys.stderr.write("fetch fail %d (%s): %s\n" % (attempt, url[:60], e))
            time.sleep(3)
    raise last

def clean_html(html, limit=120000):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    return html[:limit]

def existing():
    # 파일명=날짜라 sorted()가 곧 시간순 → 퀴즈/용어는 프롬프트에 최근분만 보내 토큰 절약
    urls, titles, qs, terms = set(), set(), [], []
    for f in sorted(glob.glob(os.path.join(DAYS, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for it in d.get("news", []):
            urls.add((it.get("url") or "").strip()); titles.add(it.get("title_kr", ""))
        q = d.get("quiz", {})
        if q.get("question"): qs.append(q["question"])
        for t in d.get("terms", []):
            name = t.get("term", "")
            if name and name not in terms: terms.append(name)
    return urls, titles, qs, terms

NEWS_SCHEMA = {"type": "OBJECT", "properties": {"items": {"type": "ARRAY", "items": {"type": "OBJECT",
    "properties": {"title_kr": {"type": "STRING"}, "source": {"type": "STRING"}, "url": {"type": "STRING"}, "blurb_kr": {"type": "STRING"}},
    "required": ["title_kr", "source", "url", "blurb_kr"]}}}, "required": ["items"]}
BODY_SCHEMA = {"type": "OBJECT", "properties": {"blocks": {"type": "ARRAY", "items": {"type": "OBJECT",
    "properties": {"t": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["t", "text"]}}}, "required": ["blocks"]}
QT_SCHEMA = {"type": "OBJECT", "properties": {
    "quiz": {"type": "OBJECT", "properties": {"category": {"type": "STRING"}, "question": {"type": "STRING"},
        "options": {"type": "ARRAY", "items": {"type": "STRING"}}, "answer": {"type": "INTEGER"}, "explain_kr": {"type": "STRING"}},
        "required": ["category", "question", "options", "answer", "explain_kr"]},
    "terms": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"term": {"type": "STRING"}, "kind": {"type": "STRING"}, "meaning_kr": {"type": "STRING"}},
        "required": ["term", "kind", "meaning_kr"]}}}, "required": ["quiz", "terms"]}

ATOM = "{http://www.w3.org/2005/Atom}"
CE = "{http://purl.org/rss/1.0/modules/content/}encoded"

def strip_tags(html, limit):
    return re.sub(r"\s+", " ", re.sub(r"(?is)<[^>]+>", " ", html or "")).strip()[:limit]

# 뉴스 소스 피드 — 다양성 위해 국내(GeekNews·요즘IT·AITimes·ZDNet KR)+해외(HackerNews·TechCrunch) 혼합.
# 피드별 실패는 graceful(그 소스만 빠지고 나머지로 진행). 추가/제거는 이 리스트만 수정.
#   kind: 'atom'|'rss' · prefix: 기사 URL 접두 검증(None=무검증) · cap: 후보 최대 · fresh_days: 최근 N일만(None=무시)
#   body: content:encoded 에 본문 전문이 있어 상세크롤 불필요(요즘IT). 나머지는 extract_body 가 기사 크롤.
FEEDS = [
    {"source": "GeekNews", "url": "https://news.hada.io/rss/news", "kind": "atom",
     "prefix": "https://news.hada.io/topic?id=", "cap": 15, "fresh_days": 2},
    {"source": "요즘IT", "url": "https://yozm.wishket.com/magazine/feed/", "kind": "rss",
     "prefix": "https://yozm.wishket.com/magazine/detail/", "cap": 10, "fresh_days": None, "body": True},
    {"source": "AITimes", "url": "https://www.aitimes.com/rss/allArticle.xml", "kind": "rss",
     "prefix": "https://www.aitimes.com/", "cap": 10, "fresh_days": 2},
    {"source": "ZDNet Korea", "url": "https://feeds.feedburner.com/zdkorea", "kind": "rss",
     "prefix": None, "cap": 10, "fresh_days": 2},
    {"source": "Hacker News", "url": "https://hnrss.org/frontpage", "kind": "rss",
     "prefix": None, "cap": 10, "fresh_days": 2},
    {"source": "TechCrunch", "url": "https://techcrunch.com/feed/", "kind": "rss",
     "prefix": None, "cap": 8, "fresh_days": 2},
]

def _entry_date(kind, e):
    """피드 항목 → YYYY-MM-DD(없으면 '')."""
    if kind == "atom":
        return (e.findtext(ATOM + "published") or e.findtext(ATOM + "updated") or "")[:10]
    pd = e.findtext("pubDate") or ""
    if pd:
        try:
            return parsedate_to_datetime(pd).date().isoformat()
        except Exception:
            return ""
    return ""

def parse_feed(feed, today):
    """한 피드 → 후보 리스트(atom/rss 공용). 실패 시 [](graceful)."""
    try:
        root = ET.fromstring(fetch(feed["url"], maxbytes=3000000))
    except Exception as e:
        sys.stderr.write("feed fail %s: %s\n" % (feed["source"], e)); return []
    kind = feed["kind"]
    entries = list(root.iter(ATOM + "entry")) if kind == "atom" else list(root.iter("item"))
    cutoff = None
    if feed.get("fresh_days"):
        cutoff = datetime.date.fromisoformat(today) - datetime.timedelta(days=feed["fresh_days"])
    out = []
    for e in entries:
        if kind == "atom":
            link = e.find(ATOM + "link")
            url = (link.get("href") if link is not None else "").strip()
            title = (e.findtext(ATOM + "title") or "").strip()
            snip = strip_tags(e.findtext(ATOM + "content") or e.findtext(ATOM + "summary"), 240)
            body = ""
        else:
            url = (e.findtext("link") or "").strip()
            title = (e.findtext("title") or "").strip()
            snip = strip_tags(e.findtext("description"), 240)
            ce = e.find(CE)
            body = (ce.text or "") if (ce is not None and feed.get("body")) else ""
        if not url or not title:
            continue
        if feed.get("prefix") and not url.startswith(feed["prefix"]):
            continue
        d = _entry_date(kind, e)
        if cutoff is not None and d:
            try:
                if datetime.date.fromisoformat(d) < cutoff:
                    continue
            except ValueError:
                pass
        out.append({"source": feed["source"], "url": url, "date": d,
                    "title": title, "snippet": snip, "body_html": body})
        if len(out) >= feed.get("cap", 12):
            break
    return out

def select_news(today, ex_urls):
    # 피드 기반(2026-07-10 개편): 페이지 HTML 통째 투입(~240KB) 대신 후보 목록(~10KB)만
    # 프롬프트에 넣는다. 날짜 필터·중복 제거·URL 검증은 전부 코드에서 확정.
    cands, seen = [], set()
    for feed in FEEDS:
        for c in parse_feed(feed, today):
            if c["url"] in seen:  # 피드 간 중복 URL 제거
                continue
            seen.add(c["url"]); cands.append(c)
    cands = [c for c in cands if c["url"] not in ex_urls]
    if not cands:
        sys.stderr.write("후보 0건 (피드 실패 또는 전부 기수록)\n"); return []
    by_url = {c["url"]: c for c in cands}
    by_src = {}
    for c in cands:
        by_src[c["source"]] = by_src.get(c["source"], 0) + 1
    sys.stderr.write("후보 %d건 · 출처별 %s\n" % (len(cands), by_src))
    lines = ["%d. [%s%s] %s\n   %s\n   요약: %s" % (
        i, c["source"], (" " + c["date"]) if c["date"] else "", c["title"], c["url"], c["snippet"])
        for i, c in enumerate(cands, 1)]
    prompt = (
        "오늘은 %s. 아래 후보 기사 중 서로 다른 주제 3건을 고른다.\n"
        "규칙:\n"
        "- 오늘 날짜(%s) 기사 우선. 날짜 없는 항목(요즘IT 등)은 번호가 낮을수록 최신.\n"
        "- **출처 다양성**: 3건을 최대한 서로 다른 출처에서 고른다. 한 출처에서 최대 2건. "
        "특정 출처(GeekNews)에 쏠리지 말 것. 국내(요즘IT/AITimes/ZDNet Korea)와 해외(Hacker News/TechCrunch)를 섞으면 좋다.\n"
        "- AI·개발·IT·기술 주제 중심. 광고·이벤트·채용·홍보·단순 툴 소개·정치/연예 등 비기술 글 제외.\n"
        "- url은 후보에 적힌 것을 글자 그대로 복사(변형 금지).\n"
        "각 항목: title_kr(한국어 제목, 영어면 자연스럽게 번역), source, url, blurb_kr(한 줄 요약, 한국어).\n\n"
        "[후보]\n%s\n"
    ) % (today, today, "\n".join(lines))
    out = gemini(prompt, NEWS_SCHEMA, max_tokens=4096)

    items = []
    for it in out.get("items", []):
        u = (it.get("url") or "").strip()
        c = by_url.get(u)
        if c is None:  # 후보에 없는 URL(환각·변형) → 버림
            sys.stderr.write("skip non-candidate url: %s\n" % u[:80]); continue
        it["url"] = u; it["source"] = c["source"]; it["body_html"] = c["body_html"]
        items.append(it)
        if len(items) >= 3:
            break
    return items

def extract_body(url):
    try:
        html = clean_html(fetch(url), limit=100000)
    except Exception as e:
        sys.stderr.write("fetch fail %s: %s\n" % (url, e)); return []
    prompt = ("다음 페이지에서 기사 핵심 본문만 추출한다. 내비·광고·댓글·추천·푸터 제외.\n"
              "blocks 배열: 소제목 {t:'h', text}, 문단 {t:'p', text}. 한국어 본문이면 한국어로, 영어면 한국어로 자연스럽게 옮겨 적는다. 최대 12블록, 각 400자 이내.\n"
              "중요: 기사 본문이 없거나(PDF뷰어·검색결과·툴 페이지 등) 추출 불가하면 반드시 blocks:[] 로만 반환하고, 설명·변명 문장을 절대 넣지 말 것.\n\n[페이지]\n%s") % html
    try:
        out = gemini(prompt, BODY_SCHEMA, max_tokens=8192)
        blocks = [{"t": ("h" if b.get("t") == "h" else "p"), "text": (b.get("text") or "").strip()}
                  for b in out.get("blocks", []) if (b.get("text") or "").strip()]
        return clean_blocks(blocks)
    except Exception as e:
        sys.stderr.write("extract fail %s: %s\n" % (url, e)); return []

FAIL_HINTS = ("추출할 수 없", "포함하고 있지 않", "본문이 없", "본문을 찾을 수 없",
              "제공된 HTML", "제공된 페이지", "PDF 뷰어", "내용을 확인할 수 없", "robots")

def clean_blocks(blocks):
    # 추출 실패 변명이 본문으로 저장되는 것 방지 → 빈 배열(모달은 blurb 폴백)
    if len(blocks) <= 1:
        txt = blocks[0]["text"] if blocks else ""
        if (not blocks) or any(h in txt for h in FAIL_HINTS) or len(txt) < 40:
            return []
    # 본문(p) 한 개도 없으면(소제목만) 버림
    if not any(b["t"] == "p" for b in blocks):
        return []
    # 뒤쪽에 본문 없이 매달린 소제목 제거
    while blocks and blocks[-1]["t"] == "h":
        blocks.pop()
    # 연속된 소제목 중 본문이 안 따라오는 것 제거
    out = []
    for i, b in enumerate(blocks):
        if b["t"] == "h" and (i + 1 >= len(blocks) or blocks[i + 1]["t"] == "h"):
            continue
        out.append(b)
    return out

# 블로그 코멘트 페르소나 — 톤 바꾸려면 이 문자열만 수정
COMMENT_PERSONA = (
    "너는 개발을 배우는 주니어 개발자이자 IT 블로거다. 아래 각 뉴스에 대해 "
    "블로그에 덧붙일 '내 코멘트'를 1인칭으로 쓴다.\n"
    "규칙:\n"
    "- 2~4문장, 자연스러운 구어체 한국어.\n"
    "- 뉴스 요약을 반복하지 말고, 내 생각·시사점·실무나 학습 관점 연결·가벼운 의견이나 질문을 담을 것.\n"
    "- 과장·홍보·클릭베이트 금지. 아는 척보다 배우는 사람의 솔직한 시선.\n"
    "- 각 코멘트는 서로 다른 각도로."
)
COMMENT_SCHEMA = {"type": "OBJECT", "properties": {"comments": {"type": "ARRAY",
    "items": {"type": "OBJECT", "properties": {"comment_kr": {"type": "STRING"}},
              "required": ["comment_kr"]}}}, "required": ["comments"]}

def gen_comments(news):
    """뉴스 리스트에 대해 1인칭 블로그 코멘트를 배치로 생성해 comment_kr 채움(실패 시 빈 문자열)."""
    if not news:
        return
    lines = []
    for i, it in enumerate(news, 1):
        body = " ".join((b.get("text") or "") for b in (it.get("content") or []))[:600]
        lines.append("[%d] 제목: %s\n요약: %s\n본문일부: %s" % (
            i, it.get("title_kr", ""), it.get("blurb_kr", ""), body))
    prompt = COMMENT_PERSONA + "\n\n뉴스 %d건. 순서대로 comments 배열로 반환.\n\n%s" % (
        len(news), "\n\n".join(lines))
    try:
        out = gemini(prompt, COMMENT_SCHEMA, max_tokens=2048, temp=0.8)
        cs = out.get("comments", [])
    except Exception as e:
        sys.stderr.write("comment gen fail: %s\n" % e); cs = []
    for i, it in enumerate(news):
        it["comment_kr"] = (cs[i].get("comment_kr", "").strip() if i < len(cs) else "")

def make_quiz_terms(ex_qs, ex_terms):
    prompt = (
        "정보처리기사(정처기) 4지선다 문제 1개와 IT·개발·기획 현업 용어 3개를 만든다.\n"
        "아래 '기존 문제/용어'와 절대 겹치지 않게 새로 만든다.\n"
        "quiz: category(분야), question, options(보기 4개), answer(정답 인덱스 0~3), explain_kr(2~3문장 해설). 정답·해설 정확히. 너무 쉬운 정의 암기보다 개념 이해를 묻는 수준으로.\n"
        "terms: 3개. 각 term(용어명), kind('IT'|'개발'|'기획' 중 하나), meaning_kr(한 문장 정의).\n"
        "용어는 기존과 '같은 개념의 변형'도 피할 것 (예: 로드밸런서/로드밸런싱, CI-CD/지속적배포는 같은 것으로 본다).\n\n"
        "[기존 문제(겹치지 말 것)]\n%s\n\n[기존 용어(겹치지 말 것)]\n%s\n"
    ) % ("\n".join(ex_qs[-60:]), ", ".join(sorted(ex_terms)))
    out = gemini(prompt, QT_SCHEMA, max_tokens=4096, temp=0.7)
    q = out["quiz"]; q["answer"] = max(0, min(3, int(q.get("answer", 0))))
    return q, out["terms"][:3]

def main():
    if not KEY:
        sys.stderr.write("GEMINI_API_KEY 없음\n"); sys.exit(1)
    today = datetime.date.today()
    did = today.isoformat()
    out_path = os.path.join(DAYS, did + ".json")
    if os.path.exists(out_path):
        print("이미 처리됨:", did); return
    ex_urls, ex_titles, ex_qs, ex_terms = existing()

    news = select_news(did, ex_urls)
    if not news:
        print("추가할 신규 뉴스 없음"); return
    for it in news:
        it["content"] = extract_body(it.get("url", ""))
    gen_comments(news)   # 뉴스별 1인칭 블로그 코멘트(복사 시에만 사용)
    quiz, terms = make_quiz_terms(ex_qs, ex_terms)

    rec = {
        "date_label": "%d. %d. %d" % (today.year, today.month, today.day),
        "weekday": WD[today.weekday()],
        "news": [{"title_kr": it["title_kr"], "source": it["source"], "url": it["url"],
                  "blurb_kr": it.get("blurb_kr", ""), "content": it.get("content", []),
                  "comment_kr": it.get("comment_kr", "")} for it in news],
        "quiz": quiz, "terms": terms,
    }
    os.makedirs(DAYS, exist_ok=True)
    json.dump(rec, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("작성:", out_path, "| 뉴스", len(news), "| 본문", sum(1 for it in news if it.get("content")))

    # day JSON은 위에서 이미 기록됨. 이미지는 부가물 → 실패해도 그날 콘텐츠를 버리지 않음
    # (check=False). 사이트 생성(build_site)만 필수라 실패 시 예외로 중단.
    print("== run fetch_images.py ==")
    r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_images.py")])
    if r.returncode != 0:
        sys.stderr.write("WARN fetch_images.py 실패(rc=%s) — 계속 진행\n" % r.returncode)
    print("== run build_site.py ==")
    subprocess.run([sys.executable, os.path.join(HERE, "build_site.py")], check=True)

if __name__ == "__main__":
    main()
