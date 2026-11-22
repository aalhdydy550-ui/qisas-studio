#!/usr/bin/env python3
"""النشر — `studio.py publish`: فيديو واحد إلى صفحة فيسبوك ويوتيوب.

- فيسبوك: عبر facebook-cli المتصل أصلًا (`pages posts create`
  بملف MP4 واحد = Reel). يُتحقق من `state: published` في الإيصال؛
  والنشر الحقيقي يطلق بطاقة موافقة عادية (متوقعة، لا تُتجاوز).
- يوتيوب: عبر YouTube Data API v3 من بيئة .venv-youtube
  (lib/youtube_upload.py). يحتاج إعداد OAuth لمرة واحدة (انظر
  YOUTUBE_SETUP في README)؛ وبدون بيانات اعتماد لا يُرفع شيء —
  تُكتب حزمة رفع يدوي (metadata.json + description.txt +
  title.txt + steps.txt) بدل ادعاء رفع لم يحدث.
- `--dry-run` يطبع الحمولة الدقيقة لكل منصة دون نشر أي شيء.
- حدود المنصات تُفرض قبل أي استدعاء (كابشن فيسبوك 1024 حرفًا،
  عنوان يوتيوب 100 حرف، وصف يوتيوب 5000 حرف).
"""
import json
import os
import shutil
import subprocess
import sys
import time

from lib import errors as errors_lib
from datetime import datetime
from zoneinfo import ZoneInfo

CAIRO_TZ = ZoneInfo("Africa/Cairo")
CAIRO_TZ_NAME = "Africa/Cairo"
SCHEDULE_FORMAT = "%Y-%m-%d %H:%M"

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HASHTAGS = ["#قصص_وعبر", "#قصص_واقعية", "#قصص_مؤثرة", "#حكايات"]
PAGE_URL = "https://www.facebook.com/1048148471706586"
FB_CAPTION_LIMIT = 1024
YT_TITLE_LIMIT = 100
YT_DESC_LIMIT = 5000
YT_TAGS_LIMIT = 500
YT_CATEGORY_ENTERTAINMENT = "24"

FACEBOOK_BIN_CANDIDATES = ("facebook-cli",
                           "/opt/hatch/bin/facebook-cli")


class PublishError(Exception):
    """خطأ في بناء النشر أو تنفيذه (رسالته عربية)."""


def parse_schedule(value, now=None):
    """حوّل موعد جدولة إلى Unix (ثوانٍ).

    يقبل نصًا بصيغة "YYYY-MM-DD HH:MM" بتوقيت Africa/Cairo
    (الجولة 6: `studio.py publish --schedule "2026-11-23 19:00"`)،
    أو عددًا/نصًا رقميًا Unix جاهزًا (توافق مع --schedule القديم).
    يرفع PublishError عند صيغة خاطئة أو موعد في الماضي.
    """
    if value is None:
        raise PublishError("موعد الجدولة مفقود")
    if isinstance(value, (int, float)):
        epoch = int(value)
    elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
        epoch = int(value.strip())
    elif isinstance(value, str):
        text = value.strip()
        try:
            naive = datetime.strptime(text, SCHEDULE_FORMAT)
        except ValueError:
            raise PublishError(
                "صيغة موعد الجدولة خاطئة: «%s» — الصيغة المطلوبة "
                "YYYY-MM-DD HH:MM بتوقيت %s (مثال: 2026-11-23 19:00)"
                % (text, CAIRO_TZ_NAME))
        epoch = int(naive.replace(tzinfo=CAIRO_TZ).timestamp())
    else:
        raise PublishError("موعد الجدولة غير صالح: %r" % (value,))
    ref = int(time.time()) if now is None else int(now)
    if epoch <= ref:
        raise PublishError(
            "موعد الجدولة في الماضي (%s بتوقيت %s) — يجب أن يكون "
            "في المستقبل" % (format_schedule(epoch), CAIRO_TZ_NAME))
    return epoch


