#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حارس الصيغة — الجولة v0.1.53 (الموجة الأولى).

ملف واحد يفشل لو أي طلب في الموجة كسر الصيغة الجاهزة.
التأكيدات الخمسة (كلها عبر واجهات عامة + CLI، بلا توليد
فيديو ثقيل وبلا شبكة وبلا توليد صوت فعلي):

1. الراوي رجل افتراضيًا عربيًا وإنجليزيًا.
2. الكتابة أسفل الصورة فقط في المسارين (عربي/إنجليزي).
3. بنية الصيغة في مخرجات `quick` (هوك جملة واحدة + عبرة
   + سؤال ختامي).
4. بلا موسيقى في assemble.
5. الإنجليزية خيار صريح والافتراضيات العربية بلا مساس.

ملاحظة صريحة عن التأكيد 3: `quick --dry-run` يطبع الخطة
فقط (العنوان/اللغة/الصوت/الحركة/المخرج/النشر) ولا يولّد
قصة أصلًا — فالهوك/العبرة/السؤال لا يظهران في مخرجاته
بطبيعة التصميم (القصة تُولَّد في التشغيل الحقيقي فقط).
لذلك يُحرس `--dry-run` كخطة عبر subprocess، وتُحرس بنية
الصيغة عبر الدوال نفسها التي يستخدمها `quick` فعليًا:
`_parse_quick_story` (تحليل نص LLM الموسوم وغير الموسوم)
و`_quick_template_story` (قصة الرجوع المدمجة) وعينات
W4 الإنجليزية الثلاث — فأي كسر في أي منها يكسر `quick`.
"""
import inspect
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import studio
from lib import capite_captions, i18n as i18n_lib, latin_captions
from lib import long_narration, long_video, omniroute_client
from tests.test_story_prompts_en import (
    SAMPLE_STORIES_EN, check_story_structure)

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STUDIO_PY = os.path.join(STUDIO_ROOT, "studio.py")

EN_LICENSE_NOTE = ("الصوت الإنجليزي للاستخدام الشخصي/التجريبي فقط "
                   "(CC BY-NC-SA 4.0) — لا يُستخدم لفيديوهات عملاء مدفوعة")

# شريط الكابشن الواحد في المسارين: محاذاة 2 (أسفل الوسط)
# وهوامش 40/40/64 — أي قيمة أخرى تعني كسر الصيغة.
# (64 = حد المنطقة الآمنة 5% عند ارتفاع 1280؛ كان 60 قبل v0.1.56.)
CAPTION_BAR = {"alignment": 2, "margin_l": 40, "margin_r": 40,
               "margin_v": 64}
# محاذاة ASS العلوية/الوسطى (7/8/9 أعلى، 4/5/6 وسط) — ممنوعة
# في أي مسار؛ والسفلية وحدها 1/2/3، والصيغة تفرض 2 تحديدًا.
FORBIDDEN_ALIGNMENTS = (4, 5, 6, 7, 8, 9)

AR_WORDS = [{"w": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
            for i, w in enumerate(
                ["رجل", "فقير", "وجد", "حقيبة", "في", "الزبالة"])]
EN_WORDS = [{"w": w, "start": i * 0.5, "end": i * 0.5 + 0.4}
            for i, w in enumerate(
                ["James", "found", "a", "bag", "in", "the", "trash"])]


def _norm_ws(text):
    """طبّع الفراغات (نص المساعدة يلتف في الطرفيات الضيقة)."""
    return re.sub(r"\s+", " ", text or "").strip()


def _style_lines(ass_text):
    """سطران Style في نص ASS ← قواميس (محاذاة/هوامش/خط/حجم)."""
    styles = []
    for line in (ass_text or "").splitlines():
        if not line.startswith("Style:"):
            continue
        fields = [f.strip() for f in line.split(",")]
        # Style: Default,Fontname,Fontsize,...,Alignment,
        # MarginL,MarginR,MarginV,Encoding
        styles.append({
            "fontname": fields[1],
            "fontsize": int(fields[2]),
            "alignment": int(fields[18]),
            "margin_l": int(fields[19]),
            "margin_r": int(fields[20]),
            "margin_v": int(fields[21]),
        })
    return styles


def _assert_caption_bar_bottom_only(testcase, ass_text, fontname):
    """شريط كابشن واحد أسفل الصورة فقط — بلا أعلى ولا وسط."""
    styles = _style_lines(ass_text)
    testcase.assertTrue(styles, "لا سطر Style في مخرج ASS")
    for style in styles:
        testcase.assertEqual(style["alignment"], 2,
                             "محاذاة الكابشن ليست سفلية (2): %r"
                             % (style,))
        testcase.assertNotIn(style["alignment"], FORBIDDEN_ALIGNMENTS,
                             "محاذاة علوية/وسطى في الكابشن: %r"
                             % (style,))
        testcase.assertEqual(style["margin_l"],
                             CAPTION_BAR["margin_l"])
        testcase.assertEqual(style["margin_r"],
                             CAPTION_BAR["margin_r"])
        testcase.assertEqual(style["margin_v"],
                             CAPTION_BAR["margin_v"])
        testcase.assertEqual(style["fontsize"], 52)
        testcase.assertEqual(style["fontname"], fontname)
    # لا أي رقم محاذاة علوي/وسطى مختبئ في أي سطر Style آخر.
    for line in ass_text.splitlines():
        if line.startswith("Style:"):
            testcase.assertNotRegex(
                line, r",[456789],\d+,\d+,\d+,1\s*$",
                "سطر Style بمحاذاة غير سفلية: %s" % line)


def _check_quick_story(testcase, story, lang):
    """بنية قصة quick: هوك جملة واحدة + عبرة + سؤال ختامي."""
    hook = (story.get("hook") or "").strip()
    moral = (story.get("moral") or "").strip()
    question = (story.get("question") or "").strip()
    body = (story.get("body") or "").strip()
    testcase.assertTrue(hook, "هوك فارغ")
    testcase.assertNotIn("\n", hook, "الهوك أكثر من سطر")
    ends = re.findall(r"[.!?؟]", hook)
    testcase.assertEqual(len(ends), 1,
                         "الهوك ليس جملة واحدة (علامات إنهاء: %d): %r"
                         % (len(ends), hook))
    testcase.assertTrue(moral, "عبرة فارغة")
    testcase.assertNotIn("\n", moral, "العبرة أكثر من سطر")
    testcase.assertTrue(body, "جسم القصة فارغ")
    testcase.assertTrue(question, "سؤال ختامي فارغ")
    mark = "؟" if lang == "ar" else "?"
    testcase.assertTrue(question.endswith(mark),
                        "السؤال الختامي لا ينتهي بـ%r: %r"
                        % (mark, question))


def _run_cli(*args):
    """شغّل studio.py كـsubprocess والتقط (rc, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, STUDIO_PY] + list(args),
        cwd=STUDIO_ROOT, capture_output=True, text=True, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


