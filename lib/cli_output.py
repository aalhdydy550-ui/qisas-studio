#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""عقد CLI الموحّد (جولة v0.1.63، بند 2 — عقدا ع1 وع2).

- مع `--json` يحمل stdout وثيقة JSON واحدة بالضبط، والفشل
  مشمول: `{"ok": false, "error", "hint", "exitCode"}`.
- التقدّم يذهب إلى stderr ككائن JSON واحد في السطر،
  و`--quiet` يُسقطه.
- كل سلسلة مطبوعة تمر عبر تنقيح أسرار عميق متكرر
  (`redact_deep`) قبل أن تخرج — حتى داخل JSON.
- رموز الخروج الثابتة (ع1): 0 تم، 1 فشل، 2 CLI سيئ/بلا
  `--yes`، 3 يحتاج إجابة بشرية، 4 يحتاج تسجيل دخول/مهلة،
  5 غير مسموح/غير قابل للوصول، 6 مشغول، 7 غير موجود،
  8 مشكلة بيانات، 130 Ctrl-C.

الاستيرادات المتقاطعة كسولة داخل الدوال (بلا اعتماد بناء
على `lib/secret_guard.py` و`lib/id_mask.py` — تُستخدمان
كما هما دون إعادة تنفيذ ما فيهما).
"""
import json
import sys

# رموز الخروج (ع1).
EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_BAD_CLI = 2
EXIT_NEEDS_HUMAN = 3
EXIT_LOGIN_TIMEOUT = 4
EXIT_FORBIDDEN = 5
EXIT_BUSY = 6
EXIT_NOT_FOUND = 7
EXIT_DATA_ERROR = 8
EXIT_INTERRUPTED = 130

EXIT_CODES = {
    "ok": EXIT_OK,
    "failure": EXIT_FAILURE,
    "bad_cli": EXIT_BAD_CLI,
    "needs_human": EXIT_NEEDS_HUMAN,
    "login_timeout": EXIT_LOGIN_TIMEOUT,
    "forbidden": EXIT_FORBIDDEN,
    "busy": EXIT_BUSY,
    "not_found": EXIT_NOT_FOUND,
    "data_error": EXIT_DATA_ERROR,
    "interrupted": EXIT_INTERRUPTED,
}


def short_id(s):
    """قصّر معرّفًا طويلًا إلى أول 8 أحرف + `…`.

    القصير (8 أحرف أو أقل) يرجع كما هو بلا قصّ.
    """
    text = "" if s is None else str(s)
    if len(text) <= 8:
        return text
    return text[:8] + "…"


def one_line(s, limit=120):
    """سطّح نصًا (أسطر/فراغات متعددة ← مسافة واحدة) وقصّه
    عند `limit` حرفًا (الافتراضي 120) مع `…` عند القصّ."""
    text = " ".join(("" if s is None else str(s)).split())
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _redact_text(text):
    """نقّح نصًا واحدًا: أسرار المزوّدين (عبر
    `lib/secret_guard.py`) + حجب الأسرار (عبر
    `lib/id_mask.py`) + إخفاء المعرّفات (بريد/هاتف/أرقام
    طويلة). الاستيراد كسول داخل الدالة."""
    from lib import id_mask
    from lib import secret_guard

    redacted = text
    # أنماط صيغ المزوّدين من secret_guard كما هي (بلا إعادة
    # تنفيذ): Google وGroq وOpenRouter وAnthropic وElevenLabs
    # وHuggingFace وGitHub وAWS والمفاتيح الخاصة وBearer.
    for attr in ("_GOOGLE_RE", "_GROQ_RE", "_OPENROUTER_RE",
                 "_ANTHROPIC_RE", "_ELEVENLABS_RE", "_HF_RE",
                 "_GITHUB_RE", "_GITHUB_PAT_RE", "_AWS_RE",
                 "_PEM_RE", "_BEARER_RE"):
        pattern = getattr(secret_guard, attr, None)
        if pattern is not None:
            redacted = pattern.sub("[REDACTED]", redacted)
    # حجب نهائي لا عكسي لقيم شبيهة بالأسرار (sk-… وghp_…
    # وAKIA… وBearer وتعيينات api_key=…).
    redacted = id_mask.redact_secrets(redacted)
    # إخفاء المعرّفات (بريد/هاتف/أرقام طويلة) برموز —
    # الـmapping عندنا ولا يخرج مع النص.
    masked, _mapping = id_mask.mask_text(redacted)
    return masked


def redact_deep(obj):
    """نقّح أسرار أي قيمة تكراريًا (dict/list/tuple/str)
    وارجع نسخة جديدة — الأصل لا يُعدَّل أبدًا.

    المفاتيح تُترك كما هي؛ القيم النصية فقط تُنقَّح؛
    والأنواع الأخرى (أرقام، None، bool…) تُعاد كما هي.
    """
    if isinstance(obj, str):
        return _redact_text(obj)
    if isinstance(obj, dict):
        return {key: redact_deep(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [redact_deep(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(redact_deep(item) for item in obj)
    return obj


def _print_json(payload, stream):
    """اطبع وثيقة JSON واحدة في سطر واحد (بلا أسطر إضافية)."""
    print(json.dumps(payload, ensure_ascii=False), file=stream)


class Output:
    """مخرجات أمر واحد ملتزمة بعقد CLI الموحّد.

    `json_mode`: اطبع النتائج JSON على stdout.
    `quiet`: أسقط التقدّم (stderr) — النتيجة والخطأ يبقيان.
    """

    def __init__(self, json_mode=False, quiet=False):
        self.json_mode = bool(json_mode)
        self.quiet = bool(quiet)

    def progress(self, obj):
        """سطر تقدّم واحد JSON على stderr دائمًا (يُسقطه
        `--quiet`). يقبل dict أو نصًا (يُغلَّف برسالة)."""
        if self.quiet:
            return None
        if isinstance(obj, dict):
            payload = redact_deep(obj)
        else:
            payload = redact_deep({"message": "" if obj is None
                                   else str(obj)})
        _print_json(payload, sys.stderr)
        return None

    def result(self, value, human_lines=None):
        """اطبع النتيجة: في وضع JSON وثيقة واحدة
        `{"ok": true, ...value}` على stdout؛ وفي الوضع
        البشري سطور `human_lines` (أو سطور `key: value`
        من القاموس) على stdout."""
        if self.json_mode:
            if isinstance(value, dict):
                payload = {"ok": True}
                payload.update(redact_deep(value))
            else:
                payload = {"ok": True,
                           "value": redact_deep(value)}
            _print_json(payload, sys.stdout)
            return None
        lines = human_lines
        if lines is None:
            if isinstance(value, dict):
                lines = ["%s: %s" % (key, val)
                         for key, val in redact_deep(value).items()]
            else:
                lines = [str(redact_deep(value))]
        for line in lines:
            print(redact_deep(line), file=sys.stdout)
        return None

    def error(self, message, hint=None, code=EXIT_FAILURE):
        """اطبع خطأً وارجع رمز الخروج.

        في وضع JSON: وثيقة واحدة `{"ok": false, "error",
        "hint", "exitCode"}` على stdout. في الوضع البشري:
        `error: …` و`hint: …` على stderr.
        """
        message = redact_deep("" if message is None else str(message))
        hint = redact_deep("" if hint is None else str(hint))
        code = int(code)
        if self.json_mode:
            payload = {"ok": False, "error": message,
                       "hint": hint, "exitCode": code}
            _print_json(payload, sys.stdout)
        else:
            print("error: %s" % message, file=sys.stderr)
            if hint:
                print("hint: %s" % hint, file=sys.stderr)
        return code
