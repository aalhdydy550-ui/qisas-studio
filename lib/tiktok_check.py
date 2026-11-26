#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قوائم فحص tiktok-skills قبل النشر — `lib/tiktok_check.py`
(الجولة v0.1.58، W3).

يطبّق قوائم فحص tiktok-skills ككود — من القوائم/الفكرة فقط،
بلا نسخ كود من أي مشروع. بايثون بالمكتبة القياسية فقط،
حتمي بلا شبكة وبلا LLM وبلا عشوائية. فحص وتقرير فقط —
لا شيء يُنشر من هنا، ولا يُكتب في الطابور.

الفحوص الأربعة:
- الهوك (أول 3 ثوانٍ): تغليف `lib.dna.score_hook` قراءةً فقط
  (لا مسجّل جديد) + قاعدة ≤12 كلمة وبلا تمهيد. **إرشادي لا
  تنبؤ بالمشاهدات** — درجة الهوك إشارة نصية حتمية، لا نموذج
  تنبؤ؛ ويُذكر ذلك صراحة في التقرير.
- الكابشن: الوسوم الأربعة من `lib.tiktok_publish.TIKTOK_HASHTAGS`
  حاضرة + العبرة حاضرة + بلا رابط يوتيوب + بلا بوابة متابعة
  (`lib.caption_check.check_caption`) + ≤2200 حرفًا (حد
  `lib.tiktok_publish.TIKTOK_CAPTION_LIMIT`) + العنوان حاضر.
- الترند: مطابقة كلمات ترند يزوّدها المشغّل (من بحث الأسبوع —
  بلا شبكة داخل الوحدة)؛ وبلا كلمات يبقى «غير مقاس» ولا يمنع
  النشر — أي رقم بلا مصدر لا يُخترع.
- خطة الأسبوع: الطابور يحوي ≥ N شورتًا `pending` لمنصة tiktok
  (قراءة `lib.queue` فقط — بلا أي كتابة في الطابور)؛ وبلا
  طابور يُمرَّر يبقى الفحص «غير مقاس».

