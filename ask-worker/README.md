# 기사 Q&A 프록시 배포 (Cloudflare Workers · 무료)

모달의 "질문" 기능이 이 Worker를 통해 Gemini를 호출한다. **API 키는 Worker Secret에만** 두므로 사이트(공개 정적)엔 노출되지 않는다.

## 배포 (대시보드, 5분)
1. https://dash.cloudflare.com → **Workers & Pages** → **Create** → **Create Worker**
2. 이름 예: `ask-news` → Deploy (기본 코드 생성됨)
3. **Edit code** → 기본 코드 전부 지우고 [`worker.js`](./worker.js) 내용 붙여넣기 → **Deploy**
4. Worker 화면 → **Settings → Variables and Secrets** → **Add**
   - Type: **Secret**, Name: `GEMINI_API_KEY`, Value: (AI Studio 무료 키) → Save
5. 배포 URL 복사: `https://ask-news.<계정>.workers.dev`
6. 그 URL을 알려주면 사이트에 연결(`ASK_ENDPOINT`)하고 재빌드 → 질문 기능 켜짐.

## (선택) 남용 방지 — 무료 Rate Limit
Worker → **Settings → 보안/Rate limiting** 규칙 1개(무료): 예) IP당 1분 20회 초과 차단.
무료 티어는 한도 초과 시 **과금이 아니라 차단**이라 비용 위험은 사실상 없음. 레이트리밋은 한도 빨리 소진되는 것만 막는 용도.

## CORS
`worker.js`의 `ALLOW` 목록에 사이트 origin이 있어야 함:
- `https://ihan0316.github.io` (운영)
- `http://localhost:8753` (로컬 테스트)
다른 도메인 추가 시 목록에 넣고 재배포.

## 비용
- Gemini 무료티어(2.5 Flash, 일 1,500회) + Cloudflare Workers(일 10만 요청) = **$0**.
- 데일리 파이프라인과 Gemini 무료 쿼터를 공유(파이프라인 ~10회/일이라 여유).