class TestMaleNarratorDefault(unittest.TestCase):
    """1 — الراوي رجل افتراضيًا عربيًا وإنجليزيًا."""

    def test_registry_has_only_male_voices(self):
        for lang, entry in i18n_lib.PIPER_VOICES.items():
            self.assertEqual(entry.get("gender"), "male",
                             "صوت %s ليس رجاليًا: %r" % (lang, entry))

    def test_arabic_default_model_is_kareem(self):
        self.assertEqual(i18n_lib.voice_model_for_lang("ar"),
                         "ar_JO-kareem-medium")
        self.assertEqual(i18n_lib.voice_model_for_lang(),
                         "ar_JO-kareem-medium")
        self.assertEqual(i18n_lib.PIPER_VOICES["ar"]["model"],
                         "ar_JO-kareem-medium")
        self.assertEqual(i18n_lib.PIPER_VOICES["ar"]["gender"], "male")

    def test_english_model_is_ryan_male_not_lessac(self):
        self.assertEqual(i18n_lib.voice_model_for_lang("en"),
                         "en_US-ryan-medium")
        self.assertEqual(i18n_lib.PIPER_VOICES["en"]["gender"], "male")
        models = [e["model"] for e in i18n_lib.PIPER_VOICES.values()]
        self.assertNotIn("en_US-lessac-medium", models,
                         "الصوت الأنثوي lessac في السجل")

    def test_synthesize_long_defaults_to_arabic_kareem(self):
        sig = inspect.signature(long_narration.synthesize_long)
        self.assertEqual(sig.parameters["lang"].default, "ar")
        self.assertIsNone(sig.parameters["model"].default)
        self.assertEqual(sig.parameters["voice"].default, "piper")
        # عند غياب model يُحسم من lang — والعربي kareem.
        name, _path = i18n_lib.resolve_voice_model(lang="ar")
        self.assertEqual(name, "ar_JO-kareem-medium")
        name_en, _path_en = i18n_lib.resolve_voice_model(lang="en")
        self.assertEqual(name_en, "en_US-ryan-medium")

    def test_resolve_voice_arg_accepts_male_models_only(self):
        engine, path = studio._resolve_voice_arg("en_US-ryan-medium")
        self.assertEqual(engine, "piper")
        self.assertTrue(path.endswith("en_US-ryan-medium.onnx"))
        engine, path = studio._resolve_voice_arg("ryan")
        self.assertEqual(engine, "piper")
        self.assertTrue(path.endswith("en_US-ryan-medium.onnx"))
        engine, path = studio._resolve_voice_arg("kareem")
        self.assertEqual(engine, "piper")
        self.assertTrue(path.endswith("ar_JO-kareem-medium.onnx"))
        self.assertEqual(studio._resolve_voice_arg(None), (None, None))
        self.assertEqual(studio._resolve_voice_arg("piper"),
                         ("piper", None))

    def test_female_voice_rejected_via_voice_path(self):
        # lessac أنثى معروفة — مرفوضة عبر مسار --voice نفسه.
        for name in ("en_US-lessac-medium", "lessac"):
            with self.subTest(voice=name):
                with self.assertRaises(ValueError):
                    studio._resolve_voice_arg(name)
        with self.assertRaises(ValueError):
            studio._resolve_voice_arg("unknown-voice-xyz")

    def test_female_registry_entry_rejected_by_gender_branch(self):
        # السجل اليوم بلا أنثى أصلًا؛ فإن دخلت أنثى يومًا ففرع
        # الجنس في _resolve_voice_arg يرفضها — أثبته بسجل مموَّه.
        female = dict(i18n_lib.PIPER_VOICES["en"])
        female["gender"] = "female"
        with mock.patch.dict(i18n_lib.PIPER_VOICES,
                             {"en": female}):
            with self.assertRaises(ValueError) as ctx:
                studio._resolve_voice_arg("en_US-ryan-medium")
            self.assertIn("رجالي", str(ctx.exception))


