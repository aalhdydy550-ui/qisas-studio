#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""اختبار حارس AGPL — الجولة 7 (v0.1.31).

يفشل صراحةً عند أي خرق لشروط الامتثال، ويمر ضمن المجموعة
الكاملة (`python3 -m unittest discover -s tests`):

(أ) شجرة الاستوديو (المستودع) بلا أي ثنائي Concat وبلا أي نسخة
    كود OpenMontage: لا ملف تنفيذي ELF باسم concat، ولا مجلد
    باسم openmontage/concat، ولا استيراد لوحدتي المكوّنين في
    أي ملف .py، ولا تعريف صنف باسميهما (نسخة كود منقولة).
(ب) قالب الرخصة التجارية يحوي صياغة الاستثناء الصريحة
    (الأدوات المنسَّقة خارج الرخصة + AGPL-3.0) والأسعار
    دون تغيير (1000 للأفراد / 5000 للشركات).
(ج) `setup.sh` و`setup-env.sh` لا يثبّتان المكوّنين ولا
    يضمّنانهما في أي حزمة — بلا أي ذكر لهما أصلًا.

ملاحظة: ملف هذا الاختبار نفسه مستثنًى من الفحص (يذكر
المكوّنين بالاسم في نصوصه — هو الذي يحرس، لا الذي يُحرس).
كود التنسيق (`lib/openmontage_stage.py` و`lib/concat_mcp.py`)
مسموح — ينسّق المكوّنين عبر ملفات بيانات وعملية منفصلة
(JSON-RPC) بلا ربط ولا استيراد ولا كود مضمّن.
"""
import os
import re
import sys
import unittest

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# جولة v0.1.41 (إصلاح CI): سكربت الإعداد يعيش داخل شجرة
# المستودع نفسها (setup-env.sh في الجذر) بعدما كان في
# ~/workspace/ خارج الشجرة فيغيب عن نسخة CI.
SETUP_ENV = os.path.join(STUDIO_ROOT, "setup-env.sh")

# مجلدات تُستثنى من الفحص: مخرجات تشغيل وسجلات وبيئات افتراضية
# (ليست جزءًا من المستودع المباع).
EXCLUDED_DIRS = {"__pycache__", ".git", ".venv-whisper",
                 ".venv-autoeditor", ".venv-moviepy", ".venv-youtube",
                 ".venv-gtts", "runs", "backups", "queue",
                 "client-orders", "demo", "whisper-test-results",
                 "node_modules", ".space-build"}
THIS_FILE = os.path.basename(__file__)

IMPORT_RE = re.compile(r"^\s*(from|import)\s+(openmontage|concat)\b")
CLASS_RE = re.compile(r"^\s*class\s+(OpenMontage|Concat)\b")
ELF_MAGIC = b"\x7fELF"

TEMPLATE_REQUIRED = ("OpenMontage", "Concat", "ليست مشمولة",
                     "AGPL-3.0", "يحصل عليها المشتري بنفسه",
                     "دون تعديل", "1000", "5000")


def _walk_files(root):
    """كل الملفات تحت الجذر عدا المستثناة وملف الحارس نفسه."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.basename(path) == THIS_FILE:
                continue
            yield path


class TestAgplGuard(unittest.TestCase):
    def test_no_concat_binary(self):
        """(أ) لا ثنائي Concat (ELF) في الشجرة."""
        offenders = []
        for path in _walk_files(STUDIO_ROOT):
            if os.path.basename(path) != "concat":
                continue
            with open(path, "rb") as f:
                if f.read(4) == ELF_MAGIC:
                    offenders.append(path)
        self.assertEqual(offenders, [],
                         "ثنائي Concat في الشجرة (ممنوع في أي حزمة): %s"
                         % offenders)

    def test_no_component_directories(self):
        """(أ) لا مجلد باسم openmontage أو concat في الشجرة."""
        offenders = []
        for dirpath, dirnames, _filenames in os.walk(STUDIO_ROOT):
            dirnames[:] = [d for d in dirnames
                           if d not in EXCLUDED_DIRS]
            for d in dirnames:
                if d in ("openmontage", "concat"):
                    offenders.append(os.path.join(dirpath, d))
        self.assertEqual(offenders, [],
                         "مجلد مكوّن في الشجرة (نسخة كود ممنوعة): %s"
                         % offenders)

    def test_no_component_imports_or_classes(self):
        """(أ) لا استيراد لوحدتي المكوّنين ولا صنف باسميهما في أي .py."""
        offenders = []
        for path in _walk_files(STUDIO_ROOT):
            if not path.endswith(".py"):
                continue
            with open(path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if IMPORT_RE.match(line) or CLASS_RE.match(line):
                        offenders.append("%s:%d: %s"
                                         % (path, i, line.strip()))
        self.assertEqual(offenders, [],
                         "استيراد/صنف من كود المكوّنين في الشجرة: %s"
                         % offenders)

    def test_license_template_exclusion(self):
        """(ب) قالب الرخصة يحوي صياغة الاستثناء والأسعار."""
        path = os.path.join(STUDIO_ROOT,
                            "LICENSE-COMMERCIAL-TEMPLATE.md")
        self.assertTrue(os.path.isfile(path),
                        "قالب الرخصة التجارية مفقود: %s" % path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        missing = [phrase for phrase in TEMPLATE_REQUIRED
                   if phrase not in text]
        self.assertEqual(missing, [],
                         "قالب الرخصة بلا صياغة الاستثناء (%s)"
                         % ", ".join(missing))

    def test_setup_scripts_do_not_install_components(self):
        """(ج) سكربتا الإعداد لا يثبّتان المكوّنين ولا يضمّنانهما."""
        for path in (os.path.join(STUDIO_ROOT, "setup.sh"),
                     os.path.abspath(SETUP_ENV)):
            self.assertTrue(os.path.isfile(path),
                            "سكربت الإعداد مفقود: %s" % path)
            with open(path, encoding="utf-8",
                      errors="replace") as f:
                text = f.read()
            found = [word for word in ("openmontage", "concat")
                     if word in text.lower()]
            self.assertEqual(found, [],
                             "%s يذكر المكوّنين (%s) — ممنوع تثبيتهما "
                             "أو تضمينهما من سكربتات المشروع"
                             % (path, ", ".join(found)))

    def test_compliance_file_records_conditions(self):
        """ملف الامتثال يسجّل الشروط الخمسة والقاعدة الداخلية."""
        path = os.path.join(STUDIO_ROOT, "COMPLIANCE-AGPL.md")
        self.assertTrue(os.path.isfile(path),
                        "ملف الامتثال مفقود: %s" % path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        required = ("يُوثَّق فورًا ويُنشر مصدره",
                    "لا يُضمَّن ثنائي Concat",
                    "مراجعة محامٍ قبل التوسع الكبير",
                    "لم تُنجَز بعد")
        missing = [phrase for phrase in required
                   if phrase not in text]
        self.assertEqual(missing, [],
                         "ملف الامتثال ناقص (%s)" % ", ".join(missing))


if __name__ == "__main__":
    unittest.main()
