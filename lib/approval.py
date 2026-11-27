#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مستويات الموافقة الخمسة لبوابات النشر — جولة v0.1.63، البنود 1 و10 و18 و20.

خمسة مستويات (``ask`` / ``edits`` / ``auto`` / ``full`` / ``custom``)
تتحكم في كل فعل مؤثر (نشر، حذف، إنفاق، تغيير إعدادات)، مع أرضية
أمان لا يتخطاها حتى ``full``، ومنح بآجال (مرة/جلسة/دائم)، وسجل
قرارات، وتسميات مصدر مضادة للحقن، ووضع قراءة-ومسودة.

ملف الإعداد: ``~/.qisas-studio/approval.json`` (0600، كتابة ذرية
على نمط ``lib/license.py``)، أو ما يشير إليه متغير البيئة
``QISAS_APPROVAL_DIR`` (للتوجيه في الاختبارات إلى مجلد مؤقت).
شكل الملف::

    {"level": "ask",
     "custom": {"edit_text": "allow", "publish": "ask"},
     "grants": [{"action": ..., "scope": ..., "duration": "always",
                 "fingerprint": ..., "created_at": ...}],
     "mode": "normal" | "read-and-draft",
     "drafts": ["thread-1"],
     "settings_version": 1}

سجل القرارات: ``runs/approval-decisions.jsonl`` — سطر JSON لكل قرار
غير مراقب (بلا أسرار أبدًا)، ويُحذف ما هو أقدم من 180 يومًا
(انظر ``prune_old_decisions``).

القواعد (العقد ع3):
- مستوى التشغيل يفوز على مستوى المشروع؛ ومستوى المنسّق يتدفق
  نزولًا للعمّال (يرتفع فقط، لا ينخفض أبدًا).
- **أرضية الأمان** ترفض دائمًا حتى تحت ``full``: حذف منشور منشور
  (``delete_published``)، إنفاق مال (``spend_money``)، تغيير مفاتيح
  (``change_keys``)، حذف ملفات مشروع (``delete_project_files``).
  (ملاحظة انحراف موثقة: نص §7 بند 1 يقول إن حذف منشور تحت ``full``
  «ما زال يسأل»؛ والعقد ع3 ومهمة الجولة يقولان «ترفض دائمًا» —
  والتزم هنا بالعقد ع3: رفض لا سؤال.)
- المنح الدائم دقيق (فعل + نطاق + إعداد)، قابل للإلغاء، يُبطل
  عند تغيير الإعدادات، و**لا يُمنح أبدًا** للنشر/المال/التحكم
  بالحاسوب.
- تسميات المصدر ``[From <who> · <what> · <authority>]``: الموافقة
  تُحتسب فقط من سياق التشغيل الفاعل نفسه؛ نص من عامل آخر أو
  webhook أو بريد هو معلومة فقط، لا تعليمة.
- وضع ``read-and-draft``: التشغيل فيه يُجبَر على ``ask``، وكل طلب
  فعل يُرفض رفضًا قاطعًا ما عدا كتابة مسودة واحدة لكل خيط.

