#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قائمة سماح الأوامر الدقيقة — جولة v0.1.63، البند 18.

يفصل «ما يُسمح به» عن «ما يُوافَق عليه» (``lib/approval.py``):
أمر خارج القائمة **مرفوض حتى تحت مستوى ``full``**، وقواعد محفوظة
قابلة للمراجعة في ملف الإعداد.

ملف القواعد: ``~/.qisas-studio/allowlist.json`` (0600، كتابة ذرية
على نمط ``lib/license.py``)، أو ما يشير إليه متغير البيئة
``QISAS_ALLOWLIST_DIR`` (للتوجيه في الاختبارات إلى مجلد مؤقت).
شكل الملف::

    {"rules": [{"command": "melt", "args": [["-version"]]},
               {"command": "ls"}]}

- كل قاعدة: اسم أمر (أول رمز في سطر الأمر) + قوائم وسائط
  مسموحة اختيارية.
- بلا مفتاح ``args``: يُسمح بالأمر وحده بلا وسائط فقط.
- ``"*"`` في قائمة وسائط يطابق رمزًا واحدًا أيًا كان؛ و``"**"``
  يطابق بقية الوسائط كلها.
- ملف غائب = قائمة فارغة = كل شيء مرفوض (فشل مغلق عمدًا)؛
  و``ensure_allowlist`` ينشئ الملف بقواعد القراءة الآمنة
  الافتراضية عند الطلب الصريح فقط.