def format_schedule(epoch):
    """صِغ Unix كوقت قاهرة مقروء: "YYYY-MM-DD HH:MM Africa/Cairo"."""
    dt = datetime.fromtimestamp(int(epoch), tz=CAIRO_TZ)
    return "%s %s" % (dt.strftime(SCHEDULE_FORMAT), CAIRO_TZ_NAME)


def schedule_publish_at(epoch):
    """صِغ Unix كـ publishAt يوتيوب (RFC 3339 UTC بلا أجزاء ثانية)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(epoch)))


def find_facebook_bin():
    for cand in FACEBOOK_BIN_CANDIDATES:
        path = shutil.which(cand) or (cand if os.path.isfile(cand) else None)
        if path:
            return path
    return None


def build_caption(title, caption, part_tag=None):
    """ابنِ كابشن فيسبوك: عنوان + نص + حزمة الهاشتاجات الثابتة.

    يرفع PublishError إن تجاوز 1024 حرفًا (حد المنصة).
    """
    lines = []
    if title:
        lines.append(title.strip())
    if caption:
        lines.append(caption.strip())
    lines.append("عندك قصة حصلتلك؟ ابعتها في رسائل الصفحة وهنحكيها "
                 "باسمك أو بدون اسم.")
    if part_tag:
        lines.append(part_tag.strip())
    lines.append(" ".join(HASHTAGS))
    text = "\n".join(lines)
    if len(text) > FB_CAPTION_LIMIT:
        raise PublishError(
            "الكابشن أطول من حد فيسبوك (1024 حرفًا): %d حرفًا — قصّره "
            "%d حرفًا" % (len(text), len(text) - FB_CAPTION_LIMIT))
    return text


def build_youtube_description(title, caption, moral=""):
    """ابنِ وصف يوتيوب: هوك + ملخص + عبرة + اشتراك + روابط + هاشتاجات."""
    lines = []
    if title:
        lines.append(title.strip())
    if caption:
        lines.append(caption.strip())
    if moral:
        lines.append("العبرة: %s" % moral.strip())
    lines.append("اشترك في القناة عشان قصة جديدة توصلك كل يوم.")
    lines.append("صفحة فيسبوك: %s" % PAGE_URL)
    lines.append(" ".join(HASHTAGS))
    text = "\n".join(lines)
    if len(text) > YT_DESC_LIMIT:
        raise PublishError(
            "الوصف أطول من حد يوتيوب (5000 حرف): %d حرفًا"
            % len(text))
    return text


def build_youtube_title(title):
    title = (title or "").strip()
    if not title:
        raise PublishError("عنوان يوتيوب فارغ")
    if len(title) > YT_TITLE_LIMIT:
        raise PublishError(
            "عنوان يوتيوب أطول من 100 حرف: %d حرفًا" % len(title))
    return title


def facebook_argv(page_id, video, caption, schedule=None,
                  facebook_bin=None):
    """أمر facebook-cli الدقيق لنشر Reel (أو جدولته)."""
    fb = facebook_bin or find_facebook_bin()
    if not fb:
        raise PublishError("facebook-cli غير متاح في PATH")
    if not page_id:
        raise PublishError("معرّف الصفحة مفقود — مرّر --page-id أو "
                           "اضبط publish.page_id في config.yaml")
    if not os.path.isfile(video):
        raise PublishError("ملف الفيديو غير موجود: %s" % video)
    argv = [fb, "pages", "posts", "create",
            "--page-id", str(page_id),
            "--text", caption,
            "--privacy", "PUBLIC",
            "--file", os.path.abspath(video),
            "--media-caption", "1=%s" % caption]
    if schedule:
        argv += ["--scheduled-publish-time", str(int(schedule))]
    return argv


def _run(cmd, what, timeout=600):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise PublishError("%s: الأمر غير موجود: %s" % (what, cmd[0]))
    except subprocess.TimeoutExpired:
        raise PublishError("%s: انتهت المهلة (%d ثانية)"
                           % (what, timeout))
    return proc


def post_facebook(page_id, video, caption, schedule=None):
    """انشر Reel على الصفحة فعلًا. يتحقق من state في الإيصال.

    يرجع {"post_id": ..., "state": ..., "scheduled_post_id": ...}.
    يرفع PublishError عند أي فشل أو حالة غير منشورة/مجدولة.
    """
    argv = facebook_argv(page_id, video, caption, schedule)
    proc = _run(argv, "النشر على فيسبوك")
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raw = (proc.stderr or out)[-500:]
        msg = ("فشل النشر على فيسبوك (رمز الخروج %d): %s"
               % (proc.returncode, raw))
        if raw.strip():
            # الخطأ الخام من facebook-cli إنجليزي غالبًا — ألحق
            # ترجمته العربية (lib.errors) دون حذف الأصل.
            msg += "\n" + errors_lib.explain_error_text(raw, "facebook")
        raise PublishError(msg)
    try:
        data = json.loads(out)
    except ValueError:
        raise PublishError("إيصال فيسبوك ليس JSON صالحًا: %s" % out[:300])
    state = data.get("state")
    post_id = (data.get("scheduled_post_id") or data.get("post_id")
               or data.get("id"))
    if schedule:
        if state != "scheduled" or not post_id:
            raise PublishError("الجدولة لم تُؤكد (state=%s): %s"
                               % (state, out[:300]))
        return {"post_id": post_id, "state": "scheduled",
                "scheduled_post_id": post_id}
    if state != "published" or not post_id:
        raise PublishError("النشر لم يُؤكد (state=%s): %s"
                           % (state, out[:300]))
    return {"post_id": post_id, "state": "published"}


def youtube_request_body(title, description, tags, privacy="public",
                         schedule=None, category_id=None):
    """جسم طلب YouTube videos.insert (كما يُرسل للـAPI).

    ملاحظة API: `publishAt` لا يقبله يوتيوب إلا مع
    `privacyStatus=private` — الفيديو المجدول يُنشأ خاصًا
    ويُنشر تلقائيًا عند موعد publishAt. أي privacy تُمرَّر
    مع جدولة تُستبدل بـ private هنا وفي youtube_upload.py.
    """
    tags = [t.strip() for t in (tags or []) if t and t.strip()]
    tags_text = ",".join(tags)
    if len(tags_text) > YT_TAGS_LIMIT:
        raise PublishError("وسوم يوتيوب أطول من 500 حرف: %d"
                           % len(tags_text))
    status = {"privacyStatus": privacy or "public"}
    if schedule:
        status["privacyStatus"] = "private"
        status["publishAt"] = schedule_publish_at(schedule)
    return {
        "snippet": {
            "title": build_youtube_title(title),
            "description": description,
            "tags": tags,
            "categoryId": category_id or YT_CATEGORY_ENTERTAINMENT,
        },
        "status": status,
    }


def youtube_payload(title, description, tags, privacy="public",
                    schedule=None, category_id=None, thumbnail=None):
    """حمولة يوتيوب الكاملة للطباعة في --dry-run (بلا رفع).

    مفتاح "schedule" (عند الجدولة فقط) بيانات عرض لا تُرسل
    للـAPI: وقت القاهرة + المنطقة الزمنية + publishAt + Unix.
    """
    payload = {
        "method": "youtube.videos.insert",
        "part": "snippet,status",
        "body": youtube_request_body(title, description, tags, privacy,
                                     schedule, category_id),
        "thumbnail": thumbnail or None,
        "upload": "resumable",
    }
    if schedule:
        payload["schedule"] = {
            "cairo": format_schedule(schedule),
            "timezone": CAIRO_TZ_NAME,
            "publishAt": schedule_publish_at(schedule),
            "unix": int(schedule),
        }
    return payload


def write_youtube_bundle(bundle_dir, video, title, description, tags,
                         privacy="public", schedule=None,
                         category_id=None, thumbnail=None):
    """اكتب حزمة رفع يدوي ليوتيوب (بلا بيانات اعتماد).

    لا ينسخ الفيديو (موجود أصلًا في مساره) — الحزمة بيانات وخطوات.
    يرجع مسار الحزمة.
    """
    os.makedirs(bundle_dir, exist_ok=True)
    body = youtube_request_body(title, description, tags, privacy,
                                schedule, category_id)
    with open(os.path.join(bundle_dir, "metadata.json"), "w",
              encoding="utf-8") as f:
        json.dump({"video": os.path.abspath(video), "body": body,
                   "thumbnail": (os.path.abspath(thumbnail)
                                 if thumbnail else None)},
                  f, ensure_ascii=False, indent=2)
    with open(os.path.join(bundle_dir, "title.txt"), "w",
              encoding="utf-8") as f:
        f.write(body["snippet"]["title"] + "\n")
    with open(os.path.join(bundle_dir, "description.txt"), "w",
              encoding="utf-8") as f:
        f.write(body["snippet"]["description"] + "\n")
    if thumbnail and os.path.isfile(thumbnail):
        import shutil as _shutil
        _shutil.copyfile(
            thumbnail,
            os.path.join(bundle_dir, "thumbnail"
                         + os.path.splitext(thumbnail)[1]))
    steps = (
        "رفع يدوي على يوتيوب (YouTube Studio):\n"
        "1) افتح https://studio.youtube.com وسجّل الدخول بحساب القناة.\n"
        "2) زر «إنشاء» ← «تحميل فيديو» واختر الملف في metadata.json\n"
        "   (حقل video).\n"
        "3) الصق العنوان من title.txt والوصف من description.txt.\n"
        "4) ارفع الصورة المصغرة من thumbnail.* إن وُجدت (زر «تحميل ملف»).\n"
        "5) الرؤية: %s — ثم «نشر».\n"
        "%s"
        "للرفع التلقائي لاحقًا: أكمل إعداد OAuth لمرة واحدة (انظر\n"
        "قسم YouTube في README) ثم أعد الأمر نفسه بلا --dry-run.\n"
        % (("private (مجدول — يُنشر تلقائيًا %s)"
            % format_schedule(schedule)) if schedule
           else (privacy or "public"),
           ("موعد النشر المجدول: %s (publishAt ‏%s).\n"
            % (format_schedule(schedule),
               schedule_publish_at(schedule))) if schedule else ""))
    with open(os.path.join(bundle_dir, "steps.txt"), "w",
              encoding="utf-8") as f:
        f.write(steps)
    return bundle_dir


def youtube_venv_python(studio_dir=None):
    """مفسّر بيئة YouTube (.venv-youtube) إن وُجد، وإلا None."""
    path = os.path.join(studio_dir or STUDIO_DIR, ".venv-youtube",
                        "bin", "python")
    return path if os.path.isfile(path) else None


def youtube_preflight(token, title, description, tags, video_size,
                      studio_dir=None, runner=None):
    """فحص ما قبل النشر على يوتيوب (الجولة 8 — بلا إرسال أي بايت
    من الفيديو وبلا نشر).

    ينفذ lib/youtube_upload.py preflight بمفسّر .venv-youtube:
    صلاحية التوكن أولًا، ثم إنشاء جلسة رفع قابلة للاستئناف.
    يرجع {"ok": True, "report": ...} عند النجاح. يرفع
    PublishError برسالة عربية عند فشل التوكن أو فشل SSL
    (بروكسي الـVM — رسالة الرفع اليدوي الجاهزة). runner:
    دالة قابلة للحقن runner(argv) -> (returncode, stdout,
    stderr) — للاختبار بلا عملية فرعية.
    """
    venv_python = youtube_venv_python(studio_dir)
    if not venv_python:
        raise PublishError("بيئة YouTube غير موجودة (.venv-youtube) — "
                           "شغّل setup.sh أولًا")
    token = os.path.expanduser(token) if token else None
    if not token or not os.path.isfile(token):
        raise PublishError("لا يوجد توكن يوتيوب (%s) — أكمل إعداد "
                           "OAuth لمرة واحدة (studio.py youtube-auth)؛ "
                           "ولم تُجرَ أي محاولة شبكة"
                           % (token or "youtube-token.json"))
    # «-I» (معزول) إلزامي: بدونه يضيف بايثون مجلد lib/ إلى
    # sys.path فيظلّل lib/queue.py وحدة stdlib ‏queue فينكسر
    # urllib3 (AttributeError: module 'queue' has no attribute
    # 'LifoQueue') قبل أي شبكة — وهو نفس الخلل الكامن في مسار
    # الرفع الحقيقي upload_youtube. -I يبقي site-packages
    # البيئة ويستبعد مجلد السكربت.
    uploader = os.path.join(studio_dir or STUDIO_DIR, "lib",
                            "youtube_upload.py")
    cmd = [venv_python, "-I", uploader, "preflight",
           "--token", token,
           "--title", build_youtube_title(title),
           "--description", description or "",
           "--tags", ",".join(tags or []),
           "--video-size", str(int(video_size))]
    if runner is None:
        proc = _run(cmd, "فحص ما قبل النشر على يوتيوب", timeout=120)
        returncode, out, err = (proc.returncode, proc.stdout or "",
                                proc.stderr or "")
    else:
        returncode, out, err = runner(cmd)
    report = (out or "").strip()
    if returncode != 0:
        raw = (err or out or "").strip()
        if "WRONG_VERSION_NUMBER" in raw or "الرفع اليدوي" in raw \
                or "YouTube Studio" in raw:
            # رسالة الرافع نفسه عربية جاهزة (فشل SSL) — تُمرَّر
            # كما هي بلا تغليف إضافي.
            raise PublishError(raw)
        raise PublishError(
            "فشل فحص ما قبل النشر على يوتيوب (رمز الخروج %d): %s"
            % (returncode, raw[-800:] if raw else "بلا تفاصيل"))
    return {"ok": True, "report": report}


def upload_youtube(video, title, description, tags, privacy="public",
                   schedule=None, category_id=None, thumbnail=None,
                   client_secrets=None, token=None, studio_dir=None,
                   timeout=1800):
    """ارفع إلى يوتيوب عبر API (يحتاج token.json صالحًا).

    ينفذ lib/youtube_upload.py بمفسّر .venv-youtube. يرجع
    {"video_id": ..., "url": ...}. يرفع PublishError عند غياب
    بيانات الاعتماد أو فشل الرفع.
    """
    venv_python = youtube_venv_python(studio_dir)
    if not venv_python:
        raise PublishError("بيئة YouTube غير موجودة (.venv-youtube) — "
                           "شغّل setup.sh أولًا")
    token = os.path.expanduser(token) if token else None
    if not token or not os.path.isfile(token):
        raise PublishError("لا يوجد توكن يوتيوب صالح (%s) — أكمل إعداد "
                           "OAuth لمرة واحدة (studio.py youtube-auth)"
                           % (token or "youtube-token.json"))
    uploader = os.path.join(studio_dir or STUDIO_DIR, "lib",
                            "youtube_upload.py")
    cmd = [venv_python, "-I", uploader, "upload",
           "--video", os.path.abspath(video),
           "--title", build_youtube_title(title),
           "--description", description,
           "--tags", ",".join(tags or []),
           "--privacy", privacy or "public",
           "--token", token]
    if schedule:
        cmd += ["--publish-at", schedule_publish_at(schedule)]
    if category_id:
        cmd += ["--category-id", category_id]
    if thumbnail:
        cmd += ["--thumbnail", os.path.abspath(thumbnail)]
    proc = _run(cmd, "الرفع على يوتيوب", timeout=timeout)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raw = (proc.stderr or out)[-500:]
        msg = ("فشل الرفع على يوتيوب (رمز الخروج %d): %s"
               % (proc.returncode, raw))
        if raw.strip():
            # الخطأ الخام من رافع يوتيوب إنجليزي غالبًا — ألحق
            # ترجمته العربية (lib.errors) دون حذف الأصل.
            msg += "\n" + errors_lib.explain_error_text(raw, "youtube")
        raise PublishError(msg)
    try:
        data = json.loads(out)
    except ValueError:
        raise PublishError("مخرجات رافع يوتيوب ليست JSON صالحًا: %s"
                           % out[:300])
    if not data.get("video_id"):
        raise PublishError("الرفع لم يرجع معرّف فيديو: %s" % out[:300])
    return data
