#!/usr/bin/env python3
"""مراقبة المنشور المجدول — `studio.py schedule --watch`.

يغلق ثغرة كروني النشر (qisas-morning-publish /
qisas-evening-publish): الكرونان يتخطّيان كل شيء عندما تكون
الخانة مجدولة/منشورة أصلًا، فلا يحدث التعليق الأول أبدًا على
المنشورات المجدولة مسبقًا. هذا الملف منطق نقي بدوال قابلة
للحقن — لا يستورد facebook_cli ولا يعمل أي شبكة بنفسه:
القراءة والنشر الحقيقيان يأتيان كدالتين محقونتين (read_fn /
comment_fn) يبنيهما المنسّق في studio.py من
`publish.find_facebook_bin` وأنماط lib/publish.py.

صيغة التعليق الأول المعتمدة (العبرة + سؤال محيّر + موعد
الجزء التالي) تُعاد هنا باستخدام الدعوة اللطيفة المعتمدة
`caption_check.approved_invite` — بلا صياغة مخالفة:
الدعوة «الجزء الثاني بكرة 7 مساءً — اعمل متابعة عشان يوصلك
أول ما ينزل» لأن الجزء سينشر في وقته سواء تابع القارئ أم لا.

قواعد صادقة: لا يُخترع أي رقم أو حالة — أي حالة لا تُعرف
تُطبع «غير معروفة»؛ والتعليق الفاشل يُعاد مرة واحدة فقط.

دلالات المهام المجدولة (جولة v0.1.41 — بند 3 من استخراج
AlphaCLI، REPORT-AR.md §4.1): كل occurrence تُسجَّل في سجل
المهام **قبل** بدئها (حقل started_at يُكتب قبل أي قراءة أو
تعليق) — فإعادة تشغيل الـVM بعد البدء تُتخطى لا تُكرر؛ وبعد
توقف تُلحق occurrence متأخرة واحدة فقط ثم يستأنف الفاصل
الأصلي؛ والإيقاف/الإلغاء للمستقبل فقط.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from lib import caption_check

CAIRO = ZoneInfo("Africa/Cairo")

SLOTS = ("morning", "evening")
# موعد الخانة القانوني بتوقيت القاهرة — هوية الـoccurrence:
# خانة واحدة لكل موعد في اليوم (صباحًا 09:00 / مساءً 19:00).
SLOT_TIMES = {"morning": "09:00", "evening": "19:00"}
UNKNOWN = "غير معروفة"


def occurrence_key(post_id, slot, due):
    """مفتاح occurrence حتمي: خانة + منشور + موعدها القانوني."""
    return "schedule-watch:%s:%s:%s" % (slot, post_id, due)


def default_due(slot):
    """موعد الخانة القانوني اليوم بتوقيت القاهرة."""
    now = datetime.now(tz=CAIRO)
    return "%sT%s" % (now.date().isoformat(), SLOT_TIMES[slot])


def catch_up_plan(missed_due, next_due=None):
    """خطة اللحاق بعد توقف: occurrence متأخرة واحدة فقط تلحق،
    والباقي يُتخطى، والفاصل الأصلي يستأنف بلا إزاحة
    (next_due يمر كما هو — لا يُعاد حسابه من وقت اللحاق).

    missed_due: قائمة مواعيد متأخرة مرتبة (الأقدم أولًا).
    ترجع {run, skipped, next_due}.
    """
    missed = list(missed_due or [])
    return {"run": missed[0] if missed else None,
            "skipped": missed[1:],
            "next_due": next_due}


def cancel_future(occurrences, cutoff):
    """إيقاف/إلغاء للمستقبل فقط: ما موعده قبل cutoff يبقى كما
    هو (بدأ أو اكتمل فلا يُمس)، وما موعده cutoff أو بعده
    يُلغى. ترجع {kept, cancelled}."""
    kept, cancelled = [], []
    for occ in (occurrences or []):
        due = str((occ or {}).get("due") or "")
        if due >= str(cutoff):
            cancelled.append(occ)
        else:
            kept.append(occ)
    return {"kept": kept, "cancelled": cancelled}


class ScheduleWatchError(Exception):
    """خطأ في مراقبة المنشور المجدول (رسالته عربية)."""


def build_first_comment(story):
    """نص أول تعليق: العبرة + السؤال المحيّر + الدعوة اللطيفة
    بموعد الجزء التالي.

    story قاموس {moral, question, next_part_time} — موعد الجزء
    التالي اختياري (الافتراضي «بكرة 7 مساءً» من
    caption_check.DEFAULT_NEXT_PART_TIME). غياب moral أو
    question يرفع ValueError صريحًا بدل نص مخترع.
    """
    story = story or {}
    moral = (story.get("moral") or "").strip()
    question = (story.get("question") or "").strip()
    if not moral:
        raise ValueError(
            "العبرة مفقودة — لا يمكن بناء أول تعليق بلا عبرة")
    if not question:
        raise ValueError(
            "السؤال المحيّر مفقود — لا يمكن بناء أول تعليق بلا سؤال")
    next_part_time = ((story.get("next_part_time") or "").strip()
                      or caption_check.DEFAULT_NEXT_PART_TIME)
    lines = ["«%s»" % moral,
             question,
             caption_check.approved_invite(next_part_time)]
    return "\n".join(lines)


def status_from_watch(result):
    """حوّل نتيجة watch_slot إلى حالة نشر موحّدة (أ2-8).

    ok=True ← المنشور نُشر وعُلّق عليه ← "published"؛
    reason=not_published ← لم يُنشر بعد ← "pending"؛
    وأي فشل (error) ← "failed"؛ وdry-run أو نتيجة بلا ok
    تُقرأ "pending" (لم يحدث نشر بعد).
    """
    result = result or {}
    if result.get("ok") is True:
        return "published"
    if result.get("reason") == "not_published":
        return "pending"
    if result.get("error"):
        return "failed"
    return "pending"


def apply_watch_result(statuses, number, result,
                       platform="facebook"):
    """طبّق نتيجة watch_slot على حالات نشر عنصر (أ2-8).

    statuses خريطة {رقم: {منصة: حالة}}؛ وwatch_slot يراقب
    فيسبوك افتراضيًا (أول تعليق على منشور الصفحة) لذا
    platform الافتراضية "facebook". يرجع حالات العنصر
    المطبّعة كاملة بعد التحديث (دالة نقية — لا تكتب ملفًا).
    """
    from lib import queue as queue_lib
    return queue_lib.update_platform_status(
        statuses, number, platform, status_from_watch(result))


def _read_state(result):
    """استخرج حالة المنشور من نتيجة read_fn.

    تقبل نص حالة مباشرًا («published»/«scheduled»/…) أو
    قاموسًا فيه مفتاح «state». أي قيمة مفقودة أو غير نصية
    تُرجع «غير معروفة» — بلا اختراع حالة.
    """
    if isinstance(result, dict):
        state = result.get("state")
    else:
        state = result
    if isinstance(state, str) and state.strip():
        return state.strip()
    return UNKNOWN


def _execute_watch(post_id, story, read_fn, comment_fn, slot, text):
    """جسم التنفيذ الفعلي (قراءة + تعليق) — بلا سجل مهام.
    يُستدعى من watch_slot بعد التسجيل المسبق للبدء.
    """
    try:
        state = _read_state(read_fn(post_id))
    except Exception as e:  # noqa: BLE001 — تُترجم لرسالة عربية
        return {"ok": False, "post_id": str(post_id), "slot": slot,
                "dry_run": False,
                "error": "تعذّرت قراءة حالة المنشور %s: %s"
                         % (post_id, e)}
    if state != "published":
        return {"ok": False, "post_id": str(post_id), "slot": slot,
                "dry_run": False, "state": state,
                "reason": "not_published",
                "message": "المنشور لم يُنشر بعد (الحالة: %s) — "
                           "لا تعليق الآن، وستُعاد المراقبة في "
                           "التشغيل التالي" % state}
    last_error = None
    for attempt in (1, 2):
        try:
            result = comment_fn(post_id, text)
            comment_id = UNKNOWN
            if isinstance(result, dict):
                comment_id = (result.get("comment_id")
                              or result.get("id") or UNKNOWN)
            return {"ok": True, "post_id": str(post_id), "slot": slot,
                    "dry_run": False, "state": "published",
                    "comment": text, "comment_id": comment_id,
                    "attempts": attempt}
        except Exception as e:  # noqa: BLE001 — إعادة واحدة فقط
            last_error = e
    return {"ok": False, "post_id": str(post_id), "slot": slot,
            "dry_run": False, "state": "published",
            "error": "فشل نشر أول تعليق على المنشور %s بعد "
                     "محاولتين: %s" % (post_id, last_error)}


def watch_slot(post_id, story, read_fn, comment_fn, execute=False,
               slot="morning", runs_dir=None, due=None):
    """راقب خانة مجدولة وعلّق أول تعليق عند نشرها.

    - dry-run (الافتراضي): لا يستدعي read_fn ولا comment_fn
      إطلاقًا؛ يرجع قاموس خطة {post_id, slot, would_check,
      would_post, dry_run} — ولا يسجّل شيئًا في سجل المهام.
    - execute=True: يستدعي read_fn(post_id)؛ إن رجع
      «published» استدعِ comment_fn(post_id, text)؛ عند فشل
      النشر أعد المحاولة مرة واحدة فقط ثم ارجع {ok: False,
      error: <رسالة عربية واضحة>}؛ وإن لم يكن المنشور منشورًا
      بعد (scheduled أو غيره) فلا تعليق وارجع {ok: False,
      reason: "not_published"} مع رسالة عربية.
    - runs_dir (اختياري، مع execute فقط): دلالات المهام
      المجدولة — تُسجَّل الـoccurrence في سجل المهام (نوع
      schedule) **قبل** أي قراءة أو تعليق؛ فإن وُجدت مسجلة
      أصلًا (ريستارت بعد البدء) تُتخطى بلا أي استدعاء
      ({reason: "already_started", skipped: True})؛ وبعد
      التنفيذ تُختم done (نُشر أو لم يُنشر بعد — الخانة
      فُحصت) أو failed عند خطأ. due هو موعد الخانة القانوني
      (الافتراضي: موعد الخانة اليوم بتوقيت القاهرة)؛ خانة
      الغد occurrence مختلفة فتُشغَّل من جديد.

    read_fn(post_id) -> نص حالة أو قاموس فيه «state».
    comment_fn(post_id, text) -> أي نتيجة (قاموس فيه
    comment_id/comment_url عند توفرهما) أو يرفع استثناءً عند
    الفشل. لا إعادة محاولة أكثر من مرة أبدًا.
    """
    post_id = (post_id or "").strip() if isinstance(post_id, str) \
        else post_id
    if not post_id:
        raise ValueError("معرّف المنشور مفقود — مرّر --post-id")
    if slot not in SLOTS:
        raise ValueError("الموعد غير صالح: %s (المسموح: morning/evening)"
                         % slot)
    text = build_first_comment(story)
    if not execute:
        return {"post_id": str(post_id), "slot": slot,
                "would_check": True, "would_post": text,
                "dry_run": True}
    job = None
    job_registry = None
    if runs_dir is not None:
        from lib import job_registry as job_registry_mod
        job_registry = job_registry_mod
        due_value = due or default_due(slot)
        key = occurrence_key(str(post_id), slot, due_value)
        existing = job_registry.list_jobs(
            runs_dir, story=key, kind="schedule")
        if existing:
            return {"ok": False, "post_id": str(post_id),
                    "slot": slot, "dry_run": False,
                    "reason": "already_started", "skipped": True,
                    "message": "هذه الخانة (%s) سُجّلت بدايتها "
                               "من قبل — تُتخطى ولا تُكرر "
                               "(ريستارت بعد البدء)" % key}
        try:
            job = job_registry.register_job(
                runs_dir, "schedule", story=key,
                title="مراقبة منشور %s (%s)" % (post_id, slot))
        except Exception as e:  # noqa: BLE001 — فشل مغلق: بلا
            # تسجيل مسبق لا ضمان ضد التكرار، فلا تنفيذ إطلاقًا.
            return {"ok": False, "post_id": str(post_id),
                    "slot": slot, "dry_run": False,
                    "error": "تعذّر تسجيل بداية الخانة %s قبل "
                             "التنفيذ — أُلغي التشغيل منعًا "
                             "للتكرار: %s" % (key, e)}
    res = _execute_watch(post_id, story, read_fn, comment_fn, slot,
                         text)
    if job is not None:
        try:
            status = ("done" if (res.get("ok")
                                 or res.get("reason") == "not_published")
                      else "failed")
            job_registry.update_job(
                runs_dir, job["job_id"], status=status,
                error=res.get("error"))
        except Exception:  # noqa: BLE001 — ختم السجل لا يغيّر
            # نتيجة التنفيذ نفسها.
            pass
    return res
