# -*- coding: utf-8 -*-
"""기존 day JSON에 블로그 코멘트(comment_kr)를 채운다. GEMINI_API_KEY 필요.

comment_kr = 복사 시에만 들어가는 1인칭 블로그 코멘트(사이트 화면엔 미표시).
매일 새 글은 pipeline_gemini.py가 자동 생성하므로, 이 스크립트는 과거분 백필용.

사용:
  python backfill_comments.py 2026-07-03      # 특정 날짜
  python backfill_comments.py all             # comment_kr 비어있는 모든 날짜
  python backfill_comments.py all --force     # 이미 있어도 재생성
반영:
  python build_site.py
"""
import io, os, sys, json, glob

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pipeline_gemini import gen_comments   # 동일 페르소나/스키마 재사용

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = os.path.join(HERE, "data", "days")


def apply(path, force=False):
    d = json.load(io.open(path, encoding="utf-8"))
    news = d.get("news", [])
    if not news:
        return False
    if not force and all(n.get("comment_kr") for n in news):
        return False
    gen_comments(news)   # news 각 항목에 comment_kr 채움
    json.dump(d, io.open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return True


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        print("usage: python backfill_comments.py <date|all> [--force]"); return
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        print("GEMINI_API_KEY 없음 — 키 설정 후 실행"); return
    if args[0] == "all":
        paths = sorted(glob.glob(os.path.join(DAYS, "*.json")))
    else:
        paths = [os.path.join(DAYS, args[0] + ".json")]
    n = 0
    for p in paths:
        if not os.path.exists(p):
            print("없음:", p); continue
        if apply(p, force):
            n += 1; print("코멘트 채움:", os.path.basename(p))
    print("완료:", n, "일 · 반영하려면 python build_site.py")


if __name__ == "__main__":
    main()
