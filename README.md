# 주간 AI 뉴스 손그림 다이제스트 (MVP)

이미지(손그림/필기체 스타일)처럼 **이번 주 AI 뉴스 3가지 + 실전 영어 표현 + 개발자 은어**를
한 장짜리 정적 사이트로 자동 생성한다.

## 구조

```
ai-weekly-news/
├─ build.py              # digest.json → dist/index.html 생성기 (손그림 스타일)
├─ data/
│  ├─ digest.json        # 이번 주 실제 뉴스 데이터 (워크플로우 산출물)
│  └─ sample_digest.json # 참고용 샘플(원본 이미지 내용)
├─ dist/
│  └─ index.html         # 최종 사이트 (자체 포함, 브라우저로 바로 열림)
└─ README.md
```

## 파이프라인 (주 1회)

```
[1] 뉴스 수집·큐레이션 (Claude 워크플로우)
      └ 5각 병렬 웹검색(model/bigtech/agents/research/business) → 상위 3개 선별 + 한글 다이제스트 작성
      └ 산출: data/digest.json (스키마 고정)
[2] 사이트 빌드
      └ python build.py data/digest.json dist/index.html
[3] 게시
      └ GitHub Pages / Netlify / 사내 정적호스팅에 dist/ 올림
```

## 수동 실행

```powershell
# 데이터가 있으면 빌드만:
python build.py data/digest.json dist/index.html

# 결과 열기:
start dist/index.html
```

## 손그림 스타일 구현

- **폰트**: Gaegu·Nanum Pen Script(한글 필기체), Patrick Hand(영문) — Google Fonts
- **테두리**: rough.js 로 패널마다 손으로 그린 듯한 사각형 동적 렌더
- **두들**: 인라인 SVG(로봇·폰·구름·전구·동전 등) + 약한 turbulence 흔들림 필터
- **배경**: 노트 줄·스프링 제본·포스트잇 날짜 메모

## 데이터 스키마 (digest.json)

`news[3]`(제목/날짜/말풍선/체크리스트/별요약/출처url) · `english_expressions[10]` ·
`dev_slang[5]` · `mini_practice` · `summary_kr[3]` · `memo`.
자세한 형태는 `data/sample_digest.json` 참고.

## 주간 자동화 (다음 단계)

- **A안 (추천)**: Claude 예약 작업(routine)으로 매주 월요일 워크플로우 실행 →
  digest.json 갱신 → build.py → GitHub Pages 푸시. 사람 개입 0.
- **B안**: 워크플로우만 자동, 게시 전 사람이 사실확인(아래 주의 참고) 후 수동 푸시.

## ⚠ 콘텐츠 정확도 주의

뉴스 본문은 LLM 웹검색 자동 수집물이다. **게시 전 출처 링크로 사실 확인 권장**
(특히 인수·금액 등 큰 숫자). 자동 파이프라인이라도 1차 게시 단계에 사람 검수 1회를 넣는 것이 안전.