الوحدة مستقلة: لا تستورد أي وحدة lib أخرى، والاستيرادات المتقاطعة
(مثل قائمة سماح الأوامر) كسولة داخل الدوال. التوصيل في ``studio.py``
وأوامر النشر للمنسّق (الموجة ب).
"""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CAIRO = ZoneInfo("Africa/Cairo")

LEVELS = ("ask", "edits", "auto", "full", "custom")
DEFAULT_LEVEL = "ask"

# ترتيب السماحية (للتدفق نزولًا: يرتفع فقط). ``custom`` ليس رقمًا
# في هذا الترتيب؛ يُستخدم فقط حين يكون هو مستوى التشغيل/المشروع.
_LEVEL_RANK = {"ask": 0, "edits": 1, "auto": 2, "full": 3}

# أرضية الأمان: تُرفض دائمًا، تحت أي مستوى وأي منح.
SAFETY_FLOOR = frozenset({
    "delete_published",      # حذف منشور منشور
    "spend_money",           # إنفاق مال
    "change_keys",           # تغيير مفاتيح
    "delete_project_files",  # حذف ملفات مشروع
})

# أفعال لا يُمنح لها منح دائم أبدًا (نشر/مال/تحكم بالحاسوب/حذف).
NEVER_ALWAYS_GRANT = frozenset({
    "publish", "publish_facebook", "publish_youtube", "publish_tiktok",
    "send_message", "send_email", "send", "spend_money", "change_keys",
    "delete_published", "delete_project_files", "delete",
    "computer_control", "computer",
})

# أفعال القراءة العادية: لا تسأل أبدًا (بوت يقرأ ملفاته هو).
READ_ACTIONS = frozenset({
    "read", "read_file", "read_own_files", "list_files", "list",
    "inspect", "check", "status",
})

# أفعال تعديل نصي يقبلها مستوى ``edits`` تلقائيًا.
EDIT_ACTIONS = frozenset({
    "edit", "edit_text", "modify_text", "fix_text", "rewrite_text",
})

GRANT_DURATIONS = ("once", "session", "always")

MODES = ("normal", "read-and-draft")

# فعل كتابة المسودة في وضع قراءة-ومسودة (واحدة لكل خيط).
DRAFT_ACTION = "write_draft"

DECISIONS_FILENAME = "approval-decisions.jsonl"
CONFIG_FILENAME = "approval.json"
APPROVAL_DIR_ENV = "QISAS_APPROVAL_DIR"
RUNS_DIR_ENV = "QISAS_APPROVAL_RUNS_DIR"
DEFAULT_APPROVAL_DIR = os.path.join("~", ".qisas-studio")

# الاحتفاظ بسجل القرارات (أيام).
DECISIONS_RETENTION_DAYS = 180

_SOURCE_RE = re.compile(
    r"^\[From\s+(.+?)\s+·\s+(.+?)\s+·\s+(.+?)\]$")

_SECRET_KEY_RE = re.compile(
    r"(key|token|secret|password|passwd|auth|credential|bearer)",
    re.IGNORECASE)


class ApprovalError(Exception):
    """خطأ في بوابة الموافقة (رسالته عربية)."""


# ------------------------------------------------------------------
# المسارات والإعداد
# ------------------------------------------------------------------

def approval_dir():
    """مجلد إعداد الموافقة: QISAS_APPROVAL_DIR أو ~/.qisas-studio."""
    override = os.environ.get(APPROVAL_DIR_ENV, "").strip()
    if override:
        return os.path.expanduser(override)
    return os.path.expanduser(DEFAULT_APPROVAL_DIR)


def config_path(directory=None):
    """المسار الكامل لملف الإعداد approval.json."""
    return os.path.join(directory or approval_dir(), CONFIG_FILENAME)


def runs_dir():
    """مجلد سجل القرارات: QISAS_APPROVAL_RUNS_DIR أو ./runs."""
    override = os.environ.get(RUNS_DIR_ENV, "").strip()
    if override:
        return os.path.expanduser(override)
    return os.path.join(os.getcwd(), "runs")


def decisions_path(directory=None):
    """المسار الكامل لسجل القرارات runs/approval-decisions.jsonl."""
    return os.path.join(directory or runs_dir(), DECISIONS_FILENAME)


def _default_config():
    """إعداد افتراضي جديد."""
    return {"level": DEFAULT_LEVEL, "custom": {}, "grants": [],
            "mode": "normal", "drafts": [], "settings_version": 1}


def _validate_config(data):
    """تحقّق من شكل الإعداد المقروء؛ ارجع إعدادًا مطبَّعًا أو None."""
    if not isinstance(data, dict):
        return None
    level = data.get("level", DEFAULT_LEVEL)
    if level not in LEVELS:
        return None
    custom = data.get("custom", {})
    if not isinstance(custom, dict):
        return None
    for action, decision in custom.items():
        if not isinstance(action, str) or not action.strip():
            return None
        if decision not in ("allow", "ask", "deny"):
            return None
    grants = data.get("grants", [])
    if not isinstance(grants, list):
        return None
    for grant in grants:
        if not isinstance(grant, dict):
            return None
        if grant.get("duration") not in GRANT_DURATIONS:
            return None
        if not isinstance(grant.get("action"), str) \
                or not grant.get("action", "").strip():
            return None
    mode = data.get("mode", "normal")
    if mode not in MODES:
        return None
    drafts = data.get("drafts", [])
    if not isinstance(drafts, list) \
            or not all(isinstance(d, str) for d in drafts):
        return None
    version = data.get("settings_version", 1)
    if not isinstance(version, int) or version < 1:
        return None
    return {"level": level,
            "custom": dict(custom),
            "grants": [dict(g) for g in grants],
            "mode": mode,
            "drafts": list(drafts),
            "settings_version": version}


def load_config(directory=None):
    """اقرأ الإعداد؛ ملف غائب أو تالف يرجع الافتراضي (بلا كتابة)."""
    path = config_path(directory)
    if not os.path.isfile(path):
        return _default_config()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return _default_config()
    validated = _validate_config(data)
    if validated is None:
        return _default_config()
    return validated


def _atomic_write_json(path, payload):
    """اكتب JSON ذريًا (ملف مؤقت + os.replace) بصلاحية 600."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def save_config(config, directory=None):
    """احفظ الإعداد ذريًا بصلاحية 600؛ ترجع نسخة مما حُفظ."""
    validated = _validate_config(config)
    if validated is None:
        raise ApprovalError("إعداد موافقة غير صالح — لم يُحفظ شيء")
    _atomic_write_json(config_path(directory), validated)
    return dict(validated)


