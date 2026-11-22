#!/usr/bin/env python3
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
"""
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
TIKTOK_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB لكل مقطع رفع
TIKTOK_MAX_DURATION = 600  # 10 دقائق حد Content Posting API
IG_REEL_MAX_DURATION = 90  # 90 ثانية حد Reels عبر API
IG_CHUNK_SIZE = 10 * 1024 * 1024  # 10MB لكل مقطع رفع قابل للاستئناف
IG_READY_TIMEOUT = 180  # ثوانٍ — أقصى انتظار لجاهزية الحاوية
MIN_TOKEN_LENGTH = 10


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


def tiktok_init_payload(video, title, caption):
    """جسم طلب TikTok video/init + بيانات الرفع (بلا أي اتصال).

    يرجع {"url", "body", "upload": {...}} — body كما يُرسل
    لـ POST /v2/post/publish/video/init/، وupload يصف خطوات
    PUT المقاطع بعده. يرفع SocialPublishError عند عنوان أطول
    من 2200 حرفًا أو ملف غير صالح.
    """
    video = _check_video(video)
    text = _caption_text(title, caption)
    if len(text) > TIKTOK_TITLE_LIMIT:
        raise SocialPublishError(
            "نص نشر TikTok أطول من حد المنصة (2200 حرفًا): %d حرفًا"
            % len(text))
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
               timeout=300):
    """طلب JSON عبر urllib. يرجع القاموس المفكوك. يرفع
    SocialPublishError برسالة عربية عند أي فشل (بلا تسريب توكن)."""
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
        raise SocialPublishError(
            "فشل طلب %s %s (HTTP %d): %s" % (method, url, e.code, detail))
    except urllib.error.URLError as e:
        raise SocialPublishError("تعذر الاتصال بـ %s: %s" % (url, e))
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
        raise SocialPublishError(
            "فشل رفع مقطع TikTok/Instagram عند البايت %d (HTTP %d)"
            % (start, e.code))
    except urllib.error.URLError as e:
        raise SocialPublishError("تعذر رفع المقطع عند البايت %d: %s"
                                 % (start, e))


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
        raise SocialPublishError(
            "فشل رفع مقطع Instagram عند البايت %d (HTTP %d): %s"
            % (offset, e.code, detail))
    except urllib.error.URLError as e:
        raise SocialPublishError("تعذر رفع المقطع عند البايت %d: %s"
                                 % (offset, e))


def _wait_ig_container_ready(media_id, token, timeout=IG_READY_TIMEOUT,
                             poll_seconds=5):
    """انتظر جاهزية حاوية Instagram (status_code ‏= FINISHED)
    قبل media_publish — النشر قبلها يفشل. يرفع
    SocialPublishError عند ERROR أو انتهاء المهلة."""
    url = "%s/%s/%s?fields=status_code" % (IG_API_BASE, IG_API_VERSION,
                                           media_id)
    deadline = time.time() + max(timeout, 0)
    while True:
        resp = _http_json("GET", url, token=token, timeout=60)
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
    _check_duration(video, TIKTOK_MAX_DURATION, "TikTok")
    payload = tiktok_init_payload(video, title, caption)
    resp = _http_json("POST", payload["url"], body=payload["body"],
                      token=token, timeout=timeout)
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
            _http_put_bytes(upload_url, chunk, offset, size,
                            token=None, timeout=timeout)
            offset += len(chunk)
    status = _http_json(
        "POST", TIKTOK_API_BASE + TIKTOK_STATUS_PATH,
        body={"publish_id": publish_id}, token=token, timeout=timeout)
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
    _check_duration(video, IG_REEL_MAX_DURATION, "Instagram")
    payload = instagram_reel_payload(video, title, caption, ig_user_id)
    create = _http_json("POST", payload["steps"][0]["url"],
                        body=payload["steps"][0]["body"], token=token,
                        timeout=timeout)
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
            _http_post_bytes_rupload(rupload_url, chunk, offset, size,
                                     token, timeout=timeout)
            offset += len(chunk)
    _wait_ig_container_ready(media_id, token)
    published = _http_json(
        "POST", payload["steps"][3]["url"],
        body={"creation_id": media_id}, token=token, timeout=timeout)
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
