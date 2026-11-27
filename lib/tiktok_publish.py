#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""نشر TikTok عبر مهمة متصفح — وجهة نشر ثالثة (جولة v0.1.57).

التصميم: الرفع هنا عبر مهمة متصفح لا عبر API — لأن حساب
TikTok ‏(@qisaswaebareg) مسجَّل أصلًا في متصفح السحابة،
فتُكتب حزمة رفع (metadata.json + caption.txt + steps.txt)
وينفّذ وكيل متصفح خطواتها حرفيًا. مسار API موجود في
`lib/social_publish.py` (Content Posting API: ‏init ثم رفع
المقاطع ثم فحص الحالة، و`token_path("tiktok")` لمكانه) لكنه
غير مربوط: يحتاج تطبيق مطوّر في TikTok Developers وصلاحية
video.upload وموافقة مراجعة قد تستغرق أيامًا — فليس مسار
هذه الجولة، ولا يُستدعى هنا أي رفع عبر الشبكة إطلاقًا.

صيغة الاستوديو مقدسة ولا تمسّها هذه الوحدة: راوٍ رجالي،
وكتابة أسفل الصورة فقط — هذه الوحدة بناء كابشن وحزمة نشر
فحسب، بلا أي إنتاج فيديو.

القواعد المطبقة:
- الكابشن: عنوان + نص القصة + «العبرة: X» إن وُجدت + الدعوة
  اللطيفة المعتمدة لجزء تالٍ (من `caption_check.approved_invite`)
  + سطر إفصاح Supertonic إن كان الصوت مولّدًا آليًا فقط +
  الوسوم الأربعة من تحليل ترند TikTok ‏2026-11-26.
- حد الكابشن 2200 حرفًا (حد TikTok الموثّق في social_publish).
- بعد البناء يُفحص الكابشن بـ `caption_check.check_caption`؛
  وإن وُجدت مشكلة يُرفع `TikTokPublishError` بسببها — بلا
  إصلاح صامت: الباني لا يُصدر إلا أسطرًا معتمدة أصلًا.
- التحقق من الفيديو مفوَّض كاملًا إلى
  `social_publish.validate_social_video` — بلا تكرار لمنطقه.
- الكاتب لا يمسّ الطابور ولا أي ملف خارج مجلد الحزمة.
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from lib import caption_check
from lib import check as check_lib
from lib import social_publish
from lib.supertonic_voice import DISCLOSURE_LINE

CAIRO_TZ = ZoneInfo("Africa/Cairo")
CAIRO_TZ_NAME = "Africa/Cairo"

TIKTOK_USERNAME_DEFAULT = "qisaswaebareg"
TIKTOK_PROFILE_URL = "https://www.tiktok.com/@qisaswaebareg"
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/upload"
TIKTOK_HASHTAGS = ["#قصص", "#قصص_حقيقية", "#قصص_واقعية",
                   "#قصة_وعبرة"]
TIKTOK_CAPTION_LIMIT = 2200


class TikTokPublishError(Exception):
    """خطأ في نشر TikTok عبر مهمة المتصفح (رسالته عربية)."""


class ApprovalBlockedError(TikTokPublishError):
    """رفضت بوابة الموافقة نشر TikTok (جولة v0.1.63).

    .exit_code: 5 عند الرفض (deny أو رفض المستخدم تفاعليًا)،
    و3 حين يحتاج النشر إجابة بشرية والتشغيل غير تفاعلي
    (سؤال معلّق مسجَّل في runs/approval-decisions.jsonl).
    """

    def __init__(self, message, exit_code=5):
        self.exit_code = exit_code
        super().__init__(message)


