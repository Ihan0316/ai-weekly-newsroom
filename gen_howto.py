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
    "너는 네이버 IT 블로거다. 아래 주제로 '검색해서 들어온 사람에게 실질적으로 도움이 되는 "
    "how-to/가이드' 글 1편을 쓴다. 최고 조회수 글의 포맷을 따른다.\n"
    "- title_blog: 검색 키워드를 맨 앞에 둔 클릭형 제목(38자 이내, 이모지 최대 1개, 과장·낚시 금지). "
    "예: '카플레이 전체화면 설정하는 법 🚗 (현대기아)'\n"
    "- hook_kr: 구어체 도입 1~2문장(왜 유용한지, 이 글로 뭘 할 수 있는지).\n"
    "- content: 실제로 따라 할 수 있는 단계별 구성. 소제목 {t:'h', text:'1단계: ...'} 와 "
    "설명 {t:'p', text:...} 를 번갈아. 10~16블록. 준비물·주의사항·팁 포함. 구체적이고 정확하게. "
    "확실하지 않은 사실·수치는 지어내지 말고 일반적 절차 위주로.\n"
    "- comment_kr: 마무리 한마디(1~2문장, 배우는 사람의 개인 톤).\n"
    "- blurb_kr: 한 줄 요약.\n"
    "- tags_kr: 검색 유입 태그 6~8개(# 없이, 공백 없이 붙여쓰기)."
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
        "아래 최근 IT/AI 뉴스 제목을 참고해, 네이버·구글 검색 수요가 있을 'how-to/가이드' 글 주제 %d개를 제안한다.\n"
        "- 초보가 실제로 검색할 실용 주제: 설치·사용법·세팅·입문·비교·문제해결. '~하는 법/~시작하기/~설치/~설정/~비교' 형태.\n"
        "- AI·개발·IT·툴/제품 범위만. 비기술(동물·정치 등) 제외.\n"
        "- 이미 다룬 주제 제외: %s\n"
        "- 서로 겹치지 않게, 검색량 있을 법한 구체 키워드로.\n\n"
        "topics 배열(문자열)로만 반환.\n\n[최근 뉴스]\n%s"
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
