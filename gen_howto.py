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


def main():
    topic = " ".join(a for a in sys.argv[1:] if not a.startswith("--")).strip()
    if not topic:
        sys.exit('주제 인자 필요. 예) python gen_howto.py "GPT-5.6 처음 쓰는 법"')
    if not P.KEY:
        sys.stderr.write("GEMINI_API_KEY 없음 — 키 설정 후 실행\n"); sys.exit(1)

    out = P.gemini(PERSONA + "\n\n주제: %s\n" % topic, SCHEMA, max_tokens=4096, temp=0.7)
    content = [{"t": ("h" if b.get("t") == "h" else "p"), "text": (b.get("text") or "").strip()}
               for b in out.get("content", []) if (b.get("text") or "").strip()]
    if len(content) < 4:
        sys.exit("본문 블록이 너무 적음(%d) — 주제를 더 구체적으로." % len(content))

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
    print("작성:", path)
    print("제목:", tb)
    print("블록:", len(content), "| 태그:", " ".join("#" + t for t in rec["tags_kr"]))
    print("초안:  python naver_publish.py --howto %s --blog-id aijnj123" % path)


if __name__ == "__main__":
    main()
