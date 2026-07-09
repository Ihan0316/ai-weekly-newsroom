# -*- coding: utf-8 -*-
"""
한 달치 일자별 day JSON 조립기.
입력:
  data/_scraped.json  = {"items":[{title_kr,source,url,date,blurb_kr}, ...]}
  data/_bank.json     = {"quizzes":[...31...], "termsets":[[...3...] x31]}
출력:
  data/days/<YYYY-MM-DD>.json  (기존 day 파일은 모두 교체)

규칙:
- 최근 31일(오늘=END_DATE 포함) 범위.
- 기사: 실제 날짜로 버킷(날짜당 최대 3). 날짜 없거나 범위 밖이면 풀(pool)로.
- 비어있는 날은 풀에서 라운드로빈으로 채움(날짜당 최대 2). 그래도 0이면 그 날은 생성 안 함.
- 각 생성일에 quiz/terms 뱅크를 인덱스로 배정.
"""
import json, os, glob, sys, hashlib
from datetime import date, timedelta

END_DATE = date(2026, 6, 24)
DAYS = 31
WD = ["월", "화", "수", "목", "금", "토", "일"]
HERE = os.path.dirname(os.path.abspath(__file__))

def load(p):
    with open(os.path.join(HERE, p), "r", encoding="utf-8") as f:
        return json.load(f)

def date_label(d):
    return f"{d.year}. {d.month}. {d.day}"

def parse_date(s):
    s = (s or "").strip().replace(".", "-").replace("/", "-")
    parts = [p for p in s.split("-") if p.strip()]
    try:
        if len(parts) >= 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass
    return None

def clean_item(it):
    return {
        "title_kr": it.get("title_kr", "").strip(),
        "source": it.get("source", "").strip(),
        "url": it.get("url", "").strip(),
        "blurb_kr": it.get("blurb_kr", "").strip(),
    }

def main():
    scraped = load(os.path.join("data", "_scraped.json")).get("items", [])
    bank = load(os.path.join("data", "_bank.json"))
    quizzes = bank.get("quizzes", [])
    termsets = bank.get("termsets", [])
    if not quizzes or not termsets:
        print("bank 비어있음 — 중단"); return

    dates = [END_DATE - timedelta(days=i) for i in range(DAYS)]  # 최신→과거
    dateset = set(dates)
    buckets = {d: [] for d in dates}
    pool = []

    # 1) 실제 날짜로 버킷
    seen_titles = set()
    for raw in scraped:
        it = clean_item(raw)
        if not it["title_kr"] or it["title_kr"] in seen_titles:
            continue
        seen_titles.add(it["title_kr"])
        d = parse_date(raw.get("date", ""))
        if d in dateset and len(buckets[d]) < 3:
            buckets[d].append(it)
        else:
            pool.append(it)

    # 2) 빈 날을 풀에서 라운드로빈으로 채움(최대 2)
    pi = 0
    for _ in range(2):
        for d in dates:
            if pi >= len(pool):
                break
            if len(buckets[d]) == 0:  # 아직 빈 날 우선
                buckets[d].append(pool[pi]); pi += 1
    # 남은 풀을 1건 미만인 날 추가 채움(최대 2)
    for d in dates:
        while pi < len(pool) and len(buckets[d]) < 2:
            buckets[d].append(pool[pi]); pi += 1

    # 3) 뉴스 있는 날만, 최신순으로 생성. quiz/terms 인덱스 배정.
    built = [d for d in dates if buckets[d]]
    built.sort(reverse=True)

    # 기존 day 파일 제거 — 파괴적. 이미 발행된 날(창 밖)의 content/comment_kr 유실 +
    # 퀴즈/용어 재셔플 위험이 있어 --force 없이는 중단 (운영 중 재실행 금지).
    days_dir = os.path.join(HERE, "data", "days")
    os.makedirs(days_dir, exist_ok=True)
    existing = glob.glob(os.path.join(days_dir, "*.json"))
    if existing and "--force" not in sys.argv:
        print(f"중단: data/days 에 {len(existing)}개 파일 존재. 이 스크립트는 전량 삭제 후 "
              f"{END_DATE} 기준 {DAYS}일 창만 재생성하므로 창 밖 날짜의 본문/코멘트가 유실됩니다.\n"
              f"정말 초기화하려면 --force 로 실행하세요.")
        return
    for f in existing:
        os.remove(f)

    for i, d in enumerate(built):
        # 위치 인덱스(i) 대신 날짜 결정적 배정 → 재실행/목록변동에도 같은 날은 같은 퀴즈/용어
        qi = int(hashlib.md5(d.isoformat().encode("utf-8")).hexdigest(), 16)
        rec = {
            "date_label": date_label(d),
            "weekday": WD[d.weekday()],
            "news": buckets[d][:3],
            "quiz": quizzes[qi % len(quizzes)],
            "terms": termsets[qi % len(termsets)],
        }
        out = os.path.join(days_dir, d.isoformat() + ".json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)

    print(f"assembled {len(built)} days (scraped={len(scraped)}, pool_used={pi})")
    print("dates:", ", ".join(d.isoformat() for d in built))

if __name__ == "__main__":
    main()