class TestCaptionsBottomOnly(unittest.TestCase):
    """2 — الكتابة أسفل الصورة فقط في المسارين."""

    def test_arabic_ass_is_bottom_only(self):
        ass_text, _groups = capite_captions.words_to_karaoke_ass(
            AR_WORDS)
        _assert_caption_bar_bottom_only(
            self, ass_text, "Noto Naskh Arabic")
        self.assertIn("رجل فقير", ass_text)

    def test_latin_ass_is_bottom_only(self):
        ass_text, _groups = latin_captions.words_to_latin_ass(EN_WORDS)
        _assert_caption_bar_bottom_only(self, ass_text, "Noto Sans")
        self.assertIn("James found", ass_text)

    def test_both_paths_share_the_same_caption_bar(self):
        ar_ass, _ = capite_captions.words_to_karaoke_ass(AR_WORDS)
        en_ass, _ = latin_captions.words_to_latin_ass(EN_WORDS)
        ar_bar = [{k: s[k] for k in
                   ("alignment", "margin_l", "margin_r", "margin_v")}
                  for s in _style_lines(ar_ass)]
        en_bar = [{k: s[k] for k in
                   ("alignment", "margin_l", "margin_r", "margin_v")}
                  for s in _style_lines(en_ass)]
        self.assertEqual(ar_bar, en_bar,
                         "شريط الكابشن العربي والإنجليزي مختلفان")
        self.assertEqual(ar_bar, [CAPTION_BAR])

    def test_latin_constants_match_arabic_bar(self):
        self.assertEqual(latin_captions.CAPTION_ALIGNMENT, 2)
        self.assertEqual(latin_captions.CAPTION_MARGIN_L, 40)
        self.assertEqual(latin_captions.CAPTION_MARGIN_R, 40)
        self.assertEqual(latin_captions.CAPTION_MARGIN_V, 64)
        self.assertEqual(latin_captions.LATIN_FONT, "Noto Sans")
        # الخط اللاتيني لا يحجب الخط العربي ولا يبدّله.
        self.assertEqual(capite_captions.ASS_FONT_FAMILY,
                         "Noto Naskh Arabic")
        self.assertNotEqual(latin_captions.LATIN_FONT,
                            capite_captions.ASS_FONT_FAMILY)


