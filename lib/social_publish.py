#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""نشر TikTok وInstagram — الجولة 7 (v0.1.31).

يمتد `publish --platforms` ليشمل tiktok وinstagram إضافة إلى
facebook وyoutube.

صراحة مهمة: لا حسابات TikTok/Instagram مربوطة حتى الآن — فالرفع
الحقيقي غير مختبر حيًا. ما هو جاهز ومختبَر:
- `--dry-run`: يطبع طلبات API الدقيقة كاملة بلا أي اتصال.
- `tiktok-auth` / `instagram-auth`: تطبعان الخطوات اليدوية الدقيقة
  لربط الحساب، وتحفظان أي توكن يُعطى في ملف 600 (بلا عرضه).
- بلا توكن: يُكتب «حزمة رفع يدوي» (metadata + steps) مثل يوتيوب،
  ويرجع الأمر 1 — بلا ادعاء رفع لم يحدث.
- بتوكن: مسارا الرفع الحقيقيان (`upload_tiktok` /
  `upload_instagram`) عبر urllib — منفَّذان لكن غير مختبَرين حيًا
  (يُعلن ذلك في المخرجات).

TikTok — Content Posting API:
  POST /v2/post/publish/video/init/ (post_info + source_info
  FILE_UPLOAD مع تقسيم المقاطع) ثم PUT المقاطع ثم استعلام الحالة.
Instagram — Graph API (Reels):
  POST /{ig-user-id}/media (media_type=REELS, upload_type=resumable)
  → يرجع id فقط (بلا upload_url)؛ ثم POST المقاطع إلى
  https://rupload.facebook.com/ig-api-upload/{version}/{id}
  برأسي offset وfile_size وتخويل OAuth؛ ثم انتظار حالة
  الحاوية FINISHED (GET ?fields=status_code) ثم POST
  /{ig-user-id}/media_publish.
  (الرفع القابل للاستئناف متاح فقط لتطبيقات Facebook Login
  for Business — حسب توثيق Meta.)

جولة v0.1.39 — إكمال المسارين كوديًا (بلا اختبار حي بعد):
- `validate_social_payload`: تحقق كامل قبل أي شبكة — الفيديو
  موجود وسليم (mp4 غير فارغ)، النص غير فارغ وضمن حد المنصة
  (2200 حرفًا للمنصتين)، الوسوم ضمن حد إنستغرام (30 وسمًا)،
  المدة والأبعاد (عمودي 9:16) والصوت عند توفر معلومات probe،
  والمصغرة (إن أُعطيت) موجودة وبأبعاد 720×1280 — برسائل عربية.
- `require_social_config`: تحقق من الإعدادات (توكن/معرّف حساب)
  برسائل عربية عبر lib.errors عند النقص.
- `dry_run_summary`: يبني الحمولة كاملة ويتحقق منها ويرجع
  ملخصها دون أي طلب شبكة (لا يقرأ التوكن أصلًا).
- `normalize_result` / `format_result`: شكل نتيجة موحّد مع
  مسارات النشر القائمة (منصة + معرّف + حالة + رابط إن وُجد).