`check_tiktok(...)` ترجع تقريرًا قاموسيًا فيه "ok" و"checks"
و"issues" و"notes"؛ و`format_report(report)` نص عربي؛ و
`to_json_dict(report)` نسخة جاهزة لـ JSON. "ok" صحيحة عندما
لا توجد مخالفات صلبة؛ والفحوص «غير المقاسة» ملاحظات إرشادية
لا تمنع النشر. `cmd_tiktok_check` دالة جاهزة للتوصيل كأمر
`tiktok-check` في `studio.py` (بنفس نمط `cmd_seo_check`):
خروج 1 عند تقرير غير سليم (فحص قبل النشر)، و2 على مدخل
فاسد، و0 استشاريًا في غير ذلك.
"""
import json
import os
import re

from lib import caption_check
from lib import dna
from lib import queue as queue_lib
from lib import tiktok_publish

HOOK_MAX_WORDS = 12
CAPTION_LIMIT = tiktok_publish.TIKTOK_CAPTION_LIMIT
REQUIRED_HASHTAGS = list(tiktok_publish.TIKTOK_HASHTAGS)
# الافتراضي التشغيلي لخطة الأسبوع: شورت واحد لكل يوم.
# قيمة تشغيلية يغيّرها المشغّل بـ --needed — ليست قياسًا.
DEFAULT_WEEK_NEEDED = 7

_YOUTUBE_LINK_RE = re.compile(r"youtube\.com|youtu\.be",
                              re.IGNORECASE)
_MORAL_MARKERS = ("العبرة", "العبره", "الدرس", "الخلاصة",
                  "الخلاصه")

# تنبيه يُطبع مع كل تقرير: درجة الهوك إرشادية لا تنبؤية.
HOOK_ADVISORY = ("درجة الهوك إرشادية — إشارة نصية حتمية لا "
                 "تتنبأ بعدد المشاهدات")


def _word_count(text):
    """عدد كلمات نص (تقسيم على الفراغات)."""
    return len((text or "").split())


def _has_warmup(hook):
    """هل يحوي الهوك كلمة تمهيد من قائمة `lib.dna`؟"""
    return any(w in (hook or "") for w in dna.WARMUP_WORDS)


def _validate(title, caption, hook, moral, story_text,
              queue_text, queue_path, needed, trend_keywords):
    """تحقق من المدخلات؛ ValueError عربي عند الفاسد."""
    if not isinstance(title, str):
        raise ValueError("العنوان يجب أن يكون نصًا")
    if not title.strip():
        raise ValueError("العنوان فارغ — أدخل عنوانًا غير فارغ")
    if not isinstance(caption, str):
        raise ValueError("الكابشن يجب أن يكون نصًا")
    if hook is not None and not isinstance(hook, str):
        raise ValueError("الهوك يجب أن يكون نصًا")
    if moral is not None and not isinstance(moral, str):
        raise ValueError("العبرة يجب أن تكون نصًا")
    if story_text is not None and not isinstance(story_text, str):
        raise ValueError("نص القصة يجب أن يكون نصًا")
    if queue_text is not None and not isinstance(queue_text, str):
        raise ValueError("نص الطابور يجب أن يكون نصًا")
    if queue_path is not None and not isinstance(queue_path, str):
        raise ValueError("مسار الطابور يجب أن يكون نصًا")
    if isinstance(needed, bool) or not isinstance(needed, int):
        raise ValueError("عدد شورتات الأسبوع يجب أن يكون عددًا "
                         "صحيحًا")
    if needed < 1:
        raise ValueError("عدد شورتات الأسبوع يجب أن يكون 1 على "
                         "الأقل")
    if trend_keywords is not None:
        if not isinstance(trend_keywords, (list, tuple)):
            raise ValueError("كلمات الترند يجب أن تكون قائمة")
        for keyword in trend_keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("كل كلمة ترند يجب أن تكون نصًا "
                                 "غير فارغ")
    return (title.strip(), caption,
            (hook or "").strip() or None,
            (moral or "").strip(),
            story_text, queue_text, queue_path, needed,
            [k.strip() for k in (trend_keywords or []) if k.strip()])


def check_hook(hook, story_text=None):
    """افحص الهوك (أول 3 ثوانٍ): تغليف `dna.score_hook`.

    يرجع قاموس فحص فيه "score" و"max" و"verdict" من المسجّل
    القائم + عدد الكلمات ووجود التمهيد. هوك فارغ = فشل فحص
    (لا خطأ إدخال — فالفحص قبل النشر يسجّل النقص لا يرفض
    المدخل). "ok" صحيحة عند درجة ≥6 (عتبة «جيد» في dna)
    مع ≤12 كلمة وبلا تمهيد.
    """
    hook = (hook or "").strip()
    word_count = _word_count(hook)
    warmup = _has_warmup(hook)
    if not hook:
        return {"id": "hook", "name": "الهوك (أول 3 ثوانٍ)",
                "status": "fail", "ok": False,
                "score": None, "max": dna.HOOK_MAX,
                "verdict": "غير مقاس",
                "word_count": 0, "word_limit": HOOK_MAX_WORDS,
                "has_warmup": False,
                "detail": "الهوك فارغ — اكتب هوكًا قبل النشر"}
    try:
        scored = dna.score_hook(hook, story_text=story_text)
    except dna.DnaError as e:
        return {"id": "hook", "name": "الهوك (أول 3 ثوانٍ)",
                "status": "fail", "ok": False,
                "score": None, "max": dna.HOOK_MAX,
                "verdict": "غير مقاس",
                "word_count": word_count,
                "word_limit": HOOK_MAX_WORDS,
                "has_warmup": warmup,
                "detail": str(e)}
    ok = scored["total"] >= 6 and word_count <= HOOK_MAX_WORDS \
        and not warmup
    detail = ("الدرجة %d / %d — %s — %d كلمة (الحد %d)%s"
              % (scored["total"], scored["max"],
                 scored["verdict"], word_count, HOOK_MAX_WORDS,
                 " — فيه تمهيد" if warmup else ""))
    return {"id": "hook", "name": "الهوك (أول 3 ثوانٍ)",
            "status": "pass" if ok else "fail", "ok": ok,
            "score": scored["total"], "max": scored["max"],
            "verdict": scored["verdict"],
            "breakdown": dict(scored["breakdown"]),
            "word_count": word_count, "word_limit": HOOK_MAX_WORDS,
            "has_warmup": warmup, "detail": detail}


def check_caption(title, caption, moral=""):
    """افحص الكابشن قبل نشر TikTok.

    الوسوم الأربعة حاضرة + العبرة حاضرة (في الكابشن أو
    كمدخل منفصل) + بلا رابط يوتيوب + بلا بوابة متابعة
    (`caption_check.check_caption`) + ≤2200 حرفًا + العنوان
    حاضر في الكابشن. يرجع قاموس فحص فيه تفصيل كل قاعدة.
    """
    caption = caption or ""
    missing_tags = [tag for tag in REQUIRED_HASHTAGS
                    if tag not in caption]
    moral_text = (moral or "").strip()
    moral_present = bool(moral_text) or any(
        marker in caption for marker in _MORAL_MARKERS)
    youtube_link = bool(_YOUTUBE_LINK_RE.search(caption))
    gate = caption_check.check_caption(caption)
    length = len(caption)
    title_present = bool((title or "").strip()) \
        and (title.strip() in caption)
    ok = (not missing_tags and moral_present
          and not youtube_link and gate["ok"]
          and length <= CAPTION_LIMIT and title_present)
    return {"id": "caption", "name": "الكابشن",
            "status": "pass" if ok else "fail", "ok": ok,
            "hashtags_present": [tag for tag in REQUIRED_HASHTAGS
                                 if tag in caption],
            "hashtags_missing": missing_tags,
            "moral_present": moral_present,
            "has_youtube_link": youtube_link,
            "gate_ok": gate["ok"],
            "gate_issues": gate["issues"],
            "length": length, "length_limit": CAPTION_LIMIT,
            "length_ok": length <= CAPTION_LIMIT,
            "title_present": title_present,
            "detail": ("الوسوم %d / %d — العبرة: %s — رابط "
                       "يوتيوب: %s — بوابة متابعة: %s — الطول: "
                       "%d / %d حرفًا — العنوان حاضر: %s"
                       % (len(REQUIRED_HASHTAGS)
                          - len(missing_tags),
                          len(REQUIRED_HASHTAGS),
                          "نعم" if moral_present else "لا",
                          "نعم" if youtube_link else "لا",
                          "نعم" if not gate["ok"] else "لا",
                          length, CAPTION_LIMIT,
                          "نعم" if title_present else "لا"))}


def check_trend(title, hook, caption, trend_keywords=None):
    """افحص صلة الترند: كلمات ترند يزوّدها المشغّل.

    بلا كلمات يُمرَّر يبقى الفحص «غير مقاس» (ملاحظة إرشادية
    لا تمنع النشر) — فلا رقم بلا مصدر. مع كلمات: النجاح =
    وجود واحدة على الأقل في العنوان أو الهوك أو الكابشن.
    """
    keywords = [k.strip() for k in (trend_keywords or [])
                if isinstance(k, str) and k.strip()]
    if not keywords:
        return {"id": "trend", "name": "الترند",
                "status": "unmeasured", "ok": True,
                "keywords": [], "matched": [],
                "detail": "غير مقاس — زوّد كلمات ترند من بحث "
                          "الأسبوع (بلا كلمات لا يُقاس)"}
    haystack = " ".join(part for part in
                        (title or "", hook or "", caption or "")
                        if part)
    matched = [k for k in keywords if k in haystack]
    ok = bool(matched)
    return {"id": "trend", "name": "الترند",
            "status": "pass" if ok else "fail", "ok": ok,
            "keywords": keywords, "matched": matched,
            "detail": ("كلمات الترند المطابقة: %s"
                       % ("، ".join(matched) if matched
                          else "لا شيء"))}


def check_week_plan(queue_text=None, queue_path=None, needed=7):
    """افحص خطة الأسبوع: ≥ N شورتًا `pending` لمنصة tiktok.

    قراءة فقط — عبر `queue.entries_with_publish` ثم
    `queue.pending_for_platform`؛ بلا أي كتابة في الطابور.
    بلا طابور يُمرَّر (لا نص ولا مسار) يبقى الفحص «غير
    مقاس». مسار غير موجود = ValueError (مدخل فاسد).
    """
    if isinstance(needed, bool) or not isinstance(needed, int) \
            or needed < 1:
        raise ValueError("عدد شورتات الأسبوع يجب أن يكون عددًا "
                         "صحيحًا ≥ 1")
    if queue_text is None and queue_path is None:
        return {"id": "week_plan", "name": "خطة الأسبوع",
                "status": "unmeasured", "ok": True,
                "needed": needed, "pending_count": None,
                "pending_titles": [],
                "detail": "غير مقاس — مرّر نص الطابور أو مساره "
                          "لفحص خطة الأسبوع"}
    text = queue_text
    if text is None:
        path = os.path.abspath(os.path.expanduser(queue_path))
        if not os.path.isfile(path):
            raise ValueError("ملف الطابور غير موجود: %s" % path)
        with open(path, encoding="utf-8") as f:
            text = f.read()
    entries = queue_lib.entries_with_publish(text, queue_path)
    pending = queue_lib.pending_for_platform(entries, "tiktok")
    count = len(pending)
    ok = count >= needed
    return {"id": "week_plan", "name": "خطة الأسبوع",
            "status": "pass" if ok else "fail", "ok": ok,
            "needed": needed, "pending_count": count,
            "pending_titles": [e.get("title", "") for e in pending],
            "detail": ("معلّق لمنصة tiktok: %d شورتًا — المطلوب "
                       "≥ %d" % (count, needed))}


def check_tiktok(title, caption, hook=None, moral="",
                 story_text=None, queue_text=None, queue_path=None,
                 needed=DEFAULT_WEEK_NEEDED, trend_keywords=None):
    """افحص شورتًا كاملًا قبل نشره على TikTok (فحص فقط).

    title نص غير فارغ؛ caption نص (قد يكون فارغًا — يُسجَّل
    كفشل فحص لا خطأ إدخال)؛ hook نص اختياري (فارغ = فشل
    فحص الهوك)؛ moral نص اختياري (العبرة)؛ story_text نص
    اختياري لقياس العائد داخل المقطع في الهوك؛ queue_text
    / queue_path لفحص خطة الأسبوع (قراءة فقط)؛ needed عدد
    شورتات الأسبوع المطلوبة (≥1)؛ trend_keywords قائمة
    كلمات ترند من بحث الأسبوع (بلاها «غير مقاس»). يرجع
    تقريرًا قاموسيًا فيه "ok" و"checks" و"issues" و"notes".
    """
    title, caption, hook, moral, story_text, queue_text, \
        queue_path, needed, trend_keywords = _validate(
            title, caption, hook, moral, story_text, queue_text,
            queue_path, needed, trend_keywords)
    hook_report = check_hook(hook, story_text=story_text)
    caption_report = check_caption(title, caption, moral=moral)
    trend_report = check_trend(title, hook, caption,
                               trend_keywords=trend_keywords)
    week_report = check_week_plan(queue_text=queue_text,
                                  queue_path=queue_path,
                                  needed=needed)

    checks = [hook_report, caption_report, trend_report,
              week_report]
    issues = []
    notes = []
    if not hook_report["ok"]:
        if hook_report["score"] is None:
            issues.append(hook_report["detail"])
        else:
            issues.append("الهوك: %s" % hook_report["detail"])
    for tag in caption_report["hashtags_missing"]:
        issues.append("الوسم %s غائب من الكابشن" % tag)
    if not caption_report["moral_present"]:
        issues.append("العبرة غائبة من الكابشن — أضف «العبرة: …»")
    if caption_report["has_youtube_link"]:
        issues.append("الكابشن يحوي رابط يوتيوب — احذفه قبل "
                      "النشر على TikTok")
    for gate in caption_report["gate_issues"]:
        issues.append("الكابشن يحوي جملة بوابة: «%s» (%s)"
                      % (gate["sentence"], gate["reason"]))
    if not caption_report["length_ok"]:
        issues.append("الكابشن أطول من %d حرفًا (%d حرفًا)"
                      % (CAPTION_LIMIT, caption_report["length"]))
    if not caption_report["title_present"]:
        issues.append("العنوان غائب من الكابشن — ضع العنوان أول "
                      "الكابشن")
    if not trend_report["ok"]:
        issues.append("لا كلمة ترند مطابقة في العنوان/الهوك/"
                      "الكابشن — راجع كلمات ترند الأسبوع")
    if not week_report["ok"]:
        issues.append("خطة الأسبوع ناقصة: %s"
                      % week_report["detail"])
    for report in checks:
        if report["status"] == "unmeasured":
            notes.append("%s: %s" % (report["name"],
                                     report["detail"]))
    notes.append(HOOK_ADVISORY)

    return {"title": title,
            "hook": hook_report,
            "caption": caption_report,
            "trend": trend_report,
            "week_plan": week_report,
            "checks": checks,
            "ok": not issues,
            "issues": issues,
            "notes": notes}


def to_json_dict(report):
    """نسخة من التقرير جاهزة لـ JSON (قابلة للتسلسل)."""
    return json.loads(json.dumps(report, ensure_ascii=False))


def format_report(report):
    """نص عربي يلخّص تقرير فحص TikTok قبل النشر."""
    lines = ["تقرير فحص TikTok قبل النشر — «%s»"
             % report["title"]]
    lines.append("النتيجة: %s"
                 % ("سليم — جاهز للنشر من ناحية قوائم الفحص"
                    if report["ok"] else "فيه ملاحظات"))
    hook = report["hook"]
    if hook["score"] is None:
        lines.append("الهوك: %s ✗" % hook["detail"])
    else:
        lines.append("الهوك: %d / %d — %s — %d كلمة (الحد %d)%s %s"
                     % (hook["score"], hook["max"],
                        hook["verdict"], hook["word_count"],
                        hook["word_limit"],
                        " — فيه تمهيد" if hook["has_warmup"] else "",
                        "✓" if hook["ok"] else "✗"))
    caption = report["caption"]
    lines.append("الكابشن: الوسوم %d / %d، العبرة: %s، رابط "
                 "يوتيوب: %s، بوابة متابعة: %s، الطول: %d / %d "
                 "حرفًا، العنوان حاضر: %s %s"
                 % (len(caption["hashtags_present"]),
                    len(REQUIRED_HASHTAGS),
                    "نعم" if caption["moral_present"] else "لا",
                    "نعم" if caption["has_youtube_link"] else "لا",
                    "نعم" if not caption["gate_ok"] else "لا",
                    caption["length"], caption["length_limit"],
                    "نعم" if caption["title_present"] else "لا",
                    "✓" if caption["ok"] else "✗"))
    trend = report["trend"]
    if trend["status"] == "unmeasured":
        lines.append("الترند: غير مقاس (بلا كلمات ترند)")
    else:
        lines.append("الترند: %s %s"
                     % (trend["detail"], "✓" if trend["ok"] else "✗"))
    week = report["week_plan"]
    if week["status"] == "unmeasured":
        lines.append("خطة الأسبوع: غير مقاسة (بلا طابور)")
    else:
        lines.append("خطة الأسبوع: %s %s"
                     % (week["detail"], "✓" if week["ok"] else "✗"))
    if report["issues"]:
        lines.append("الملاحظات:")
        for issue in report["issues"]:
            lines.append("  - %s" % issue)
    if report.get("notes"):
        lines.append("ملاحظات إرشادية (لا تمنع النشر):")
        for note in report["notes"]:
            lines.append("  - %s" % note)
    return "\n".join(lines)


def _read_text_file(path, what):
    """اقرأ ملفًا نصيًا؛ None مع رسالة عربية عند الفشل."""
    try:
        with open(os.path.abspath(os.path.expanduser(path)),
                  encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print("تعذّرت قراءة %s %s: %s"
              % (what, os.path.expanduser(path), e))
        return None


def cmd_tiktok_check(cfg, title, caption, hook=None, moral="",
                     story_file=None, queue_file=None,
                     needed=DEFAULT_WEEK_NEEDED,
                     trend_keywords=None, as_json=False):
    """افحص شورتًا قبل نشره على TikTok (فحص فقط).

    جاهزة للتوصيل كأمر `tiktok-check` في `studio.py` بنمط
    `cmd_seo_check`: خروج 1 إن كان التقرير ok=False (فحص
    قبل النشر)، و0 إن كان ok=True، و2 على مدخل فاسد (عنوان
    فارغ، ملف قصة/طابور مفقود، عدد أسبوع غير صالح).
    --json يطبع JSON خالصًا بلا أي سطر نصي قبله (درس v0.1.56).
    cfg غير مستخدم: الأمر فحص نصي صريح بلا إنتاج.
    """
    del cfg  # الإعداد غير مستخدم: الأمر فحص نصي صريح بلا إنتاج.
    story_text = None
    if story_file:
        story_text = _read_text_file(story_file, "ملف القصة")
        if story_text is None:
            return 2
    queue_text = None
    queue_path = None
    if queue_file:
        queue_text = _read_text_file(queue_file, "ملف الطابور")
        if queue_text is None:
            return 2
        # المسار لحالات النشر الجانبية (قراءة فقط).
        queue_path = os.path.abspath(os.path.expanduser(queue_file))
    try:
        report = check_tiktok(title, caption, hook=hook,
                              moral=moral, story_text=story_text,
                              queue_text=queue_text,
                              queue_path=queue_path, needed=needed,
                              trend_keywords=trend_keywords)
    except (ValueError, TypeError) as e:
        print("مدخل فحص TikTok غير صالح: %s" % e)
        return 2
    if as_json:
        print(json.dumps(to_json_dict(report), ensure_ascii=False))
    else:
        print(format_report(report))
    return 0 if report["ok"] else 1
