#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تركيبة تحكم معزولة + سطح تحكم واحد (بند 17، جولة v0.1.63).

سطح التحكم يشغّل الأفعال المنشورة نفسها (التي يلفّها أمر
`studio.py control <verb>`)، وتجهيزة الاختبار معزولة تمامًا:
مجلد بيانات مؤقت + home مؤقت + منافذ حرة + محرك مزيف فقط —
فلا تمسّ صدفة الوالد ولا بيانات الاستوديو الحقيقية أبدًا.

قاعدتان صارمتان:
1. **أوامر التعديل ترفض اكتشاف الهدف الصامت**: فعل تعديل
   بلا هدف صريح (تركيبة/هدف معلَن) مرفوض — فيمنع وصفة تحقق
   من إرسال رسائل إلى تشغيل حي بالخطأ.
2. **خريطة السلوك**: كل سلوك موثق له مدخل؛ ولا يُضاف مدخل
   إلا بعد أن يقود الحزام فعلًا (انظر `tests/CONTROL-MAP.md`)؛
   وسلوك لا يثبته الحزام يُوسم صراحة كقيد.

فقط متغيرات `FAKE_CLAUDE_*` تعبر من بيئة المُطلق إلى الابن،
فيستطيع وصفة برمجة وضع المحرك المزيف وردوده واستدعاءات أدواته
دون كتابة CLI غلاف.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile

__all__ = [
    "ControlError", "ControlTarget", "ControlFixture",
    "READ_VERBS", "MUTATING_VERBS", "BEHAVIOR_MAP",
    "free_port", "child_env", "require_explicit_target",
    "run_control", "behavior_map_entries",
]

# ─── الأفعال ───
# أفعال قراءة: مسموحة بلا هدف صريح.
READ_VERBS = frozenset({
    "inspect", "jobs", "runs", "read-log", "search-log", "status",
    "list", "show", "health",
})
# أفعال تعديل: ترفض الهدف الصامت.
MUTATING_VERBS = frozenset({
    "publish", "delete", "send", "send-work", "stop", "pause",
    "resume", "interrupt", "interrupt-job", "approve", "set",
    "apply", "cancel", "switch-model", "wait-job",
})

# متغيرات البيئة الوحيدة التي تعبر من المُطلق إلى الابن.
FAKE_ENV_PREFIX = "FAKE_CLAUDE_"
# مفتاح المحرك المزيف داخل التركيبة.
FAKE_ENGINE_NAME = "fake"


class ControlError(Exception):
    """خطأ سطح التحكم (هدف صامت، فعل مجهول، تركيبة مغلقة...)."""


