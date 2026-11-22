#!/usr/bin/env python3
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

لا يُنشر شيء وهمي: أي فشل يخرج برمز غير صفري ورسالة على stderr.
"""
import argparse
import json
import os
import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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
    args = ap.parse_args(argv)
    if args.cmd == "auth":
        return run_auth(os.path.expanduser(args.client_secrets),
                        os.path.expanduser(args.token))
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
