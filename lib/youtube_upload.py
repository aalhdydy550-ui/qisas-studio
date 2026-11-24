#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""رافع يوتيوب عبر YouTube Data API v3 — يُشغَّل بمفسّر .venv-youtube.

أمران:
  python youtube_upload.py auth --client-secrets FILE --token FILE
      # تبادل OAuth لمرة واحدة (يفتح المتصفح لتسجيل الدخول) ويحفظ
      # token.json. لا يُستدعى تلقائيًا أبدًا — خطوة يدوية للمستخدم.
  python youtube_upload.py upload --video FILE --title T
      --description D [--tags a,b] [--privacy public|unlisted|private]
      [--publish-at ISO] [--category-id 24] [--thumbnail IMG]
      --token FILE
      # رفع resumable + صورة مصغرة اختيارية. يطبع JSON واحدًا:
      # {"video_id": ..., "url": ...} — بلا أي نص آخر على stdout.
      # --publish-at يفرض privacyStatus=private تلقائيًا (شرط
      # YouTube API للفيديو المجدول: خاص حتى موعده ثم يُنشر).
  python youtube_upload.py preflight --token FILE --title T
      --description D [--tags a,b] --video-size BYTES
      # فحص ما قبل النشر (الجولة 8 — `studio.py publish
      # --preflight`): يتحقق من التوكن أولًا (بلا شبكة)، ثم
      # ينشئ جلسة رفع قابلة للاستئناف (resumable session) بلا
      # إرسال أي بايت من الفيديو وبلا نشر أي شيء. النجاح يعني
      # «المسار يعمل من الـVM»؛ وفشل SSL (WRONG_VERSION_NUMBER
      # — بروكسي الخروج) يطبع رسالة الرفع اليدوي الجاهزة.

