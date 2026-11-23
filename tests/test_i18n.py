#!/usr/bin/env python3
"""اختبارات ثنائية اللغة — الجولة v0.1.41 (lib/i18n + قوالب
إنجليزية + ASS ثنائي اللغة + ربط --lang في studio.py).

تعمل بـ `python3 -m unittest discover -s tests -v`.
بلا شبكة وبلا رصيد Veo وبلا نشر: كل الكتابة في مجلدات
مؤقتة، وملفات ASS المعطوبة في ملفات مؤقتة، واستدعاءات
CLI المباشرة عبر دوال cmd_* (بلا عملية فرعية إلا لفحص
--help). اختبار وجود ملف الصوت الإنجليزي يُتخطى إن غاب
الملف (بيئة CI عارية) — فالصوت خيار موثَّق لا ملف مفروض.
"""
import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import ass_shaping
from lib import i18n
from lib import omniroute_client
from lib import scene_plan
from lib import story_templates

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Naskh Arabic,46,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,0,0,1,2.5,0,2,40,40,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

QUEUE_EN = """# Story queue

## في الانتظار

1. **The Widow Aisha** — test story
"""

QUEUE_AR = """# طابور قصص

## في الانتظار

1. **عائشة الأرملة** — قصة اختبار
"""


def _capture(fn, *args, **kwargs):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args, **kwargs)
    return rc, buf.getvalue()


def _ass_file(directory, name, dialogue_lines):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASS_HEAD)
        for i, text in enumerate(dialogue_lines):
            f.write("Dialogue: 0,0:00:0%d.00,0:00:0%d.00,Default,,0,0,0,,%s\n"
                    % (i, i + 1, text))
    return path


def _cfg(balance=680):
    return {"veo": {"balance_units": balance, "renews": "2026-12-13"}}


class TestDetectLang(unittest.TestCase):
    def test_default_is_arabic(self):
        self.assertEqual(i18n.detect_lang(), "ar")
        self.assertEqual(i18n.detect_lang(env={}), "ar")
        self.assertEqual(i18n.detect_lang(cli=None, env={}, config={}),
                         "ar")

    def test_cli_wins_over_everything(self):
        self.assertEqual(
            i18n.detect_lang(cli="en", env={"LANG": "ar_EG.UTF-8"},
                             config={"lang": "ar"}), "en")
        self.assertEqual(
            i18n.detect_lang(cli="ar", env={"LANG": "en_US.UTF-8"},
                             config={"lang": "en"}), "ar")

    def test_lang_env_variants(self):
        self.assertEqual(i18n.detect_lang(env={"LANG": "en_US.UTF-8"}),
                         "en")
        self.assertEqual(i18n.detect_lang(env={"LANG": "en"}), "en")
        self.assertEqual(i18n.detect_lang(env={"LANG": "ar_EG.UTF-8"}),
                         "ar")
        self.assertEqual(i18n.detect_lang(env={"LANGUAGE": "en:ar"}),
                         "en")

    def test_unrecognized_env_falls_back_to_arabic(self):
        for env in ({"LANG": "C"}, {"LANG": "POSIX"},
                    {"LANG": "fr_FR.UTF-8"}, {"LANG": ""}):
            self.assertEqual(i18n.detect_lang(env=env), "ar",
                             env)

    def test_config_lang_used_when_no_cli_or_env(self):
        self.assertEqual(
            i18n.detect_lang(env={}, config={"lang": "en"}), "en")
        self.assertEqual(
            i18n.detect_lang(env={}, config={"lang": "fr"}), "ar")
        self.assertEqual(
            i18n.detect_lang(env={"LANG": "en_US.UTF-8"},
                             config={"lang": "ar"}), "en")

    def test_invalid_cli_falls_through_to_env(self):
        self.assertEqual(
            i18n.detect_lang(cli="xx", env={"LANG": "en_US.UTF-8"}),
            "en")
        self.assertEqual(i18n.detect_lang(cli="xx", env={}), "ar")

    def test_normalize_lang(self):
        self.assertEqual(i18n.normalize_lang("en"), "en")
        self.assertEqual(i18n.normalize_lang("EN-us"), "en")
        self.assertEqual(i18n.normalize_lang("ar"), "ar")
        self.assertEqual(i18n.normalize_lang("de"), "ar")
        self.assertEqual(i18n.normalize_lang(None), "ar")
        self.assertEqual(i18n.normalize_lang(5), "ar")


