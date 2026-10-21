# -*- coding: utf-8 -*-
"""
각 뉴스 기사의 대표 이미지(og:image 등) 추출 → docs/images/<urlhash>.<ext> 저장.
- 핫링크 깨짐 방지 위해 로컬 저장.
- build_site가 url 해시로 매칭해 모달/리스트에 연결.
- 이미 있으면 건너뜀(증분). 실패는 조용히 스킵.

usage: python fetch_images.py
"""
import json, glob, os, re, hashlib, io
from urllib.request import Request, urlopen
from urllib.parse import urljoin
try:
    from PIL import Image, ImageOps   # 선택 의존성(requirements.txt): 없으면 최적화 없이 원본 저장
except ImportError:
    Image = None

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "docs", "images")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
MAX_W = 1200        # 표시 최대폭(모달 720px·피처드 카드)의 레티나 대비 여유
PNG_MAX = 300000    # 이보다 큰 불투명 PNG는 JPEG로 변환 (사진형 PNG가 용량 대부분)
EXT = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "image/avif": "avif"}

def sniff_ext(data):
    """매직 바이트로 실제 이미지 포맷 판별. 이미지 아니면 None (HTML 오류페이지 저장 방지)."""
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:12] in (b"ftypavif", b"ftypavis") or data[4:8] == b"ftyp" and b"avif" in data[8:20]:
        return "avif"
    return None

def optimize(data, ext):
    """큰 이미지 축소·재인코딩 → (bytes, ext). 폭 > MAX_W 이거나 큰 불투명 PNG일 때만 처리, 더 작아질 때만 교체.
    폭 ≤ MAX_W 인 JPEG/WebP는 손대지 않음 → 매일 재실행돼도 손실 재압축이 반복되지 않음."""
    if Image is None or ext in ("gif", "avif"):
        return data, ext
    try:
        im = Image.open(io.BytesIO(data))
        if getattr(im, "is_animated", False):
            return data, ext
        alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        if alpha and (im.width > MAX_W or (ext == "png" and len(data) > PNG_MAX)):
            alpha = im.convert("RGBA").getchannel("A").getextrema()[0] < 255   # 알파 채널이 전부 불투명이면 JPEG 가능
        big_png =ext == "png" and not alpha and len(data) > PNG_MAX
        if im.width <= MAX_W and not big_png:
            return data, ext
        im = ImageOps.exif_transpose(im).convert("RGBA" if alpha else "RGB")
        if im.width > MAX_W:
            im = im.resize((MAX_W, max(1, round(im.height * MAX_W / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        if alpha:
            im.save(buf, "PNG", optimize=True); out = "png"
        else:
            im.save(buf, "JPEG", quality=82, optimize=True, progressive=True); out = "jpg"
        if buf.tell() < len(data):
            return buf.getvalue(), out
    except Exception:
        pass
    return data, ext

def optimize_existing():
    """기존 저장분 중 큰 이미지 최적화(첫 실행에 일괄 적용, 이후엔 대상 거의 없음). 확장자가 바뀌면 원본 삭제
    → 같은 실행의 build_site 가 새 파일명으로 연결. 반환: (처리 수, 절감 바이트)."""
    if Image is None:
        return 0, 0
    n = saved = 0
    for fn in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, fn)
        if not os.path.isfile(p):
            continue
        h, _, ext = fn.partition(".")
        with open(p, "rb") as fb:
            data = fb.read()
        new, new_ext = optimize(data, ext)
        if new is data:
            continue
        with open(os.path.join(OUT, h + "." + new_ext), "wb") as fb:
            fb.write(new)
        if new_ext != ext:
            os.remove(p)
        n += 1; saved += len(data) - len(new)
    return n, saved

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
            if not data or len(data) < 1000:
                fail += 1; print("tiny", u[:60]); continue
            # 매직바이트 우선(신뢰), 없으면 Content-Type. 둘 다 이미지 아니면 버림
            # (증분 스킵 때문에 손상/HTML 파일이 저장되면 영구 고착되므로 저장 전 차단).
            ext = sniff_ext(data) or EXT.get(ct.split(";")[0].strip().lower())
            if not ext:
                fail += 1; print("notimg", u[:60], ct[:30]); continue
            data, ext = optimize(data, ext)
            with open(os.path.join(OUT, h + "." + ext), "wb") as fb:
                fb.write(data)
            done += 1
            print(f"ok {h}.{ext} {len(data)//1024}KB  <- {img[:70]}")
        except Exception as e:
            fail += 1; print("FAIL", u[:60], type(e).__name__)
    on, saved = optimize_existing()
    if on:
        print(f"optimized existing={on} saved={saved//1024}KB")
    total = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024 // 1024
    print(f"done. new={done} skip={skip} fail={fail} files={len(os.listdir(OUT))} total={total}MB")

if __name__ == "__main__":
    main()
