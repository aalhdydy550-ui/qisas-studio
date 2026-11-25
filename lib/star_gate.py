#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""بوابة النجمة — اشتراط إضافة نجمة لمستودع qisas-studio (جولة v0.1.48).

القاعدة: من يستخدم الاستوديو يضيف نجمة (star) لمستودع
``aalhdydy550-ui/qisas-studio`` على GitHub مرة واحدة؛ بعدها
يُحفظ الفحص محليًا ولا يُسأل عنه مجددًا. الاستخدام الشخصي
غير التجاري يبقى مجانيًا دائمًا — النجمة طلب دعم لا دفع.

التحقق عبر GitHub API العام بلا توكن: ``GET
https://api.github.com/users/{username}/starred?per_page=100``
مع ترقيم الصفحات، ويُبحث عن ``full_name ==
"aalhdydy550-ui/qisas-studio"``. لا توكنات تُحفظ في ملفات
أبدًا — اسم المستخدم وحده يُحفظ في ملف الحالة.

ملف الحالة المحلي: ``<dir>/star.json`` حيث ``dir`` هو نفسه
مجلد الترخيص (``license_lib.license_dir()`` — ``~/.qisas-studio``
افتراضيًا، أو ``QISAS_LICENSE_DIR`` للاختبارات)، بصلاحية 600
وكتابة ذرية (مؤقت + ``os.replace``) ومجلد 700 — على نمط
``lib/license.py`` تمامًا. الشكل::

    {"github_user": "<اسم المستخدم>",
     "starred": true,
     "checked_at": "<ISO 8601>",
     "repo": "aalhdydy550-ui/qisas-studio"}

قواعد صريحة:
1. يُخزَّن في الـcache **النتيجة الإيجابية فقط** (``starred=True``).
   النتيجة السلبية لا تُخزَّن أبدًا — يُعاد الفحص في كل تشغيل
   حتى يضيف المستخدم النجمة.
2. السؤال عن اسم المستخدم عبر ``input()`` مرة واحدة عند أول
   تشغيل بلا cache، وفقط عندما يكون stdin تفاعليًا
   (``sys.stdin.isatty()``)؛ وإن لم يكن تفاعليًا (كرون/CI/أنبوب)
   → تحذير والسماح بالتشغيل (fail-open).
3. تعذّر الوصول لـGitHub (خطأ شبكة / 403 حد المعدل) بلا cache
   → تحذير والسماح بالتشغيل (fail-open) مع إعادة التحقق في أول
   تشغيل متصل.
4. **قيد موثَّق: إطفاء الواي فاي يتجاوز الفحص الأول.** الفحص
   يعتمد على اتصال حي بـGitHub؛ بلا شبكة لا يمكن تمييز «لم
   يضف النجمة» من «لا اتصال»، فالتصميم يختار السماح
   (fail-open) عمدًا بدل حجب مستخدم شرعي بلا نت. من يطفئ
   الواي فاي عمدًا قبل أول تشغيل يتجاوز الفحص الأول — هذا
   مقبول عمدًا لهذه الجولة (الهدف تذكير المستخدم الشريف
   بالدعم لا منع المخادع)؛ وأي تصلّب (تحقق لاحق إلزامي
   عند عودة الشبكة) عمل لاحق إن طُلب. لاحظ أن التجاوز
   مؤقت: أول تشغيل متصل تفاعلي بلا cache يعيد الفحص فورًا.
5. إعفاء المالك: إن كان ``license_lib.license_status()["status"]
   == "owner"`` فلا سؤال ولا شبكة ولا فحص إطلاقًا.
6. متغير البيئة ``QISAS_SKIP_STAR_CHECK=1`` يعطّل الفحص كليًا —
   **للاختبار فقط**، وليس طريقًا موثقًا للمستخدم.
7. لا فحص جديد في ``doctor`` في هذه الجولة.

الوحدة مستقلة عن ``studio``: لا تستورد إلا ``lib.license``
(للمسار وإعفاء المالك) والمكتبة القياسية فقط.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

from lib import license as license_lib

REPO = "aalhdydy550-ui/qisas-studio"
REPO_URL = "https://github.com/" + REPO
API_STARRED_URL = "https://api.github.com/users/%s/starred?per_page=100"
SKIP_ENV = "QISAS_SKIP_STAR_CHECK"
STATE_FILENAME = "star.json"
_PER_PAGE = 100
_MAX_PAGES = 100
_TIMEOUT_SECONDS = 10


class StarCheckUnavailable(Exception):
    """تعذّر الوصول لـGitHub (شبكة / حد معدل / خطأ خادم) —
    يستدعي fail-open لا رفضًا."""


# ------------------------------------------------------------------
# المسارات والحالة (على نمط lib/license.py)
# ------------------------------------------------------------------

def state_path(directory=None):
    """المسار الكامل لملف الحالة star.json (مجلد الترخيص نفسه)."""
    return os.path.join(directory or license_lib.license_dir(),
                        STATE_FILENAME)


def _read_cache():
    """ارجع cache النجمة الإيجابي أو None.

    None = لا ملف، أو ملف تالف، أو نتيجة غير إيجابية، أو مستودع
    مختلف — كلها تُعامل كغياب cache (يُعاد الفحص).
    """
    path = state_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("starred") is not True:
        return None
    if data.get("repo") != REPO:
        return None
    user = data.get("github_user")
    if not isinstance(user, str) or not user.strip():
        return None
    return {"github_user": user.strip(),
            "starred": True,
            "checked_at": data.get("checked_at"),
            "repo": REPO}


