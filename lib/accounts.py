#!/usr/bin/env python3
"""فحوصات الحسابات — `studio.py doctor --accounts` (قراءة فقط).

ثلاثة فحوصات منفصلة عن فحوصات البيئة الـ24، بعدّادها الخاص:

1. صفحة فيسبوك: معرّف الصفحة من الإعداد + قراءة آخر المنشورات
   عبر facebook-cli (نفس مسار `analyze` — قراءة فقط). أي تعذر
   قراءة يُبلَّغ تحذيرًا لا خطأً (قد يكون بطاقة موافقة عابرة أو
   شبكة)، أما غياب معرّف الصفحة نفسه فخطأ.
2. توكن يوتيوب: الملف موجود وصالح وفيه refresh_token والنطاق
   youtube.upload. وضع الاختبار (Testing) يُنهي صلاحية التوكن
   بعد 7 أيام من الموافقة — التقدير من تاريخ إنشاء الملف،
   والتحذير عند 3 أيام أو أقل، والخطأ عند الانتهاء.
3. رصيد Veo المسجَّل: من قسم `veo` في الإعداد (ليس حيًا من API)
   + توقع الأيام من `balance.forecast`؛ والتحذير عند رصيد أقل
   من فيديو Veo واحد (120 وحدة).

لا يكتب شيئًا ولا ينشر شيئًا — قراءة ملفات واستدعاء قراءة واحد.
"""
import datetime
import json
import os

from lib import analyze as analyze_lib
from lib import balance as balance_lib
from lib import publish as publish_lib

TESTING_TOKEN_DAYS = 7
TOKEN_WARN_DAYS = 3
VEO_ONE_VIDEO_UNITS = 120
YT_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
DEFAULT_TOKEN_PATH = "~/workspace/studio/youtube-token.json"


def _check(name, ok, level, detail, fix=""):
    return {"name": name, "ok": ok, "level": level,
            "detail": detail, "fix": fix}


def check_facebook_page(cfg, runner=None):
    """صفحة فيسبوك: المعرّف + قراءة آخر المنشورات."""
    name = "صفحة فيسبوك (قراءة المنشورات)"
    page_id = str((cfg.get("publish") or {}).get("page_id") or "").strip()
    if not page_id:
        return _check(name, False, "error",
                      "معرّف الصفحة مفقود في الإعداد",
                      "اضبط publish.page_id في config.yaml "
                      "أو عبر `studio.py init --page-id`")
    if not page_id.isdigit():
        return _check(name, False, "error",
                      "معرّف الصفحة ليس أرقامًا: %s" % page_id,
                      "صحّح publish.page_id في config.yaml")
    fb = publish_lib.find_facebook_bin()
    if not fb:
        return _check(name, False, "warn",
                      "facebook-cli غير متاح — لا يمكن التحقق من الصفحة",
                      "ثبّت facebook-cli أو أكمل الربط (انظر README)")
    entry, reason = analyze_lib.fb_last_video(fb, page_id, run=runner)
    if entry is not None:
        caption = (entry.get("caption") or "")[:40]
        views = entry.get("views")
        detail = "الصفحة متاحة — آخر منشور: %s" % (caption or
                                                    entry.get("object_id")
                                                    or "؟")
        if views is not None:
            detail += " (%s مشاهدة)" % views
        return _check(name, True, "error", detail)
    return _check(name, False, "warn",
                  "تعذر قراءة منشورات الصفحة: %s" % (reason or "؟"),
                  "تحقق من الاتصال وصلاحيات الصفحة ثم أعد الفحص")


