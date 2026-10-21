# -*- coding: utf-8 -*-
"""파이프라인·빌드·이미지 단위 테스트 (네트워크·Gemini 호출 없음, 저장소 데이터 미변경).

실행(저장소 루트): python -m unittest discover -s tests -v
"""
import io, json, os, shutil, sys, tempfile, unittest, urllib.error
from unittest import mock

import pipeline_gemini as P
import build_site
import fetch_images as F
import replace_article as R


def http_err(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


class Resp:
    """urlopen 응답 대역(컨텍스트 매니저)."""
    def __init__(self, text):
        self.body = json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]}).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def day(news=1, quiz=True):
    d = {"date_label": "2026. 1. 1", "weekday": "목", "quiz": {}, "terms": [],
         "news": [{"title_kr": "t%d" % i, "source": "GeekNews", "url": "https://n/%d" % i, "blurb_kr": "b"}
                  for i in range(news)]}
    if quiz:
        d["quiz"] = {"category": "c", "question": "q", "options": ["a", "b", "c", "d"], "answer": 0, "explain_kr": "e"}
    return d


class GeminiRetryTest(unittest.TestCase):
    def run_with(self, effects):
        sleeps = []
        with mock.patch.object(P.urllib.request, "urlopen", side_effect=effects), \
                mock.patch.object(P.time, "sleep", side_effect=sleeps.append), \
                mock.patch.object(P.sys, "stderr", io.StringIO()):
            try:
                return P.gemini("p"), sleeps
            except RuntimeError as e:
                return e, sleeps

    def test_5xx_backoff_then_give_up(self):
        out, sleeps = self.run_with([http_err(503)] * 5)
        self.assertIsInstance(out, RuntimeError)
        self.assertEqual(sleeps, [45, 90, 135, 180])   # 마지막 실패 후엔 대기 없음

    def test_429_then_success(self):
        self.assertEqual(self.run_with([http_err(429), Resp('{"ok": 1}')]), ({"ok": 1}, [45]))

    def test_other_errors_short_wait(self):
        self.assertEqual(self.run_with([http_err(400), Resp("not json"), Resp('{"ok": 1}')]), ({"ok": 1}, [6, 6]))


