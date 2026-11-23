#!/usr/bin/env python3
"""حزمة اختبار verify-by-replay (جولة v0.1.40 — الحزمة 1أ).

الفكرة مقتبسة من fast-anything (التقييم
``~/workspace/fastanything-eval/REPORT-AR.md`` §7.2 بند 1 و§9 بند 1):
سجّل مكالمات حقيقية لدالة نقية حتمية، ثم أعد تشغيلها كلها ضد
الدالة نفسها وارفض أي اختلاف — فأي انحدار مستقبلي في الدالة
يُكتشف فورًا بلا كتابة توقعات يدوية لكل حالة.

قواعد السلامة (§8 من التقرير):
- الدوال المغطاة هنا نقية حتمية فقط (نص داخل ← قيمة خارج،
  بلا ملفات وبلا شبكة وبلا عشوائية وبلا وقت) من أربع وحدات:
  ``lib.ass_shaping`` و``lib.caption_check`` و``lib.queue``
  و``lib.dna``. لا تُسجَّل أبدًا دوال تلمس أسرارًا أو ملفات
  أو شبكة.
- كل المدخلات اصطناعية بأسلوب قصص الصفحة — لا بيانات مستخدم
  حقيقية ولا محتوى طابور حقيقي إطلاقًا.
- ملفات التسجيل تذهب لمجلد runs مؤقت عبر ``tempfile`` في
  الاختبارات فقط — لا ``runs/`` الحقيقي أبدًا.

يعمل بـ ``python3 -m unittest tests.test_verify_replay -v``
من جذر الاستوديو. بلا أي مكالمة شبكة حية.
"""
import copy
import hashlib
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import ass_shaping, caption_check, dna, queue

# ---------------------------------------------------------- مساعد التسجيل
# صيغة السجل (JSON): {"function", "args", "kwargs", "result"}
# أو {"function", "args", "kwargs", "error": {"type", "message"}}
# عند رفع الدالة استثناءً حتميًا (مثل هوك فارغ). القيم غير
# المتوافقة مع JSON (tuple) تُشفَّر بوسم "$tuple" وتُعاد كما هي
# عند المقارنة، فقاعدة «3 ≠ ‏3.0» و«القائمة ≠ التuple» محفوظة.


def _to_jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, tuple):
        return {"$tuple": [_to_jsonable(v) for v in value]}
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    raise TypeError("قيمة غير قابلة للتسجيل كـJSON: %r" % (value,))


def _from_jsonable(value):
    if isinstance(value, dict) and set(value) == {"$tuple"}:
        return tuple(_from_jsonable(v) for v in value["$tuple"])
    if isinstance(value, list):
        return [_from_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _from_jsonable(v) for k, v in value.items()}
    return value


def _fn_id(fn):
    return "%s.%s" % (fn.__module__, fn.__qualname__)


def _resolve_fn(fn_id):
    module_name, _, attr = fn_id.rpartition(".")
    obj = importlib.import_module(module_name)
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def record_call(fn, args, kwargs, runs_dir):
    """نفّذ الدالة الحقيقية واحفظ المكالمة + النتيجة كـJSON.

    يرجع (السجل، مسار ملف التسجيل). اسم الملف حتمي من بصمة
    الدالة والوسائط، فإعادة التسجيل لنفس المكالمة تُعيد كتابة
    الملف نفسه لا نسخة جديدة.
    """
    os.makedirs(runs_dir, exist_ok=True)
    args = list(args or [])
    kwargs = dict(kwargs or {})
    record = {"function": _fn_id(fn),
              "args": _to_jsonable(args),
              "kwargs": _to_jsonable(kwargs)}
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — الاستثناء جزء من السجل
        record["error"] = {"type": type(exc).__name__,
                           "message": str(exc)}
    else:
        record["result"] = _to_jsonable(result)
    blob = json.dumps(record, ensure_ascii=False, sort_keys=True,
                      indent=2).encode("utf-8")
    digest = hashlib.sha256(
        (record["function"] + "\n" + json.dumps(
            record["args"], ensure_ascii=False, sort_keys=True)
         + "\n" + json.dumps(
             record["kwargs"], ensure_ascii=False, sort_keys=True)
         ).encode("utf-8")).hexdigest()[:12]
    name = "%s-%s.json" % (fn.__name__, digest)
    path = os.path.join(runs_dir, name)
    with open(path, "wb") as f:
        f.write(blob + b"\n")
    return record, path


