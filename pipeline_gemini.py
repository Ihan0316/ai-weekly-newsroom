# -*- coding: utf-8 -*-
"""
무인 데일리 파이프라인 (GitHub Actions용). LLM 단계는 Google Gemini(무료 티어) 사용.
오늘 날짜의 뉴스 3건을 골라 본문 추출·퀴즈/용어 생성 → data/days/<오늘>.json 작성 →
fetch_images.py / gen_audio.py / build_site.py 실행. (git 커밋·푸시는 워크플로우가 담당.)

env: GEMINI_API_KEY 필요. TZ=Asia/Seoul 권장(오늘 날짜 기준).
"""
import os, sys, json, re, glob, time, datetime, subprocess
import urllib.request

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
    # 직접 시도 → 실패(데이터센터 IP 403 등) 시 r.jina.ai 리더 프록시 경유
    last = None
    for u in (url, "https://r.jina.ai/" + url):
        try:
            req = urllib.request.Request(u, headers={
                "User-Agent": UA, "Accept": "text/html,*/*", "Accept-Language": "ko,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read(maxbytes).decode("utf-8", "ignore")
        except Exception as e:
            last = e
            sys.stderr.write("fetch fail (%s): %s\n" % (u[:40], e))
    raise last

def clean_html(html, limit=120000):
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<!--.*?-->", " ", html)
    return html[:limit]

def existing():
    urls, titles, qs, terms = set(), set(), [], set()
    for f in glob.glob(os.path.join(DAYS, "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for it in d.get("news", []):
            urls.add((it.get("url") or "").strip()); titles.add(it.get("title_kr", ""))
        q = d.get("quiz", {})
        if q.get("question"): qs.append(q["question"])
        for t in d.get("terms", []): terms.add(t.get("term", ""))
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

def select_news(today, ex_urls):
    yozm = clean_html(fetch("https://yozm.wishket.com/magazine/list/new/"))
    hada = clean_html(fetch("https://news.hada.io/"))
    prompt = (
        "오늘은 %s. 아래는 요즘IT 매거진 목록과 GeekNews 프런트 페이지 내용이다.\n"
        "가장 최근(오늘 또는 가장 신선한) 기사 중 서로 다른 주제 3건을 고른다.\n"
        "규칙:\n"
        "- 출처를 섞을 것: 가능하면 요즘IT 1건 이상 포함.\n"
        "- 한국어 본문이 있는 기사를 우선(영어 전용 외부 페이지·검색결과·툴·PDF 뷰어는 피함).\n"
        "- GeekNews 항목의 url은 반드시 'https://news.hada.io/topic?id=...' (GeekNews 토픽 페이지)로 줄 것. 외부 원문 링크 금지.\n"
        "- 요즘IT 항목의 url은 'https://yozm.wishket.com/magazine/detail/...' 형태.\n"
        "- 광고·이벤트·채용·홍보 글 제외. 아래 '이미 수록된 URL'에 있는 것 제외.\n"
        "각 항목: title_kr(한국어 제목), source('요즘IT' 또는 'GeekNews'), url(위 규칙대로), blurb_kr(한 줄 요약, 한국어).\n\n"
        "[이미 수록된 URL]\n%s\n\n[요즘IT 페이지]\n%s\n\n[GeekNews 페이지]\n%s\n"
    ) % (today, "\n".join(sorted(ex_urls)), yozm, hada)
    out = gemini(prompt, NEWS_SCHEMA, max_tokens=4096)

    def valid_url(u):
        # 프롬프트 규칙 강제: GeekNews=토픽 페이지, 요즘IT=매거진 상세. 그 외(모델이 재구성한
        # 외부 원문/환각 링크)는 본문추출 실패·죽은 링크로 이어지므로 코드에서 버림.
        return (u.startswith("https://news.hada.io/topic?id=")
                or u.startswith("https://yozm.wishket.com/magazine/detail/"))

    items = []
    for it in out.get("items", []):
        u = (it.get("url") or "").strip()
        if not u or u in ex_urls:
            continue
        if not valid_url(u):
            sys.stderr.write("skip off-pattern url: %s\n" % u[:80]); continue
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

    # day JSON은 위에서 이미 기록됨. 이미지·오디오는 부가물 → 실패해도 그날 콘텐츠를 버리지 않음
    # (check=False). 사이트 생성(build_site)만 필수라 실패 시 예외로 중단.
    for script in ("fetch_images.py", "gen_audio.py"):
        print("== run", script, "==")
        r = subprocess.run([sys.executable, os.path.join(HERE, script)])
        if r.returncode != 0:
            sys.stderr.write("WARN %s 실패(rc=%s) — 계속 진행\n" % (script, r.returncode))
    print("== run build_site.py ==")
    subprocess.run([sys.executable, os.path.join(HERE, "build_site.py")], check=True)

if __name__ == "__main__":
    main()
