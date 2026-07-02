// 기사 Q&A 프록시 (Cloudflare Worker)
// 브라우저 → 이 Worker → Gemini. GEMINI_API_KEY는 Worker Secret에 보관(클라이언트 노출 X).
// 배포: ask-worker/README.md 참고. Secret 이름: GEMINI_API_KEY

const ALLOW = [
  "https://ihan0316.github.io",
  "http://localhost:8753",
];
const MODEL = "gemini-2.5-flash";

function cors(origin) {
  const allow = ALLOW.includes(origin) ? origin : ALLOW[0];
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}
function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status, headers: { ...headers, "Content-Type": "application/json; charset=utf-8" },
  });
}

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const h = cors(origin);
    if (req.method === "OPTIONS") return new Response(null, { headers: h });
    if (req.method !== "POST") return json({ error: "POST only" }, 405, h);
    if (!env.GEMINI_API_KEY) return json({ error: "server not configured" }, 500, h);

    let body;
    try { body = await req.json(); } catch { return json({ error: "bad json" }, 400, h); }
    if (!body || typeof body !== "object") return json({ error: "bad json" }, 400, h);
    const q = String(body.question || "").slice(0, 500).trim();
    const title = String(body.title || "").slice(0, 200);
    const ctx = String(body.context || "").slice(0, 8000);
    const sel = String(body.selection || "").slice(0, 500);
    const hist = Array.isArray(body.history) ? body.history.slice(-4) : [];
    const histText = hist
      .map(function (t) { return "Q: " + String(t.q || "").slice(0, 300) + "\nA: " + String(t.a || "").slice(0, 500); })
      .join("\n");
    if (!q) return json({ error: "empty question" }, 400, h);

    const prompt =
      "너는 아래 '기사 본문'을 읽는 독자를 돕는 도우미다. 규칙:\n" +
      "- 질문이 기사 주제·내용과 조금이라도 관련되면, 기사 본문에 근거해 한국어로 친절히 답한다. 기사 속 용어·개념·문장을 쉽게 풀어 설명하는 것도 적극 돕는다.\n" +
      "- 이전 대화의 지시어('그것/그게/이건' 등)는 기사·대화 맥락으로 해석해서 답한다.\n" +
      "- 답이 애매하거나 확실치 않아도 일단 기사 내용으로 최대한 설명한다. 함부로 거절하지 않는다.\n" +
      "- 단, 기사와 '명백히 무관한' 요청(코드 작성, 전혀 다른 주제, 일반 잡담, 번역/창작 대행 등)일 때만 정확히 이 문장만 출력한다: 이 기사 내용에 대한 질문만 답할 수 있어요.\n" +
      "- 기사에 없는 사실을 지어내지 말 것. 3~5문장으로 간결히.\n\n" +
      (sel ? ("[사용자가 선택한 부분]\n" + sel + "\n\n") : "") +
      "[기사 제목]\n" + title + "\n\n[기사 본문]\n" + ctx + "\n\n" +
      (histText ? ("[이전 대화]\n" + histText + "\n\n") : "") +
      "[질문]\n" + q;

    let r;
    try {
      r = await fetch(
        "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent?key=" + env.GEMINI_API_KEY,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: { temperature: 0.4, maxOutputTokens: 1024, thinkingConfig: { thinkingBudget: 0 } },
          }),
        }
      );
    } catch (e) {
      return json({ error: "upstream fetch failed" }, 502, h);
    }
    if (!r.ok) {
      // 무료 한도 초과 등 → 과금이 아니라 차단(429). 사용자에겐 안내만.
      return json({ error: "gemini " + r.status, answer: r.status === 429 ? "오늘 질문 한도를 다 썼어요. 잠시 후 다시 시도해 주세요." : "답변 생성에 실패했어요." }, 200, h);
    }
    const j = await r.json();
    const text = j && j.candidates && j.candidates[0] && j.candidates[0].content &&
      j.candidates[0].content.parts && j.candidates[0].content.parts[0] &&
      j.candidates[0].content.parts[0].text;
    return json({ answer: text || "답변을 생성하지 못했어요." }, 200, h);
  },
};