def check_youtube_token(cfg, today=None):
    """توكن يوتيوب: الصلاحية وعمر الموافقة في وضع الاختبار."""
    name = "توكن يوتيوب (OAuth)"
    today = today or datetime.date.today()
    token_path = os.path.expanduser(
        (cfg.get("publish") or {}).get("youtube_token")
        or DEFAULT_TOKEN_PATH)
    if not os.path.isfile(token_path):
        return _check(name, False, "warn",
                      "لا يوجد توكن يوتيوب — النشر على يوتيوب يدوي",
                      "أكمل `studio.py youtube-auth` مرة واحدة")
    try:
        with open(token_path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        return _check(name, False, "error",
                      "ملف التوكن تالف أو غير مقروء: %s" % e,
                      "احذفه وأعد `studio.py youtube-auth`")
    if not isinstance(data, dict) or not data.get("refresh_token"):
        return _check(name, False, "error",
                      "التوكن بلا refresh_token — لا يمكن تجديده",
                      "أعد `studio.py youtube-auth`")
    scopes = data.get("scopes") or []
    if YT_UPLOAD_SCOPE not in scopes:
        return _check(name, False, "warn",
                      "التوكن بلا نطاق youtube.upload — الرفع سيفشل",
                      "أعد `studio.py youtube-auth` بنطاق الرفع")
    # وضع الاختبار: صلاحية التوكن 7 أيام من الموافقة (تاريخ إنشاء
    # الملف هو أقرب تقدير للموافقة — لا حقل تاريخ في الملف).
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(token_path)).date()
    days_left = TESTING_TOKEN_DAYS - (today - mtime).days
    expires = mtime + datetime.timedelta(days=TESTING_TOKEN_DAYS)
    if days_left <= 0:
        return _check(name, False, "error",
                      "انتهت صلاحية توكن يوتيوب (وضع الاختبار: 7 أيام "
                      "من %s)" % mtime.isoformat(),
                      "أعد الموافقة عبر `studio.py youtube-auth`")
    if days_left <= TOKEN_WARN_DAYS:
        return _check(name, False, "warn",
                      "توكن يوتيوب ينتهي خلال %d %s (حوالي %s) — "
                      "أعد الموافقة قريبًا"
                      % (days_left, "يوم" if days_left == 1 else "أيام",
                         expires.isoformat()),
                      "أعد الموافقة عبر `studio.py youtube-auth`")
    return _check(name, True, "error",
                  "توكن يوتيوب ساري — ينتهي خلال %d أيام (حوالي %s؛ "
                  "التقدير من تاريخ إنشاء الملف)"
                  % (days_left, expires.isoformat()))


def check_veo_balance(cfg, today=None):
    """رصيد Veo المسجَّل + توقع الأيام."""
    name = "رصيد Veo المسجَّل"
    veo = cfg.get("veo") or {}
    if "balance_units" not in veo:
        return _check(name, False, "warn",
                      "رصيد Veo غير مسجَّل في الإعداد",
                      "حدّث veo.balance_units في config.yaml بعد كل "
                      "توليد في Flow")
    try:
        result = balance_lib.forecast(
            veo.get("balance_units", balance_lib.DEFAULT_BALANCE),
            veo.get("renews", balance_lib.DEFAULT_RENEWS),
            veo.get("daily_cost_min", balance_lib.DEFAULT_COST_MIN),
            veo.get("daily_cost_max", balance_lib.DEFAULT_COST_MAX),
            today=today)
    except (ValueError, TypeError) as e:
        return _check(name, False, "error",
                      "قيم رصيد غير صالحة: %s" % e,
                      "صحّح قسم veo في config.yaml")
    balance = result["balance_units"]
    detail = ("%d وحدة — تكفي %.1f يومًا في المتوسط؛ التجديد %s"
              % (balance, result["days_avg"], result["renews"]))
    if balance < VEO_ONE_VIDEO_UNITS:
        return _check(name, False, "warn",
                      detail + " — أقل من فيديو Veo واحد (120 وحدة)",
                      "فيديوهات الغد عبر OpenMontage بلا رصيد حتى "
                      "التجديد")
    return _check(name, True, "error", detail)


def run_account_checks(cfg, runner=None, today=None):
    """شغّل فحوصات الحسابات الثلاثة. يرجع قائمة قواميس doctor."""
    return [check_facebook_page(cfg, runner=runner),
            check_youtube_token(cfg, today=today),
            check_veo_balance(cfg, today=today)]
