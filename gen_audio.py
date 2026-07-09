# -*- coding: utf-8 -*-
"""
뉴스 본문 TTS(뉴럴) MP3 생성. Microsoft Edge 뉴럴 보이스(edge-tts, 무료/키 불필요).
- data/days/*.json 의 각 뉴스 본문(title + content) → docs/audio/<urlhash>.mp3
- 매니페스트 data/_audio.json {url: hash} 작성 (build_site가 모달에 연결)
- 이미 있는 mp3는 건너뜀(증분).

usage: python gen_audio.py
"""
import json, glob, os, hashlib, asyncio, sys
import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE = "ko-KR-SunHiNeural"
OUT = os.path.join(HERE, "docs", "audio")

def text_of(item):
    parts = [item.get("title_kr", "")]
    for b in item.get("content", []) or []:
        t = b.get("text")
        if t:
            parts.append(t)
    if len(parts) <= 1 and item.get("blurb_kr"):
        parts.append(item["blurb_kr"])
    return ".\n".join(p for p in parts if p and p.strip())

def collect():
    seen = {}
    for f in glob.glob(os.path.join(HERE, "data", "days", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for it in d.get("news", []):
            u = (it.get("url") or "").strip()
            if not u or u in seen:
                continue
            seen[u] = text_of(it)
    return seen

async def synth(text, path):
    # 임시 파일에 쓰고 성공 시에만 원자적 교체 → 네트워크 중단으로 잘린 mp3가
    # 최종 경로에 남아 증분 스킵으로 영구 고착되는 것 방지.
    tmp = path + ".part"
    try:
        c = edge_tts.Communicate(text, VOICE)
        await c.save(tmp)
        if os.path.getsize(tmp) < 1024:   # 정상 mp3면 최소 수 KB
            raise RuntimeError("출력 too small (%dB)" % os.path.getsize(tmp))
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def main():
    os.makedirs(OUT, exist_ok=True)
    seen = collect()
    manifest, todo = {}, []
    for u, text in seen.items():
        if not text.strip():
            continue
        h = hashlib.md5(u.encode("utf-8")).hexdigest()[:12]
        manifest[u] = h
        path = os.path.join(OUT, h + ".mp3")
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            todo.append((u, text, path))
    print(f"total={len(manifest)} todo={len(todo)}", flush=True)

    async def run():
        done = 0
        for u, text, path in todo:
            try:
                await synth(text, path)
                done += 1
                print(f"[{done}/{len(todo)}] {os.path.basename(path)} {os.path.getsize(path)}B", flush=True)
            except Exception as e:
                print(f"FAIL {os.path.basename(path)} {e}", flush=True)
    asyncio.run(run())

    json.dump(manifest, open(os.path.join(HERE, "data", "_audio.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    total_bytes = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT) if f.endswith(".mp3"))
    print(f"done. files={len([f for f in os.listdir(OUT) if f.endswith('.mp3')])} total={total_bytes//1024//1024}MB", flush=True)

if __name__ == "__main__":
    main()
