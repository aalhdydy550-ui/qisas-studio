#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
"""اختبارات توصيل أوامر GuinRank في جولة v0.1.61:
keyword-analyze / content-optimize / keyword-generate /
micro-niche / page-analyze / fresh-keywords / topical-authority.

تعمل بـ `python3 -m unittest tests.test_guinrank_wiring_0161 -v` من
`~/workspace/studio`. بلا شبكة وبلا LLM إطلاقًا — كل المدخلات
ملفات مؤقتة تُبنى هنا.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio

SEVEN_COMMANDS = ("keyword-analyze", "content-optimize",
                  "keyword-generate", "micro-niche", "page-analyze",
                  "fresh-keywords", "topical-authority")


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _write(td, name, text):
    path = os.path.join(td, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _write_json(td, name, payload):
    return _write(td, name, json.dumps(payload, ensure_ascii=False))


def _run_main(argv):
    with mock.patch.object(sys, "argv", argv):
        return _capture(studio.main)


class TestKeywordAnalyzeCmd(unittest.TestCase):
    def test_single_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            metrics = _write_json(td, "m.json", {
                "volume": 39618, "competition": 40, "growth_pct": 92.6})
            rc, out = _run_main(["studio.py", "keyword-analyze",
                                 "--keyword", "قصص واقعية",
                                 "--metrics-json", metrics, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["keyword"], "قصص واقعية")
        self.assertEqual(parsed["difficulty"], 24.0)
        self.assertEqual(parsed["verdict"], "استهدف")

    def test_batch_json_pure(self):
        with tempfile.TemporaryDirectory() as td:
            batch = _write_json(td, "b.json", [
                {"keyword": "قصص", "metrics": {"volume": 483574,
                                               "competition": 59}},
                {"keyword": "قصص اطفال", "metrics": {"volume": 75888,
                                                     "competition": 32}}])
            rc, out = _run_main(["studio.py", "keyword-analyze",
                                 "--keywords-json", batch, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(len(parsed), 2)
        self.assertLess(parsed[0]["difficulty"], parsed[1]["difficulty"])

    def test_neither_input_returns_2(self):
        rc, _out = _run_main(["studio.py", "keyword-analyze", "--json"])
        self.assertEqual(rc, 2)

    def test_both_inputs_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            batch = _write_json(td, "b.json", [
                {"keyword": "قصص", "metrics": {"competition": 59}}])
            rc, _out = _run_main(["studio.py", "keyword-analyze",
                                  "--keyword", "قصص",
                                  "--keywords-json", batch, "--json"])
        self.assertEqual(rc, 2)

    def test_missing_file_returns_2(self):
        rc, _out = _run_main(["studio.py", "keyword-analyze",
                              "--keywords-json", "/no/such/0161.json",
                              "--json"])
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            bad = _write(td, "bad.json", "{ليس json")
            rc, _out = _run_main(["studio.py", "keyword-analyze",
                                  "--keywords-json", bad, "--json"])
        self.assertEqual(rc, 2)


class TestContentOptimizeCmd(unittest.TestCase):
    def _body(self):
        parts = ["العبرة من هذه القصة واضحة.",
                 "قصص واقعية حدثت فعلا."]
        parts.extend(["كلمة"] * 190)
        parts.append("قصص قصص")
        return " ".join(parts)

    def _run(self, td, phrases=None):
        body = _write(td, "body.txt", self._body())
        argv = ["studio.py", "content-optimize",
                "--title", "قصص واقعية مؤثرة من الحياة | قصة حقيقية",
                "--keyword", "قصص",
                "--body-file", body,
                "--description", "قصص واقعية مؤثرة تروى كعبرة من الحياة",
                "--json"]
        if phrases is not None:
            argv[argv.index("--json"):argv.index("--json")] = [
                "--phrases-json", phrases]
        return _run_main(argv)

    def test_healthy_without_phrases(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = self._run(td)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["score"], 65)
        self.assertEqual(parsed["verdict"], "صحي")
        self.assertEqual(parsed["healthy_range"], [55, 75])

    def test_over_75_warns_and_no_add(self):
        with tempfile.TemporaryDirectory() as td:
            phrases = _write_json(td, "p.json", [
                {"phrase": "قصص واقعية", "used_by_top": 15}])
            rc, out = self._run(td, phrases=phrases)
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["score"], 95)
        self.assertEqual(parsed["verdict"], "مبالغ فيه — خطر حشو")
        self.assertIn("لا ترفع", parsed["warning"])
        self.assertNotIn("أضف", json.dumps(parsed["recommendations"],
                                            ensure_ascii=False))

    def test_missing_body_returns_2(self):
        rc, _out = _run_main(["studio.py", "content-optimize",
                              "--title", "قصص واقعية مؤثرة من الحياة",
                              "--keyword", "قصص",
                              "--body-file", "/no/such/0161.txt", "--json"])
        self.assertEqual(rc, 2)

    def test_empty_title_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            body = _write(td, "body.txt", self._body())
            rc, _out = _run_main(["studio.py", "content-optimize",
                                  "--title", "",
                                  "--keyword", "قصص",
                                  "--body-file", body, "--json"])
        self.assertEqual(rc, 2)


class TestKeywordGenerateCmd(unittest.TestCase):
    def test_seed_json_pure(self):
        rc, out = _run_main(["studio.py", "keyword-generate",
                             "--seed", "قصص", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["seed"], "قصص")
        self.assertGreater(parsed["total"], 0)
        self.assertNotIn("قصص", [k["keyword"]
                                 for k in parsed["keywords"]])

    def test_limit_out_of_range_returns_2(self):
        rc, _out = _run_main(["studio.py", "keyword-generate",
                              "--seed", "قصص", "--limit", "101", "--json"])
        self.assertEqual(rc, 2)

    def test_empty_seed_returns_2(self):
        rc, _out = _run_main(["studio.py", "keyword-generate",
                              "--seed", "", "--json"])
        self.assertEqual(rc, 2)


class TestMicroNicheCmd(unittest.TestCase):
    NICHES = [
        {"name": "قصص توبة", "keywords": [
            {"keyword": "قصص توبة", "volume": 5000, "competition": 20}]},
        {"name": "قصص رعب", "keywords": [
            {"keyword": "قصص رعب", "volume": 5000, "competition": 90}]},
    ]

    def test_ranking_and_verdicts(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "n.json", self.NICHES)
            rc, out = _run_main(["studio.py", "micro-niche",
                                 "--niches-json", path, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["niches"][0]["verdict"], "فرصة")
        self.assertEqual(parsed["niches"][1]["verdict"], "مزدحم")

    def test_missing_file_returns_2(self):
        rc, _out = _run_main(["studio.py", "micro-niche",
                              "--niches-json", "/no/such/0161.json",
                              "--json"])
        self.assertEqual(rc, 2)

    def test_empty_list_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "n.json", [])
            rc, _out = _run_main(["studio.py", "micro-niche",
                                  "--niches-json", path, "--json"])
        self.assertEqual(rc, 2)


class TestPageAnalyzeCmd(unittest.TestCase):
    PAGE = {
        "title": "قصص واقعية مؤثرة من الحياة | قصة حقيقية",
        "description": ("هل سمعت قصة رجل تاب؟ قصص واقعية مؤثرة تروى "
                        "كعبرة من الحياة، فيها عبرة لكل من يسمعها. "
                        "تابعنا للجزء الثاني."),
        "tags": ["قصص", "قصص واقعية", "قصة حقيقية", "قصص مؤثرة",
                 "عبرة", "قصص قبل النوم", "حكايات", "قصص قصيرة"],
        "url": "https://www.youtube.com/shorts/4C9LjipW99w",
        "duration": 50,
        "keyword": "قصص",
    }

    def test_good_page_excellent(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "p.json", self.PAGE)
            rc, out = _run_main(["studio.py", "page-analyze",
                                 "--page-json", path, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(parsed["grade"], "ممتاز")
        self.assertGreaterEqual(parsed["score"], 85)
        self.assertIsInstance(parsed["suggestions"], list)

    def test_empty_title_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            bad = dict(self.PAGE)
            bad["title"] = ""
            path = _write_json(td, "p.json", bad)
            rc, _out = _run_main(["studio.py", "page-analyze",
                                  "--page-json", path, "--json"])
        self.assertEqual(rc, 2)

    def test_missing_file_returns_2(self):
        rc, _out = _run_main(["studio.py", "page-analyze",
                              "--page-json", "/no/such/0161.json", "--json"])
        self.assertEqual(rc, 2)


class TestFreshKeywordsCmd(unittest.TestCase):
    TRENDS = [
        {"keyword": "قصص واقعية", "growth_pct": 92.6, "volume": 39618,
         "date": "2026-11-26", "source": "vidIQ"},
        {"keyword": "قصص غموض", "growth_pct": 84.8, "volume": 6739,
         "date": "2026-11-26", "source": "vidIQ"},
        {"keyword": "قصص اطفال", "growth_pct": 10.0, "volume": 75888,
         "date": "2026-11-10", "source": "vidIQ"},
    ]

    def test_fresh_and_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "t.json", self.TRENDS)
            rc, out = _run_main(["studio.py", "fresh-keywords",
                                 "--trends-json", path, "--days", "7",
                                 "--today", "2026-11-26", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        suggested = [k["keyword"] for k in parsed["suggestions"]]
        self.assertIn("قصص واقعية", suggested)
        self.assertEqual(parsed["suggestions"][0]["keyword"],
                         "قصص واقعية")
        self.assertNotIn("قصص غموض", suggested)
        self.assertIn("قصص غموض", parsed["excluded"])
        self.assertIn("قصص اطفال",
                      [s["keyword"] for s in parsed["stale"]])

    def test_missing_file_returns_2(self):
        rc, _out = _run_main(["studio.py", "fresh-keywords",
                              "--trends-json", "/no/such/0161.json",
                              "--json"])
        self.assertEqual(rc, 2)

    def test_corrupt_json_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            bad = _write(td, "bad.json", "[فساد")
            rc, _out = _run_main(["studio.py", "fresh-keywords",
                                  "--trends-json", bad, "--json"])
        self.assertEqual(rc, 2)


class TestTopicalAuthorityCmd(unittest.TestCase):
    LIBRARY = ([{"title": "توبة كعب بن مالك"}] * 2
               + [{"title": "أمانة التاجر"}]
               + [{"title": "عجائب الصدقة"}] * 3
               + [{"title": "قصة صبر أيوب"}] * 6
               + [{"title": "قصة رجل غريب"}])

    def test_known_library_authority(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "l.json", self.LIBRARY)
            rc, out = _run_main(["studio.py", "topical-authority",
                                 "--library-json", path, "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertAlmostEqual(parsed["authority"], 27.5, places=1)
        self.assertEqual(parsed["verdict"], "ضعيفة")
        self.assertEqual(parsed["total"], 13)

    def test_missing_file_returns_2(self):
        rc, _out = _run_main(["studio.py", "topical-authority",
                              "--library-json", "/no/such/0161.json",
                              "--json"])
        self.assertEqual(rc, 2)

    def test_empty_library_returns_2(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_json(td, "l.json", [])
            rc, _out = _run_main(["studio.py", "topical-authority",
                                  "--library-json", path, "--json"])
        self.assertEqual(rc, 2)


class TestGuinrankDispatch0161(unittest.TestCase):
    def test_help_lists_seven_commands(self):
        studio_dir = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))
        proc = subprocess.run(
            [sys.executable, "studio.py", "--help"],
            cwd=studio_dir, capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0)
        for cmd in SEVEN_COMMANDS:
            self.assertIn(cmd, proc.stdout)

    def test_help_ar_lists_seven_commands(self):
        rc, out = _run_main(["studio.py", "help-ar"])
        self.assertEqual(rc, 0)
        for cmd in SEVEN_COMMANDS:
            self.assertIn(cmd, out)

    def test_commands_outside_gates(self):
        for cmd in SEVEN_COMMANDS:
            self.assertNotIn(cmd, studio.COMMERCIAL_COMMANDS)
            self.assertNotIn(cmd, studio.STAR_GATED_COMMANDS)

    def test_dispatch_keyword_generate(self):
        rc, out = _run_main(["studio.py", "keyword-generate",
                             "--seed", "قصص", "--limit", "3", "--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(out)
        self.assertEqual(len(parsed["keywords"]), 3)


if __name__ == "__main__":
    unittest.main()