def _save_cache(username):
    """احفظ نتيجة إيجابية ذريًا (مؤقت + os.replace) بصلاحية 600،
    ومجلد الحالة 700. ترجع نسخة من الحالة المحفوظة."""
    directory = license_lib.license_dir()
    os.makedirs(directory, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    path = state_path(directory)
    tmp = path + ".tmp"
    payload = {"github_user": username,
               "starred": True,
               "checked_at": datetime.now(timezone.utc).isoformat(),
               "repo": REPO}
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return dict(payload)


# ------------------------------------------------------------------
# التحقق عبر GitHub API العام (بلا توكن)
# ------------------------------------------------------------------

def _default_fetch(url):
    """اجلب صفحة JSON من GitHub API العام — ترجع قائمة محللة."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "qisas-studio-star-gate",
                 "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
        return json.load(resp)


def has_starred(username, fetcher=None):
    """هل أضاف ``username`` نجمة للمستودع؟

    fetcher: دالة ``fetcher(url) -> list`` قابلة للحقن
    (الاختبارات)؛ الافتراضي يجلب عبر urllib. ترجع True/False.
    ترفع ``StarCheckUnavailable`` عند تعذّر الوصول (شبكة / 403
    حد المعدل / خطأ خادم)؛ واسم مستخدم غير موجود (404) يُعامل
    كغير مضيف للنجمة (False) لا كخطأ.
    """
    fetch = fetcher or _default_fetch
    page = 1
    while page <= _MAX_PAGES:
        url = API_STARRED_URL % username + "&page=%d" % page
        try:
            items = fetch(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if e.code == 403:
                raise StarCheckUnavailable(
                    "رفض GitHub الطلب (403 — حد المعدل على الأرجح)")
            raise StarCheckUnavailable(
                "خطأ HTTP من GitHub: %s" % e.code)
        except urllib.error.URLError as e:
            raise StarCheckUnavailable(
                "تعذّر الوصول إلى GitHub: %s" % e.reason)
        except (OSError, ValueError) as e:
            raise StarCheckUnavailable(
                "تعذّر التحقق من GitHub: %s" % e)
        if not isinstance(items, list):
            raise StarCheckUnavailable(
                "رد غير متوقع من GitHub (ليس قائمة)")
        for item in items:
            if isinstance(item, dict) \
                    and item.get("full_name") == REPO:
                return True
        if len(items) < _PER_PAGE:
            return False
        page += 1
    return False


# ------------------------------------------------------------------
# الرسائل
# ------------------------------------------------------------------

def denial_message():
    """رسالة الرفض العربية الكاملة (للطباعة عند الرفض)."""
    return ("النجمة مطلوبة لاستخدام qisas-studio: أضف نجمة (★) "
            "لمستودع المشروع على GitHub ثم أعد التشغيل:\n"
            "  %s\n"
            "الاستخدام الشخصي غير التجاري يبقى مجانيًا دائمًا — "
            "النجمة دعم للمشروع لا دفع. بعد إضافتها يُحفظ الفحص "
            "على جهازك ولا تُسأل عنها مجددًا."
            % REPO_URL)


def _fail_open_warning(reason):
    """تحذير fail-open (للطباعة عند السماح رغم تعذّر التحقق)."""
    return ("تحذير: تعذّر التحقق من نجمة GitHub (%s) — يُسمح "
            "بالتشغيل الآن، وسيُعاد التحقق في أول تشغيل متصل."
            % reason)


# ------------------------------------------------------------------
# البوابة
# ------------------------------------------------------------------

def check_star_gate(fetcher=None, input_fn=None):
    """بوابة النجمة: True = مسموح بالتشغيل، False = مرفوض.

    تطبع التحذيرات ورسالة الرفض بنفسها (عربي). الترتيب:
    تعطيل بيئة الاختبار → إعفاء المالك → cache إيجابي →
    stdin غير تفاعلي (fail-open) → سؤال مرة واحدة → فحص
    GitHub (fail-open عند تعذّره) → حفظ الإيجابي فقط.
    """
    if os.environ.get(SKIP_ENV, "").strip() == "1":
        return True
    try:
        if license_lib.license_status()["status"] == "owner":
            return True
    except Exception:
        pass
    if _read_cache() is not None:
        return True
    if not sys.stdin.isatty():
        print(_fail_open_warning(
            "الإدخال غير تفاعلي (كرون/CI/أنبوب) — لا يمكن سؤالك "
            "عن اسم مستخدم GitHub"))
        return True
    ask = input_fn or input
    try:
        username = ask("اسم مستخدم GitHub الخاص بك (لإضافة نجمة "
                       "لمستودع qisas-studio): ").strip()
    except (EOFError, KeyboardInterrupt):
        print(_fail_open_warning("تعذّر قراءة اسم المستخدم"))
        return True
    if not username:
        print(_fail_open_warning("لم يُدخل اسم مستخدم"))
        return True
    try:
        starred = has_starred(username, fetcher=fetcher)
    except StarCheckUnavailable as e:
        print(_fail_open_warning(str(e)))
        return True
    if starred:
        try:
            _save_cache(username)
        except OSError:
            pass
        return True
    print(denial_message())
    return False


__all__ = ["REPO", "REPO_URL", "SKIP_ENV", "STATE_FILENAME",
           "StarCheckUnavailable", "state_path", "has_starred",
           "check_star_gate", "denial_message"]