class TestQuickFormulaStructure(unittest.TestCase):
    """3 — بنية الصيغة في مخرجات `quick`."""

    def test_dry_run_prints_plan_arabic_defaults(self):
        rc, out, _err = _run_cli("quick", "عنوان تجريبي", "--dry-run")
        self.assertEqual(rc, 0, "quick --dry-run فشل: %s" % out)
        self.assertIn("== خطة quick", out)
        self.assertIn("العنوان: عنوان تجريبي", out)
        self.assertIn("اللغة: ar", out)
        self.assertIn("الصوت: piper", out)
        self.assertIn("kenburns", out)
        self.assertIn("النشر: لا", out)

    def test_dry_run_english_prints_license_note(self):
        rc, out, _err = _run_cli(
            "quick", "The Honest Carpenter", "--lang", "en", "--dry-run")
        self.assertEqual(rc, 0, "quick --dry-run الإنجليزي فشل: %s"
                         % out)
        self.assertIn("اللغة: en", out)
        self.assertIn(_norm_ws(EN_LICENSE_NOTE), _norm_ws(out))

    def test_parse_tagged_llm_story_arabic(self):
        text = ("هوك: رجل وجد حقيبة.\n"
                "القصة: عاش فقيرًا ثم وجدها وأعادها.\n"
                "العبرة: الأمانة تنجي صاحبها.\n"
                "سؤال: لو كنت مكانه ماذا تفعل؟")
        _check_quick_story(
            self, studio._parse_quick_story(text, "ar"), "ar")

    def test_parse_tagged_llm_story_english(self):
        text = ("HOOK: James found a bag.\n"
                "STORY: He was poor and returned it.\n"
                "MORAL: Honesty is never lost.\n"
                "QUESTION: What would you do?")
        _check_quick_story(
            self, studio._parse_quick_story(text, "en"), "en")

    def test_parse_untagged_llm_story(self):
        ar = ("رجل فقير وجد حقيبة في الزبالة. كان محتاجًا للمال. "
              "أعاد الحقيبة لصاحبها. الأمانة تنجي صاحبها. "
              "لو كنت مكانه ماذا تفعل؟")
        _check_quick_story(
            self, studio._parse_quick_story(ar, "ar"), "ar")
        en = ("James found a bag in the trash. He was poor and honest. "
              "He returned it to its owner. Honesty is never lost. "
              "What would you do?")
        _check_quick_story(
            self, studio._parse_quick_story(en, "en"), "en")

    def test_parse_rejects_story_without_structure(self):
        with self.assertRaises(ValueError):
            studio._parse_quick_story("", "ar")
        with self.assertRaises(ValueError):
            studio._parse_quick_story("جملة واحدة فقط.", "ar")

    def test_template_fallback_story_has_formula(self):
        _check_quick_story(
            self, studio._quick_template_story("النجار الأمين", "ar"),
            "ar")
        _check_quick_story(
            self,
            studio._quick_template_story("The Honest Carpenter", "en"),
            "en")

    def test_english_sample_stories_have_formula(self):
        self.assertEqual(len(SAMPLE_STORIES_EN), 3)
        for story in SAMPLE_STORIES_EN:
            with self.subTest(title=story["title"]):
                check_story_structure(story)
                _check_quick_story(self, {
                    "hook": story["hook"],
                    "body": story["choice"] + " " + story["twist"],
                    "moral": story["moral"],
                    "question": story["closing_question"],
                }, "en")