الوحدة مستقلة: لا تستورد أي وحدة lib أخرى. التوصيل في
``studio.py`` للمنسّق (الموجة ب).
"""
import json
import os
import shlex

ALLOWLIST_DIR_ENV = "QISAS_ALLOWLIST_DIR"
DEFAULT_ALLOWLIST_DIR = os.path.join("~", ".qisas-studio")
ALLOWLIST_FILENAME = "allowlist.json"


class AllowlistError(Exception):
    """خطأ في قائمة سماح الأوامر (رسالته عربية)."""


# قواعد افتراضية آمنة (قراءة/تشخيص فقط — بلا كتابة ولا شبكة).
def default_rules():
    """قواعد القراءة الآمنة الافتراضية (نسخة جديدة كل مرة)."""
    return [
        {"command": "ls"},
        {"command": "pwd"},
        {"command": "cat"},
        {"command": "melt", "args": [["-version"]]},
        {"command": "python3", "args": [["-m", "unittest"]]},
    ]


# ------------------------------------------------------------------
# المسارات
# ------------------------------------------------------------------

def allowlist_dir():
    """مجلد قائمة السماح: QISAS_ALLOWLIST_DIR أو ~/.qisas-studio."""
    override = os.environ.get(ALLOWLIST_DIR_ENV, "").strip()
    if override:
        return os.path.expanduser(override)
    return os.path.expanduser(DEFAULT_ALLOWLIST_DIR)


def allowlist_path(directory=None):
    """المسار الكامل لملف القواعد allowlist.json."""
    return os.path.join(directory or allowlist_dir(),
                        ALLOWLIST_FILENAME)


# ------------------------------------------------------------------
# التحقق من القواعد
# ------------------------------------------------------------------

def validate_rule(rule):
    """تحقّق من قاعدة واحدة؛ ارجع نسخة مطبَّعة أو ارفع AllowlistError."""
    if not isinstance(rule, dict):
        raise AllowlistError("القاعدة يجب أن تكون قاموسًا")
    command = rule.get("command")
    if not isinstance(command, str) or not command.strip():
        raise AllowlistError("القاعدة تحتاج اسم أمر غير فارغ")
    if len(command.strip().split()) != 1:
        raise AllowlistError("اسم الأمر رمز واحد فقط: %s" % command)
    args = rule.get("args")
    if args is not None:
        if not isinstance(args, list) or not args:
            raise AllowlistError("args يجب أن تكون قائمة غير فارغة")
        for entry in args:
            if not isinstance(entry, list):
                raise AllowlistError("كل قائمة وسائط قائمة رموز")
            for token in entry:
                if not isinstance(token, str) or not token:
                    raise AllowlistError("رمز وسيط فارغ في القاعدة")
    cleaned = {"command": command.strip()}
    if args is not None:
        cleaned["args"] = [list(entry) for entry in args]
    return cleaned


def validate_rules(rules):
    """تحقّق من قائمة قواعد كاملة؛ ارجع نسخة مطبَّعة."""
    if not isinstance(rules, list):
        raise AllowlistError("القواعد يجب أن تكون قائمة")
    return [validate_rule(rule) for rule in rules]


# ------------------------------------------------------------------
# حفظ/تحميل القواعد
# ------------------------------------------------------------------

def load_rules(directory=None):
    """اقرأ القواعد المحفوظة؛ ملف غائب أو تالف = قائمة فارغة."""
    path = allowlist_path(directory)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return []
    if not isinstance(data, dict) or not isinstance(data.get("rules"), list):
        return []
    try:
        return validate_rules(data["rules"])
    except AllowlistError:
        return []


def save_rules(rules, directory=None):
    """احفظ القواعد ذريًا بصلاحية 600؛ ترجع نسخة مما حُفظ."""
    cleaned = validate_rules(rules)
    path = allowlist_path(directory)
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    try:
        os.chmod(parent, 0o700)
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"rules": cleaned}, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return [dict(rule) for rule in cleaned]


def ensure_allowlist(directory=None):
    """أنشئ الملف بالقواعد الافتراضية إن غاب؛ وارجع القواعد."""
    path = allowlist_path(directory)
    if os.path.isfile(path):
        return load_rules(directory)
    return save_rules(default_rules(), directory)


# ------------------------------------------------------------------
# إضافة/حذف قواعد
# ------------------------------------------------------------------

def add_rule(rule, directory=None):
    """أضف قاعدة (أو استبدل قاعدة بنفس الأمر)؛ ترجع القواعد كلها."""
    cleaned = validate_rule(rule)
    rules = load_rules(directory)
    rules = [r for r in rules if r["command"] != cleaned["command"]]
    rules.append(cleaned)
    return save_rules(rules, directory)


def remove_rule(command, directory=None):
    """احذف قاعدة بالاسم؛ ترجع True إن وُجدت وحُذفت."""
    if not isinstance(command, str) or not command.strip():
        raise AllowlistError("اسم الأمر فارغ")
    rules = load_rules(directory)
    kept = [r for r in rules if r["command"] != command.strip()]
    if len(kept) == len(rules):
        return False
    save_rules(kept, directory)
    return True


# ------------------------------------------------------------------
# المطابقة
# ------------------------------------------------------------------

def _match_args(pattern, given):
    """هل تطابق وسائط معطاة نمطًا؟ ``*`` رمز واحد، ``**`` البقية."""
    index = 0
    for token in pattern:
        if token == "**":
            return True
        if index >= len(given):
            return False
        if token != "*" and token != given[index]:
            return False
        index += 1
    return index == len(given)


def _rule_matches(rule, tokens):
    """هل تطابق قاعدة رموز أمر مفككة؟"""
    if not tokens:
        return False
    if tokens[0] != rule["command"]:
        return False
    given = tokens[1:]
    if "args" not in rule:
        return not given
    return any(_match_args(pattern, given)
               for pattern in rule["args"])


def allowed(command, rules=None, directory=None):
    """هل الأمر مسموح؟ ترجع True/False.

    ``command`` سطر أمر نصي (يُفكك بـ shlex) أو قائمة رموز.
    ``rules`` قواعد صريحة؛ وإن غابت تُقرأ من الملف. أمر خارج
    القائمة مرفوض — حتى تحت مستوى موافقة ``full``.
    """
    if isinstance(command, str):
        if not command.strip():
            return False
        try:
            tokens = shlex.split(command)
        except ValueError:
            return False
    elif isinstance(command, (list, tuple)):
        tokens = [str(t) for t in command]
    else:
        return False
    if not tokens:
        return False
    if rules is None:
        rules = load_rules(directory)
    try:
        rules = validate_rules(rules)
    except AllowlistError:
        return False
    return any(_rule_matches(rule, tokens) for rule in rules)