def free_port():
    """احجز منفذًا حرًا وأطلقه فورًا؛ ارجع رقمه.

    المنفذ يُحجز لحظيًا للقياس فقط — المتصل يربطه هو؛
    والتسابق على المنفذ بين القياس والربط مقبول هنا لأن
    التركيبة مؤقتة ومحلية (127.0.0.1 فقط).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


def child_env(base_env=None):
    """ابنِ بيئة الابن: فقط `FAKE_CLAUDE_*` تعبر من بيئة المُطلق.

    بلا أي متغير آخر — لا مفاتيح حقيقية ولا مسارات بيانات
    الوالد — فيبقى الابن معزولًا عن حساب المستخدم.
    """
    source = base_env if base_env is not None else os.environ
    return {key: value for key, value in source.items()
            if key.startswith(FAKE_ENV_PREFIX)}


class ControlTarget:
    """هدف صريح يوجَّه إليه فعل تحكم (تركيبة أو تشغيل معلَن).

    `data_dir`: مجلد بيانات الهدف؛ `port`: منفذه؛ `pid`: معرّف
    عمليته (إن وجد). الهدف الصامت = `None`، لا هدف افتراضي
    يُكتشف من البيئة أبدًا.
    """

    def __init__(self, data_dir, port=None, pid=None, label=None):
        if not data_dir:
            raise ControlError("الهدف يحتاج مجلد بيانات صريحًا")
        self.data_dir = os.path.abspath(data_dir)
        self.port = port
        self.pid = pid
        self.label = label or os.path.basename(self.data_dir)

    def as_dict(self):
        """تمثيل قابل للطباعة/السجل (بلا أسرار)."""
        return {
            "data_dir": self.data_dir,
            "port": self.port,
            "pid": self.pid,
            "label": self.label,
        }


def require_explicit_target(verb, target):
    """ارفض أمر تعديل بلا هدف صريح؛ واسمح لفعل القراءة.

    يرجع `target` بعد التحقق. يرفع `ControlError` برسالة
    عربية حين يكون الفعل تعديلًا والهدف `None`.
    """
    if verb in MUTATING_VERBS and target is None:
        raise ControlError(
            "الفعل '%s' فعل تعديل ويرفض الهدف الصامت: مرّر هدفًا "
            "صريحًا (تركيبة تحكم أو --target) بدل اكتشاف تشغيل حي"
            % verb)
    if verb not in READ_VERBS and verb not in MUTATING_VERBS:
        raise ControlError("فعل تحكم مجهول: %s" % verb)
    return target


class ControlFixture:
    """تركيبة اختبار معزولة: بيانات مؤقتة + home مؤقت + منافذ
    حرة + محرك مزيف فقط.

    تُستخدم كمدير سياق (`with ControlFixture() as fx:`)؛
    وتُنظَّف مجلداتها المؤقتة عند الخروج. الابن (إن بدأ
    بـ`start()`) عملية نوم بايثون محلية فقط — بلا شبكة
    وبلا لمس لبيانات الوالد.
    """

    def __init__(self, base_env=None):
        self._tmp = tempfile.mkdtemp(prefix="qisas-control-")
        self.data_dir = os.path.join(self._tmp, "data")
        self.home_dir = os.path.join(self._tmp, "home")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.home_dir, exist_ok=True)
        self.port = free_port()
        self.control_port = free_port()
        self.log_path = os.path.join(self.data_dir, "control.log")
        self.engine = FAKE_ENGINE_NAME
        self._base_env = base_env
        self._child = None
        self._closed = False

    @property
    def pid(self):
        """معرّف عملية الابن أو None إن لم يبدأ."""
        return self._child.pid if self._child is not None else None

    @property
    def url(self):
        """عنوان سطح التحكم المحلي (127.0.0.1 فقط)."""
        return "http://127.0.0.1:%d" % self.port

    def child_environment(self):
        """بيئة الابن: HOME مؤقت + بيانات مؤقتة + `FAKE_CLAUDE_*` فقط."""
        env = child_env(self._base_env)
        env["HOME"] = self.home_dir
        env["QISAS_STUDIO_DATA_DIR"] = self.data_dir
        env["QISAS_CONTROL_ENGINE"] = self.engine
        return env

    def configure_fake_engine(self, mode="echo", responses=None,
                              tool_calls=None):
        """ثبّت المحرك المزيف للتركيبة فقط واكتب وصفته.

        `mode`: وضع الرد (`echo` افتراضيًا)؛ `responses`:
        ردود نصية محفوظة؛ `tool_calls`: استدعاءات أدوات
        محاكاة. تُكتب الوصفة داخل مجلد البيانات المؤقت فقط.
        يرجع مسار ملف الوصفة.
        """
        recipe = {
            "engine": FAKE_ENGINE_NAME,
            "mode": mode,
            "responses": list(responses or []),
            "tool_calls": list(tool_calls or []),
        }
        path = os.path.join(self.data_dir, "fake-engine.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(recipe, handle, ensure_ascii=False, indent=2)
        return path

    def target(self, label=None):
        """هدف صريح يشير إلى هذه التركيبة (لأفعال التعديل)."""
        return ControlTarget(
            self.data_dir, port=self.port, pid=self.pid,
            label=label or "control-fixture")

    def start(self):
        """ابدأ الابن المعزول (عملية نوم محلية)؛ ارجع `pid`.

        الابن يرث بيئة `child_environment()` فقط، ويبقى
        مرتبطًا بهذه التركيبة بالضبط.
        """
        if self._closed:
            raise ControlError("التركيبة مغلقة — لا يمكن بدء ابن جديد")
        if self._child is not None:
            return self._child.pid
        self._child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(3600)"],
            env=self.child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        return self._child.pid

    def stop(self):
        """أوقف الابن (إن بدأ) وانتظر خروجه."""
        if self._child is not None:
            try:
                self._child.terminate()
                self._child.wait(timeout=10)
            except Exception:
                try:
                    self._child.kill()
                except Exception:
                    pass
            self._child = None

    def close(self):
        """أوقف الابن وامسح المجلدات المؤقتة."""
        if self._closed:
            return
        self.stop()
        self._closed = True
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def run_control(verb, target=None, handler=None, fixture=None):
    """شغّل فعل تحكم واحد عبر المعالج المنشور نفسه.

    `verb`: الفعل؛ `target`: هدف صريح (مطلوب لأفعال
    التعديل)؛ `handler`: دالة `handler(verb, target)` تنفّذ
    الفعل المنشور؛ `fixture`: تركيبة تحكم تُشتق منها
    الهدف حين يغيب `target` (لأفعال التعديل فقط — فعل
    تعديل بلا تركيبة ولا هدف مرفوض).

    يرجع نتيجة المعالج (dict)؛ ويرفع `ControlError` عند
    الرفض. فعل قراءة بلا معالج يرجع ملخص هدف/تركيبة.
    """
    if target is None and fixture is not None:
        target = fixture.target()
    require_explicit_target(verb, target)
    if handler is None:
        return {
            "verb": verb,
            "target": target.as_dict() if target is not None else None,
            "engine": FAKE_ENGINE_NAME if fixture is not None else None,
            "ok": True,
        }
    return handler(verb, target)


# ─── خريطة السلوك (CONTROL-MAP) ───
# كل مدخل: id ثابت، ووصف، وharness: هل يقوده الحزام فعلًا،
# وconstraint: القيد الصريح حيث لا يثبت الحزام شيئًا.
# القاعدة: لا مدخل بلا `harness=True` ولا `constraint` غير فارغ.
BEHAVIOR_MAP = [
    {
        "id": "fixture-isolation",
        "description": "التركيبة تستخدم مجلد بيانات مؤقتًا وhome مؤقتًا لا الحقيقيين",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "fixture-fake-engine-only",
        "description": "التركيبة تثبّت المحرك المزيف فقط (لا محرك حقيقي ولا مفاتيح)",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "fixture-free-ports",
        "description": "التركيبة تستخدم منفذين حرين على 127.0.0.1 فقط",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "fixture-env-passthrough",
        "description": "فقط متغيرات FAKE_CLAUDE_* تعبر من بيئة المُطلق إلى الابن",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "mutating-refuses-silent-target",
        "description": "أوامر التعديل ترفض الهدف الصامت (لا اكتشاف تشغيل حي)",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "read-verbs-no-target",
        "description": "أفعال القراءة تعمل بلا هدف صريح",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "unknown-verb-rejected",
        "description": "فعل تحكم مجهول مرفوض برسالة صريحة",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "fixture-cleanup",
        "description": "خروج التركيبة يوقف الابن ويمسح المجلدات المؤقتة",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "control-surface-same-actions",
        "description": "سطح التحكم يشغّل الأفعال المنشورة نفسها (نفس المعالج)",
        "harness": True,
        "constraint": "",
    },
    {
        "id": "viewer-only-behavior",
        "description": "سلوك العارض فقط (الإعدادات، السحب والإفلات، نوافذ العرض)",
        "harness": False,
        "constraint": "لا يثبته الحزام — الاستوديو CLI بلا واجهة رسومية؛ يُذكر القيد صراحة هنا ولا يُدَّعى إثباته.",
    },
]


def behavior_map_entries():
    """ارجع نسخة من خريطة السلوك (قائمة dicts)."""
    return [dict(entry) for entry in BEHAVIOR_MAP]
