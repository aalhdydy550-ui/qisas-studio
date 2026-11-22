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
"""
from lib import caption_check

SLOTS = ("morning", "evening")
UNKNOWN = "غير معروفة"


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


def watch_slot(post_id, story, read_fn, comment_fn, execute=False,
               slot="morning"):
    """راقب خانة مجدولة وعلّق أول تعليق عند نشرها.

    - dry-run (الافتراضي): لا يستدعي read_fn ولا comment_fn
      إطلاقًا؛ يرجع قاموس خطة {post_id, slot, would_check,
      would_post, dry_run}.
    - execute=True: يستدعي read_fn(post_id)؛ إن رجع
      «published» استدعِ comment_fn(post_id, text)؛ عند فشل
      النشر أعد المحاولة مرة واحدة فقط ثم ارجع {ok: False,
      error: <رسالة عربية واضحة>}؛ وإن لم يكن المنشور منشورًا
      بعد (scheduled أو غيره) فلا تعليق وارجع {ok: False,
      reason: "not_published"} مع رسالة عربية.

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