def _require_approval(action, scope="*"):
    """افحص بوابة الموافقة قبل نشر TikTok — قاعدة «بلا تغيير
    سلوك افتراضي» (قرار المنسق الملزم).

    - بلا ملف إعداد (~/.qisas-studio/approval.json غائب):
      allow فورًا بلا أي سؤال — فيبقى سلوك أوامر النشر
      الحالية (والكرونات) كما هو.
    - أرضية الأمان: deny دائمًا حتى بلا إعداد.
    - allow ← تمضي الحزمة؛ وdeny ← ApprovalBlockedError
      خروج 5؛ وask + stdin طرفية ← سؤال تفاعلي؛ وask + بلا
      طرفية ← السؤال معلّق مسجَّل في
      runs/approval-decisions.jsonl (تسجله gate.check) +
      ApprovalBlockedError خروج 3 — بلا تعليق أبدًا.
    - أي عطل في وحدة الموافقة ← allow (fail-open للمسار
      القديم، ما عدا أرضية الأمان).
    """
    try:
        from lib import approval as approval_lib
    except Exception:  # noqa: BLE001 — البوابة غائبة = يمضي
        return "allow"
    try:
        if action in getattr(approval_lib, "SAFETY_FLOOR",
                             frozenset()):
            raise ApprovalBlockedError(
                "أرضية الأمان: الفعل «%s» مرفوض دائمًا — لا "
                "موافقة تسمح به" % action, exit_code=5)
        if not os.path.isfile(approval_lib.config_path()):
            return "allow"
        gate = approval_lib.ApprovalGate()
        decision = gate.check(action, scope=scope)
    except ApprovalBlockedError:
        raise
    except Exception:  # noqa: BLE001 — فشل البوابة = يمضي
        return "allow"
    if decision == "allow":
        return "allow"
    if decision == "deny":
        raise ApprovalBlockedError(
            "بوابة الموافقة رفضت النشر «%s» — اضبط مستوى "
            "الموافقة أو امنح النشر صراحةً ثم أعد النشر"
            % action, exit_code=5)
    try:
        interactive = sys.stdin.isatty()
    except Exception:  # noqa: BLE001 — بلا طرفية = غير تفاعلي
        interactive = False
    if interactive:
        try:
            answer = input(
                "النشر يحتاج موافقتك — «%s» (نعم/لا): "
                % action).strip().lower()
        except EOFError:
            raise ApprovalBlockedError(
                "النشر «%s» يحتاج موافقة بشرية — أُغلق الإدخال "
                "قبل الإجابة؛ وسُجّل السؤال المعلّق في "
                "runs/approval-decisions.jsonl" % action,
                exit_code=3)
        except KeyboardInterrupt:
            raise
        if answer in ("نعم", "ن", "yes", "y"):
            return "allow"
        raise ApprovalBlockedError(
            "رفضتَ النشر «%s» — لم يُنشر شيء" % action,
            exit_code=5)
    raise ApprovalBlockedError(
        "النشر «%s» يحتاج موافقة بشرية — التشغيل غير تفاعلي "
        "(كرون/اختبار) فسُجّل السؤال المعلّق في "
        "runs/approval-decisions.jsonl؛ أجب عنه ثم أعد النشر"
        % action, exit_code=3)


def build_tiktok_caption(title, caption, moral="",
                         next_part=False,
                         next_part_time="بكرة 7 مساءً",
                         ai_voice=False):
    """ابنِ كابشن TikTok: عنوان + نص + عبرة + دعوة لطيفة +
    إفصاح (لصوت Supertonic فقط) + الوسوم الأربعة.

    يرفع TikTokPublishError إن كان النص فارغًا أو أطول من
    2200 حرفًا، أو إن وجد `caption_check.check_caption` أي
    مشكلة في الناتج (بلا إصلاح صامت).
    """
    title = (title or "").strip()
    caption = (caption or "").strip()
    if not title and not caption:
        raise TikTokPublishError(
            "كابشن TikTok فارغ — اكتب عنوانًا أو نص قصة قبل النشر")
    lines = []
    if title:
        lines.append(title)
    if caption:
        lines.append(caption)
    if (moral or "").strip():
        lines.append("العبرة: %s" % moral.strip())
    if next_part:
        lines.append(caption_check.approved_invite(next_part_time))
    if ai_voice:
        lines.append(DISCLOSURE_LINE)
    lines.append(" ".join(TIKTOK_HASHTAGS))
    text = "\n".join(lines)
    if len(text) > TIKTOK_CAPTION_LIMIT:
        raise TikTokPublishError(
            "كابشن TikTok أطول من حد المنصة (2200 حرفًا): %d حرفًا — "
            "قصّره %d حرفًا"
            % (len(text), len(text) - TIKTOK_CAPTION_LIMIT))
    checked = caption_check.check_caption(text, next_part_time)
    if not checked["ok"]:
        reasons = "; ".join(
            "%s (%s)" % (issue["reason"], issue["sentence"])
            for issue in checked["issues"])
        raise TikTokPublishError(
            "كابشن TikTok يحوي جملة غير معتمدة — أعد كتابته: %s"
            % reasons)
    return text


