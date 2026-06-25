# -*- coding: utf-8 -*-
"""
각 뉴스 기사의 대표 이미지(og:image 등) 추출 → docs/images/<urlhash>.<ext> 저장.
- 핫링크 깨짐 방지 위해 로컬 저장.
- build_site가 url 해시로 매칭해 모달/리스트에 연결.
- 이미 있으면 건너뜀(증분). 실패는 조용히 스킵.

usage: python fetch_images.py
"""
import json, glob, os, re, hashlib
from urllib.request import Request, urlopen
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "images")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
EXT = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif"}

def get(url, maxbytes):
    req = Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urlopen(req, timeout=15) as r:
        return r.read(maxbytes), r.headers.get("Content-Type", ""), r.geturl()

def find_og(html, base):
    pats = [
        r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]
    for p in pats:
        m = re.search(p, html, re.I)
        if m:
            return urljoin(base, m.group(1).strip())
    # fallback: 첫 본문 이미지
    m = re.search(r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
    if m:
        return urljoin(base, m.group(1).strip())
    return None

def collect():
    seen = {}
    for f in glob.glob(os.path.join(HERE, "data", "days", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        for it in d.get("news", []):
            u = (it.get("url") or "").strip()
            if u and u not in seen:
                seen[u] = True
    return list(seen.keys())

def main():
    os.makedirs(OUT, exist_ok=True)
    urls = collect()
    done = skip = fail = 0
    for u in urls:
        h = hashlib.md5(u.encode("utf-8")).hexdigest()[:12]
        if glob.glob(os.path.join(OUT, h + ".*")):
            skip += 1; continue
        try:
            html, _ct, final = get(u, 300000)
            html = html.decode("utf-8", "ignore")
            img = find_og(html, final)
            if not img:
                fail += 1; print("noimg", u[:60]); continue
            data, ct, _ = get(img, 6000000)
            ext = EXT.get(ct.split(";")[0].strip().lower())
            if not ext:
                m = re.search(r'\.(jpg|jpeg|png|webp|gif|avif)(?:\?|$)', img, re.I)
                ext = (m.group(1).lower() if m else "jpg")
                if ext == "jpeg": ext = "jpg"
            if not data or len(data) < 1000:
                fail += 1; print("tiny", u[:60]); continue
            with open(os.path.join(OUT, h + "." + ext), "wb") as fb:
                fb.write(data)
            done += 1
            print(f"ok {h}.{ext} {len(data)//1024}KB  <- {img[:70]}")
        except Exception as e:
            fail += 1; print("FAIL", u[:60], type(e).__name__)
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024 // 1024
    print(f"done. new={done} skip={skip} fail={fail} files={len(os.listdir(OUT))} total={total}MB")

if __name__ == "__main__":
    main()
