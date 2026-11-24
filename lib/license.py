#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تتبع الترخيص — شهر مجاني لكل مستخدم جديد (جولة v0.1.43، بند 2).

القاعدة التجارية (من README):
- الاستخدام الشخصي غير التجاري مجاني دائمًا (PolyForm Noncommercial).
- الاستخدام التجاري: 1000 جنيه للأفراد / 5000 للشركات، بعد فترة
  تجربة 30 يومًا تبدأ من أول تشغيل.

ملف الحالة المحلي: ``<dir>/license.json`` حيث ``dir`` هو
``~/.qisas-studio`` افتراضيًا، أو ما يشير إليه متغير البيئة
``QISAS_LICENSE_DIR`` (للتوجيه في الاختبارات إلى مجلد مؤقت).
شكل الملف::

    {"kind": "trial" | "owner" | "commercial",
     "first_run": "YYYY-MM-DD",
     "license_key": "<مفتاح الرخصة المدفوعة>" | null,
     "license_type": "individual" | "company" | null,
     "licensed_on": "YYYY-MM-DD" | null}

الحالات التي يرجعها ``license_status``:
- ``owner`` — تثبيت صاحب المشروع/المُرخِّص؛ معفى دائمًا من الفحص،
  فلا يغلق أي أمر أبدًا (وهذا ما يحمي خط صاحب الاستوديو نفسه،
  ومنه الكرون اليومي 20:03 الذي يشغّل ``studio.py long-video``
  على هذه الآلة).
- ``trial`` — داخل الـ30 يومًا (اليوم 1 = تاريخ أول تشغيل،
  ``days_left`` من 30 إلى 1)؛ وإن لم يُسجَّل أول تشغيل بعد
  فالتجربة «لم تبدأ» و``days_left`` = 30.
- ``trial_expired`` — مرّت الـ30 يومًا بلا رخصة مدفوعة
  (``days_left`` = 0)؛ الاستخدام التجاري متوقف.
- ``licensed`` — ``kind`` تجاري مع ``license_key`` موجود.

قيود صريحة (لا تُقرأ كضمانات):
1. لا توليد مفاتيح ولا تحقق منها عبر شبكة في هذه الجولة —
   وجود ملف ترخيص يضعه المستخدم (عبر ``mark_licensed``)
   يكفي، والتحقق الكامل من المفتاح (توقيع/خادم) مؤجل لجولة
   لاحقة. مفتاح مزوَّر يدويًا في الملف سيُقبل.
2. لا حماية ضد العبث: من يحذف مجلد الحالة
   (``~/.qisas-studio``) يعيد التجربة من الصفر، لأن تاريخ أول
   تشغيل يعيش في هذا الملف وحده ولا توجد بصمة ثانية (ملف
   مرساة آخر أو معرّف آلة). هذا مقبول عمدًا لهذه الجولة —
   الهدف تذكير المستخدم الشريف بموعد الدفع لا منع المخادع —
   وأي تصلّب (مرساة ثانية/توقيع) عمل لاحق إن طُلب.
3. ``license_status`` و``commercial_allowed`` قراءة فقط ولا
   تنشئان ملف الحالة أبدًا؛ الساعة تبدأ فقط عندما يستدعي
   التوصيل ``record_first_run`` قبل الفحص (انظر مواصفة
   التوصيل في تقرير البند). ملف تالف أو ``first_run`` غير
   صالح يُعامل كتجربة لم تبدأ (مع ``corrupt: True``) ولا
   يُسقط أي أمر — الفشل هنا مفتوح لا مغلق، عمدًا.
4. تاريخ مستقبلي في ``first_run`` (انحراف ساعة أو تعديل يدوي)
   يُعامل كيوم أول (30 يومًا متبقية) ولا يُحسب منتهيًا.