- `build_social_payload`: موزّع واحد لبناء حمولة أي منصة.
"""
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from lib import errors as errors_lib
from lib import retry_policy as retry_lib

import json
import math
import os
import time
import urllib.error
import urllib.request

TIKTOK_API_BASE = "https://open.tiktokapis.com"
TIKTOK_INIT_PATH = "/v2/post/publish/video/init/"
TIKTOK_STATUS_PATH = "/v2/post/publish/status/fetch/"
IG_API_BASE = "https://graph.facebook.com"
IG_RUPLOAD_BASE = "https://rupload.facebook.com/ig-api-upload"
IG_API_VERSION = "v21.0"

TIKTOK_TITLE_LIMIT = 2200
IG_CAPTION_LIMIT = 2200
# حد إنستغرام الموثّق: 30 وسمًا كحد أقصى في المنشور الواحد.
IG_HASHTAG_LIMIT = 30
TIKTOK_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB لكل مقطع رفع
TIKTOK_MAX_DURATION = 600  # 10 دقائق حد Content Posting API
IG_REEL_MAX_DURATION = 90  # 90 ثانية حد Reels عبر API
IG_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB لكل مقطع رفع قابل للاستئناف
IG_READY_TIMEOUT = 180  # ثوانٍ — أقصى انتظار لجاهزية الحاوية
MIN_TOKEN_LENGTH = 10
# المصغرة (إن أُعطيت): نفس مقاس مصغرات الاستوديو 720×1280.
THUMBNAIL_SIZE = (720, 1280)
THUMBNAIL_EXTS = (".jpg", ".jpeg", ".png")
PLATFORM_NAMES = {"tiktok": "تيك توك", "instagram": "إنستغرام"}

# صلاحية التوكنات (حسب توثيق المنصتين): توكن TikTok قصير
# (24 ساعة)، وتوكن Instagram طويل العمر (60 يومًا). تُستخدم
# في check_token_freshness فقط — تحذير مبكر لا منع (التوكن
# قد يُجدَّد من جهة المنصة).
TIKTOK_TOKEN_MAX_DAYS = 1
INSTAGRAM_TOKEN_MAX_DAYS = 60

# سياسة إعادة محاولة النشر الافتراضية (جولة الأنماط W1):
# 3 محاولات إجمالًا، وفاصل أولي ثانيتان، وميزانية 120 ثانية.
# Retry-After فوق 30 ثانية لا يُنام — يرفع RetryAfterTooLong
# فيعيد الكرون الجدولة لاحقًا.
PUBLISH_RETRY_POLICY = retry_lib.RetryPolicy(
    max_attempts=3, base_delay=2.0,
    total_budget_seconds=120.0)

FACEBOOK_BIN_CANDIDATES = ("facebook-cli",
                           "/opt/hatch/bin/facebook-cli")


def _classify_social_error(exc):
    """صنّف SocialPublishError إلى (kind, retry_after) أو None.

    يقرأ الحالة من خاصية status_code (يضعها _http_json
    ودوال الرفع) أو من نص «HTTP NNN» كاحتياط، وخاصية
    transport لأخطاء الاتصال. غير SocialPublishError ← None.
    """
    if not isinstance(exc, SocialPublishError):
        return None
    if getattr(exc, "transport", False):
        return ("transport", None)
    status = getattr(exc, "status_code", None)
    if status is None:
        match = re.search(r"HTTP (\d{3})", str(exc))
        if match:
            status = int(match.group(1))
    if status is None:
        return ("logical", None)
    return (retry_lib.classify_status(status),
            getattr(exc, "retry_after", None))


def _with_retry(fn, policy=None, sleep=time.sleep):
    """نفّذ fn() مع إعادة محاولة حسب سياسة النشر الموحّدة.

    يعيد المحاولة على 429/5xx/النقل فقط؛ والمنطقي (400/401/
    403) يرفع فورًا بلا إعادة. sleep قابل للحقن في الاختبارات.
    """
    return retry_lib.call_with_retry(
        fn, policy=policy or PUBLISH_RETRY_POLICY, sleep=sleep,
        classify=_classify_social_error)


def _http_json_with_retry(method, url, body=None, token=None,
                          headers=None, timeout=300, context=None,
                          policy=None):
    """_http_json مع إعادة محاولة منضبطة (429/5xx/نقل فقط)."""
    return _with_retry(
        lambda: _http_json(method, url, body=body, token=token,
                           headers=headers, timeout=timeout,
                           context=context),
        policy=policy)


class ReadOnlyClient:
    """عميل قراءة فقط (نمط PRAW ‏read_only — جولة الأنماط W1).

    GET مسموح (فحص الحالة/الرؤى)؛ وأي كتابة (POST/PUT) تفشل
    بصوت عالٍ فورًا بدل النشر العرضي من سكربت تحليل. يمنع
    نشرًا عرضيًا من مسار قراءة.
    """

    def __init__(self, http_json=None, token=None):
        self._http_json = http_json
        self.token = token

    def _call(self, method, url, **kwargs):
        fn = self._http_json or _http_json
        return fn(method, url, token=self.token, **kwargs)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        raise SocialPublishError(
            "عميل القراءة لا ينشر — استدعاء POST مرفوض "
            "(استخدم عميل النشر PublishClient)")

    def put(self, url, **kwargs):
        raise SocialPublishError(
            "عميل القراءة لا ينشر — استدعاء PUT مرفوض "
            "(استخدم عميل النشر PublishClient)")


class PublishClient:
    """عميل نشر: كتابة مع إعادة محاولة منضبطة (429/5xx/نقل).

    القراءة (GET) تمر بلا إعادة محاولة هنا — فحص الحالة له
    حلقته الخاصة (_wait_ig_container_ready عبر ReadOnlyClient).
    """

    def __init__(self, http_json=None, token=None, policy=None):
        self._http_json = http_json
        self.token = token
        self.policy = policy or PUBLISH_RETRY_POLICY

    def _call(self, method, url, **kwargs):
        fn = self._http_json or _http_json
        call = lambda: fn(method, url, token=self.token, **kwargs)
        return _with_retry(call, policy=self.policy)

    def get(self, url, **kwargs):
        fn = self._http_json or _http_json
        return fn("GET", url, token=self.token, **kwargs)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._call("PUT", url, **kwargs)


def read_client(token=None, http_json=None):
    """عميل قراءة فقط (فحص حالة/رؤى بلا أي كتابة)."""
    return ReadOnlyClient(http_json=http_json, token=token)


def publish_client(token=None, http_json=None, policy=None):
    """عميل نشر مع إعادة محاولة منضبطة."""
    return PublishClient(http_json=http_json, token=token,
                         policy=policy)


def _find_facebook_bin():
    """مسار facebook-cli (نفس مرشحات lib.publish)."""
    for cand in FACEBOOK_BIN_CANDIDATES:
        path = shutil.which(cand) or (cand if os.path.isfile(cand)
                                      else None)
        if path:
            return path
    return None


def _default_runner(argv, timeout):
    return subprocess.run(argv, capture_output=True, text=True,
                          timeout=timeout)


def facebook_token_preflight(facebook_bin=None, runner=None,
                             timeout=30):
    """فحص مبكر لصلاحية توكن فيسبوك قبل النشر (جولة الأنماط W1).

    يستدعي `facebook-cli me` — قراءة فقط لا تنشر شيئًا — فإن
    نجح فالتوكن صالح، وإن فشل فالتوكن منتهٍ أو غير صالح فيُرفع
    SocialPublishError برسالة عربية تقول أعد الربط من الهاتف
    قبل النشر بدل الفشل في منتصف النشر.
    runner: دالة runner(argv, timeout) -> كائن
    (returncode/stdout/stderr) — للاختبار؛ الافتراضي
    subprocess.run.
    التجديد الفعلي نفسه (تبديل توكن قصير العمر بآخر طويل
    العمر عبر Graph API) مؤجل: يحتاج سرّ التطبيق + تسجيل
    دخول جديد من هاتف المستخدم — انظر تقرير W1.
    يرجع {"ok": True, "detail": "..."}.
    """
    fb = facebook_bin or _find_facebook_bin()
    if not fb:
        raise SocialPublishError(
            "facebook-cli غير متاح في PATH — لا يمكن فحص صلاحية "
            "توكن فيسبوك قبل النشر")
    run = runner or _default_runner
    try:
        proc = run([fb, "me"], timeout)
    except FileNotFoundError:
        raise SocialPublishError(
            "facebook-cli غير موجود: %s" % fb)
    except subprocess.TimeoutExpired:
        raise SocialPublishError(
            "انتهت مهلة فحص صلاحية توكن فيسبوك (%d ثانية) — "
            "أعد المحاولة لاحقًا" % timeout)
    if proc.returncode != 0:
        detail = ((proc.stderr or proc.stdout or "")
                  .strip()[:200])
        raise SocialPublishError(
            "توكن فيسبوك غير صالح أو منتهٍ — فشل فحص الصلاحية "
            "قبل النشر (%s)؛ أعد ربط الحساب من الهاتف ثم أعد "
            "النشر" % (detail or "بلا تفاصيل"))
    return {"ok": True,
            "detail": "توكن فيسبوك صالح — فحص الهوية نجح"}


def check_token_freshness(platform, studio_dir=None, now=None):
    """عمر توكن TikTok/Instagram المحفوظ: هل تجاوز صلاحيته؟

    يقرأ حقل "saved" من ملف التوكن (أو زمن تعديل الملف عند
    غيابه). يرجع {"platform", "saved", "age_days",
    "max_days", "stale", "message"} — stale=None عند غياب
    التوكن أصلًا. تحذير مبكر لا منع: التوكن قد يُجدَّد من
    جهة المنصة.
    """
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    max_days = (TIKTOK_TOKEN_MAX_DAYS if platform == "tiktok"
                else INSTAGRAM_TOKEN_MAX_DAYS)
    path = token_path(platform, studio_dir)
    if not os.path.isfile(path):
        return {"platform": platform, "saved": None,
                "age_days": None, "max_days": max_days,
                "stale": None,
                "message": "لا يوجد ملف توكن لـ %s"
                           % PLATFORM_NAMES[platform]}
    saved_epoch = None
    saved_text = None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        saved_text = (data or {}).get("saved")
        if isinstance(saved_text, str) and saved_text.strip():
            saved_epoch = time.mktime(time.strptime(
                saved_text.strip(), "%Y-%m-%d %H:%M:%S"))
    except (ValueError, OSError):
        saved_epoch = None
    if saved_epoch is None:
        saved_epoch = os.path.getmtime(path)
        saved_text = time.strftime("%Y-%m-%d %H:%M:%S",
                                   time.localtime(saved_epoch))
    now_epoch = time.time() if now is None else float(now)
    age_days = (now_epoch - saved_epoch) / 86400.0
    stale = age_days > max_days
    if stale:
        message = ("توكن %s قديم (%.1f يوم — الحد %d يومًا) — "
                   "جدّده قبل النشر" % (PLATFORM_NAMES[platform],
                                        age_days, max_days))
    else:
        message = ("توكن %s ضمن الصلاحية (%.1f/%d يومًا)"
                   % (PLATFORM_NAMES[platform], age_days, max_days))
    return {"platform": platform, "saved": saved_text,
            "age_days": age_days, "max_days": max_days,
            "stale": stale, "message": message}


class SocialPublishError(Exception):
    """خطأ في نشر TikTok/Instagram (رسالته عربية)."""


def token_path(platform, studio_dir=None):
    """مسار ملف توكن المنصة (tiktok-token.json / instagram-token.json)."""
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    root = studio_dir or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "%s-token.json" % platform)


def save_token(platform, token, studio_dir=None):
    """احفظ توكن المنصة في ملف 600. يرفع SocialPublishError عند
    توكن فارغ أو قصير جدًا. لا يطبع قيمة التوكن أبدًا."""
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    if not isinstance(token, str) or len(token.strip()) < MIN_TOKEN_LENGTH:
        raise SocialPublishError(
            "توكن %s غير صالح — يجب أن يكون نصًا لا يقل عن %d أحرف"
            % (platform, MIN_TOKEN_LENGTH))
    path = token_path(platform, studio_dir)
    data = {"platform": platform,
            "token": token.strip(),
            "saved": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.chmod(path, 0o600)
    return path


def load_token(platform, studio_dir=None):
    """اقرأ توكن المنصة من ملفه، أو None إن لم يوجد أو كان تالفًا."""
    path = token_path(platform, studio_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError):
        return None
    token = (data or {}).get("token")
    return token if isinstance(token, str) and token.strip() else None


def _check_video(video):
    """تحقق من ملف فيديو قبل بناء أي حمولة. يرجع مساره المطلق."""
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise SocialPublishError("ملف الفيديو غير موجود: %s" % video)
    if not video.lower().endswith(".mp4"):
        raise SocialPublishError("صيغة الفيديو غير مدعومة (المطلوب mp4): %s"
                                 % video)
    return video


def _caption_text(title, caption):
    """نص النشر الموحّد: عنوان + كابشن (لـ TikTok title وIG caption)."""
    lines = []
    if (title or "").strip():
        lines.append(title.strip())
    if (caption or "").strip():
        lines.append(caption.strip())
    return "\n".join(lines)


def _text_limit(platform):
    """حد نص النشر بالحروف: 2200 للمنصتين."""
    return (TIKTOK_TITLE_LIMIT if platform == "tiktok"
            else IG_CAPTION_LIMIT)


def _validate_text(platform, text):
    """النص غير فارغ وضمن حد المنصة — قبل أي شبكة."""
    name = PLATFORM_NAMES[platform]
    if not (text or "").strip():
        raise SocialPublishError(
            "نص النشر على %s فارغ — اكتب عنوانًا أو كابشنًا قبل "
            "النشر" % name)
    limit = _text_limit(platform)
    if len(text) > limit:
        raise SocialPublishError(
            "نص نشر %s أطول من حد المنصة (%d حرفًا): %d حرفًا — "
            "قصّره %d حرفًا"
            % (name, limit, len(text), len(text) - limit))
    return text


def extract_hashtags(text):
    """وسوم النص (#كلمة) — عربي/لاتيني/أرقام وشرطة سفلية."""
    return re.findall(r"#([\w\u0600-\u06FF]+)", text or "")


def validate_hashtags(text, platform):
    """عدد الوسوم ضمن حد المنصة.

    إنستغرام: 30 وسمًا كحد أقصى (حد موثّق من Meta). تيك توك:
    بلا حد عددي موثّق — الوسوم تُحسب ضمن حد 2200 حرفًا فقط
    (يُفحص في _validate_text).
    """
    if platform != "instagram":
        return extract_hashtags(text)
    tags = extract_hashtags(text)
    if len(tags) > IG_HASHTAG_LIMIT:
        raise SocialPublishError(
            "وسوم إنستغرام زائدة عن حد المنصة (%d وسمًا): %d وسمًا "
            "— احذف %d وسمًا على الأقل"
            % (IG_HASHTAG_LIMIT, len(tags),
               len(tags) - IG_HASHTAG_LIMIT))
    return tags


def validate_thumbnail(path, probe_fn=None):
    """تحقق من المصغرة (إن أُعطيت): موجودة، صورة، 720×1280.

    probe_fn: دالة probe_fn(path) -> (width, height) — للاختبار؛
    الافتراضي: lib.thumbnail.probe_image (ffprobe محلي، بلا شبكة).
    يرجع (العرض، الارتفاع). None تعني: بلا مصغرة (اختياري).
    """
    if not path:
        return None
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(path):
        raise SocialPublishError(
            "الصورة المصغرة غير موجودة: %s" % path)
    if not path.lower().endswith(THUMBNAIL_EXTS):
        raise SocialPublishError(
            "صيغة الصورة المصغرة غير مدعومة (المطلوب jpg أو png): %s"
            % path)
    probe = probe_fn
    if probe is None:
        from lib import thumbnail as thumbnail_lib
        probe = thumbnail_lib.probe_image
    try:
        width, height = probe(path)
    except Exception as e:
        raise SocialPublishError(
            "تعذرت قراءة أبعاد الصورة المصغرة %s: %s" % (path, e))
    if (width, height) != THUMBNAIL_SIZE:
        raise SocialPublishError(
            "أبعاد الصورة المصغرة غير صحيحة: %d×%d — المطلوب "
            "%d×%d (مصغرة الاستوديو العمودية)"
            % (width, height, THUMBNAIL_SIZE[0], THUMBNAIL_SIZE[1]))
    return (width, height)


def _duration_limit(platform):
    return (TIKTOK_MAX_DURATION if platform == "tiktok"
            else IG_REEL_MAX_DURATION)


def validate_social_video(video, platform, duration=None,
                          probe_info=None, thumbnail=None,
                          thumbnail_probe=None):
    """تحقق من الفيديو قبل أي شبكة: موجود، mp4 غير فارغ، المدة
    والأبعاد والصوت عند توفر معلومات probe، والمصغرة إن أُعطيت.

    duration: مدة معروفة بالثواني (أو None)؛ وprobe_info قاموس
    probe من lib.check (duration/width/height/has_audio) — عند
    غيابهما تُفحص المدة/الأبعاد في مسار الرفع عبر _check_duration
    قبل أي طلب شبكة. يرجع معلومات الفيديو المفحوصة.
    """
    video = _check_video(video)
    name = PLATFORM_NAMES[platform]
    size = os.path.getsize(video)
    if size <= 0:
        raise SocialPublishError("ملف الفيديو فارغ: %s" % video)
    info = {"video": video, "size": size, "duration": duration,
            "width": None, "height": None, "has_audio": None,
            "thumbnail": None}
    probe_duration = None
    if probe_info:
        probe_duration = probe_info.get("duration")
        info["width"] = probe_info.get("width")
        info["height"] = probe_info.get("height")
        info["has_audio"] = probe_info.get("has_audio")
    seconds = duration if duration is not None else probe_duration
    if seconds is not None:
        info["duration"] = seconds
        limit = _duration_limit(platform)
        if seconds > limit:
            raise SocialPublishError(
                "مدة الفيديو (%.1f ثانية) تتجاوز حد %s (%d ثانية) — "
                "قصّر الفيديو قبل الرفع" % (seconds, name, limit))
    width, height = info["width"], info["height"]
    if width and height:
        # عمودي 9:16 (بتسامح 2% — يقبل 720×1280 و1080×1920).
        ratio = width / height
        if abs(ratio - 9.0 / 16.0) > 0.02:
            raise SocialPublishError(
                "أبعاد الفيديو ليست عمودية 9:16 (%d×%d) — %s يقبل "
                "فيديو عموديًا فقط" % (width, height, name))
    if info["has_audio"] is False:
        raise SocialPublishError(
            "الفيديو بلا مسار صوتي — %s يحتاج فيديو بسرد مسموع"
            % name)
    if thumbnail:
        info["thumbnail"] = validate_thumbnail(
            thumbnail, probe_fn=thumbnail_probe)
    return info


def validate_social_payload(platform, video, title, caption,
                            ig_user_id=None, thumbnail=None,
                            probe_info=None, duration=None,
                            thumbnail_probe=None):
    """التحقق الكامل من حمولة TikTok/Instagram قبل أي شبكة.

    - المنصة معروفة؛ الفيديو موجود وسليم (mp4، مدة/أبعاد/صوت
      عند توفر probe)؛ النص غير فارغ وضمن الحد؛ الوسوم ضمن حد
      إنستغرام؛ معرّف حساب إنستغرام موجود (لأنه جزء من الحمولة
      نفسها — بلا معرّف لا تُبنى حمولة كاملة)؛ المصغرة (إن
      أُعطيت) بالأبعاد الصحيحة.
    - التوكن لا يُفحص هنا: الـdry-run معاينة بلا شبكة ولا
      يحتاج توكنًا (يُفحص في require_social_config قبل الرفع).
    يرجع قاموس معلومات الحمولة المفحوصة. يرفع
    SocialPublishError برسالة عربية عند أول نقص.
    """
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    name = PLATFORM_NAMES[platform]
    text = _caption_text(title, caption)
    _validate_text(platform, text)
    tags = validate_hashtags(text, platform)
    if platform == "instagram" and not (ig_user_id or "").strip():
        raise SocialPublishError(
            "معرّف حساب Instagram مفقود — اضبط "
            "publish.instagram_user_id في config.yaml أو مرّر "
            "--ig-user-id")
    info = validate_social_video(video, platform, duration=duration,
                                 probe_info=probe_info,
                                 thumbnail=thumbnail,
                                 thumbnail_probe=thumbnail_probe)
    info.update({"platform": platform, "text": text,
                 "text_length": len(text), "hashtags": tags,
                 "ig_user_id": (ig_user_id or "").strip() or None})
    return info


def build_social_payload(platform, video, title, caption,
                         ig_user_id=None):
    """موزّع واحد: حمولة TikTok أو Instagram (بلا أي اتصال)."""
    if platform == "tiktok":
        return tiktok_init_payload(video, title, caption)
    if platform == "instagram":
        return instagram_reel_payload(video, title, caption, ig_user_id)
    raise SocialPublishError("منصة غير معروفة: %s" % platform)


def dry_run_summary(platform, video, title, caption, ig_user_id=None,
                    thumbnail=None, probe_info=None, duration=None,
                    thumbnail_probe=None):
    """وضع تجريبي لمنصة واحدة: ابنِ الحمولة كاملة وتحقق منها
    وارجع ملخصها — دون أي طلب شبكة ودون قراءة التوكن.

    يرجع {"platform", "mode": "dry-run", "ok": True,
    "network_calls": 0, "payload", "video": <معلومات مفحوصة>,
    "checks": [...], "summary": "..."}. يرفع SocialPublishError
    برسالة عربية عند أي نقص (فيديو/نص/وسوم/معرّف/مصغرة).
    """
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    name = PLATFORM_NAMES[platform]
    validated = validate_social_payload(
        platform, video, title, caption, ig_user_id=ig_user_id,
        thumbnail=thumbnail, probe_info=probe_info, duration=duration,
        thumbnail_probe=thumbnail_probe)
    payload = build_social_payload(platform, video, title, caption,
                                   ig_user_id)
    checks = [
        "الفيديو موجود بصيغة mp4 (%d بايت)" % validated["size"],
        "النص ضمن حد المنصة (%d/%d حرفًا)"
        % (validated["text_length"], _text_limit(platform)),
        "الوسوم ضمن الحد (%d وسمًا)"
        % len(validated["hashtags"]),
    ]
    if validated["duration"] is not None:
        checks.append("المدة ضمن حد %s (%.1f/%d ثانية)"
                      % (name, validated["duration"],
                         _duration_limit(platform)))
    else:
        checks.append("المدة لم تُفحص (لا معلومات probe — تُفحص في "
                      "مسار الرفع قبل أي شبكة)")
    if validated["width"] and validated["height"]:
        checks.append("الأبعاد عمودية 9:16 (%d×%d)"
                      % (validated["width"], validated["height"]))
    if validated["thumbnail"]:
        checks.append("المصغرة بالأبعاد الصحيحة (720×1280)")
    summary = ("وضع تجريبي — %s: الحمولة جاهزة للنشر (بلا أي طلب "
               "شبكة) — %s" % (name, "؛ ".join(checks)))
    return {"platform": platform, "mode": "dry-run", "ok": True,
            "network_calls": 0, "payload": payload,
            "video": validated, "checks": checks, "summary": summary}


def normalize_result(platform, raw):
    """وحّد نتيجة الرفع مع مسارات النشر القائمة.

    TikTok يرجع {publish_id, status, public_url} وإنستغرام
    {media_id, creation_id} — هنا يرجع الاثنان:
    {"platform", "ok": True, "status", "id", "url",
    "detail": "..."}. يرفع SocialPublishError إن لم يرجع
    الرفع معرّفًا.
    """
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    raw = raw or {}
    if platform == "tiktok":
        post_id = raw.get("publish_id")
        url = raw.get("public_url")
        status = raw.get("status")
        detail = "publish_id=%s" % post_id if post_id else ""
    else:
        post_id = raw.get("media_id") or raw.get("creation_id")
        url = None
        status = "published"
        detail = "media_id=%s" % post_id if post_id else ""
    if not post_id:
        raise SocialPublishError(
            "الرفع على %s لم يرجع معرّف منشور: %s"
            % (PLATFORM_NAMES[platform], str(raw)[:200]))
    return {"platform": platform, "ok": True, "status": status,
            "id": post_id, "url": url, "detail": detail}


def format_result(result):
    """سطـر عربي واحد لنتيجة موحّدة (مثل «فيسبوك: نُشر ...»)."""
    name = PLATFORM_NAMES[result["platform"]]
    line = "%s: نُشر — %s" % (name, result["detail"])
    if result.get("url"):
        line += " (الرابط: %s)" % result["url"]
    return line


def require_social_config(platform, cfg=None, studio_dir=None,
                          ig_user_id=None):
    """تحقق من إعدادات المنصة قبل الرفع — توكن ومعرّف حساب.

    يرجع {"platform", "token", "ig_user_id"}. يرفع
    SocialPublishError برسالة عربية عبر lib.errors عند النقص
    (توكن غير مربوط / معرّف حساب إنستغرام مفقود) — بلا أي
    شبكة وبلا عرض قيمة التوكن. لا يتحقق من صلاحية التوكن عبر
    الشبكة (ذلك في الرفع نفسه).
    """
    if platform not in ("tiktok", "instagram"):
        raise SocialPublishError("منصة غير معروفة: %s" % platform)
    name = PLATFORM_NAMES[platform]
    uid = None
    if platform == "instagram":
        uid = ((ig_user_id or "")
               or ((cfg or {}).get("publish") or {}).get(
                   "instagram_user_id") or "").strip()
        if not uid:
            raise SocialPublishError(errors_lib.explain_error_text(
                "معرّف حساب Instagram مفقود — اضبط "
                "publish.instagram_user_id في config.yaml أو مرّر "
                "--ig-user-id", "instagram"))
    token = load_token(platform, studio_dir=studio_dir)
    if not token or len(token.strip()) < MIN_TOKEN_LENGTH:
        raise SocialPublishError(errors_lib.explain_error_text(
            "توكن %s غير مربوط — لا يوجد ملف توكن صالح؛ أكمل "
            "`studio.py %s-auth --token <التوكن>` مرة واحدة"
            % (name, platform), platform))
    return {"platform": platform, "token": token.strip(),
            "ig_user_id": uid or None}



def tiktok_init_payload(video, title, caption):
    """جسم طلب TikTok video/init + بيانات الرفع (بلا أي اتصال).

    يرجع {"url", "body", "upload": {...}} — body كما يُرسل
    لـ POST /v2/post/publish/video/init/، وupload يصف خطوات
    PUT المقاطع بعده. يرفع SocialPublishError عند عنوان أطول
    من 2200 حرفًا أو ملف غير صالح.
    """
    video = _check_video(video)
    text = _caption_text(title, caption)
    _validate_text("tiktok", text)
    validate_hashtags(text, "tiktok")
    size = os.path.getsize(video)
    chunk_size = TIKTOK_CHUNK_SIZE
    total_chunks = max(1, math.ceil(size / chunk_size))
    body = {
        "post_info": {
            "title": text,
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    return {
        "method": "POST",
        "url": TIKTOK_API_BASE + TIKTOK_INIT_PATH,
        "headers": {"Authorization": "Bearer <توكن TikTok>",
                    "Content-Type": "application/json; charset=UTF-8"},
        "body": body,
        "upload": {
            "steps": [
                "PUT كل مقطع إلى upload_url من الرد مع رأس "
                "Content-Range: bytes <بداية>-<نهاية>/<الحجم الكلي>",
                "بعد آخر مقطع: GET %s مع publish_id للتحقق من "
                "اكتمال الرفع" % (TIKTOK_API_BASE + TIKTOK_STATUS_PATH),
            ],
            "video_size": size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }


def instagram_reel_payload(video, title, caption, ig_user_id=None):
    """أجسام طلبات Instagram Reels عبر Graph API (بلا أي اتصال).

    التدفق القابل للاستئناف (حسب توثيق Meta):
      1) POST /{ig-user-id}/media — إنشاء حاوية (media_type=REELS,
         upload_type=resumable) → يرجع id فقط (بلا upload_url).
      2) POST المقاطع إلى
         rupload.facebook.com/ig-api-upload/{version}/{id}
         برأسي offset وfile_size وتخويل OAuth.
      3) GET /{id}?fields=status_code حتى FINISHED.
      4) POST /{ig-user-id}/media_publish — نشر الحاوية (creation_id).
    يرجع قاموسًا بالخطوات الأربع. ig_user_id من الإعداد
    (publish.instagram_user_id) أو --ig-user-id؛ وبدونه يُطبع
    موضعه كعنصر نائب صريح (لا يُخترع معرّف).
    """
    video = _check_video(video)
    text = _caption_text(title, caption)
    _validate_text("instagram", text)
    validate_hashtags(text, "instagram")
    uid = (ig_user_id or "").strip() or "<معرّف حساب Instagram>"
    base = "%s/%s/%s" % (IG_API_BASE, IG_API_VERSION, uid)
    rupload = "%s/%s/<id من الخطوة 1>" % (IG_RUPLOAD_BASE,
                                           IG_API_VERSION)
    return {
        "ig_user_id": uid,
        "steps": [
            {
                "step": 1,
                "method": "POST",
                "url": base + "/media",
                "body": {"media_type": "REELS",
                         "upload_type": "resumable",
                         "caption": text},
                "returns": "id (معرّف الحاوية) فقط — بلا upload_url",
            },
            {
                "step": 2,
                "method": "POST",
                "url": rupload,
                "headers": {"Authorization": "OAuth <التوكن>",
                            "offset": "<بايت البداية>",
                            "file_size": "<حجم الفيديو الكلي>"},
                "note": "ارفع ملف الفيديو كاملًا بمقاطع متتابعة "
                        "(10 ميجا لكل مقطع) — PUT مع Content-Range "
                        "لا يعمل هنا",
            },
            {
                "step": 3,
                "method": "GET",
                "url": "%s/%s/<id من الخطوة 1>?fields=status_code"
                        % (IG_API_BASE, IG_API_VERSION),
                "note": "انتظر status_code ‏= FINISHED قبل النشر "
                        "(ERROR تعني فشل المعالجة)",
            },
            {
                "step": 4,
                "method": "POST",
                "url": base + "/media_publish",
                "body": {"creation_id": "<id من الخطوة 1>"},
                "returns": "id المنشور النهائي",
            },
        ],
        "video": video,
        "video_size": os.path.getsize(video),
        "note": "Instagram لا يقبل رفع ملف محلي مباشر — الرفع "
                "القابل للاستئناف أعلاه هو المسار الصحيح عبر API؛ "
                "والحد الأقصى لمدة Reels عبر API ‏%d ثانية؛ "
                "والرفع القابل للاستئناف متاح فقط لتطبيقات "
                "Facebook Login for Business."
                % IG_REEL_MAX_DURATION,
    }


def _http_json(method, url, body=None, token=None, headers=None,
               timeout=300, context=None):
    """طلب JSON عبر urllib. يرجع القاموس المفكوك. يرفع
    SocialPublishError برسالة عربية عند أي فشل (بلا تسريب توكن).
    context: "tiktok"/"instagram" — تُلحق ترجمة lib.errors
    العربية بالخطأ الخام (مثل مساري فيسبوك/يوتيوب)."""
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json; charset=UTF-8"
    if token:
        hdrs["Authorization"] = "Bearer %s" % token
    req = urllib.request.Request(url, data=data, headers=hdrs,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        retry_lib.log_rate_limit(context or "social", e.headers)
        msg = ("فشل طلب %s %s (HTTP %d): %s" % (method, url, e.code,
                                                 detail))
        if context in ("tiktok", "instagram"):
            msg += "\n" + errors_lib.explain_error_text(msg, context)
        err = SocialPublishError(msg)
        err.status_code = e.code
        err.retry_after = retry_lib.parse_retry_after(e.headers)
        raise err
    except urllib.error.URLError as e:
        msg = "تعذر الاتصال بـ %s: %s" % (url, e)
        if context in ("tiktok", "instagram"):
            msg += "\n" + errors_lib.explain_error_text(msg, context)
        err = SocialPublishError(msg)
        err.transport = True
        raise err
    try:
        return json.loads(raw)
    except ValueError:
        raise SocialPublishError("رد غير JSON من %s: %s" % (url, raw[:200]))


def _check_duration(video, limit_seconds, platform):
    """ارفض فيديو أطول من حد المنصة قبل أي رفع. يرفع
    SocialPublishError عند التجاوز أو عند تعذر قراءة المدة
    (ملف تالف لا يُرفع)."""
    from lib import check as check_lib
    try:
        info = check_lib.probe(video)
    except check_lib.CheckError as e:
        raise SocialPublishError(
            "تعذر قراءة مدة الفيديو قبل الرفع إلى %s: %s"
            % (platform, e))
    duration = info.get("duration")
    if duration is None or duration > limit_seconds:
        raise SocialPublishError(
            "مدة الفيديو (%.1f ثانية) تتجاوز حد %s (%d ثانية) — "
            "قصّر الفيديو قبل الرفع"
            % (duration if duration is not None else -1,
               platform, limit_seconds))


def _http_put_bytes(url, chunk, start, total, token=None, timeout=600):
    """ارفع مقطع بايتات واحدًا عبر PUT مع Content-Range."""
    hdrs = {"Content-Type": "video/mp4",
            "Content-Range": "bytes %d-%d/%d"
                             % (start, start + len(chunk) - 1, total)}
    if token:
        hdrs["Authorization"] = "Bearer %s" % token
    req = urllib.request.Request(url, data=chunk, headers=hdrs,
                                 method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        err = SocialPublishError(
            "فشل رفع مقطع TikTok/Instagram عند البايت %d (HTTP %d)"
            % (start, e.code))
        err.status_code = e.code
        err.retry_after = retry_lib.parse_retry_after(e.headers)
        raise err
    except urllib.error.URLError as e:
        err = SocialPublishError("تعذر رفع المقطع عند البايت %d: %s"
                                 % (start, e))
        err.transport = True
        raise err


def _http_post_bytes_rupload(url, chunk, offset, total, token,
                             timeout=600):
    """ارفع مقطع بايتات واحدًا إلى rupload.facebook.com عبر POST
    (بروتوكول الرفع القابل للاستئناف في Instagram: رأسا offset
    وfile_size + تخويل OAuth — لا Content-Range ولا PUT)."""
    hdrs = {"Content-Type": "application/octet-stream",
            "Authorization": "OAuth %s" % token,
            "offset": str(offset),
            "file_size": str(total)}
    req = urllib.request.Request(url, data=chunk, headers=hdrs,
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        err = SocialPublishError(
            "فشل رفع مقطع Instagram عند البايت %d (HTTP %d): %s"
            % (offset, e.code, detail))
        err.status_code = e.code
        err.retry_after = retry_lib.parse_retry_after(e.headers)
        raise err
    except urllib.error.URLError as e:
        err = SocialPublishError("تعذر رفع المقطع عند البايت %d: %s"
                                 % (offset, e))
        err.transport = True
        raise err


def _wait_ig_container_ready(media_id, token, timeout=IG_READY_TIMEOUT,
                             poll_seconds=5):
    """انتظر جاهزية حاوية Instagram (status_code ‏= FINISHED)
    قبل media_publish — النشر قبلها يفشل. يرفع
    SocialPublishError عند ERROR أو انتهاء المهلة."""
    url = "%s/%s/%s?fields=status_code" % (IG_API_BASE, IG_API_VERSION,
                                           media_id)
    reader = ReadOnlyClient(token=token)
    deadline = time.time() + max(timeout, 0)
    while True:
        resp = reader.get(url, timeout=60, context="instagram")
        code = (resp or {}).get("status_code")
        if code == "FINISHED":
            return True
        if code == "ERROR":
            raise SocialPublishError(
                "معالجة حاوية Instagram فشلت (status_code=ERROR): %s"
                % str(resp)[:200])
        if time.time() >= deadline:
            raise SocialPublishError(
                "انتهت مهلة انتظار جاهزية حاوية Instagram (%d ثانية) "
                "— الحالة الأخيرة: %s" % (timeout, code))
        time.sleep(poll_seconds)


def upload_tiktok(video, title, caption, token, timeout=600):
    """ارفع فيديو إلى TikTok عبر Content Posting API.

    منفَّذ كاملًا لكن غير مختبَر حيًا (لا حساب مربوط) — لا
    يُستدعى إلا عند وجود توكن محفوظ. يرجع
    {"publish_id": ..., "status": ..., "public_url": ...}.
    يرفع SocialPublishError إن أعاد فحص الحالة FAILED (كان
    الكود يرجع بنجاح ويطبع «رُفع» حتى عند الفشل).
    """
    validate_social_payload("tiktok", video, title, caption)
    _check_duration(video, TIKTOK_MAX_DURATION, "TikTok")
    payload = tiktok_init_payload(video, title, caption)
    resp = _http_json_with_retry(
        "POST", payload["url"], body=payload["body"],
        token=token, timeout=timeout, context="tiktok")
    data = resp.get("data") or {}
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")
    if not publish_id or not upload_url:
        raise SocialPublishError("رد TikTok init بلا publish_id أو "
                                 "upload_url: %s" % str(resp)[:300])
    size = payload["upload"]["video_size"]
    chunk_size = payload["upload"]["chunk_size"]
    with open(video, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            _with_retry(lambda chunk=chunk, offset=offset: (
                _http_put_bytes(upload_url, chunk, offset, size,
                                token=None, timeout=timeout)))
            offset += len(chunk)
    status = _http_json_with_retry(
        "POST", TIKTOK_API_BASE + TIKTOK_STATUS_PATH,
        body={"publish_id": publish_id}, token=token, timeout=timeout,
        context="tiktok")
    status_data = (status or {}).get("data") or {}
    state = status_data.get("status")
    if state == "FAILED":
        raise SocialPublishError(
            "فشل نشر TikTok (publish_id=%s): %s"
            % (publish_id,
               status_data.get("fail_reason") or str(status)[:200]))
    return {"publish_id": publish_id,
            "status": state or status,
            "public_url": status_data.get("public_url")}


def upload_instagram(video, title, caption, ig_user_id, token,
                     timeout=600):
    """ارفع Reel إلى Instagram عبر Graph API (رفع قابل للاستئناف).

    منفَّذ كاملًا لكن غير مختبَر حيًا (لا حساب مربوط) — لا
    يُستدعى إلا عند وجود توكن ومعرّف حساب محفوظين.
    يرجع {"media_id": ...}.
    """
    if not (ig_user_id or "").strip():
        raise SocialPublishError(
            "معرّف حساب Instagram مفقود — اضبط "
            "publish.instagram_user_id في config.yaml أو مرّر "
            "--ig-user-id")
    validate_social_payload("instagram", video, title, caption,
                            ig_user_id=ig_user_id)
    _check_duration(video, IG_REEL_MAX_DURATION, "Instagram")
    payload = instagram_reel_payload(video, title, caption, ig_user_id)
    create = _http_json_with_retry(
        "POST", payload["steps"][0]["url"],
        body=payload["steps"][0]["body"], token=token,
        timeout=timeout, context="instagram")
    # إنشاء الحاوية يرجع id فقط — بلا upload_url (كان الكود
    # يطلب upload_url فيرفض كل رد صحيح من Meta).
    media_id = create.get("id")
    if not media_id:
        raise SocialPublishError("رد إنشاء حاوية Instagram بلا id: %s"
                                 % str(create)[:300])
    size = payload["video_size"]
    chunk_size = IG_CHUNK_SIZE
    rupload_url = "%s/%s/%s" % (IG_RUPLOAD_BASE, IG_API_VERSION,
                                media_id)
    with open(video, "rb") as f:
        offset = 0
        while offset < size:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            _with_retry(lambda chunk=chunk, offset=offset: (
                _http_post_bytes_rupload(rupload_url, chunk, offset,
                                         size, token,
                                         timeout=timeout)))
            offset += len(chunk)
    _wait_ig_container_ready(media_id, token)
    published = _http_json_with_retry(
        "POST", payload["steps"][3]["url"],
        body={"creation_id": media_id}, token=token, timeout=timeout,
        context="instagram")
    return {"media_id": published.get("id") or media_id,
            "creation_id": media_id}


def write_social_bundle(bundle_dir, platform, video, title, caption,
                        payload, ig_user_id=None):
    """اكتب حزمة رفع يدوي لمنصة اجتماعية (بلا توكن) — metadata
    + steps مثل حزمة يوتيوب. يرجع مسار الحزمة."""
    os.makedirs(bundle_dir, exist_ok=True)
    with open(os.path.join(bundle_dir, "metadata.json"), "w",
              encoding="utf-8") as f:
        json.dump({"platform": platform,
                   "video": os.path.abspath(video),
                   "title": title, "caption": caption,
                   "payload": payload},
                  f, ensure_ascii=False, indent=2)
    steps = setup_steps(platform)
    steps += ("\nالملف: %s\nالحمولة الكاملة في metadata.json.\n"
              % os.path.abspath(video))
    with open(os.path.join(bundle_dir, "steps.txt"), "w",
              encoding="utf-8") as f:
        f.write(steps)
    return bundle_dir


def setup_steps(platform):
    """الخطوات اليدوية الدقيقة لربط حساب المنصة (نص عربي)."""
    if platform == "tiktok":
        return (
            "ربط TikTok (Content Posting API) — خطوات يدوية لمرة واحدة:\n"
            "1) افتح https://developers.tiktok.com وسجّل الدخول بحساب TikTok.\n"
            "2) أنشئ تطبيقًا (Create an app) — اختر «Login Kit» و"
            "«Content Posting API».\n"
            "3) في إعدادات التطبيق: أضف صلاحية video.upload، ثم أرسل "
            "التطبيق للمراجعة (قد تستغرق أيامًا — بلا موافقة لا يعمل "
            "النشر عبر API).\n"
            "4) بعد الموافقة: اربط حسابك من التطبيق (Login with TikTok) "
            "وخذ Access Token بصلاحية video.upload.\n"
            "5) احفظ التوكن: python3 studio.py tiktok-auth --token "
            "<التوكن> — يُحفظ في tiktok-token.json بصلاحية 600 ولا يُعرض.\n"
            "6) أعد النشر: python3 studio.py publish --video <ملف> "
            "--title \"...\" --platforms tiktok\n"
            "ملاحظة: النشر عبر API غير مختبَر حيًا بعد — أول رفع حقيقي "
            "يُراقب ويُتحقق من ظهور الفيديو على الحساب.\n")
    if platform == "instagram":
        return (
            "ربط Instagram (Graph API — Reels) — خطوات يدوية لمرة واحدة:\n"
            "1) حوّل حساب Instagram إلى Business أو Creator (من إعدادات "
            "التطبيق).\n"
            "2) اربط الحساب بصفحة فيسبوك (من Meta Business Suite ← "
            "الإعدادات ← الحسابات المرتبطة ← Instagram).\n"
            "3) في تطبيق Meta للمطورين: أضف صلاحيتي instagram_basic و"
            "instagram_content_publish، وخذ Access Token.\n"
            "4) اعرف معرّف حساب Instagram (instagram_business_account id) "
            "من Graph API — اضبطه في config.yaml "
            "(publish.instagram_user_id).\n"
            "5) احفظ التوكن: python3 studio.py instagram-auth --token "
            "<التوكن> — يُحفظ في instagram-token.json بصلاحية 600 "
            "ولا يُعرض.\n"
            "6) أعد النشر: python3 studio.py publish --video <ملف> "
            "--title \"...\" --platforms instagram\n"
            "ملاحظة: Instagram لا يقبل رفع ملف محلي مباشر — الأداة "
            "تستخدم الرفع القابل للاستئناف عبر API (rupload)؛ "
            "والرفع القابل للاستئناف متاح فقط لتطبيقات Facebook "
            "Login for Business؛ والنشر عبر API "
            "غير مختبَر حيًا بعد.\n")
    raise SocialPublishError("منصة غير معروفة: %s" % platform)