class TestMessages(unittest.TestCase):
    def test_arabic_default_matches_previous_output(self):
        self.assertEqual(i18n.t("status_llm_section"),
                         "== OmniRoute (الذكاء) ==")
        self.assertEqual(i18n.t("status_llm_section", "ar"),
                         "== OmniRoute (الذكاء) ==")
        self.assertEqual(i18n.t("run_done", "ar", "out.mp4"),
                         "اكتمل خط الإنتاج: out.mp4")
        self.assertEqual(i18n.t("sceneplan_saved", "ar", "/tmp/x.json"),
                         "حُفظت الخطة في: /tmp/x.json")

    def test_english_translations(self):
        self.assertEqual(i18n.t("status_llm_section", "en"),
                         "== OmniRoute (AI) ==")
        self.assertEqual(i18n.t("run_done", "en", "out.mp4"),
                         "Pipeline finished: out.mp4")
        self.assertEqual(i18n.t("sceneplan_saved", "en", "/tmp/x.json"),
                         "Plan saved to: /tmp/x.json")
        self.assertEqual(i18n.t("llm_chain", "en"),
                         "Provider chain (in order):")
        self.assertEqual(i18n.t("publish_video_missing", "en", "v.mp4"),
                         "Video file not found: v.mp4")

    def test_unknown_key_returns_key_itself(self):
        self.assertEqual(i18n.t("no_such_key_xyz"), "no_such_key_xyz")
        self.assertEqual(i18n.t("no_such_key_xyz", "en"),
                         "no_such_key_xyz")

    def test_coverage_lists_documented(self):
        self.assertIn("status", i18n.COVERED)
        self.assertTrue(any("doctor" in item for item in i18n.NOT_COVERED))
        self.assertTrue(any("errors" in item for item in i18n.NOT_COVERED))


class TestLlmErrorTranslation(unittest.TestCase):
    def test_all_failed_translated_to_english(self):
        exc = omniroute_client.LLMAllFailedError(
            [("ddgw/gpt-5.4-mini", "quota", "429"),
             ("gemini-3-flash-preview", "network", "timeout")])
        out = i18n.translate_llm_all_failed(str(exc), "en")
        self.assertIn("All AI providers failed (2):", out)
        self.assertIn("ddgw/gpt-5.4-mini (quota)", out)
        self.assertIn("llm-status", out)
        self.assertNotIn("فشلت", out)

    def test_all_failed_arabic_unchanged(self):
        exc = omniroute_client.LLMAllFailedError(
            [("ddgw/gpt-5.4-mini", "quota", "429")])
        self.assertEqual(i18n.translate_llm_all_failed(str(exc), "ar"),
                         str(exc))

    def test_non_matching_text_returned_as_is(self):
        self.assertEqual(
            i18n.translate_llm_all_failed("خطأ آخر", "en"), "خطأ آخر")

    def test_print_translated_prefix_and_llm_error_in_english(self):
        exc = omniroute_client.LLMAllFailedError(
            [("ddgw/gpt-5.4-mini", "quota", "429")])
        _rc, out = _capture(studio._print_translated,
                            "فشل خط الإنتاج", exc, "run", "en")
        self.assertIn("Pipeline failed:", out)
        self.assertIn("All AI providers failed (1):", out)

    def test_print_translated_arabic_default(self):
        # الفئة المعروفة تُطبع عبر errors.format_error (بلا بادئة
        # سطرية — سلوك _print_translated القائم)؛ والرسالة
        # الأصلية العربية موجودة فيه.
        exc = omniroute_client.LLMAllFailedError(
            [("ddgw/gpt-5.4-mini", "quota", "429")])
        _rc, out = _capture(studio._print_translated,
                            "فشل خط الإنتاج", exc, "run")
        self.assertIn("فشلت كل مزودات الذكاء", out)