class TestAssembleNoMusic(unittest.TestCase):
    """4 — بلا موسيقى في assemble."""

    def test_assemble_music_flag_rejected_exit_2(self):
        rc, _out, err = _run_cli(
            "assemble", "--run", "x", "--out", "y.mp4",
            "--music", "z.mp3")
        self.assertEqual(rc, 2,
                         "assemble --music لم يُرفض بالخروج 2 "
                         "(rc=%s)" % rc)
        self.assertIn("unrecognized arguments", err)
        self.assertIn("--music", err)

    def test_assemble_help_has_no_music_flag(self):
        rc, out, _err = _run_cli("assemble", "--help")
        self.assertEqual(rc, 0)
        self.assertNotIn("--music", out,
                         "راية --music ظهرت في مساعدة assemble")


class TestEnglishExplicitArabicDefaults(unittest.TestCase):
    """5 — الإنجليزية خيار صريح والافتراضيات العربية بلا مساس."""

    def test_quick_help_defaults_to_arabic(self):
        rc, out, _err = _run_cli("quick", "--help")
        self.assertEqual(rc, 0)
        self.assertIn("ar (العربية، الافتراضي)", _norm_ws(out))
        self.assertIn(_norm_ws(EN_LICENSE_NOTE), _norm_ws(out))
        self.assertEqual(studio.EN_VOICE_LICENSE_NOTE, EN_LICENSE_NOTE)

    def test_load_system_prompt_defaults_to_arabic(self):
        ar_path = os.path.join(STUDIO_ROOT, "lib", "prompts",
                               "story_system.md")
        with open(ar_path, encoding="utf-8") as fh:
            expected_ar = fh.read()
        self.assertEqual(omniroute_client.load_system_prompt(),
                         expected_ar)
        self.assertEqual(omniroute_client.load_system_prompt("ar"),
                         expected_ar)
        self.assertEqual(omniroute_client.load_system_prompt("xx"),
                         expected_ar)
        en_prompt = omniroute_client.load_system_prompt("en")
        self.assertNotEqual(en_prompt, expected_ar)

    def test_fast_motion_default_exists_and_arabic_path_untouched(self):
        self.assertEqual(long_video.FAST_MOTION_DEFAULT, "kenburns")
        # المسار العربي الافتراضي (صوت kareem + خط عربي +
        # ثوابت عربية) لم يتغيّر.
        self.assertEqual(i18n_lib.voice_model_for_lang(), 
                         "ar_JO-kareem-medium")
        self.assertEqual(capite_captions.ASS_FONT_FAMILY,
                         "Noto Naskh Arabic")
        sig = inspect.signature(long_narration.synthesize_long)
        self.assertEqual(sig.parameters["lang"].default, "ar")
        self.assertEqual(omniroute_client.load_system_prompt(),
                         omniroute_client.load_system_prompt("ar"))


class TestNegativeControl(unittest.TestCase):
    """اختبار سلبي: إثبات أن الحارس يفشل فعلًا عند قلب القيمة.

    كل قلب هنا مؤقت عبر mock داخل الاختبار نفسه — بلا أي
    تعديل لملفات الشجرة — ويُستعاد تلقائيًا بعد الاختبار.
    """

    def test_flipped_voice_gender_is_caught(self):
        female = dict(i18n_lib.PIPER_VOICES["en"])
        female["gender"] = "female"
        with mock.patch.dict(i18n_lib.PIPER_VOICES,
                             {"en": female}):
            # تأكيد الجنس نفسه يفشل عند القلب — أي أن الحارس
            # حيّ لا يمرّر صوتًا أنثويًا بصمت.
            self.assertNotEqual(
                i18n_lib.PIPER_VOICES["en"]["gender"], "male")
            with self.assertRaises(ValueError):
                studio._resolve_voice_arg("en_US-ryan-medium")
        # وبعد الخروج من الـmock يعود السجل سليمًا.
        self.assertEqual(i18n_lib.PIPER_VOICES["en"]["gender"], "male")

    def test_flipped_caption_alignment_is_caught(self):
        with mock.patch.object(latin_captions, "CAPTION_ALIGNMENT", 8):
            ass_text, _groups = latin_captions.words_to_latin_ass(
                EN_WORDS)
            styles = _style_lines(ass_text)
            self.assertEqual(styles[0]["alignment"], 8)
            with self.assertRaises(AssertionError):
                _assert_caption_bar_bottom_only(
                    self, ass_text, "Noto Sans")
        self.assertEqual(latin_captions.CAPTION_ALIGNMENT, 2)


if __name__ == "__main__":
    unittest.main()
