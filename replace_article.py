# -*- coding: utf-8 -*-
"""day JSON의 특정 뉴스 1건을 새로운 기술 기사로 교체. GEMINI_API_KEY 필요.

비기술/부적절 픽이 들어갔을 때 그 항목만 교체(나머지 뉴스·이미 발행분은 보존).
새 기사는 FEEDS 후보 중 TOPIC_RULE(기술) 통과 + 전 기간 기수록 URL 제외 + 나머지와 주제 비중복.
반영: fetch_images.py + build_site.py 자동 실행(--no-build 로 생략). 커밋은 워크플로우/사용자.

사용:
  python replace_article.py 2026-07-16 --match 원숭이     # 제목에 '원숭이' 포함 항목 교체
  python replace_article.py 2026-07-16 --index 2          # 3번째(0부터) 항목 교체
"""
import os, sys, io, json, argparse, subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pipeline_gemini as P


def load_day(date):
    p = os.path.join(P.DAYS, date + ".json")
    if not os.path.exists(p):
        raise SystemExit("없음: " + p)
    return p, json.load(io.open(p, encoding="utf-8"))


def find_index(news, match, index):
    if index is not None:
        if 0 <= index < len(news):
            return index
        raise SystemExit("index 범위 밖: %d (뉴스 %d건)" % (index, len(news)))
    if match:
        for i, it in enumerate(news):
            if match in (it.get("title_kr") or ""):
                return i
        raise SystemExit("'%s' 포함 뉴스 없음" % match)
    raise SystemExit("--match 또는 --index 중 하나 필요")


def pick_replacement(date, ex_urls, keep_titles):
    cands = P.gather_candidates(date, ex_urls)
    if not cands:
        raise SystemExit("교체 후보 0건 (피드 실패 또는 전부 기수록)")
    by_url = {c["url"]: c for c in cands}
    prompt = (
        "아래 후보 기사 중 '기술 기사' 딱 1건을 고른다.\n"
        "규칙:\n"
        "- %s\n"
        "- 이미 실린 다음 글들과 주제가 겹치지 않을 것: %s\n"
        "- url 은 후보에 적힌 것을 글자 그대로 복사(변형 금지).\n"
        "items 배열에 1건만: title_kr(한국어 제목), source, url, blurb_kr(한 줄 요약, 한국어).\n\n"
        "[후보]\n%s\n"
    ) % (P.TOPIC_RULE, " / ".join(t for t in keep_titles if t), "\n".join(P.cand_lines(cands)))
    out = P.gemini(prompt, P.NEWS_SCHEMA, max_tokens=1024)
    for it in out.get("items", []):
        u = (it.get("url") or "").strip()
        c = by_url.get(u)
        if c is None:
            sys.stderr.write("skip non-candidate url: %s\n" % u[:80]); continue
        it["url"] = u; it["source"] = c["source"]
        return it
    raise SystemExit("유효한 교체 기사를 못 골랐다(후보 밖 URL만 반환)")


def main():
    ap = argparse.ArgumentParser(description="day JSON 뉴스 1건 교체")
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("--match", help="교체할 뉴스 제목 부분문자열")
    ap.add_argument("--index", type=int, help="교체할 뉴스 인덱스(0부터)")
    ap.add_argument("--no-build", action="store_true", help="fetch_images/build_site 생략")
    a = ap.parse_args()
    if not P.KEY:
        sys.stderr.write("GEMINI_API_KEY 없음 — 키 설정 후 실행\n"); sys.exit(1)

    path, d = load_day(a.date)
    news = d.get("news", [])
    idx = find_index(news, a.match, a.index)
    print("교체 대상[%d]: [%s] %s" % (idx, news[idx].get("source", ""), (news[idx].get("title_kr") or "")[:50]))

    ex_urls, _, _, _ = P.existing()          # 전 기간 기수록 URL → 중복 방지
    # 같은 날 유지 뉴스 + 최근 게재 제목 → 주제 겹치는 후보 배제
    avoid = [it.get("title_kr", "") for i, it in enumerate(news) if i != idx] + P.recent_titles()
    new_it = pick_replacement(a.date, ex_urls, avoid)
    print("새 기사: [%s] %s" % (new_it["source"], (new_it.get("title_kr") or "")[:50]))

    new_it["content"] = P.extract_body(new_it["url"])
    P.gen_comments([new_it])
    news[idx] = {
        "title_kr": new_it["title_kr"], "source": new_it["source"], "url": new_it["url"],
        "blurb_kr": new_it.get("blurb_kr", ""), "content": new_it.get("content", []),
        "comment_kr": new_it.get("comment_kr", ""),
    }
    json.dump(d, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("교체 완료 →", path, "| 본문", len(news[idx]["content"]), "블록 | 코멘트",
          "O" if news[idx]["comment_kr"] else "X")

    if not a.no_build:
        print("== run fetch_images.py ==")
        subprocess.run([sys.executable, os.path.join(P.HERE, "fetch_images.py")])
        print("== run build_site.py ==")
        subprocess.run([sys.executable, os.path.join(P.HERE, "build_site.py")], check=True)


if __name__ == "__main__":
    main()