class TestPiperVoices(unittest.TestCase):
    def test_arabic_voice_is_default_male_kareem(self):
        self.assertEqual(i18n.voice_model_for_lang("ar"),
                         "ar_JO-kareem-medium")
        self.assertEqual(i18n.voice_model_for_lang(),
                         "ar_JO-kareem-medium")
        self.assertEqual(i18n.PIPER_VOICES["ar"]["gender"], "male")

    def test_english_voice_is_male_ryan_not_lessac(self):
        self.assertEqual(i18n.voice_model_for_lang("en"),
                         "en_US-ryan-medium")
        self.assertEqual(i18n.PIPER_VOICES["en"]["gender"], "male")
        self.assertNotEqual(i18n.voice_model_for_lang("en"),
                            "en_US-lessac-medium")

    def test_download_urls_are_public_huggingface(self):
        for lang in ("ar", "en"):
            url = i18n.voice_download_url(lang)
            self.assertTrue(
                url.startswith(
                    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"),
                url)
            self.assertIn(i18n.voice_model_for_lang(lang) + ".onnx", url)
            json_url = i18n.voice_download_url(lang, ".onnx.json")
            self.assertTrue(json_url.endswith(".onnx.json"), json_url)

    def test_voice_paths(self):
        self.assertTrue(i18n.voice_model_path("ar").endswith(
            "ar_JO-kareem-medium.onnx"))
        self.assertTrue(i18n.voice_model_path("en").endswith(
            "en_US-ryan-medium.onnx"))

    def test_voice_available_matches_disk(self):
        for lang in ("ar", "en"):
            self.assertEqual(
                i18n.voice_available(lang),
                os.path.isfile(i18n.voice_model_path(lang)))

    @unittest.skipUnless(
        os.path.isfile(i18n.voice_model_path("en")),
        "English Piper model not downloaded on this machine")
    def test_english_model_downloaded_and_nontrivial(self):
        path = i18n.voice_model_path("en")
        self.assertGreater(os.path.getsize(path), 10 * 1024 * 1024)
        self.assertTrue(os.path.isfile(path + ".json"))

    def test_resolve_voice_model_config_override(self):
        name, path = i18n.resolve_voice_model(
            {"narration": {"piper_model_en": "en_US-ryan-medium"}}, "en")
        self.assertEqual(name, "en_US-ryan-medium")
        self.assertTrue(path.endswith("en_US-ryan-medium.onnx"))
        name_ar, _ = i18n.resolve_voice_model({}, "ar")
        self.assertEqual(name_ar, "ar_JO-kareem-medium")


class TestEnglishTemplates(unittest.TestCase):
    def test_same_three_template_names_both_languages(self):
        names_ar = [n for n, _ in story_templates.list_templates()]
        names_en = [n for n, _ in story_templates.list_templates("en")]
        self.assertEqual(names_ar, ["relatives_injustice", "parents",
                                    "honesty_charity"])
        self.assertEqual(names_en, names_ar)

    def test_english_labels(self):
        labels = dict(story_templates.list_templates("en"))
        self.assertEqual(labels["relatives_injustice"],
                         "Injustice by relatives and in-laws")
        self.assertEqual(labels["parents"],
                         "Honoring / disobeying parents")
        self.assertEqual(labels["honesty_charity"], "Honesty / charity")

    def test_english_outline_structure(self):
        out = story_templates.build_scene_outline(
            "relatives_injustice", "The Widow Aisha", "Aisha",
            "was wronged by her mother-in-law and thrown out of her home",
            lang="en")
        self.assertEqual(out["lang"], "en")
        self.assertEqual(out["clips"], 6)
        self.assertEqual(out["total_duration_seconds"], 48)
        self.assertEqual([s["beat"] for s in out["scenes"]],
                         ["hook", "escalation", "escalation",
                          "twist", "twist", "moral"])
        self.assertEqual([s["beat_label"] for s in out["scenes"]][:2],
                         ["Hook", "Escalation"])
        self.assertIn("Aisha", out["hook"])
        self.assertIn("wronged by her mother-in-law", out["hook"])

    def test_english_beats_carry_specific_numbers(self):
        out = story_templates.build_scene_outline(
            "honesty_charity", "The Honest Carpenter", "a poor carpenter",
            "found a wallet on the road", lang="en", clips=4)
        joined = " ".join(s["prompt"] for s in out["scenes"])
        self.assertIn("$5,000", joined)
        self.assertIn("$20", joined)
        self.assertIn("The lesson:", out["scenes"][-1]["prompt"])

    def test_english_twist_numbers_parents(self):
        out = story_templates.build_scene_outline(
            "parents", "The Distant Son", "Ahmad",
            "left his parents and travelled far", lang="en", clips=4)
        self.assertIn("10 years", out["scenes"][1]["prompt"])
        self.assertTrue(out["closing_question"].endswith("?"))
        self.assertIn("kind word", out["closing_question"])

    def test_english_render_and_format(self):
        out = story_templates.build_scene_outline(
            "parents", "The Distant Son", "Ahmad",
            "left his parents and travelled far", lang="en", clips=4)
        text = story_templates.render_story_text(out)
        self.assertIn("Ahmad", text)
        self.assertEqual(len(text.splitlines()), 5)
        formatted = story_templates.format_outline(out)
        self.assertIn("Story outline", formatted)
        self.assertIn("Hook", formatted)
        self.assertIn("Moral", formatted)
        self.assertNotIn("مخطط قصة", formatted)

    def test_arabic_default_unchanged(self):
        out = story_templates.build_scene_outline(
            "parents", "الابن البعيد", "أحمد",
            "ترك أهله وسافر عشر سنين", clips=4)
        self.assertEqual(out["lang"], "ar")
        self.assertIn("هوك", [s["beat_label"] for s in out["scenes"]])
        self.assertIn("العبرة:", out["scenes"][-1]["prompt"])

    def test_unknown_template_english_error(self):
        with self.assertRaises(ValueError) as cm:
            story_templates.get_template("nope", lang="en")
        self.assertIn("Unknown story template", str(cm.exception))

    def test_invalid_template_lang_rejected(self):
        with self.assertRaises(ValueError):
            story_templates.build_scene_outline(
                "parents", "عنوان", "بطل", "موقف", lang="fr")
        with self.assertRaises(ValueError):
            story_templates.set_template_lang("de")

    def test_template_lang_seam_defaults_to_arabic(self):
        self.assertEqual(story_templates.get_template_lang(), "ar")


class TestTemplateLangSeam(unittest.TestCase):
    def test_scene_plan_uses_module_default_lang(self):
        story_templates.set_template_lang("en")
        try:
            plan = scene_plan.build_scene_plan(
                _cfg(), {"number": 99, "title": "The Widow Aisha"},
                template="relatives_injustice",
                template_hero="Aisha",
                template_situation=("was wronged by her mother-in-law "
                                    "and thrown out of her home"))
            self.assertIn("everything turned upside down",
                          plan["scenes"][0]["prompt"])
            self.assertEqual(plan["template"], "relatives_injustice")
        finally:
            story_templates.set_template_lang("ar")
        plan_ar = scene_plan.build_scene_plan(
            _cfg(), {"number": 99, "title": "عائشة الأرملة"},
            template="relatives_injustice",
            template_hero="عائشة الأرملة",
            template_situation="ظلمتها حماتها وطردتها من بيتها")
        self.assertIn("انقلب", plan_ar["scenes"][0]["prompt"])

    def test_from_template_helper_english(self):
        story_templates.set_template_lang("en")
        try:
            plan = scene_plan.build_scene_plan_from_template(
                _cfg(), "honesty_charity", "The Honest Carpenter",
                "a poor carpenter", "found a wallet on the road",
                clips=4)
        finally:
            story_templates.set_template_lang("ar")
        self.assertIn("$5,000", " ".join(
            s["prompt"] for s in plan["scenes"]))


class TestAssBilingual(unittest.TestCase):
    def test_detect_text_lang(self):
        self.assertEqual(
            ass_shaping.detect_text_lang("A poor widow lost everything."),
            "en")
        self.assertEqual(
            ass_shaping.detect_text_lang("أرملة فقيرة خسرت كل شيء."),
            "ar")
        self.assertEqual(
            ass_shaping.detect_text_lang("Aisha عائشة lost everything."),
            "mixed")
        self.assertEqual(ass_shaping.detect_text_lang("12345 !?"), "other")

    def test_classify_line_bidi_scope(self):
        en = ass_shaping.classify_line("A poor widow lost everything.")
        self.assertEqual(en["lang"], "en")
        self.assertFalse(en["bidi_applies"])
        mixed_latin = ass_shaping.classify_line(
            "John lost everything, وظلمته حماته.")
        self.assertEqual(mixed_latin["lang"], "mixed")
        self.assertFalse(mixed_latin["bidi_applies"])
        mixed_ar = ass_shaping.classify_line("A قصة عن رجل فقير.")
        self.assertTrue(mixed_ar["bidi_applies"])

    def _audit(self, name, lines):
        with tempfile.TemporaryDirectory() as td:
            path = _ass_file(td, name, lines)
            return ass_shaping.audit_ass_file(path)

    def test_pure_english_line_passes(self):
        res = self._audit("en-ok.ass",
                          ["A poor widow lost everything in one night."])
        self.assertTrue(res["ok"], res["issues"])

    def test_mixed_latin_majority_passes(self):
        res = self._audit("mixed-ok.ass",
                          ["John lost everything, and no one believed him. "
                           "ظلمته حماته."])
        self.assertTrue(res["ok"], res["issues"])

    def test_mixed_arabic_majority_latin_start_flagged(self):
        res = self._audit("mixed-bad.ass", ["A قصة عن رجل فقير."])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("bidi_start", kinds)

    def test_arabic_digit_start_still_flagged(self):
        res = self._audit("ar-bad.ass",
                          ["3 قصص عن رجل فقير غيّرت حياته."])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("bidi_start", kinds)

    def test_presentation_form_still_flagged_with_english(self):
        res = self._audit("pres-form.ass",
                          ["A poor widow ﺍ lost everything."])
        kinds = [i["kind"] for i in res["issues"]]
        self.assertIn("presentation_form", kinds)


class TestCmdWiring(unittest.TestCase):
    def _base_cfg(self, td):
        cfg = json.loads(json.dumps(studio.DEFAULTS))
        cfg["paths"]["runs_dir"] = td
        cfg["paths"]["videos_dir"] = td
        return cfg

    def test_status_arabic_default(self):
        with tempfile.TemporaryDirectory() as td:
            _rc, out = _capture(studio.cmd_status, self._base_cfg(td))
            self.assertIn("== OmniRoute (الذكاء) ==", out)
            self.assertIn("موجود", out)

    def test_status_english(self):
        with tempfile.TemporaryDirectory() as td:
            _rc, out = _capture(studio.cmd_status, self._base_cfg(td),
                                lang="en")
            self.assertIn("== OmniRoute (AI) ==", out)
            self.assertIn("exists", out)
            self.assertNotIn("الذكاء", out)

    def test_llm_status_both_languages(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._base_cfg(td)
            _rc, out_ar = _capture(studio.cmd_llm_status, cfg)
            self.assertIn("سلسلة المزودين (بالترتيب):", out_ar)
            _rc, out_en = _capture(studio.cmd_llm_status, cfg, lang="en")
            self.assertIn("Provider chain (in order):", out_en)

    def test_doctor_llm_section_english(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._base_cfg(td)
            _rc, out = _capture(studio.cmd_doctor, cfg, llm_flag=True,
                                lang="en")
            self.assertIn("== LLM checks (", out)

    def test_run_dry_run_both_languages(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._base_cfg(td)
            rc, out_ar = _capture(
                studio.cmd_run, cfg, "anza", "anza-part1", "/tmp/x.mp4",
                True, dry_run=True)
            self.assertEqual(rc, 0)
            self.assertIn("== وضع تجريبي", out_ar)
            rc, out_en = _capture(
                studio.cmd_run, cfg, "anza", "anza-part1", "/tmp/x.mp4",
                True, dry_run=True, lang="en")
            self.assertEqual(rc, 0)
            self.assertIn("== Dry run", out_en)
            self.assertIn("Script: story=anza", out_en)

    def test_run_unknown_backend_english(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _capture(
                studio.cmd_run, self._base_cfg(td), "anza", "anza-part1",
                "/tmp/x.mp4", True, dry_run=True, backend="nope",
                lang="en")
            self.assertEqual(rc, 1)
            self.assertIn("Unknown assemble backend: nope", out)

    def test_scene_plan_english_template(self):
        with tempfile.TemporaryDirectory() as td:
            queue = os.path.join(td, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(QUEUE_EN)
            cfg = {"veo": {"balance_units": 680},
                   "paths": {"runs_dir": td, "queue_file": queue}}
            rc, out = _capture(
                studio.cmd_scene_plan, cfg, story="1",
                template="parents", template_hero="Ahmad",
                template_situation="left his parents and travelled far",
                lang="en", template_lang="en")
            self.assertEqual(rc, 0, out)
            self.assertIn("10 years", out)
            self.assertIn("Plan saved to:", out)
            # الجسر يعيد الافتراضي إلى العربي بعد البناء.
            self.assertEqual(story_templates.get_template_lang(), "ar")

    def test_scene_plan_arabic_default_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            queue = os.path.join(td, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(QUEUE_AR)
            cfg = {"veo": {"balance_units": 680},
                   "paths": {"runs_dir": td, "queue_file": queue}}
            rc, out = _capture(
                studio.cmd_scene_plan, cfg, story="1",
                template="parents", template_hero="أحمد",
                template_situation="ترك أهله وسافر بعيدًا")
            self.assertEqual(rc, 0, out)
            self.assertIn("ترك أهله", out)
            self.assertIn("حُفظت الخطة في:", out)

    def test_scene_plan_unknown_template_english(self):
        with tempfile.TemporaryDirectory() as td:
            queue = os.path.join(td, "queue.md")
            with open(queue, "w", encoding="utf-8") as f:
                f.write(QUEUE_EN)
            cfg = {"veo": {"balance_units": 680},
                   "paths": {"runs_dir": td, "queue_file": queue}}
            rc, out = _capture(
                studio.cmd_scene_plan, cfg, story="1", template="nope",
                lang="en")
            self.assertEqual(rc, 2)
            self.assertIn("Unknown template: nope", out)

    def test_publish_missing_video_english(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = self._base_cfg(td)
            rc, out = _capture(
                studio.cmd_publish, cfg, "/tmp/no-such-video.mp4",
                "Title", "caption", lang="en")
            self.assertEqual(rc, 1)
            self.assertIn("Video file not found: /tmp/no-such-video.mp4",
                          out)


class TestCliHelp(unittest.TestCase):
    def test_lang_and_template_lang_flags_exist(self):
        studio_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "studio.py")
        for args in (["--lang", "en", "scene-plan", "--help"],
                     ["scene-plan", "--help"],
                     ["--lang", "en", "--help"]):
            proc = subprocess.run(
                [sys.executable, studio_py, *args],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "LANG": "C"})
            self.assertEqual(proc.returncode, 0, args)
            self.assertIn("usage:", proc.stdout.lower(), args)
        proc = subprocess.run(
            [sys.executable, studio_py, "--lang", "en",
             "scene-plan", "--help"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LANG": "C"})
        self.assertIn("--template-lang", proc.stdout)
        # وصف --help نفسه يتبع LANG من البيئة (يُقرأ قبل التحليل)،
        # لا --lang — فاختبره بـ LANG إنجليزية.
        proc = subprocess.run(
            [sys.executable, studio_py, "--help"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LANG": "en_US.UTF-8"})
        self.assertIn("Unified production line", proc.stdout)

    def test_invalid_lang_rejected_by_argparse(self):
        studio_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "studio.py")
        proc = subprocess.run(
            [sys.executable, studio_py, "--lang", "xx", "status"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "LANG": "C"})
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