لا يُنشر شيء وهمي: أي فشل يخرج برمز غير صفري ورسالة على stderr.
"""
import argparse
import json
import os
import ssl
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YT_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
UPLOAD_SESSION_URL = ("https://www.googleapis.com/upload/youtube/v3/"
                      "videos?uploadType=resumable&part=snippet,status")

# رسالة الرفع اليدوي الجاهزة عند فشل SSL (بروكسي الـVM يمنع
# الاتصال المباشر بـ youtube.googleapis.com — الجولة 6/8).
SSL_MANUAL_UPLOAD_MESSAGE = (
    "فشل الاتصال بـ YouTube API من هذه الـVM "
    "(SSL: WRONG_VERSION_NUMBER — بروكسي الشبكة يمنع الاتصال "
    "المباشر بـ youtube.googleapis.com) — الرفع التلقائي غير "
    "متاح من هنا. الحل: ارفع الفيديو يدويًا من YouTube Studio "
    "(https://studio.youtube.com ← «إنشاء» ← «تحميل فيديو») "
    "بالعنوان والوصف نفسيهما؛ وحزمة الرفع اليدوي تُبنى بـ "
    "`studio.py publish --video <الملف> --title <العنوان> "
    "--dry-run` لطباعة العنوان والوصف. لم يُرسَل أي بايت من "
    "الفيديو ولم يُنشر شيء.")


class PreflightError(Exception):
    """خطأ في فحص ما قبل النشر (رسالته عربية)."""


def _import_google():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        print("مكتبات Google غير مثبّتة في هذه البيئة: %s" % e,
              file=sys.stderr)
        print("ثبّتها بـ: .venv-youtube/bin/pip install "
              "google-api-python-client google-auth-oauthlib "
              "google-auth-httplib2", file=sys.stderr)
        sys.exit(2)
    return Request, Credentials, InstalledAppFlow, build, HttpError, \
        MediaFileUpload


def load_credentials(token_path):
    """اقرأ token.json وحدّثه إن انتهى. يرجع None إن غاب أو فسد."""
    _, Credentials, _, _, _, _ = _import_google()
    if not os.path.isfile(token_path):
        return None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    except (ValueError, OSError):
        return None
    Request, _, _, _, _, _ = _import_google()
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception:
            return None
    return creds if creds.valid else None


def run_auth(client_secrets, token_path):
    """تبادل OAuth لمرة واحدة (يفتح المتصفح). يحفظ token.json."""
    _, _, InstalledAppFlow, _, _, _ = _import_google()
    if not os.path.isfile(client_secrets):
        print("ملف client_secrets غير موجود: %s" % client_secrets,
              file=sys.stderr)
        return 2
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets,
                                                     SCOPES)
    creds = flow.run_local_server(port=0)
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print("حُفظ توكن يوتيوب في: %s" % token_path)
    return 0


def build_service(creds):
    _, _, _, build, _, _ = _import_google()
    return build("youtube", "v3", credentials=creds)


def build_upload_body(title, description, tags, privacy="public",
                      publish_at=None, category_id="24"):
    """ابنِ جسم videos.insert (دالة نقية — بلا مكتبات Google).

    ملاحظة API: `publishAt` لا يقبله يوتيوب إلا مع
    `privacyStatus=private` — الفيديو المجدول يُنشأ خاصًا
    ويُنشر تلقائيًا عند موعده؛ أي privacy تُمرَّر مع
    publish_at تُستبدل بـ private.
    """
    status = {"privacyStatus": privacy or "public"}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [t for t in tags if t],
            "categoryId": category_id or "24",
        },
        "status": status,
    }


def upload_video(service, video, title, description, tags,
                 privacy="public", publish_at=None, category_id="24",
                 thumbnail=None):
    """ارفع فيديو (resumable) + صورة مصغرة اختيارية. يرجع dict النتيجة."""
    _, _, _, _, HttpError, MediaFileUpload = _import_google()
    body = build_upload_body(title, description, tags, privacy,
                             publish_at, category_id)
    media = MediaFileUpload(video, chunksize=1024 * 1024, resumable=True)
    try:
        request = service.videos().insert(part="snippet,status",
                                          body=body, media_body=media)
        response = None
        while response is None:
            _, response = request.next_chunk()
    except HttpError as e:
        raise RuntimeError("رفض YouTube API الرفع: %s"
                           % getattr(e, "content", e))
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("الرفع اكتمل بلا معرّف فيديو: %s" % response)
    if thumbnail and os.path.isfile(thumbnail):
        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail)).execute()
        except HttpError as e:
            print("تحذير: فشل رفع الصورة المصغرة: %s"
                  % getattr(e, "content", e), file=sys.stderr)
    return {"video_id": video_id,
            "url": "https://www.youtube.com/watch?v=%s" % video_id}


def token_file_status(token_path):
    """فحص ثابت لملف التوكن (بلا أي شبكة): يرجع
    ("ok"|"missing"|"invalid", تفصيل عربي).

    «غير صالح» = ملف تالف أو بلا refresh_token أو بلا نطاق
    الرفع. التوكن المنتهي زمنيًا (access token) بلا refresh
    فاشل يُجدَّد تلقائيًا في load_credentials — فانتهاؤه وحده
    ليس «غير صالح» هنا؛ وإن فشل التجديد يرجع load_credentials
    ‏None فيُبلَّغ «منتهٍ أو غير صالح» قبل أي محاولة إلى
    YouTube API.
    """
    if not os.path.isfile(token_path):
        return "missing", "غير موجود (%s)" % token_path
    try:
        with open(token_path, encoding="utf-8") as f:
            data = json.load(f)
    except (ValueError, OSError) as e:
        return "invalid", "تالف أو غير مقروء: %s" % e
    if not isinstance(data, dict) or not data.get("refresh_token"):
        return "invalid", "بلا refresh_token — لا يمكن تجديده"
    scopes = data.get("scopes") or []
    if scopes and YT_UPLOAD_SCOPE not in scopes:
        return "invalid", "بلا نطاق youtube.upload — الرفع سيفشل"
    return "ok", "صالح (فيه refresh_token ونطاق الرفع)"


def _is_ssl_error(exc):
    """هل هذا الخطأ فشل SSL المعروف لبروكسي الخروج؟"""
    if isinstance(exc, ssl.SSLError):
        return True
    return "WRONG_VERSION_NUMBER" in str(exc)


def create_resumable_session(creds, body, video_size, http_post=None):
    """أنشئ جلسة رفع قابلة للاستئناف بلا إرسال أي بايت من
    الفيديو: POST واحد إلى نقطة uploadType=resumable بهدف
    إنشاء الجلسة فقط (الترويسات تعلن نوع المحتوى وحجمه)؛
    والرد 200 يرجع رابط الجلسة في ترويسة Location — يُرجع
    الرابط ويُترك الرفع نفسه (لا يُرسَل أي مقطع بعده).

    http_post: دالة قابلة للحقن http_post(url, headers, data)
    -> رد فيه status_code وheaders — للاختبار بلا شبكة؛
    والافتراضي AuthorizedSession من بيانات الاعتماد.
    يرفع PreflightError برسالة عربية عند أي فشل.
    """
    if http_post is None:
        from google.auth.transport.requests import AuthorizedSession
        http_post = AuthorizedSession(creds).post
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(int(video_size)),
    }
    try:
        response = http_post(UPLOAD_SESSION_URL, headers=headers,
                             data=json.dumps(body, ensure_ascii=False))
    except Exception as e:
        if _is_ssl_error(e):
            raise PreflightError(SSL_MANUAL_UPLOAD_MESSAGE)
        raise PreflightError("تعذر الاتصال بـ YouTube API: %s" % e)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        raise PreflightError(
            "رفض YouTube API إنشاء جلسة الرفع (رمز %s) — التوكن بلا "
            "صلاحية رفع على الأرجح؛ أعد الموافقة عبر "
            "`studio.py youtube-reauth`" % status)
    if status != 200:
        raise PreflightError(
            "رفض YouTube API إنشاء جلسة الرفع (رمز HTTP %s)"
            % status)
    headers_out = getattr(response, "headers", {}) or {}
    location = (headers_out.get("Location")
                or headers_out.get("location"))
    if not location:
        raise PreflightError(
            "أنشأ YouTube API الجلسة بلا رابط استئناف (بلا ترويسة "
            "Location) — لا يمكن تأكيد المسار")
    return location


def run_preflight(token_path, title, description, tags, video_size,
                  http_post=None):
    """فحص ما قبل النشر: صلاحية التوكن أولًا (بلا شبكة)، ثم
    إنشاء جلسة رفع قابلة للاستئناف (بلا أي بايت وبلا نشر).

    يرجع {"ok": True, "session_uri": ..., "video_size": ...}.
    يرفع PreflightError برسالة عربية: توكن منتهٍ/غير صالح
    (قبل أي محاولة إلى YouTube API)، أو فشل SSL (رسالة الرفع
    اليدوي الجاهزة)، أو رفض API.
    """
    status, detail = token_file_status(token_path)
    if status != "ok":
        raise PreflightError(
            "توكن يوتيوب %s — أعد الموافقة عبر "
            "`studio.py youtube-reauth` قبل أي محاولة رفع؛ ولم "
            "تُجرَ أي محاولة شبكة إلى YouTube API." % detail)
    creds = load_credentials(token_path)
    if not creds:
        raise PreflightError(
            "توكن يوتيوب منتهٍ أو غير صالح — أعد الموافقة عبر "
            "`studio.py youtube-reauth` قبل أي محاولة رفع؛ ولم "
            "تُجرَ أي محاولة شبكة إلى YouTube API.")
    body = build_upload_body(title, description, tags, "private")
    session_uri = create_resumable_session(
        creds, body, video_size, http_post=http_post)
    return {"ok": True, "session_uri": session_uri,
            "video_size": int(video_size)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="youtube_upload",
                                 description="رفع يوتيوب عبر Data API v3")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("auth", help="تبادل OAuth لمرة واحدة")
    p.add_argument("--client-secrets", required=True)
    p.add_argument("--token", required=True)
    p = sub.add_parser("upload", help="رفع فيديو")
    p.add_argument("--video", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--privacy", default="public",
                   choices=["public", "unlisted", "private"])
    p.add_argument("--publish-at", default=None)
    p.add_argument("--category-id", default="24")
    p.add_argument("--thumbnail", default=None)
    p.add_argument("--token", required=True)
    p = sub.add_parser("preflight",
                       help="فحص ما قبل النشر: جلسة رفع بلا بايتات "
                            "وبلا نشر")
    p.add_argument("--token", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--video-size", type=int, required=True)
    args = ap.parse_args(argv)
    if args.cmd == "auth":
        return run_auth(os.path.expanduser(args.client_secrets),
                        os.path.expanduser(args.token))
    if args.cmd == "preflight":
        try:
            result = run_preflight(
                os.path.expanduser(args.token), args.title,
                args.description,
                [t.strip() for t in args.tags.split(",")
                 if t.strip()],
                args.video_size)
        except PreflightError as e:
            print("فحص ما قبل النشر على يوتيوب: فشل — %s" % e,
                  file=sys.stderr)
            return 1
        print("فحص ما قبل النشر على يوتيوب: المسار يعمل من الـVM — "
              "أُنشئت جلسة رفع قابلة للاستئناف (بلا إرسال أي بايت "
              "من الفيديو وبلا نشر).")
        print("حجم الفيديو المعلن للجلسة: %d بايت"
              % result["video_size"])
        return 0
    creds = load_credentials(os.path.expanduser(args.token))
    if not creds:
        print("توكن يوتيوب غير صالح أو غائب: %s — أكمل "
              "youtube_upload.py auth أولًا"
              % os.path.expanduser(args.token), file=sys.stderr)
        return 2
    try:
        service = build_service(creds)
        result = upload_video(
            service, os.path.expanduser(args.video), args.title,
            args.description,
            [t.strip() for t in args.tags.split(",") if t.strip()],
            privacy=args.privacy, publish_at=args.publish_at,
            category_id=args.category_id,
            thumbnail=(os.path.expanduser(args.thumbnail)
                       if args.thumbnail else None))
    except RuntimeError as e:
        print("فشل الرفع: %s" % e, file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
