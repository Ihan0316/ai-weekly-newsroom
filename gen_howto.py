# -*- coding: utf-8 -*-
"""주제 하나로 네이버 검색 최적화 'how-to/가이드' 글 1편 생성. GEMINI_API_KEY 필요.

뉴스 요약보다 검색 유입·조회수에 유리한 실용 가이드 포맷(최고 조회수 글 분석 반영:
검색키워드 제목 + 구어체 도입 + 단계별 소제목 + 실용 팁).

사용:
  python gen_howto.py "GPT-5.6 처음 쓰는 법"
  python gen_howto.py "클로드 코드 설치하고 세팅하기"
출력: data/howto/<날짜>-<slug>.json
  → 로컬에서:  python naver_publish.py --howto data/howto/<파일>.json --blog-id aijnj123
  (이미지·스크린샷은 발행 전 직접 추가 권장 — 조회수엔 이미지가 크게 작용)
"""
import os, sys, io, json, re, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pipeline_gemini as P

HOWTO_DIR = os.path.join(P.HERE, "data", "howto")

PERSONA = (
    "너는 네이버 인기 블로거다. **독자는 IT를 잘 모르는 일반인**이다. "
    "검색해서 들어온 사람이 '오 이거 나한테 필요한데?' 하고 끝까지 읽고 따라 하게 만드는 글을 쓴다.\n"
    "말투·구성 규칙:\n"
    "- 전문용어를 쓰면 반드시 바로 옆에 쉬운 말로 풀어준다. 예: 'API(프로그램끼리 대화하는 통로)'\n"
    "- 개발자만 아는 표현·명령어 나열식 금지. 꼭 필요할 때만 최소한으로.\n"
    "- 공감으로 시작한다. '이런 적 있으시죠?' 같은 상황 묘사 → 그래서 이 글이 뭘 해결해주는지.\n"
    "- 결론을 먼저 준다. 뭘 얻는지 초반에 명확히.\n"
    "- 한 문단 2~3줄. 길게 늘어놓지 말 것. 구어체(~해요, ~됩니다).\n"
    "- 비유를 적극 쓴다. 어려운 개념은 일상 사물에 빗대서.\n"
    "- 과장·낚시·광고 문구 금지. 모르는 사실은 지어내지 말 것.\n"
    "필드:\n"
    "- title_blog: 일반인이 검색할 법한 쉬운 말 제목(38자 이내, 이모지 최대 1개). "
    "전문용어 대신 '~하는 법', '~쉽게 쓰는 법' 형태.\n"
    "- hook_kr: 공감 도입 2~3문장. 상황 묘사 + 이 글로 뭘 할 수 있는지.\n"
    "- content: {t:'h'} 소제목과 {t:'p'} 설명을 번갈아 14~20블록. 구성은 "
    "①이게 뭔데요?(쉬운 설명) ②왜 필요한가(실생활 이득) ③준비물 ④따라하기 단계 "
    "⑤초보가 자주 하는 실수 ⑥더 편하게 쓰는 팁 순서.\n"
    "- comment_kr: 마무리 한마디 2~3문장. 직접 해본 사람의 솔직한 소감 톤.\n"
    "- blurb_kr: 한 줄 요약(쉬운 말).\n"
    "- tags_kr: 일반인이 검색할 태그 6~8개(# 없이, 공백 없이 붙여쓰기)."
)

SCHEMA = {"type": "OBJECT", "properties": {
    "title_blog": {"type": "STRING"}, "hook_kr": {"type": "STRING"},
    "blurb_kr": {"type": "STRING"}, "comment_kr": {"type": "STRING"},
    "tags_kr": {"type": "ARRAY", "items": {"type": "STRING"}},
    "content": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "t": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["t", "text"]}},
}, "required": ["title_blog", "hook_kr", "blurb_kr", "tags_kr", "content"]}


def slugify(t):
    return re.sub(r"[^0-9a-z가-힣]+", "-", t.lower()).strip("-")[:40] or "howto"


def existing_topics():
    """이미 만든 how-to 주제 set(배치 중복 방지)."""
    import glob
    ts = set()
    for f in glob.glob(os.path.join(HOWTO_DIR, "*.json")):
        try:
            ts.add((json.load(io.open(f, encoding="utf-8")).get("topic") or "").strip())
        except Exception:
            pass
    return {t for t in ts if t}


TOPIC_SCHEMA = {"type": "OBJECT", "properties": {
    "topics": {"type": "ARRAY", "items": {"type": "STRING"}}}, "required": ["topics"]}