def _settings_fingerprint(config):
    """بصمة الإعدادات (المستوى + خريطة custom + الإصدار).

    المنح الدائم مربوط بهذه البصمة؛ أي تغيير في الإعدادات يغيّر
    البصمة فيُبطل المنح الدائم.
    """
    raw = json.dumps({"level": config.get("level"),
                      "custom": config.get("custom", {}),
                      "settings_version": config.get("settings_version", 1)},
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------
# تسميات المصدر (بند 10)
# ------------------------------------------------------------------

def format_source(who, what, authority):
    """كوّن تسمية مصدر: [From <who> · <what> · <authority>]."""
    for value, name in ((who, "who"), (what, "what"),
                        (authority, "authority")):
        if not isinstance(value, str) or not value.strip():
            raise ApprovalError("تسمية المصدر تحتاج %s غير فارغ" % name)
        if "·" in value or "[" in value or "]" in value:
            raise ApprovalError("تسمية المصدر لا تقبل «·» أو أقواسًا")
    return "[From %s · %s · %s]" % (who.strip(), what.strip(),
                                    authority.strip())


def parse_source(label):
    """حلّل تسمية مصدر؛ ارجع (who, what, authority) أو None."""
    if not isinstance(label, str):
        return None
    match = _SOURCE_RE.match(label.strip())
    if not match:
        return None
    return match.groups()


def is_valid_source(label):
    """هل التسمية بصيغة [From <who> · <what> · <authority>]؟"""
    return parse_source(label) is not None


def approval_from_actor(label, actor):
    """هل الموافقة من سياق التشغيل الفاعل نفسه؟

    نص من عامل آخر أو webhook أو بريد هو معلومة فقط — الموافقة
    تُحتسب فقط حين يكون ``who`` في التسمية هو الفاعل نفسه.
    بلا تسمية أو بلا فاعل: لا يُحتسب شيء (False).
    """
    parsed = parse_source(label)
    if parsed is None or not actor:
        return False
    return parsed[0] == actor


# ------------------------------------------------------------------
# حلّ المستوى الفعّال
# ------------------------------------------------------------------

def resolve_level(level=None, run_level=None, chief_level=None):
    """حلّ المستوى الفعّال.

    - مستوى التشغيل يفوز على مستوى المشروع.
    - مستوى المنسّق يتدفق نزولًا: يرفع فقط، لا يخفض أبدًا.
    - مستوى غير صالح يُتجاهل (كأنه غائب)؛ والكل غائب = ``ask``.
    - ``custom`` لا يُرفع رقميًا: إن كان مستوى التشغيل/المشروع
      ``custom`` بقي ``custom``؛ و``custom`` من المنسّق وحده لا
      يغيّر مستوى غير مخصص.
    """
    base = None
    for candidate in (level, run_level):
        if candidate in LEVELS:
            base = candidate
    if base is None:
        base = DEFAULT_LEVEL
    if chief_level in LEVELS and chief_level != "custom" \
            and base != "custom":
        if _LEVEL_RANK[chief_level] > _LEVEL_RANK[base]:
            base = chief_level
    return base


# ------------------------------------------------------------------
# تنقيح الأسرار من سجل القرارات
# ------------------------------------------------------------------

def _redact_value(value):
    """نقّح قيمة قد تحمل سرًا قبل كتابتها في السجل."""
    if isinstance(value, dict):
        return {k: ("«redacted»" if _SECRET_KEY_RE.search(str(k))
                    else _redact_value(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


# ------------------------------------------------------------------
# بوابة الموافقة
# ------------------------------------------------------------------

class ApprovalGate:
    """بوابة موافقة واحدة: إعداد + منح جلسة/مرة + سجل قرارات.

    ``config_dir`` مجلد الإعداد (الافتراضي ~/.qisas-studio أو
    QISAS_APPROVAL_DIR)، و``runs_directory`` مجلد سجل القرارات
    (الافتراضي ./runs أو QISAS_APPROVAL_RUNS_DIR). منح الجلسة
    والمرة تعيش في الذاكرة فقط (في نسخة البوابة هذه)؛ والمنح
    الدائم يُحفظ في ملف الإعداد.
    """

    def __init__(self, config_dir=None, runs_directory=None):
        self.config_dir = config_dir or approval_dir()
        self.runs_directory = runs_directory or runs_dir()
        self.config = load_config(self.config_dir)
        self._session_grants = []   # [{"action", "scope"}]
        self._once_grants = []      # [{"action", "scope"}] تُستهلك
        self._session_id = None

    # -- الإعداد ---------------------------------------------------

    def get_level(self):
        """مستوى المشروع الحالي."""
        return self.config.get("level", DEFAULT_LEVEL)

    def set_level(self, level):
        """عيّن مستوى المشروع واحفظه؛ تغييره يُبطل المنح الدائم."""
        if level not in LEVELS:
            raise ApprovalError("مستوى موافقة غير معروف: %s" % level)
        self.config["level"] = level
        self.config["settings_version"] = \
            self.config.get("settings_version", 1) + 1
        self._invalidate_always_grants()
        save_config(self.config, self.config_dir)
        return self.config["level"]

    def set_custom_action(self, action, decision):
        """عيّن قرار فعل في خريطة custom واحفظه (يُبطل المنح الدائم)."""
        if not isinstance(action, str) or not action.strip():
            raise ApprovalError("اسم الفعل فارغ")
        if decision not in ("allow", "ask", "deny"):
            raise ApprovalError("قرار custom غير صالح: %s" % decision)
        self.config.setdefault("custom", {})[action.strip()] = decision
        self.config["settings_version"] = \
            self.config.get("settings_version", 1) + 1
        self._invalidate_always_grants()
        save_config(self.config, self.config_dir)
        return decision

    def set_mode(self, mode):
        """عيّن وضع التشغيل (normal أو read-and-draft) واحفظه."""
        if mode not in MODES:
            raise ApprovalError("وضع غير معروف: %s" % mode)
        self.config["mode"] = mode
        save_config(self.config, self.config_dir)
        return mode

    def get_mode(self):
        """وضع التشغيل الحالي."""
        return self.config.get("mode", "normal")

    def reload(self):
        """أعد قراءة الإعداد من القرص."""
        self.config = load_config(self.config_dir)
        return self.config

    # -- المنح ------------------------------------------------------

    def _invalidate_always_grants(self):
        """أبطل المنح الدائم عند تغيير الإعدادات."""
        self.config["grants"] = [
            g for g in self.config.get("grants", [])
            if g.get("duration") != "always"]

    def _grant_allowed(self, action, duration):
        """هل يُسمح بهذا المنح؟ (دائم ممنوع للنشر/المال/الحاسوب)."""
        if action in SAFETY_FLOOR:
            return False, "فعل في أرضية الأمان — ممنوع منحه أبدًا"
        if duration == "always" and action in NEVER_ALWAYS_GRANT:
            return False, ("منح دائم ممنوع للنشر/الإرسال/المال/"
                           "التحكم بالحاسوب")
        if duration not in GRANT_DURATIONS:
            return False, "مدة منح غير صالحة: %s" % duration
        return True, ""

    def grant(self, action, scope="*", duration="once"):
        """امنح فعلًا (once/session/always)؛ ترجع (ok, reason).

        - ``once``: يُستهلك عند أول استخدام.
        - ``session``: يعيش في ذاكرة هذه البوابة فقط.
        - ``always``: يُحفظ في ملف الإعداد مع بصمة الإعدادات،
          ويُبطل عند تغييرها، وممنوع للنشر/المال/الحاسوب.
        ``scope`` نطاق دقيق (أداة + هدف + إعداد)؛ ``*`` يعني أي نطاق.
        """
        if not isinstance(action, str) or not action.strip():
            return False, "اسم الفعل فارغ"
        action = action.strip()
        allowed, reason = self._grant_allowed(action, duration)
        if not allowed:
            return False, reason
        scope = scope if isinstance(scope, str) and scope else "*"
        entry = {"action": action, "scope": scope}
        if duration == "once":
            self._once_grants.append(entry)
        elif duration == "session":
            self._session_grants.append(entry)
        else:
            stored = {"action": action, "scope": scope,
                      "duration": "always",
                      "fingerprint": _settings_fingerprint(self.config),
                      "created_at": datetime.now(tz=CAIRO).isoformat(
                          timespec="seconds")}
            grants = [g for g in self.config.get("grants", [])
                      if not (g.get("action") == action
                              and g.get("scope") == scope
                              and g.get("duration") == "always")]
            grants.append(stored)
            self.config["grants"] = grants
            save_config(self.config, self.config_dir)
        return True, ""

    def revoke(self, action=None, scope=None):
        """ألغِ منحًا (كلها إن لم يُحدد فعل)؛ ترجع عدد الملغى."""
        removed = 0
        for store in (self._once_grants, self._session_grants):
            before = len(store)
            store[:] = [g for g in store
                        if not ((action is None or g["action"] == action)
                                and (scope is None
                                     or g["scope"] == scope))]
            removed += before - len(store)
        before = len(self.config.get("grants", []))
        self.config["grants"] = [
            g for g in self.config.get("grants", [])
            if not ((action is None or g.get("action") == action)
                    and (scope is None or g.get("scope") == scope))]
        removed += before - len(self.config["grants"])
        if removed:
            save_config(self.config, self.config_dir)
        return removed

    def list_grants(self):
        """كل المنح (مرة + جلسة + دائم) بلا أسرار."""
        out = [{"action": g["action"], "scope": g["scope"],
                "duration": "once"} for g in self._once_grants]
        out += [{"action": g["action"], "scope": g["scope"],
                 "duration": "session"} for g in self._session_grants]
        out += [{"action": g.get("action"), "scope": g.get("scope"),
                 "duration": "always",
                 "fingerprint": g.get("fingerprint")}
                for g in self.config.get("grants", [])]
        return out

    def _has_grant(self, action, scope, consume_once=True):
        """هل يوجد منح يغطي الفعل؟ (once يُستهلك عند الاستخدام)."""
        for store, consume in ((self._once_grants, consume_once),
                               (self._session_grants, False)):
            for entry in list(store):
                if entry["action"] == action and (
                        entry["scope"] == "*" or entry["scope"] == scope
                        or scope == "*"):
                    if consume:
                        store.remove(entry)
                    return True
        fingerprint = _settings_fingerprint(self.config)
        for entry in self.config.get("grants", []):
            if entry.get("duration") != "always":
                continue
            if entry.get("fingerprint") != fingerprint:
                continue  # أُبطل بتغيير الإعدادات
            if entry.get("action") == action and (
                    entry.get("scope") == "*"
                    or entry.get("scope") == scope or scope == "*"):
                return True
        return False

    # -- وضع قراءة-ومسودة ------------------------------------------

    def allow_draft(self, thread_id):
        """هل يُسمح بكتابة مسودة لهذا الخيط؟ (واحدة لكل خيط)."""
        if not isinstance(thread_id, str) or not thread_id.strip():
            return False
        thread_id = thread_id.strip()
        drafts = self.config.get("drafts", [])
        if thread_id in drafts:
            return False
        drafts.append(thread_id)
        self.config["drafts"] = drafts
        save_config(self.config, self.config_dir)
        return True

    # -- القرار ------------------------------------------------------

    def check(self, action, level=None, run_level=None,
              chief_level=None, scope="*", source_label=None,
              actor=None, thread_id=None, log=True):
        """قرر فعلًا؛ ترجع ``allow`` أو ``ask`` أو ``deny``.

        ``level`` مستوى المشروع (الافتراضي من الإعداد)، و``run_level``
        مستوى التشغيل (يفوز)، و``chief_level`` مستوى المنسّق
        (يرفع فقط). ``source_label`` تسمية مصدر؛ و``actor`` الفاعل —
        منح من مصدر غير الفاعل معلومة فقط ولا يُحتسب.
        """
        decision, _reason = self.decide(
            action, level=level, run_level=run_level,
            chief_level=chief_level, scope=scope,
            source_label=source_label, actor=actor,
            thread_id=thread_id, log=log)
        return decision

    def decide(self, action, level=None, run_level=None,
               chief_level=None, scope="*", source_label=None,
               actor=None, thread_id=None, log=True):
        """قرر فعلًا مع السبب؛ ترجع (decision, reason)."""
        if not isinstance(action, str) or not action.strip():
            raise ApprovalError("اسم الفعل فارغ")
        action = action.strip()
        scope = scope if isinstance(scope, str) and scope else "*"
        mode = self.get_mode()

        # وضع قراءة-ومسودة: إجبار ask + رفض قاطع لكل فعل عدا
        # مسودة واحدة لكل خيط.
        if mode == "read-and-draft":
            if action == DRAFT_ACTION:
                if thread_id is None:
                    result = ("deny", "read-and-draft: مسودة بلا خيط")
                elif self.allow_draft(thread_id):
                    result = ("allow", "read-and-draft: مسودة الخيط")
                else:
                    result = ("deny",
                              "read-and-draft: مسودة واحدة لكل خيط")
            else:
                result = ("deny", "read-and-draft: الفعل مرفوض")
            if log:
                self._log_decision(action, result[0], result[1],
                                   "read-and-draft", source_label)
            return result

        # أرضية الأمان أولًا: ترفض دائمًا، تحت أي مستوى وأي منح.
        if action in SAFETY_FLOOR:
            result = ("deny", "أرضية الأمان: %s مرفوض دائمًا" % action)
            if log:
                self._log_decision(action, "deny", result[1],
                                   resolve_level(level, run_level,
                                                 chief_level),
                                   source_label)
            return result

        # القراءة العادية لا تسأل أبدًا.
        if action in READ_ACTIONS:
            result = ("allow", "قراءة عادية")
            if log:
                self._log_decision(action, "allow", result[1],
                                   resolve_level(level, run_level,
                                                 chief_level),
                                   source_label)
            return result

        effective = resolve_level(
            level if level is not None else self.get_level(),
            run_level, chief_level)

        # المنح: يُحتسب فقط من سياق التشغيل الفاعل نفسه؛ تسمية
        # مصدر من عامل آخر معلومة فقط ولا تمنح شيئًا.
        grant_counts = True
        if source_label is not None and actor is not None:
            grant_counts = approval_from_actor(source_label, actor)
        if grant_counts and self._has_grant(action, scope):
            result = ("allow", "منح سارٍ للفعل")
            if log:
                self._log_decision(action, "allow", result[1], effective,
                                   source_label)
            return result

        if effective == "custom":
            mapped = self.config.get("custom", {}).get(action)
            if mapped == "allow":
                result = ("allow", "custom: مسموح للفعل")
            elif mapped == "deny":
                result = ("deny", "custom: مرفوض للفعل")
            else:
                result = ("ask", "custom: الفعل غير مذكور — يسأل")
        elif effective == "full":
            result = ("allow", "full: وصول كامل (عدا أرضية الأمان)")
        elif effective == "auto":
            result = ("allow", "auto: موافقة نيابة عن المستخدم")
        elif effective == "edits":
            if action in EDIT_ACTIONS:
                result = ("allow", "edits: تعديل نصي مقبول تلقائيًا")
            else:
                result = ("ask", "edits: الفعل ليس تعديلًا نصيًا")
        else:  # ask
            result = ("ask", "ask: يسأل عن كل فعل")
        if log:
            self._log_decision(action, result[0], result[1], effective,
                               source_label)
        return result

    # -- سجل القرارات -----------------------------------------------

    def _log_decision(self, action, decision, reason, level,
                      source_label):
        """سجّل قرارًا (سطر JSONL بلا أسرار)."""
        record = {"ts": datetime.now(tz=CAIRO).isoformat(
                      timespec="seconds"),
                  "action": action, "decision": decision,
                  "reason": reason, "level": level,
                  "source": source_label}
        record = _redact_value(record)
        try:
            os.makedirs(self.runs_directory, exist_ok=True)
            path = os.path.join(self.runs_directory, DECISIONS_FILENAME)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass  # فشل السجل لا يسقط القرار نفسه

    def read_decisions(self, limit=None):
        """اقرأ سجل القرارات (الأحدث آخرًا)؛ سطر تالف يُتخطى."""
        path = os.path.join(self.runs_directory, DECISIONS_FILENAME)
        if not os.path.isfile(path):
            return []
        records = []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            return []
        if limit is not None:
            records = records[-limit:]
        return records

    def prune_old_decisions(self, days=DECISIONS_RETENTION_DAYS,
                            now=None):
        """احذف قرارات أقدم من ``days`` يومًا؛ ترجع عدد المحذوف."""
        if now is None:
            now = datetime.now(tz=CAIRO)
        cutoff = now - timedelta(days=days)
        path = os.path.join(self.runs_directory, DECISIONS_FILENAME)
        if not os.path.isfile(path):
            return 0
        kept = []
        removed = 0
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        ts = datetime.fromisoformat(record.get("ts", ""))
                    except (ValueError, TypeError):
                        removed += 1
                        continue
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=CAIRO)
                    if ts < cutoff:
                        removed += 1
                    else:
                        kept.append(line)
        except OSError:
            return 0
        if removed:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                for line in kept:
                    fh.write(line + "\n")
            os.replace(tmp, path)
        return removed


# ------------------------------------------------------------------
# دوال على مستوى الوحدة (بوابة افتراضية — للتوصيل السريع)
# ------------------------------------------------------------------

def check(action, level=None, run_level=None, chief_level=None,
          scope="*", source_label=None, actor=None, thread_id=None):
    """قرر فعلًا عبر بوابة افتراضية؛ ترجع allow/ask/deny."""
    return ApprovalGate().check(
        action, level=level, run_level=run_level,
        chief_level=chief_level, scope=scope,
        source_label=source_label, actor=actor, thread_id=thread_id)


def show():
    """الحالة الحالية للموافقة (لأمر approval show)."""
    gate = ApprovalGate()
    return {"level": gate.get_level(), "mode": gate.get_mode(),
            "custom": dict(gate.config.get("custom", {})),
            "grants": gate.list_grants()}