def load_record(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def replay_call(record_or_path):
    """أعد تنفيذ مكالمة مسجلة وأكّد تطابق النتيجة تمامًا.

    يقبل سجلًا (dict) أو مسار ملف تسجيل. يرجع النتيجة المعاد
    تنفيذها عند التطابق (أو الاستثناء المسجل نفسه عند سجل
    خطأ)، ويرفع AssertionError عند أي عدم تطابق — في النتيجة
    أو في نوع/رسالة الخطأ — فالعبث بالسجل يُكتشف هنا.
    """
    record = (load_record(record_or_path)
              if isinstance(record_or_path, str) else record_or_path)
    fn = _resolve_fn(record["function"])
    args = _from_jsonable(record["args"])
    kwargs = _from_jsonable(record["kwargs"])
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — يُقارَن بالسجل
        expected = record.get("error")
        if expected is None:
            raise AssertionError(
                "إعادة التشغيل رفعت %s: %s بينما السجل يحمل نتيجة"
                % (type(exc).__name__, exc))
        if (type(exc).__name__ != expected["type"]
                or str(exc) != expected["message"]):
            raise AssertionError(
                "الخطأ المعاد تنفيذه يختلف عن المسجل: "
                "سُجّل %s: %s، وأُعيد %s: %s"
                % (expected["type"], expected["message"],
                   type(exc).__name__, exc))
        return exc
    if "error" in record:
        raise AssertionError(
            "إعادة التشغيل رجعت نتيجة بينما السجل يحمل خطأ %s: %s"
            % (record["error"]["type"], record["error"]["message"]))
    replayed = _to_jsonable(result)
    if replayed != record["result"]:
        raise AssertionError(
            "إعادة التشغيل تختلف عن السجل للدالة %s:\nمسجل: %r\n"
            "معاد: %r" % (record["function"], record["result"],
                          replayed))
    return result


# ---------------------------------------------------------- مدخلات اصطناعية
# بأسلوب قصص الصفحة (هوك صادم، ظلم حماة/أقارب، عبرة واضحة) —
# مؤلفة لهذا الاختبار، ليست من الطابور الحقيقي ولا من أي منشور.

HOOK_QUESTION = "ليه الحماة ظلمت مرات ابنها؟ الحقيقة هتصدمك!"
HOOK_NUMBER = "3 أخطاء دمرت بيت الأرملة في سنة واحدة"
HOOK_SUSPENSE = "الجار اللي سرق الخبز من الأرملة… فجأة انكشف سره"
HOOK_WEAK = "قصة جميلة عن الأرملة والصبر"
STORY_TAIL = ("عاشت الأرملة سنين تصبر على الظلم. وفجأة انكشف "
              "سر الحماة أمام الجميع. والعبرة أن الصبر مفتاح الفرج، "
              "ومن حفر حفرة لأخيه وقع فيها.")

CAPTION_CLEAN = ("الأرملة صبرت سنين على ظلم حماتها.\n"
                 "الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان "
                 "يوصلك أول ما ينزل")
CAPTION_BAIT = ("الأرملة صبرت سنين على ظلم حماتها.\n"
                "لو عايز الجزء الثاني اعمل متابعة")
CAPTION_STORY_BAIT = ("عندك قصة حصلتلك؟ ابعتها في التعليقات "
                      "وهنحكيها باسمك.")

ASS_TAGGED = r"{\pos(360,1100)}ظلمتها حماتها سنين طويلة\Nفصبرت واحتسبت"
ASS_PLAIN = "الأرملة باعت الخبز وعادت لأولادها الخمسة"
ASS_LONG_WORD = "الأرملة " + "صبر" * 12 + " على الظلم"

QUEUE_TEXT = ("# طابور قصص\n\n## في الانتظار\n\n"
              "1. **الأرملة الصابرة** — منشور واحد\n"
              "2. **ظلم الحماة** — يحتاج 2 أجزاء\n\n"
              "## منشورة\n\n"
              "3. **قصة قديمة** — منشور واحد\n")

CUTS_FAST = {"cuts": [3.1, 6.4, 11.0], "duration": 47.6,
             "shot_count": 4, "avg_shot_seconds": 11.9}
CUTS_SINGLE = {"cuts": [], "duration": 31.7,
               "shot_count": 1, "avg_shot_seconds": 31.7}
CUTS_OUT_OF_RANGE = {"cuts": [50.0, 4.0], "duration": 40.0,
                     "shot_count": 3, "avg_shot_seconds": 13.33}

# الحالات الحدّية العربية المطلوبة (§9 بند 1: نص غير ASCII،
# فارغ، ومدخلات أكبر).
RLM = "\u200f"
EDGE_TEXTS = {
    "empty": "",
    "diacritics": ("ظُلِمَتِ الأرملةُ ظلمًا شديدًا من حماتِها، "
                   "فصَبَرَتْ واحتَسَبَتْ حتى جاءَ عِوَضُ اللهِ."),
    "mixed_digits": ("عاشت الأرملة 3 سنوات في بيت حماتها، ولديها "
                     "٥ أولاد، ودفعت 12 ألف جنيه مهرًا."),
    "rtl_marks": (RLM + "قصة حقيقية: الأرملة التي صبرت على ظلم "
                  "حماتها" + RLM + " " + "صبرت" + RLM + " واحتسبت"),
    "non_arabic": ("The widow waited three years for justice, "
                   "and God compensated her in the end."),
    "punctuation_only": "؟؟؟!!!... ،،، ؛؛؛",
}
_LONG_BASE = ("في قرية صغيرة عاشت أرملة صابرة تبيع الخبز كل صباح، "
              "وتعود إلى أولادها الخمسة آخر النهار وهي تحمد الله "
              "على كل حال. ")
LONG_TEXT = (_LONG_BASE * 60)[:5000]


class VerifyReplayTest(unittest.TestCase):
    """تسجيل مكالمات حقيقية + إعادة تشغيلها حرفيًا."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.runs_dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    # -- مساعد: سجّل ثم أعد التشغيل فورًا وطابق.
    def _record_replay(self, fn, *args, **kwargs):
        record, path = record_call(fn, list(args), kwargs,
                                   self.runs_dir)
        self.assertTrue(os.path.isfile(path),
                        "ملف التسجيل لم يُكتب: %s" % path)
        self.assertTrue(path.startswith(self.runs_dir),
                        "التسجيل خرج عن مجلد runs المؤقت")
        replayed = replay_call(record)
        replayed_from_file = replay_call(path)
        if "error" in record:
            # سجل خطأ: الإعادة تعيد الاستثناء نفسه لا نتيجة.
            self.assertIsInstance(replayed, Exception)
            self.assertEqual(type(replayed).__name__,
                             record["error"]["type"])
            self.assertEqual(str(replayed),
                             record["error"]["message"])
            self.assertIsInstance(replayed_from_file, Exception)
        else:
            self.assertEqual(_to_jsonable(replayed_from_file),
                             _to_jsonable(replayed))
        return record, path

    # ------------------------------------------------ ass_shaping (3 دوال)
    def test_ass_shaping_strip_ass_tags(self):
        self._record_replay(ass_shaping.strip_ass_tags, ASS_TAGGED)
        self._record_replay(ass_shaping.strip_ass_tags, ASS_PLAIN)
        self._record_replay(ass_shaping.strip_ass_tags, "")
        self._record_replay(ass_shaping.strip_ass_tags,
                            r"{\an8}الهوك\Nفي سطرين{\i1}")
        record, _ = self._record_replay(ass_shaping.strip_ass_tags,
                                        ASS_TAGGED)
        self.assertEqual(record["result"],
                         "ظلمتها حماتها سنين طويلة فصبرت واحتسبت")

    def test_ass_shaping_check_line(self):
        self._record_replay(ass_shaping._check_line, ASS_PLAIN,
                            "aisha2-scene1.ass", 12)
        self._record_replay(ass_shaping._check_line, "", "x.ass", 1)
        self._record_replay(ass_shaping._check_line,
                            "3 أخطاء دمرت بيت الأرملة",
                            "aisha2-scene1.ass", 5)
        self._record_replay(ass_shaping._check_line, ASS_LONG_WORD,
                            "x.ass", 7)
        self._record_replay(ass_shaping._check_line,
                            "النص فيه \ufffd حرف استبدال",
                            "x.ass", 9)
        self._record_replay(ass_shaping._check_line,
                            "الأرملة " + "\ufefb" + " صبرت",
                            "x.ass", 3)
        record, _ = self._record_replay(ass_shaping._check_line,
                                        "3 أخطاء دمرت بيت الأرملة",
                                        "aisha2-scene1.ass", 5)
        kinds = [i["kind"] for i in record["result"]]
        self.assertIn("bidi_start", kinds)

    def test_ass_shaping_format_report(self):
        clean = {"ok": True, "files_checked": 2,
                 "lines_checked": 12, "issues": []}
        self._record_replay(ass_shaping.format_report, clean)
        with_issues = {"ok": False, "files_checked": 1,
                       "lines_checked": 4,
                       "issues": [{"file": "aisha2-scene1.ass",
                                   "line_no": 5, "kind": "bidi_start",
                                   "detail": "سطر عربي يبدأ بـ '3'"}]}
        record, _ = self._record_replay(ass_shaping.format_report,
                                        with_issues)
        self.assertIn("bidi_start", record["result"])

    # ------------------------------------------------ caption_check (5 دوال)
    def test_caption_check_split_sentences(self):
        self._record_replay(caption_check.split_sentences,
                            CAPTION_CLEAN)
        self._record_replay(caption_check.split_sentences, "")
        self._record_replay(caption_check.split_sentences,
                            "سطر واحد بلا علامات")
        self._record_replay(caption_check.split_sentences,
                            "هوك صادم! عبرة واضحة؟ ختام محيّر.")

    def test_caption_check_sentence_issue(self):
        self._record_replay(caption_check.sentence_issue,
                            "لو عايز الجزء الثاني اعمل متابعة")
        self._record_replay(caption_check.sentence_issue,
                            "الأرملة صبرت سنين على ظلم حماتها")
        self._record_replay(caption_check.sentence_issue, "")
        self._record_replay(caption_check.sentence_issue,
                            "عندك قصة؟ ابعتها في التعليقات وهنحكيها")
        record, _ = self._record_replay(
            caption_check.sentence_issue,
            "لو عايز الجزء الثاني اعمل متابعة")
        # tuple تُسجَّل بوسم $tuple وتُعاد tuple عند الإعادة.
        self.assertEqual(record["result"],
                         {"$tuple": ["next_part",
                                     "الجزء التالي مشروط بالمتابعة "
                                     "أو التعليق"]})
        self.assertEqual(replay_call(record),
                         ("next_part",
                          "الجزء التالي مشروط بالمتابعة أو التعليق"))

    def test_caption_check_find_issues_and_check(self):
        self._record_replay(caption_check.find_issues, CAPTION_CLEAN)
        self._record_replay(caption_check.find_issues, CAPTION_BAIT)
        self._record_replay(caption_check.find_issues,
                            CAPTION_STORY_BAIT)
        self._record_replay(caption_check.find_issues, "")
        record, _ = self._record_replay(caption_check.check_caption,
                                        CAPTION_BAIT)
        self.assertFalse(record["result"]["ok"])
        # الحظر في السطر الثاني (لا الهوك): يُستبدل بالدعوة اللطيفة.
        self.assertEqual(record["result"]["fixed"], CAPTION_CLEAN)
        # الحظر في الهوك نفسه: لا إصلاح تلقائي.
        hook_bait = ("لو عايز الجزء الثاني اعمل متابعة\n"
                     "الأرملة صبرت سنين")
        record, _ = self._record_replay(caption_check.check_caption,
                                        hook_bait)
        self.assertFalse(record["result"]["ok"])
        self.assertIsNone(record["result"]["fixed"])
        record, _ = self._record_replay(caption_check.check_caption,
                                        CAPTION_CLEAN)
        self.assertTrue(record["result"]["ok"])

    def test_caption_check_fix_caption(self):
        self._record_replay(caption_check.fix_caption, CAPTION_BAIT)
        bait_tail = ("الأرملة صبرت سنين.\n"
                     "لو عايز الجزء الثاني اعمل متابعة")
        record, _ = self._record_replay(caption_check.fix_caption,
                                        bait_tail)
        self.assertIn("بكرة 7 مساءً", record["result"])

    # ------------------------------------------------ queue (4 دوال)
    def test_queue_slug(self):
        self._record_replay(queue._slug, "الأرملة الصابرة")
        self._record_replay(queue._slug, "ظلم الحماة! قصة حقيقية؟")
        self._record_replay(queue._slug, "  قصة   بمسافات  زائدة  ")
        self._record_replay(queue._slug, "")
        record, _ = self._record_replay(queue._slug,
                                        "الأرملة الصابرة")
        self.assertEqual(record["result"], "الأرملة-الصابرة")

    def test_queue_parse_waiting_entries(self):
        self._record_replay(queue.parse_waiting_entries, QUEUE_TEXT)
        self._record_replay(queue.parse_waiting_entries, "")
        self._record_replay(queue.parse_waiting_entries, QUEUE_TEXT,
                            {1: {"facebook": "published"}})
        record, _ = self._record_replay(queue.parse_waiting_entries,
                                        QUEUE_TEXT)
        self.assertEqual([e["number"] for e in record["result"]],
                         [1, 2])  # سطر قسم «منشورة» لا يُقرأ
        self.assertEqual(record["result"][0]["title"],
                         "الأرملة الصابرة")

    def test_queue_normalize_publish_statuses(self):
        self._record_replay(queue.normalize_publish_statuses, None)
        self._record_replay(queue.normalize_publish_statuses, {})
        self._record_replay(queue.normalize_publish_statuses,
                            {"facebook": "published"})
        self._record_replay(queue.normalize_publish_statuses,
                            {"youtube": "failed", "tiktok": "skipped"})
        record, _ = self._record_replay(
            queue.normalize_publish_statuses,
            {"facebook": "published"})
        self.assertEqual(record["result"]["facebook"], "published")
        self.assertEqual(record["result"]["youtube"], "pending")
        # منصة غير معروفة: خطأ حتمي يُسجَّل ويُعاد كما هو.
        record, _ = self._record_replay(
            queue.normalize_publish_statuses,
            {"myspace": "published"})
        self.assertEqual(record["error"]["type"], "QueueError")

    def test_queue_publish_summary(self):
        entries = queue.parse_waiting_entries(
            QUEUE_TEXT, {1: {"facebook": "published"}})
        self._record_replay(queue.publish_summary, entries)
        self._record_replay(queue.publish_summary, [])
        record, _ = self._record_replay(queue.publish_summary, entries)
        self.assertEqual(record["result"]["entries"], 2)
        self.assertEqual(record["result"]["facebook"]["published"], 1)
        self.assertEqual(record["result"]["facebook"]["pending"], 1)

    # ------------------------------------------------ dna (6 دوال)
    def test_dna_normalize_hook(self):
        self._record_replay(dna.normalize_hook, HOOK_NUMBER)
        self._record_replay(dna.normalize_hook, "٣ أخطاء دمرت البيت")
        self._record_replay(dna.normalize_hook, HOOK_QUESTION)
        self._record_replay(dna.normalize_hook, "")
        self._record_replay(dna.normalize_hook, "11 خطأ في القصة")
        record, _ = self._record_replay(dna.normalize_hook,
                                        HOOK_NUMBER)
        self.assertEqual(record["result"],
                         "ثلاثة أخطاء دمرت بيت الأرملة في سنة واحدة")

    def test_dna_score_hook(self):
        self._record_replay(dna.score_hook, HOOK_QUESTION)
        self._record_replay(dna.score_hook, HOOK_SUSPENSE)
        self._record_replay(dna.score_hook, HOOK_WEAK)
        self._record_replay(dna.score_hook, HOOK_QUESTION,
                            story_text=STORY_TAIL)
        record, _ = self._record_replay(dna.score_hook, HOOK_QUESTION)
        self.assertEqual(record["result"]["max"], 9)  # بلا نص قصة
        self.assertGreaterEqual(record["result"]["total"], 6)
        record, _ = self._record_replay(dna.score_hook, HOOK_QUESTION,
                                        story_text=STORY_TAIL)
        self.assertEqual(record["result"]["max"], 10)
        self.assertEqual(record["result"]["breakdown"]["payoff"], 1)

    def test_dna_score_hook_empty_is_recorded_error(self):
        record, path = record_call(dna.score_hook, [""], {},
                                   self.runs_dir)
        self.assertEqual(record["error"]["type"], "DnaError")
        self.assertIn("الهوك فارغ", record["error"]["message"])
        # إعادة التشغيل تعيد نفس الخطأ لا نتيجة.
        exc = replay_call(path)
        self.assertIsInstance(exc, dna.DnaError)

    def test_dna_hook_type_and_emotional_arc(self):
        score = dna.score_hook(HOOK_QUESTION)
        self._record_replay(dna.hook_type, score)
        self._record_replay(dna.hook_type, None)
        record, _ = self._record_replay(dna.hook_type, score)
        self.assertEqual(record["result"]["kind"],
                         "question_conflict")
        weak = dna.score_hook(HOOK_WEAK)
        self._record_replay(dna.analyze_emotional_arc, weak,
                            story_text=STORY_TAIL)
        self._record_replay(dna.analyze_emotional_arc, None)
        self._record_replay(dna.analyze_emotional_arc, weak)
        record, _ = self._record_replay(dna.analyze_emotional_arc,
                                        weak, story_text=STORY_TAIL)
        self.assertTrue(record["result"]["twist"])
        self.assertTrue(record["result"]["moral"])

    def test_dna_shot_lengths_and_pacing(self):
        self._record_replay(dna.shot_lengths, CUTS_FAST)
        self._record_replay(dna.shot_lengths, CUTS_SINGLE)
        self._record_replay(dna.shot_lengths, CUTS_OUT_OF_RANGE)
        self._record_replay(dna.shot_lengths, {})
        self._record_replay(dna.analyze_pacing, CUTS_FAST)
        self._record_replay(dna.analyze_pacing, CUTS_SINGLE)
        self._record_replay(dna.analyze_pacing, {})
        record, _ = self._record_replay(dna.shot_lengths,
                                        CUTS_OUT_OF_RANGE)
        self.assertEqual(record["result"], [4.0, 36.0])
        record, _ = self._record_replay(dna.analyze_pacing, CUTS_FAST)
        # أطوال اللقطات [3.1, 3.3, 4.6, 36.6] — الوسيط 3.95 ≤ 4.
        self.assertEqual(record["result"]["verdict"], "سريع")
        cuts_balanced = {"cuts": [6.0, 12.0, 18.0], "duration": 47.6,
                         "shot_count": 4, "avg_shot_seconds": 11.9}
        record, _ = self._record_replay(dna.analyze_pacing,
                                        cuts_balanced)
        self.assertEqual(record["result"]["verdict"], "متوازن")

    # ------------------------------------------------ الحالات الحدّية العربية
    def test_edge_cases_arabic(self):
        """كل نص حدّي يمر عبر دوال نصية من كل وحدة ويُعاد حرفيًا."""
        text_fns = [
            ass_shaping.strip_ass_tags,
            caption_check.split_sentences,
            caption_check.sentence_issue,
            caption_check.find_issues,
            caption_check.check_caption,
            dna.normalize_hook,
            queue._slug,
        ]
        for name, text in EDGE_TEXTS.items():
            for fn in text_fns:
                with self.subTest(edge=name, fn=_fn_id(fn)):
                    self._record_replay(fn, text)
            with self.subTest(edge=name, fn="ass_shaping._check_line"):
                self._record_replay(ass_shaping._check_line, text,
                                    "edge.ass", 1)

    def test_edge_long_text_5000_chars(self):
        self.assertEqual(len(LONG_TEXT), 5000)
        self._record_replay(ass_shaping.strip_ass_tags, LONG_TEXT)
        self._record_replay(caption_check.split_sentences, LONG_TEXT)
        self._record_replay(caption_check.check_caption, LONG_TEXT)
        self._record_replay(dna.score_hook, LONG_TEXT)
        self._record_replay(queue._slug, LONG_TEXT)
        record, _ = self._record_replay(dna.score_hook, LONG_TEXT)
        self.assertLessEqual(
            len(record["result"]["hook"]), 5000)

    def test_edge_score_hook_with_long_story(self):
        long_story = (STORY_TAIL + " ") * 40
        self._record_replay(dna.score_hook, HOOK_QUESTION,
                            story_text=long_story)
        self._record_replay(dna.analyze_emotional_arc,
                            dna.score_hook(HOOK_QUESTION),
                            story_text=long_story)

    # ------------------------------------------------ كشف العبث + السلامة
    def test_tampered_result_is_detected(self):
        record, path = record_call(dna.score_hook, [HOOK_QUESTION],
                                   {}, self.runs_dir)
        tampered = copy.deepcopy(record)
        tampered["result"]["total"] += 1
        with self.assertRaises(AssertionError):
            replay_call(tampered)
        # العبث بالوسائط نفسها يُكتشف أيضًا (نتيجة مختلفة).
        tampered_args = copy.deepcopy(record)
        tampered_args["args"] = [HOOK_WEAK]
        with self.assertRaises(AssertionError):
            replay_call(tampered_args)
        # العبث بتفصيلة رقمية: 4.2 → 4 (int ≠ float).
        record2, _ = record_call(dna.shot_lengths, [CUTS_FAST], {},
                                 self.runs_dir)
        tampered2 = copy.deepcopy(record2)
        tampered2["result"][0] = 4
        with self.assertRaises(AssertionError):
            replay_call(tampered2)
        # والسجل الأصلي السليم ما زال يُعاد بنجاح.
        self.assertIsNotNone(replay_call(path))

    def test_tampered_error_record_is_detected(self):
        record, _ = record_call(dna.score_hook, [""], {},
                                self.runs_dir)
        tampered = copy.deepcopy(record)
        tampered["error"]["message"] = "رسالة مختلفة"
        with self.assertRaises(AssertionError):
            replay_call(tampered)

    def test_replay_is_deterministic(self):
        record, path = record_call(caption_check.check_caption,
                                   [CAPTION_BAIT], {}, self.runs_dir)
        first = replay_call(record)
        second = replay_call(path)
        self.assertEqual(_to_jsonable(first), _to_jsonable(second))
        self.assertEqual(_to_jsonable(first), record["result"])

    def test_record_file_is_json_in_temp_runs_only(self):
        record, path = record_call(ass_shaping.strip_ass_tags,
                                   [ASS_TAGGED], {}, self.runs_dir)
        self.assertTrue(path.startswith(self.runs_dir))
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(set(loaded),
                         {"function", "args", "kwargs", "result"})
        self.assertEqual(loaded["function"],
                         "lib.ass_shaping.strip_ass_tags")
        self.assertEqual(loaded["args"], [ASS_TAGGED])
        # لا ملف تسجيل كُتب خارج مجلد runs المؤقت لهذا الاختبار.
        self.assertEqual(os.listdir(self.runs_dir),
                         [os.path.basename(path)])


if __name__ == "__main__":
    unittest.main()