def validate_tiktok_video(video, probe_info=None, duration=None):
    """تحقق من الفيديو قبل أي نشر — مفوَّض كاملًا إلى
    `social_publish.validate_social_video` (منصة tiktok).
    يرجع معلومات الفيديو المفحوصة. يرفع TikTokPublishError
    برسالة عربية عند أي نقص (ملف مفقود/فارغ، صيغة غير mp4،
    مدة أو أبعاد أو صوت غير صالحة).

    إن لم يُمرَّر probe_info يُحاوَل قراءته هنا عبر
    `check.probe` (ffprobe) — فإن تعذّر (ملف وهمي في اختبار،
    أو ffprobe غائب) يُترك None ويُفحص الفيديو عند الرفع،
    كما في عقد `validate_social_video` نفسه — بلا فشل صامت
    في بناء الحزمة.
    """
    if probe_info is None:
        try:
            probe_info = check_lib.probe(video)
        except check_lib.CheckError:
            probe_info = None
    try:
        return social_publish.validate_social_video(
            video, "tiktok", duration=duration, probe_info=probe_info)
    except social_publish.SocialPublishError as e:
        raise TikTokPublishError(str(e))


def _browser_task_steps(video_abs):
    """نص مهمة المتصفح الكامل بالعربية لرفع فيديو على TikTok."""
    return (
        "رفع فيديو على TikTok عبر المتصفح (حساب @%s):\n"
        "1) افتح %s مسجَّلًا باسم @%s (الحساب: %s).\n"
        "2) ارفع الملف من المسار:\n"
        "   %s\n"
        "3) الصق الكابشن من ملف caption.txt في مجلد الحزمة حرفيًا "
        "كما هو — بلا إضافة ولا حذف ولا تعديل.\n"
        "4) الرؤية: عامة (Public).\n"
        "5) انشر الفيديو.\n"
        "6) تحقق: افتح رابط الفيديو المنشور وتأكد أنه يعمل ويُشغَّل.\n"
        "قواعد فشل (لا تُتجاوز):\n"
        "- لا تتابع أحدًا ولا تعلّق على أي فيديو أثناء المهمة.\n"
        "- إن نُشر الفيديو فلا تعيد الرفع — الرفع المكرر مرفوض.\n"
        "- إن طلب TikTok تسجيل دخول فأبلغ عن ذلك ولا تسجّل بحساب آخر.\n"
        % (TIKTOK_USERNAME_DEFAULT, TIKTOK_UPLOAD_URL,
           TIKTOK_USERNAME_DEFAULT, TIKTOK_PROFILE_URL, video_abs))


def write_tiktok_bundle(bundle_dir, video, title, caption, moral="",
                        next_part=False,
                        next_part_time="بكرة 7 مساءً",
                        ai_voice=False, probe_info=None, duration=None):
    """اكتب حزمة رفع TikTok عبر مهمة متصفح: metadata.json +
    caption.txt + steps.txt.

    لا ينسخ الفيديو (موجود أصلًا في مساره) ولا يمسّ الطابور
    ولا أي ملف خارج مجلد الحزمة. يرجع قاموسًا فيه
    {"bundle_dir", "caption", "metadata_path", "steps_path",
    "video_info"}.
    بوابة الموافقة أولًا (جولة v0.1.63): الحزمة هي خطوة
    النشر الخارجي في هذا المسار (مهمة متصفح) — فبلا ملف
    إعداد موافقة تُكتب بلا سؤال؛ وdeny يرفع
    ApprovalBlockedError خروج 5 قبل كتابة أي ملف؛ وask غير
    التفاعلي يرفع خروج 3 (سؤال معلّق مسجَّل).
    """
    _require_approval("publish_tiktok")
    text = build_tiktok_caption(title, caption, moral=moral,
                                next_part=next_part,
                                next_part_time=next_part_time,
                                ai_voice=ai_voice)
    info = validate_tiktok_video(video, probe_info=probe_info,
                                 duration=duration)
    video_abs = info["video"]
    bundle_dir = os.path.abspath(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)
    metadata_path = os.path.join(bundle_dir, "metadata.json")
    steps_path = os.path.join(bundle_dir, "steps.txt")
    caption_path = os.path.join(bundle_dir, "caption.txt")
    metadata = {
        "platform": "tiktok",
        "account": TIKTOK_USERNAME_DEFAULT,
        "profile_url": TIKTOK_PROFILE_URL,
        "upload_url": TIKTOK_UPLOAD_URL,
        "video": video_abs,
        "caption": text,
        "hashtags": list(TIKTOK_HASHTAGS),
        "privacy": "public",
        "created_at": datetime.now(CAIRO_TZ).isoformat(),
        "video_info": info,
    }
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(text)
    with open(steps_path, "w", encoding="utf-8") as f:
        f.write(_browser_task_steps(video_abs))
    return {"bundle_dir": bundle_dir, "caption": text,
            "metadata_path": metadata_path, "steps_path": steps_path,
            "video_info": info}