class DaysDirTest(unittest.TestCase):
    """P.DAYS 를 임시 폴더로 바꿔 data/days 를 건드리지 않음."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        for p in (mock.patch.object(P, "DAYS", self.tmp), mock.patch.object(P.sys, "stderr", io.StringIO()),
                  mock.patch("sys.stdout", io.StringIO())):
            p.start(); self.addCleanup(p.stop)

    def put(self, did, rec):
        with open(os.path.join(self.tmp, did + ".json"), "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)

    def get(self, did):
        with open(os.path.join(self.tmp, did + ".json"), encoding="utf-8") as f:
            return json.load(f)


class FillMissingQuizTest(DaysDirTest):
    QT = (day()["quiz"], [{"term": "T", "kind": "IT", "meaning_kr": "m"}])

    def test_newest_first_with_limit_and_skip(self):
        olds = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        for did in olds:
            self.put(did, day(quiz=False))
        self.put("2026-01-05", day(quiz=False))           # skip_id(오늘)
        self.put("2026-01-06", day(news=0, quiz=False))   # 뉴스 없는 날은 대상 아님
        with mock.patch.object(P, "make_quiz_terms", return_value=self.QT):
            self.assertEqual(P.fill_missing_quiz("2026-01-05", limit=3), 3)
        self.assertEqual([d for d in olds if self.get(d)["quiz"]], olds[1:])
        self.assertFalse(self.get("2026-01-05")["quiz"])
        self.assertFalse(self.get("2026-01-06")["quiz"])

    def test_stops_on_first_failure(self):
        self.put("2026-01-01", day(quiz=False)); self.put("2026-01-02", day(quiz=False))
        fake = mock.Mock(side_effect=RuntimeError("gemini failed: 429"))
        with mock.patch.object(P, "make_quiz_terms", fake):
            self.assertEqual(P.fill_missing_quiz("x"), 0)
        self.assertEqual(fake.call_count, 1)


class MainFlowTest(DaysDirTest):
    def run_main(self, quiz_ok):
        mqt = (mock.Mock(return_value=FillMissingQuizTest.QT) if quiz_ok
               else mock.Mock(side_effect=RuntimeError("gemini failed")))
        news = [{"title_kr": "t", "source": "GeekNews", "url": "https://n/new", "blurb_kr": "b"}]
        fill = mock.Mock(return_value=0)
        with mock.patch.multiple(P, KEY="k", select_news=mock.Mock(return_value=news),
                                 extract_body=mock.Mock(return_value=[]), gen_comments=mock.Mock(),
                                 gen_seo=mock.Mock(), make_quiz_terms=mqt, fill_missing_quiz=fill), \
                mock.patch.object(P.subprocess, "run"), \
                mock.patch.dict(os.environ, {"PIPELINE_DATE": "2026-02-01"}):
            P.main()
        return fill, self.get("2026-02-01")

    def test_backfill_after_quiz_success(self):
        fill, rec = self.run_main(quiz_ok=True)
        fill.assert_called_once_with("2026-02-01")
        self.assertTrue(rec["quiz"]["question"])

    def test_no_backfill_when_quiz_fails_but_news_kept(self):
        fill, rec = self.run_main(quiz_ok=False)
        fill.assert_not_called()
        self.assertEqual((len(rec["news"]), rec["quiz"]), (1, {}))


class ReplaceArticleTest(DaysDirTest):
    def test_keeps_seo_and_comment_fields(self):
        self.put("2026-01-01", day(news=2))
        cand = {"source": "TechCrunch", "url": "https://tc/x", "date": "", "title": "T", "snippet": "s", "body_html": ""}

        def seo(news):
            for it in news:
                it.update(title_blog="TB", tags_kr=["태그"], hook_kr="HK")

        def cmt(news):
            for it in news:
                it["comment_kr"] = "C"

        with mock.patch.multiple(P, KEY="k", gather_candidates=mock.Mock(return_value=[cand]),
                                 gemini=mock.Mock(return_value={"items": [{"title_kr": "새", "source": "?", "url": "https://tc/x", "blurb_kr": "b"}]}),
                                 extract_body=mock.Mock(return_value=[]), gen_comments=cmt, gen_seo=seo), \
                mock.patch.object(sys, "argv", ["replace_article.py", "2026-01-01", "--index", "1", "--no-build"]):
            R.main()
        it = self.get("2026-01-01")["news"][1]
        self.assertEqual((it["url"], it["source"], it["comment_kr"], it["title_blog"], it["tags_kr"], it["hook_kr"]),
                         ("https://tc/x", "TechCrunch", "C", "TB", ["태그"], "HK"))


class CleanBlocksTest(unittest.TestCase):
    def test_rejects_failure_excuse(self):
        self.assertEqual(P.clean_blocks([{"t": "p", "text": "제공된 HTML에는 기사 본문이 포함되어 있지 않습니다."}]), [])

    def test_rejects_headings_only(self):
        self.assertEqual(P.clean_blocks([{"t": "h", "text": "a"}, {"t": "h", "text": "b"}]), [])

    def test_drops_dangling_headings(self):
        b = [{"t": "h", "text": "h1"}, {"t": "h", "text": "h2"}, {"t": "p", "text": "x" * 50}, {"t": "h", "text": "tail"}]
        self.assertEqual(P.clean_blocks(b), [{"t": "h", "text": "h2"}, {"t": "p", "text": "x" * 50}])


class ValidateDayTest(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(build_site.validate_day(day()))

    def test_missing_quiz_is_skipped(self):
        self.assertIsNotNone(build_site.validate_day(day(quiz=False)))

    def test_answer_out_of_range(self):
        d = day(); d["quiz"]["answer"] = 4
        self.assertIsNotNone(build_site.validate_day(d))


@unittest.skipUnless(F.Image, "Pillow 미설치")
class ImageOptimizeTest(unittest.TestCase):
    @staticmethod
    def encode(w, h, fmt="PNG", mode="RGB", **kw):
        im = F.Image.frombytes("RGB", (w, h), os.urandom(w * h * 3)).convert(mode)   # 노이즈 = 압축 안 되는 사진형
        b = io.BytesIO(); im.save(b, fmt, **kw); return b.getvalue()

    def test_wide_images_resized_to_1200_jpeg(self):
        for data, ext in ((self.encode(2400, 1200), "png"), (self.encode(2400, 1200, "JPEG"), "jpg")):
            out, out_ext = F.optimize(data, ext)
            self.assertEqual((out_ext, F.Image.open(io.BytesIO(out)).size), ("jpg", (1200, 600)))

    def test_opaque_rgba_png_to_jpeg(self):
        self.assertEqual(F.optimize(self.encode(800, 600, mode="RGBA"), "png")[1], "jpg")

    def test_small_or_narrow_jpeg_untouched(self):
        for data, ext in ((self.encode(300, 200), "png"), (self.encode(1200, 800, "JPEG", quality=95), "jpg")):
            out, out_ext = F.optimize(data, ext)
            self.assertIs(out, data); self.assertEqual(out_ext, ext)

    def test_keeps_icc_profile(self):   # Display P3 등 색공간 유지(프로필 유실 시 색 틀어짐)
        from PIL import ImageCms
        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        out, ext = F.optimize(self.encode(2400, 1200, icc_profile=icc), "png")
        self.assertEqual((ext, F.Image.open(io.BytesIO(out)).info.get("icc_profile")), ("jpg", icc))

    def test_skips_16bit_grayscale(self):   # RGB 변환 시 값이 255로 잘려 하얗게 됨
        im = F.Image.frombytes("I;16", (2000, 1000), os.urandom(2000 * 1000 * 2))
        b = io.BytesIO(); im.save(b, "PNG"); data = b.getvalue()
        out, ext = F.optimize(data, "png")
        self.assertEqual((out is data, ext), (True, "png"))

    def test_keeps_color_key_transparency(self):   # tRNS 지정색 투명 PNG → JPEG 로 바뀌면 투명 유실
        im = F.Image.frombytes("RGB", (2000, 1000), os.urandom(2000 * 1000 * 3))
        im.paste((255, 255, 255), (0, 0, 500, 500))
        b = io.BytesIO(); im.save(b, "PNG", transparency=(255, 255, 255))
        out, ext = F.optimize(b.getvalue(), "png")
        o = F.Image.open(io.BytesIO(out))
        self.assertEqual((ext, o.mode, o.getpixel((10, 10))[3]), ("png", "RGBA", 0))

    def test_without_pillow_passthrough(self):
        data = self.encode(2400, 1200)
        with mock.patch.object(F, "Image", None):
            self.assertEqual(F.optimize(data, "png"), (data, "png"))

    def test_existing_renamed_once_then_idempotent(self):
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp)
        with open(os.path.join(tmp, "abc123.png"), "wb") as f:
            f.write(self.encode(2400, 1200))
        with mock.patch.object(F, "OUT", tmp):
            self.assertEqual(F.optimize_existing()[0], 1)
            self.assertEqual(os.listdir(tmp), ["abc123.jpg"])
            self.assertEqual(F.optimize_existing(), (0, 0))


if __name__ == "__main__":
    unittest.main()
