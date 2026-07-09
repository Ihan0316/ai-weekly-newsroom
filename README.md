# 데일리 다이제스트 (Daily Digest)

매일 **오늘의 뉴스 + 기초상식(정처기 문제) + IT·개발·기획 용어**를 미니멀 에디토리얼 + 3D 정적 사이트로.
뉴스는 요즘IT(yozm) · GeekNews(news.hada.io)에서 수집. **PC 없이 매일 자동**으로 갱신·배포된다.

🔗 **라이브: https://ihan0316.github.io/ai-weekly-newsroom/**

## 기능
- **오늘의 뉴스**: 클릭 시 외부 이동 대신 **3D 모달**로 크롤한 원문 표시 + 대표 이미지 + 기사 Q&A
- **기초상식**: 정보처리기사 4지선다 — 보기 클릭 시 정답/오답 즉시 표시
- **IT·개발·기획 용어** 3개/일
- **검색**: 제목·요약·출처 + **본문 전체** 대상, 가중 랭킹 + 매칭 스니펫 (`docs/search.json` 지연 로드)
- **자동 갱신**: 새 빌드 감지 시 강제 새로고침 없이 자동 반영(`build.json` + `<meta site-build>`)
- 데스크톱·모바일 반응형, WCAG AA 대비

## 구조
```
data/days/<YYYY-MM-DD>.json   # 하루치 원천 (news[]/quiz/terms)
build.py                      # render_day(): 하루 상세 HTML
build_site.py                 # 전체 빌드 → docs/ (index 피드 + 날짜별 + search.json + build.json)
assets/site.css, site.js      # 공유 디자인·인터랙션(3D 히어로/틸트/모달/검색/Q&A/자동갱신)
fetch_images.py               # 기사 대표 이미지(og:image) → docs/images (증분)
attach_content.py             # 크롤 본문(_crawled.json) → day json 주입
pipeline_gemini.py            # [무인용] 뉴스선별·본문추출·퀴즈/용어를 Gemini로 + 위 스크립트 호출
naver_export.py               # 최신 day → 네이버 붙여넣기용 텍스트 + docs/naver 복사 페이지
ask-worker/                   # 기사 Q&A용 Cloudflare Worker(Gemini 프록시)
.github/workflows/daily.yml   # 매일 07:23 KST 자동 실행 → 커밋 → Pages 배포
```
주의: `assemble_days.py`는 **초기 한 달 일괄 생성용**. 재실행하면 기존 날짜의 퀴즈/용어가 재셔플되니 **운영 중 실행 금지**(하루 추가는 day json 하나만 넣고 `build_site.py`).

## 자동화 (무인 CI/CD)
```
GitHub Actions (cron 07:23 KST)
 → pipeline_gemini.py: Gemini(무료 2.5 Flash)로 뉴스 3선별·본문추출·퀴즈/용어 생성
 → fetch_images / build_site
 → github-actions[bot] 커밋 → GitHub Pages 자동 배포
```
- 키: repo secret `GEMINI_API_KEY` (무료). 비용 $0 (Gemini 무료티어·Pages 전부 무료).
- 데이터센터 IP 차단(yozm 403) 우회: `r.jina.ai` 리더 프록시 폴백.
- 수동 실행: `gh workflow run "Daily digest"` 또는 Actions 탭.

## 수동 빌드/배포
```powershell
python build_site.py
git add -A; git commit -m "update"; git push   # Pages 자동 재배포(1~2분)
```

## ⚠ 콘텐츠 정확도
뉴스 본문은 자동 수집·요약물이다. 공개 사이트이므로 큰 수치·민감 내용은 원문 확인 권장(모달에 출처 링크 있음).