الوحدة مستقلة تمامًا: لا تستورد أي وحدة lib أخرى ولا ``studio``،
ولا تُوصَّل في ``studio.py`` من هنا — التوصيل للمنسّق (انظر
تقرير البند 2 في الجولة).
"""
import json
import os
from datetime import date, datetime

TRIAL_DAYS = 30

LICENSE_DIR_ENV = "QISAS_LICENSE_DIR"
DEFAULT_LICENSE_DIR = os.path.join("~", ".qisas-studio")
STATE_FILENAME = "license.json"

PAYMENT_NUMBER = "01023468196"
PRICE_INDIVIDUAL_EGP = 1000
PRICE_COMPANY_EGP = 5000

KINDS = ("trial", "owner", "commercial")
LICENSE_TYPES = ("individual", "company")

_LICENSE_TYPE_AR = {"individual": "أفراد", "company": "شركات"}


# ------------------------------------------------------------------
# المسارات والتواريخ
# ------------------------------------------------------------------

def license_dir():
    """مجلد حالة الترخيص: QISAS_LICENSE_DIR أو ~/.qisas-studio."""
    override = os.environ.get(LICENSE_DIR_ENV, "").strip()
    if override:
        return os.path.expanduser(override)
    return os.path.expanduser(DEFAULT_LICENSE_DIR)


def state_path(directory=None):
    """المسار الكامل لملف الحالة license.json."""
    return os.path.join(directory or license_dir(), STATE_FILENAME)


def _today(now=None):
    """طبيع ``now`` إلى date: None = اليوم المحلي؛ date كما هو؛
    datetime = تاريخه المحلي. أي نوع آخر = TypeError."""
    if now is None:
        return datetime.now().astimezone().date()
    if isinstance(now, datetime):
        return now.date()
    if isinstance(now, date):
        return now
    raise TypeError("now يجب أن يكون date أو datetime أو None")


def _parse_date(text):
    """حلّل تاريخ ISO (YYYY-MM-DD) أو ارجع None."""
    if not isinstance(text, str):
        return None
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


# ------------------------------------------------------------------
# قراءة/كتابة الحالة (داخلية)
# ------------------------------------------------------------------

def _read_state():
    """ارجع (state أو None، corrupt؟).

    None = لا يوجد ملف بعد. corrupt=True = الملف موجود لكنه
    JSON تالف أو حقوله خارج القيم المقبولة — يُعامل كغياب.
    """
    path = state_path()
    if not os.path.isfile(path):
        return None, False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None, True
    if not isinstance(data, dict):
        return None, True
    kind = data.get("kind", "trial")
    if kind not in KINDS:
        return None, True
    first_run = data.get("first_run")
    if first_run is not None and _parse_date(first_run) is None:
        return None, True
    key = data.get("license_key")
    if key is not None and (not isinstance(key, str)
                            or not key.strip()):
        return None, True
    ltype = data.get("license_type")
    if ltype is not None and ltype not in LICENSE_TYPES:
        return None, True
    licensed_on = data.get("licensed_on")
    if licensed_on is not None and _parse_date(licensed_on) is None:
        return None, True
    state = {"kind": kind,
             "first_run": first_run,
             "license_key": key.strip() if key else None,
             "license_type": ltype,
             "licensed_on": licensed_on}
    return state, False


def _save_state(state):
    """احفظ الحالة ذريًا (ملف مؤقت + os.replace) بصلاحية 600،
    ومجلد الحالة 700. ترجع نسخة من الحالة المحفوظة."""
    directory = license_dir()
    os.makedirs(directory, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    path = state_path(directory)
    tmp = path + ".tmp"
    payload = {"kind": state["kind"],
               "first_run": state.get("first_run"),
               "license_key": state.get("license_key"),
               "license_type": state.get("license_type"),
               "licensed_on": state.get("licensed_on")}
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return dict(payload)


def _public_state(state):
    """نسخة الحالة بلا مفاتيح داخلية (لا شيء داخلي حاليًا —
    الدالة حارس للمستقبل)."""
    return dict(state)


# ------------------------------------------------------------------
# واجهة الترخيص
# ------------------------------------------------------------------

def record_first_run(now=None):
    """سجّل تاريخ أول تشغيل مرة واحدة ولا تغيّره أبدًا بعد ذلك.

    - لا ملف بعد: أنشئ حالة trial بتاريخ اليوم.
    - ملف موجود بلا first_run (أو تالف): أنشئ/أصلح بتاريخ اليوم
      مع الحفاظ على kind الموجود إن كان صالحًا.
    - ملف فيه first_run صالح: ارجع الحالة كما هي بلا أي كتابة.
    ترجع الحالة المحفوظة/المقروءة.
    """
    today = _today(now)
    state, _corrupt = _read_state()
    if state is not None and state.get("first_run"):
        return _public_state(state)
    if state is None:
        state = {"kind": "trial", "first_run": None,
                 "license_key": None, "license_type": None,
                 "licensed_on": None}
    state["first_run"] = today.isoformat()
    return _public_state(_save_state(state))


def license_status(now=None):
    """حالة الترخيص الآن (قراءة فقط — لا تنشئ ملف الحالة).

    ترجع قاموسًا: {"status", "kind", "first_run", "days_left",
    "licensed", "license_type", "has_license_key", "licensed_on",
    "corrupt"} حيث status واحد من owner/trial/trial_expired/
    licensed، وdays_left عدد صحيح (30..0) في التجربة أو None
    في owner/licensed.
    """
    today = _today(now)
    state, corrupt = _read_state()
    base = {"first_run": None, "days_left": None,
            "licensed": False, "license_type": None,
            "has_license_key": False, "licensed_on": None,
            "corrupt": corrupt}
    if state is None:
        base.update({"status": "trial", "kind": "trial",
                     "days_left": TRIAL_DAYS})
        return base
    kind = state["kind"]
    first_run = _parse_date(state.get("first_run"))
    base.update({"kind": kind,
                 "first_run": (first_run.isoformat()
                               if first_run else None),
                 "license_type": state.get("license_type"),
                 "has_license_key": bool(state.get("license_key")),
                 "licensed_on": state.get("licensed_on")})
    if kind == "owner":
        base.update({"status": "owner"})
        return base
    if kind == "commercial" and state.get("license_key"):
        base.update({"status": "licensed", "licensed": True})
        return base
    # تجاري بلا مفتاح، أو trial: الحكم بتاريخ أول تشغيل.
    if first_run is None:
        base.update({"status": "trial", "days_left": TRIAL_DAYS})
        return base
    elapsed = (today - first_run).days
    if elapsed < 0:
        # تاريخ مستقبلي (انحراف ساعة/تعديل يدوي): يوم أول.
        elapsed = 0
    days_left = TRIAL_DAYS - elapsed
    if days_left >= 1:
        base.update({"status": "trial", "days_left": days_left})
    else:
        base.update({"status": "trial_expired", "days_left": 0})
    return base


def _trial_end(first_run_iso):
    """تاريخ انتهاء التجربة (أول تشغيل + 29 يومًا) أو None."""
    first = _parse_date(first_run_iso) if first_run_iso else None
    if first is None:
        return None
    from datetime import timedelta
    return first + timedelta(days=TRIAL_DAYS - 1)


def commercial_allowed(now=None):
    """هل الاستخدام التجاري مسموح الآن؟ ترجع (bool, رسالة عربية).

    True في owner/trial/licensed (وتجربة لم تبدأ بعد)؛ False
    فقط في trial_expired مع رسالة تذكر الـ30 يومًا والسعرين
    وطريقة الدفع. قراءة فقط — لا تسجّل أول تشغيل.
    """
    st = license_status(now)
    status = st["status"]
    if status == "owner":
        return True, ("الترخيص: مالك المشروع — معفى دائمًا؛ "
                      "الاستخدام التجاري مسموح بلا قيد.")
    if status == "licensed":
        return True, ("الترخيص: تجاري مدفوع ساري — الاستخدام "
                      "التجاري مسموح.")
    if status == "trial":
        if st["first_run"] is None:
            return True, ("فترة التجربة (30 يومًا) لم تبدأ بعد — "
                          "يبدأ العدّ من أول تشغيل تجاري؛ الاستخدام "
                          "التجاري مسموح الآن.")
        end = _trial_end(st["first_run"])
        return True, ("فترة تجربة: بقي %d يومًا من 30 (تنتهي في %s) — "
                      "الاستخدام التجاري مسموح حتى انتهائها."
                      % (st["days_left"], end.isoformat()))
    return False, expired_message(st)


def expired_message(state=None):
    """رسالة انتهاء التجربة العربية الكاملة (للطباعة/الرفض)."""
    st = state or license_status()
    first = st.get("first_run") or "غير مسجَّل"
    return ("انتهت فترة التجربة المجانية (30 يومًا، بدأت في %s) "
            "بلا رخصة تجارية — الاستخدام التجاري متوقف.\n"
            "للاستمرار: رخصة تجارية — للأفراد %d جنيه، وللشركات "
            "%d جنيه. الدفع: فودافون كاش على %s، ثم افتح Issue "
            "في مستودع qisas-studio مع لقطة شاشة للتحويل ونوع "
            "الرخصة (أفراد/شركات)، وسيُرسل لك ملف الترخيص.\n"
            "الاستخدام الشخصي غير التجاري يبقى مجانيًا دائمًا."
            % (first, PRICE_INDIVIDUAL_EGP, PRICE_COMPANY_EGP,
               PAYMENT_NUMBER))


def set_owner(now=None):
    """أنشئ/حوّل الحالة إلى owner (معفى دائمًا).

    يستخدمها المنسّق لتهيئة آلة صاحب المشروع فقط — لا تُنادَ
    من أي كود تلقائي. تحافظ على first_run الموجود، وتسجّل
    اليوم إن غاب. ترجع الحالة المحفوظة.
    """
    today = _today(now)
    state, _corrupt = _read_state()
    if state is None:
        state = {"kind": "owner", "first_run": None,
                 "license_key": None, "license_type": None,
                 "licensed_on": None}
    state["kind"] = "owner"
    if not state.get("first_run"):
        state["first_run"] = today.isoformat()
    return _public_state(_save_state(state))


def mark_licensed(key, license_type=None, now=None):
    """سجّل رخصة تجارية مدفوعة (يضعها المستخدم/المنسّق يدويًا).

    key: نص المفتاح كما في ملف الترخيص المُرسَل (لا يُتحقق
    منه هنا — انظر قيود الوحدة)؛ license_type: "individual"
    أو "company" أو None. ValueError على مفتاح فارغ أو نوع
    غير مقبول. ترجع الحالة المحفوظة.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("مفتاح الترخيص فارغ — ضع مفتاحًا صالحًا")
    if license_type is not None and license_type not in LICENSE_TYPES:
        raise ValueError("نوع الرخصة غير مقبول: %s (المقبول: %s)"
                         % (license_type, "/".join(LICENSE_TYPES)))
    today = _today(now)
    state, _corrupt = _read_state()
    if state is None:
        state = {"kind": "commercial", "first_run": None,
                 "license_key": None, "license_type": None,
                 "licensed_on": None}
    state["kind"] = "commercial"
    state["license_key"] = key.strip()
    state["license_type"] = license_type
    state["licensed_on"] = today.isoformat()
    if not state.get("first_run"):
        state["first_run"] = today.isoformat()
    return _public_state(_save_state(state))