def browser_task_brief(bundle_dir):
    """نص مهمة المتصفح لحزمة مكتوبة: يقرأ metadata.json
    للتأكد (منصة tiktok وحساب صحيحان) ثم يرجع محتوى steps.txt.
    يرفع TikTokPublishError إن غابت الحزمة أو كانت غير صالحة."""
    bundle_dir = os.path.abspath(bundle_dir)
    metadata_path = os.path.join(bundle_dir, "metadata.json")
    steps_path = os.path.join(bundle_dir, "steps.txt")
    if not os.path.isfile(metadata_path):
        raise TikTokPublishError(
            "حزمة TikTok غير موجودة — لا يوجد metadata.json في %s"
            % bundle_dir)
    if not os.path.isfile(steps_path):
        raise TikTokPublishError(
            "حزمة TikTok ناقصة — لا يوجد steps.txt في %s" % bundle_dir)
    try:
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
    except (ValueError, OSError) as e:
        raise TikTokPublishError(
            "metadata.json في حزمة TikTok تالف: %s" % e)
    if (metadata or {}).get("platform") != "tiktok":
        raise TikTokPublishError(
            "الحزمة في %s ليست حزمة TikTok (platform=%s)"
            % (bundle_dir, (metadata or {}).get("platform")))
    if (metadata or {}).get("account") != TIKTOK_USERNAME_DEFAULT:
        raise TikTokPublishError(
            "الحزمة في %s لحساب غير متوقع (%s) — المطلوب @%s"
            % (bundle_dir, (metadata or {}).get("account"),
               TIKTOK_USERNAME_DEFAULT))
    with open(steps_path, encoding="utf-8") as f:
        return f.read()


def tiktok_status(cfg=None, studio_dir=None):
    """حالة إعداد TikTok — بلا أي شبكة.

    configured صحيحة فقط إن كان في cfg مفتاح
    publish.tiktok_username غير فارغ. api_linked = وجود ملف
    tiktok-token.json (مسار API موجود لكنه غير مربوط عبر
    تطبيق مطوّر — انظر docstring الملف). يرجع
    {"configured", "username", "profile_url",
    "upload_method": "browser-task", "api_linked", "detail"}
    وdetail سطر عربي واحد.
    """
    publish_cfg = ((cfg or {}).get("publish") or {})
    username = (publish_cfg.get("tiktok_username") or "").strip()
    configured = bool(username)
    if not configured:
        username = TIKTOK_USERNAME_DEFAULT
    token_path = social_publish.token_path("tiktok",
                                           studio_dir=studio_dir)
    api_linked = os.path.isfile(token_path)
    if configured:
        detail = ("تيك توك مضبوط — الحساب @%s — الرفع عبر مهمة "
                  "متصفح" % username)
    else:
        detail = ("تيك توك غير مضبوط — اضبط publish.tiktok_username "
                  "في config.yaml (الحساب @%s)"
                  % TIKTOK_USERNAME_DEFAULT)
    if api_linked:
        detail += " — ملف توكن API موجود (المسار غير مربوط بعد)"
    return {"configured": configured,
            "username": username,
            "profile_url": TIKTOK_PROFILE_URL,
            "upload_method": "browser-task",
            "api_linked": api_linked,
            "detail": detail}