def propose_topics(n):
    """최근 뉴스 기반으로 검색수요 있는 how-to 주제 n개 제안(이미 만든 것·비기술 제외)."""
    recent = P.recent_titles(days=21, cap=40)
    done = existing_topics()
    prompt = (
        "네이버·구글에서 **일반인이 실제로 많이 검색할** how-to/가이드 글 주제 %d개를 제안한다.\n"
        "독자는 IT를 잘 모르는 보통 사람이다. 아래 최근 IT/AI 뉴스는 '요즘 뭐가 이슈인지' 참고용일 뿐,\n"
        "주제는 반드시 일반인이 검색할 만한 형태로 바꿔서 제안할 것.\n"
        "- 좋은 예: 'ChatGPT 무료로 쓰는 법', 'AI로 사진 배경 지우는 법', '스마트폰 저장공간 늘리는 법',\n"
        "  'AI로 자기소개서 쓰는 법', '갤럭시 AI 기능 켜는 법', '무료 AI 이미지 만드는 사이트'\n"
        "- 나쁜 예(절대 금지): CLI 도구·npm 패키지·API 연동·오픈소스 라이브러리 설치 등 개발자 전용 주제.\n"
        "  'ADBC CLI 설치', 'sem 버전관리', 'gh-attach' 같은 건 일반인이 검색하지 않는다.\n"
        "- 실생활에서 바로 써먹는 이득이 분명할 것(돈 절약·시간 절약·귀찮음 해결).\n"
        "- 이미 다룬 주제 제외: %s\n"
        "- 서로 겹치지 않게.\n\n"
        "topics 배열(문자열)로만 반환.\n\n[참고용 최근 뉴스]\n%s"
    ) % (n, (" / ".join(sorted(done)) or "(없음)"), "\n".join("- " + t for t in recent))
    out = P.gemini(prompt, TOPIC_SCHEMA, max_tokens=1024, temp=0.8)
    seen, topics = set(), []
    for t in out.get("topics", []):
        t = (t or "").strip()
        if t and t not in done and t.lower() not in seen:
            seen.add(t.lower()); topics.append(t)
    return topics[:n]


def generate_one(topic):
    """주제 1개 → how-to json 작성, 경로 반환(실패 시 None)."""
    out = P.gemini(PERSONA + "\n\n주제: %s\n" % topic, SCHEMA, max_tokens=4096, temp=0.7)
    content = [{"t": ("h" if b.get("t") == "h" else "p"), "text": (b.get("text") or "").strip()}
               for b in out.get("content", []) if (b.get("text") or "").strip()]
    if len(content) < 4:
        sys.stderr.write("본문 블록 부족(%d) 스킵: %s\n" % (len(content), topic)); return None
    today = datetime.date.today().isoformat()
    sl = slugify(topic)
    tb = (out.get("title_blog") or topic).strip()
    rec = {
        "title_kr": tb, "title_blog": tb, "blurb_kr": (out.get("blurb_kr") or "").strip(),
        "hook_kr": (out.get("hook_kr") or "").strip(), "comment_kr": (out.get("comment_kr") or "").strip(),
        "tags_kr": [t.strip() for t in (out.get("tags_kr") or []) if t and t.strip()][:8],
        "content": content, "source": "직접작성", "url": "howto:%s" % sl,
        "date": today, "topic": topic,
    }
    os.makedirs(HOWTO_DIR, exist_ok=True)
    path = os.path.join(HOWTO_DIR, "%s-%s.json" % (today, sl))
    json.dump(rec, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("작성:", path, "| 제목:", tb, "| 블록:", len(content))
    return path


def main():
    import argparse
    ap = argparse.ArgumentParser(description="how-to 글 생성(단일 주제 또는 --batch 자동제안)")
    ap.add_argument("topic", nargs="*", help="주제(생략 시 --batch 필요)")
    ap.add_argument("--batch", type=int, help="최근 뉴스에서 N개 주제 자동제안 후 생성")
    a = ap.parse_args()
    if not P.KEY:
        sys.stderr.write("GEMINI_API_KEY 없음 — 키 설정 후 실행\n"); sys.exit(1)

    if a.batch:
        topics = propose_topics(a.batch)
        if not topics:
            sys.exit("제안된 신규 주제 없음(이미 다 다뤘거나 뉴스 부족)")
        print("제안 주제 %d개: %s" % (len(topics), " / ".join(topics)))
        made = [p for t in topics if (p := generate_one(t))]
        print("배치 완료: %d편" % len(made))
        print("티스토리 변환:  ls data/howto/*.json  →  python tistory_export.py <파일>")
        return

    topic = " ".join(a.topic).strip()
    if not topic:
        sys.exit('주제 인자 또는 --batch N 필요. 예) python gen_howto.py "GPT-5.6 처음 쓰는 법"')
    path = generate_one(topic)
    if path:
        print("티스토리:  python tistory_export.py %s" % path)
        print("네이버(선택):  python naver_publish.py --howto %s --blog-id aijnj123" % path)


if __name__ == "__main__":
    main()