def status_lines(state=None):
    """أسطر عربية جاهزة للطباعة من حالة license_status.

    state قاموس من license_status (أو None فيُحسب الآن).
    لا تتضمن مفتاح الترخيص أبدًا — المفتاح سرّ لا يُطبع.
    """
    st = state if state is not None else license_status()
    lines = []
    if st.get("corrupt"):
        lines.append("تحذير: ملف حالة الترخيص تالف — يُعامل كتجربة "
                     "لم تبدأ؛ أعد إنشاءه أو تحقق منه يدويًا.")
    status = st["status"]
    if status == "owner":
        lines.append("الترخيص: مالك المشروع (owner) — معفى دائمًا "
                     "من فحص التجربة.")
        lines.append("الاستخدام التجاري مسموح بلا قيد.")
        return lines
    if status == "licensed":
        ltype = _LICENSE_TYPE_AR.get(st.get("license_type"),
                                     "غير محدد")
        lines.append("الترخيص: تجاري مدفوع — نوع الرخصة: %s."
                     % ltype)
        if st.get("licensed_on"):
            lines.append("صدرت الرخصة في %s." % st["licensed_on"])
        lines.append("الاستخدام التجاري مسموح.")
        return lines
    if status == "trial":
        if st.get("first_run") is None:
            lines.append("الترخيص: فترة التجربة (30 يومًا) لم تبدأ "
                         "بعد — تبدأ من أول تشغيل.")
        else:
            end = _trial_end(st["first_run"])
            lines.append("الترخيص: فترة تجربة — بقي %d يومًا من 30 "
                         "(تنتهي في %s؛ أول تشغيل %s)."
                         % (st["days_left"], end.isoformat(),
                            st["first_run"]))
        lines.append("الاستخدام الشخصي غير التجاري مجاني دائمًا؛ "
                     "والتجاري يحتاج رخصة مدفوعة بعد انتهاء التجربة "
                     "(أفراد %d جنيه / شركات %d جنيه)."
                     % (PRICE_INDIVIDUAL_EGP, PRICE_COMPANY_EGP))
        return lines
    # trial_expired
    lines.append("الترخيص: انتهت فترة التجربة (30 يومًا، بدأت في %s)."
                 % (st.get("first_run") or "غير مسجَّل"))
    lines.append("الاستخدام التجاري متوقف حتى شراء رخصة: أفراد %d "
                 "جنيه / شركات %d جنيه — فودافون كاش %s ثم Issue "
                 "في المستودع مع لقطة شاشة للتحويل."
                 % (PRICE_INDIVIDUAL_EGP, PRICE_COMPANY_EGP,
                    PAYMENT_NUMBER))
    lines.append("الاستخدام الشخصي غير التجاري يبقى مجانيًا دائمًا.")
    return lines


