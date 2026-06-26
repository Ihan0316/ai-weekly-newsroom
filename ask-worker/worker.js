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
    const q = String(body.question || "").slice(0, 500).trim();
    const title = String(body.title || "").slice(0, 200);
    const ctx = String(body.context || "").slice(0, 8000);
    if (!q) return json({ error: "empty question" }, 400, h);

    const prompt =
      "다음은 한국어 뉴스 기사다. 사용자가 기사를 읽다가 모르는 부분을 물었다. " +
      "기사 맥락을 바탕으로 한국어로 쉽고 간결하게(3~5문장) 답하라. " +
      "기사에 없는 내용은 일반 지식으로 보완하되 '(일반 지식)'처럼 표시하고, 모르면 모른다고 하라.\n\n" +
      "[제목]\n" + title + "\n\n[기사]\n" + ctx + "\n\n[질문]\n" + q;

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