def doctor_check(now=None):
    """فحص ترخيص بصيغة فحوصات doctor: {"name", "ok", "level",
    "detail", "fix"} — للربط في `doctor` لاحقًا (لا يُستدعى
    من هنا). التجربة التي بقي لها ≤7 أيام تحذير؛ والمنتهية
    خطأ؛ وowner/licensed/تجربة واسعة سليمة."""
    st = license_status(now)
    name = "الترخيص (license)"
    if st["status"] == "owner":
        return {"name": name, "ok": True, "level": "ok",
                "detail": "مالك المشروع — معفى دائمًا",
                "fix": ""}
    if st["status"] == "licensed":
        return {"name": name, "ok": True, "level": "ok",
                "detail": "تجاري مدفوع ساري",
                "fix": ""}
    if st["status"] == "trial_expired":
        return {"name": name, "ok": False, "level": "error",
                "detail": ("انتهت فترة التجربة (30 يومًا من %s) "
                           "بلا رخصة تجارية"
                           % (st.get("first_run") or "غير مسجَّل")),
                "fix": ("اشترِ رخصة تجارية (أفراد %d جنيه / شركات "
                        "%d جنيه): فودافون كاش %s ثم Issue في "
                        "المستودع مع لقطة الشاشة"
                        % (PRICE_INDIVIDUAL_EGP, PRICE_COMPANY_EGP,
                           PAYMENT_NUMBER))}
    if st.get("first_run") is None:
        return {"name": name, "ok": True, "level": "ok",
                "detail": "فترة التجربة (30 يومًا) لم تبدأ بعد",
                "fix": ""}
    if st["days_left"] <= 7:
        return {"name": name, "ok": False, "level": "warn",
                "detail": ("فترة التجربة تنتهي قريبًا — بقي %d أيام "
                           "(تنتهي في %s)"
                           % (st["days_left"],
                              _trial_end(st["first_run"]).isoformat())),
                "fix": ("اشترِ رخصة تجارية قبل انتهائها (أفراد %d "
                        "جنيه / شركات %d جنيه): فودافون كاش %s"
                        % (PRICE_INDIVIDUAL_EGP, PRICE_COMPANY_EGP,
                           PAYMENT_NUMBER))}
    return {"name": name, "ok": True, "level": "ok",
            "detail": ("فترة تجربة — بقي %d يومًا من 30"
                       % st["days_left"]),
            "fix": ""}


__all__ = ["TRIAL_DAYS", "LICENSE_DIR_ENV", "PAYMENT_NUMBER",
           "PRICE_INDIVIDUAL_EGP", "PRICE_COMPANY_EGP",
           "license_dir", "state_path", "record_first_run",
           "license_status", "commercial_allowed", "expired_message",
           "set_owner", "mark_licensed", "status_lines",
           "doctor_check"]
