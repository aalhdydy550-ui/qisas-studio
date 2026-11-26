#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تدقيق قناة ينتهي في إصلاح واحد — `studio.py channel-audit` (الجولة v0.1.57).

تطبيق أصلي من الصفر لقائمة فحص yt-audit (youtube-agent-skill، قرئت من
GitHub web — بلا نسخ كود): ينظر بالترتيب إلى آخر 10 عناوين كمجموعة،
والمصغرات بحجم الخلاصة (عبر نصوصها)، وأول 15 ثانية من أحدث 3 فيديوهات
(عبر هوكاتها)، وإيقاع الرفع، وشكل الاحتفاظ إن أمكن تصديره — وينتهي في
**إصلاح واحد** + 3 أشياء تعمل فعلًا + ما لا يُفعل بعد ولماذا.

يعيد استخدام وحدات الجولة نفسها: `title_lint` و`hook_panel` و
`retention_read` و`seo_check` و`viral_rank.classify_title_format`.
كل المدخلات صريحة من المستخدم (ملفات/وسائط) — لا يُخترع أي رقم ولا
يُجلب أي شيء من الشبكة. الأقسام غير المزوّدة تُذكر «لم تُقيَّم» بدل
تخمين حكم عنها. ولا شيء هنا ينشر أو يعدّل القناة — تقرير فقط.

أولوية الإصلاح الواحد (موثقة — لا تُغيَّر بصمت):
1. المصغرات: ≥3 نصوص مصغرة مخالفة (أكثر من 3 كلمات أو تكرر العنوان).
2. الهوك: تسرب هوك غير صحي من تصدير الاحتفاظ، أو أضعف هوك ≤5/9.
3. العناوين: ≥70% من العناوين بصيغة واحدة (و≥5 عناوين) — مشكلة صيغة.
4. الإيقاع: دفعة (≥3 رفعات في 7 أيام) يليها صمت ≥14 يومًا.
5. الاحتفاظ: منحدر أو انزلاق في التصدير.
6. SEO: بيانات النشر الأخيرة غير سليمة.
7. لا شيء حرج: بلا إصلاح، مع أصغر تحسين تالٍ.
"""
import statistics
from collections import Counter
from datetime import date

from lib import hook_panel, retention_read, seo_check, title_lint
from lib.viral_rank import classify_title_format

SAME_SHAPE_MIN_TITLES = 5
SAME_SHAPE_MIN_SHARE = 0.7
BAD_THUMB_MIN = 3
WEAK_HOOK_MAX_TOTAL = 5
STEADY_MEDIAN_GAP_DAYS = 3
LONG_GAP_DAYS = 14
BURST_WINDOW_DAYS = 7
BURST_MIN_UPLOADS = 3

_NOT_YET = {
    "thumbnails": ("لا تعيد كتابة العناوين كلها",
                   "المشكلة في المصغرات لا العناوين — تغيير العناوين "
                   "يضيع ما يعمل فعلًا."),
    "hooks": ("لا توسّع النشر على منصات جديدة",
              "جمهور جديد سيتسرب من نفس أول 15 ثانية — أصلح الهوك أولًا."),
    "titles": ("لا تغيّر صيغة القصص نفسها",
               "المشكلة تشابه الوعود في العناوين لا القصص."),
    "rhythm": ("لا تضاعف عدد الفيديوهات",
               "الانتظام أهم من الكثرة — دفعة ثم صمت أسوأ من فيديو ثابت."),
    "retention": ("لا تعيد تصوير الفيديو",
                  "المشكلة لحظة محددة — قصّها أو مهّد لها."),
    "seo": ("لا تشتري أدوات SEO مدفوعة",
            "الأساسيات المجانية (العنوان وأول سطرين) لم تُستكمل بعد."),
    "none": ("لا تصلح ما يعمل",
             "القناة سليمة في المقاس — حسّن أصغر ملاحظة فقط."),
}


def _parse_dates(raw):
    """رتّب تواريخ رفع YYYY-MM-DD تصاعديًا؛ ValueError عربي عند الفساد."""
    if raw is None:
        return None
    if isinstance(raw, str) or not isinstance(raw, (list, tuple)):
        raise ValueError("تواريخ الرفع يجب أن تكون قائمة تواريخ YYYY-MM-DD")
    out = []
    for item in raw:
        if isinstance(item, date):
            out.append(item)
            continue
        if not isinstance(item, str):
            raise ValueError("تاريخ رفع غير نص: %r" % (item,))
        parts = item.strip().split("-")
        try:
            if len(parts) != 3:
                raise ValueError("bad")
            out.append(date(int(parts[0]), int(parts[1]), int(parts[2])))
        except ValueError:
            raise ValueError(
                "تاريخ رفع غير صالح (YYYY-MM-DD): %s" % item)
    if not out:
        return None
    return sorted(out)


def _titles_section(titles, thumb_texts):
    """عناوين كمجموعة + نصوص المصغرات (إن زُوّدت)."""
    lints = []
    formats = Counter()
    bad_thumbs = 0
    thumb_assessed = False
    for i, title in enumerate(titles):
        thumb = None
        if thumb_texts is not None and i < len(thumb_texts):
            thumb = thumb_texts[i]
        lint = title_lint.lint_title(title, thumb_text=thumb)
        lints.append(lint)
        formats[classify_title_format(title)] += 1
        if thumb:
            thumb_assessed = True
            if lint["thumb_too_long"] or lint["thumb_overlap"]["repeats"]:
                bad_thumbs += 1
    top_format, top_count = formats.most_common(1)[0]
    share = top_count / len(titles)
    worst = max(lints, key=lambda l: l["issue_count"])
    return {
        "count": len(titles),
        "partial": len(titles) < 10,
        "formats": dict(formats),
        "top_format": top_format,
        "top_format_count": top_count,
        "top_format_share": round(share, 2),
        "same_shape": (len(titles) >= SAME_SHAPE_MIN_TITLES
                       and share >= SAME_SHAPE_MIN_SHARE),
        "bad_thumbs": bad_thumbs,
        "thumb_assessed": thumb_assessed,
        "worst_title": worst["title"],
        "worst_title_issues": worst["issue_count"],
        "total_issues": sum(l["issue_count"] for l in lints),
    }


def _hooks_section(hooks):
    """لوحة هوكات أحدث الفيديوهات (الأضعف هو المرشح للإصلاح)."""
    panels = hook_panel.score_hooks(hooks)
    weakest = panels[-1]
    best = panels[0]
    return {
        "count": len(panels),
        "weakest_hook": weakest["hook"],
        "weakest_total": weakest["total"],
        "weakest_max": weakest["max"],
        "weak": weakest["total"] <= WEAK_HOOK_MAX_TOTAL,
        "best_hook": best["hook"],
        "best_total": best["total"],
        "best_max": best["max"],
    }


def _rhythm_section(dates):
    """إيقاع الرفع: الانتظام لا التكرار."""
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    median_gap = statistics.median(gaps) if gaps else 0
    longest = max(gaps) if gaps else 0
    burst_silence = False
    for i, gap in enumerate(gaps):
        if gap < LONG_GAP_DAYS:
            continue
        window_start = dates[i]
        before = [d for d in dates[:i + 1]
                  if (window_start - d).days <= BURST_WINDOW_DAYS]
        if len(before) >= BURST_MIN_UPLOADS:
            burst_silence = True
            break
    return {
        "count": len(dates),
        "median_gap_days": median_gap,
        "longest_gap_days": longest,
        "burst_silence": burst_silence,
        "steady": median_gap <= STEADY_MEDIAN_GAP_DAYS
        and longest < LONG_GAP_DAYS,
    }


def audit_channel(titles, hooks=None, thumb_texts=None, upload_dates=None,
                  retention_csv=None, retention_duration=None,
                  latest_meta=None):
    """دقّق القناة من مدخلات صريحة؛ يرجع قاموسًا فيه إصلاح واحد.

    titles قائمة عناوين (الأحدث أولًا، والأفضل 10). hooks قائمة أسطر
    أولى لأحدث الفيديوهات. thumb_texts قائمة نصوص مصغرات موازية
    للعناوين (عنصر None يعني بلا نص). upload_dates قائمة تواريخ
    YYYY-MM-DD. retention_csv نص أو مسار تصدير احتفاظ Studio.
    latest_meta قاموس {title, description?, tags?} لفحص SEO.
    القوائم الفارغة تُعامل كغياب. أخطاء الإدخال ValueError عربي.
    """
    if not isinstance(titles, (list, tuple)) or not titles:
        raise ValueError("قائمة العناوين فارغة — مرّر آخر 10 عناوين")
    titles = list(titles)
    for title in titles:
        if not isinstance(title, str) or not title.strip():
            raise ValueError("عنوان فارغ في قائمة العناوين")
    if hooks is not None and (not isinstance(hooks, (list, tuple))
                              or any(not isinstance(h, str) or not h.strip()
                                     for h in hooks)):
        raise ValueError("الهوكات يجب أن تكون قائمة أسطر غير فارغة")
    if thumb_texts is not None and not isinstance(
            thumb_texts, (list, tuple)):
        raise ValueError("نصوص المصغرات يجب أن تكون قائمة")
    if latest_meta is not None:
        if not isinstance(latest_meta, dict) \
                or not isinstance(latest_meta.get("title"), str) \
                or not latest_meta.get("title", "").strip():
            raise ValueError("بيانات النشر الأخيرة تحتاج عنوانًا نصيًا")

    sections = {}
    sections["titles"] = _titles_section(
        titles, thumb_texts if thumb_texts else None)
    sections["hooks"] = _hooks_section(list(hooks)) if hooks else None
    dates = _parse_dates(upload_dates) if upload_dates else None
    sections["rhythm"] = _rhythm_section(dates) if dates else None
    sections["retention"] = None
    if retention_csv:
        sections["retention"] = retention_read.read_retention(
            retention_csv, duration=retention_duration)
    sections["seo"] = None
    if latest_meta is not None:
        sections["seo"] = seo_check.check_seo(
            latest_meta["title"], latest_meta.get("description", ""),
            latest_meta.get("tags", []))

    fix = None
    tsec = sections["titles"]
    if tsec["thumb_assessed"] and tsec["bad_thumbs"] >= BAD_THUMB_MIN:
        fix = {
            "section": "thumbnails",
            "title": "المصغرات غير مقروءة بحجم الخلاصة "
                     "(%d مخالفة)" % tsec["bad_thumbs"],
            "what_to_do": "أعد كتابة نصوص المصغرات المخالفة: ≤3 كلمات "
                          "لكل مصغرة، وبكلمات مختلفة عن العنوان (نفس "
                          "الوعد لا نفس الكلمات)، ثم أعد رفعها قبل "
                          "الفيديو التالي.",
        }
    elif sections["retention"] is not None \
            and not sections["retention"]["healthy"]:
        leak = sections["retention"]["hook_leak_pct"]
        fix = {
            "section": "hooks",
            "title": "تسرب الهوك: %s%% من المشاهدين يغادرون في أول "
                     "30 ثانية" % leak,
            "what_to_do": "أعد كتابة أول 15 ثانية من النص: أكّد ما وعد "
                          "به العنوان، وافتح سؤالًا لا يُغلق، وأثبت وجود "
                          "العائد — ولا تلمس المونتاج قبل النص.",
        }
    elif sections["hooks"] is not None and sections["hooks"]["weak"]:
        hsec = sections["hooks"]
        fix = {
            "section": "hooks",
            "title": "أضعف هوك يسجل %d/%d: «%s»" % (
                hsec["weakest_total"], hsec["weakest_max"],
                hsec["weakest_hook"]),
            "what_to_do": "أعد كتابة الهوك الأضعف أولًا (خمسة بدائل "
                          "بأمر hook-score وأبقِ أفضل اثنين)، ولا تنشر "
                          "فيديو بهوك دون 6/9.",
        }
    elif tsec["same_shape"]:
        fix = {
            "section": "titles",
            "title": "العناوين كلها بنفس الشكل: %d%% بصيغة «%s»" % (
                round(tsec["top_format_share"] * 100),
                tsec["top_format"]),
            "what_to_do": "نوّع وعود العناوين العشرة التالية (سؤال، "
                          "رقم في البداية، فضول، جزء من سلسلة) — تشابه "
                          "الشكل مشكلة صيغة لا مشكلة عنوان واحد.",
        }
    elif sections["rhythm"] is not None \
            and sections["rhythm"]["burst_silence"]:
        fix = {
            "section": "rhythm",
            "title": "دفعة ثم صمت: أطول فاصل %d يومًا" % (
                sections["rhythm"]["longest_gap_days"]),
            "what_to_do": "ثبّت إيقاعًا واحدًا تستطيع الاستمرار عليه "
                          "(فيديو ثابت في موعده) قبل أي زيادة في العدد.",
        }
    elif sections["retention"] is not None \
            and sections["retention"]["verdict"] in ("منحدر", "انزلاق"):
        rsec = sections["retention"]
        fix = {
            "section": "retention",
            "title": "احتفاظ: %s" % rsec["verdict"],
            "what_to_do": rsec["fix"],
        }
    elif sections["seo"] is not None and not sections["seo"]["ok"]:
        first = sections["seo"]["issues"][0] \
            if sections["seo"]["issues"] else "بيانات نشر ناقصة"
        fix = {
            "section": "seo",
            "title": "بيانات النشر الأخيرة غير سليمة: %s" % first,
            "what_to_do": "صلّح العنوان وأول سطرين من الوصف والوسوم "
                          "للفيديو التالي بأمر seo-check قبل النشر.",
        }

    working = []
    hsec = sections["hooks"]
    if hsec is not None and hsec["best_total"] >= 6:
        working.append("أقوى هوك يسجل %d/%d: «%s»" % (
            hsec["best_total"], hsec["best_max"], hsec["best_hook"]))
    if len(tsec["formats"]) >= 3 and not tsec["same_shape"]:
        working.append("العناوين متنوعة: %d صيغ مختلفة في آخر %d" % (
            len(tsec["formats"]), tsec["count"]))
    rsec = sections["rhythm"]
    if rsec is not None and rsec["steady"]:
        working.append("إيقاع ثابت: متوسط الفاصل %s يوم" % (
            rsec["median_gap_days"],))
    ret = sections["retention"]
    if ret is not None and ret["healthy"] and not ret["cliffs"]:
        working.append("تسرب الهوك صحي: %s%%" % ret["hook_leak_pct"])
    if sections["seo"] is not None and sections["seo"]["ok"]:
        working.append("بيانات النشر الأخيرة سليمة (SEO)")
    if tsec["thumb_assessed"] and tsec["bad_thumbs"] == 0:
        working.append("نصوص المصغرات سليمة: ≤3 كلمات وبلا تكرار للعنوان")
    working = working[:3]

    key = fix["section"] if fix else "none"
    not_yet_text, not_yet_why = _NOT_YET[key]
    return {
        "fix": fix,
        "working": working,
        "not_yet": {"text": not_yet_text, "why": not_yet_why},
        "sections": sections,
    }


def to_json_dict(result):
    """نسخة القاموس كما هي — كل قيمه أنواع JSON عادية."""
    return result


def format_report(result):
    """نص عربي: الإصلاح الواحد + ما يعمل + ما لا يُفعل بعد."""
    lines = ["تدقيق القناة — ينتهي في إصلاح واحد"]
    fix = result["fix"]
    if fix:
        lines.append("الإصلاح: %s" % fix["title"])
        lines.append("  ما تفعله هذا الأسبوع: %s" % fix["what_to_do"])
    else:
        lines.append("الإصلاح: لا إصلاح حرج — القناة سليمة في المقاس")
    tsec = result["sections"]["titles"]
    lines.append("العناوين (%d%s): %d صيغ، أعلاها «%s» (%d%%)%s" % (
        tsec["count"], " — مجموعة جزئية" if tsec["partial"] else "",
        len(tsec["formats"]), tsec["top_format"],
        round(tsec["top_format_share"] * 100),
        " — نفس الشكل!" if tsec["same_shape"] else ""))
    if tsec["thumb_assessed"]:
        lines.append("المصغرات: %d مخالفة من %d" % (
            tsec["bad_thumbs"], tsec["count"]))
    else:
        lines.append("المصغرات: لم تُقيَّم (بلا نصوص مصغرات)")
    hsec = result["sections"]["hooks"]
    if hsec:
        lines.append("الهوكات: الأضعف %d/%d، والأقوى %d/%d" % (
            hsec["weakest_total"], hsec["weakest_max"],
            hsec["best_total"], hsec["best_max"]))
    else:
        lines.append("الهوكات: لم تُقيَّم (بلا أسطر أولى)")
    rsec = result["sections"]["rhythm"]
    if rsec:
        lines.append("الإيقاع: متوسط الفاصل %s يوم، وأطول فاصل %d يوم%s"
                     % (rsec["median_gap_days"], rsec["longest_gap_days"],
                        " — دفعة ثم صمت!" if rsec["burst_silence"] else ""))
    else:
        lines.append("الإيقاع: لم يُقيَّم (بلا تواريخ رفع)")
    ret = result["sections"]["retention"]
    if ret:
        lines.append("الاحتفاظ: %s (تسرب الهوك %s%%)" % (
            ret["verdict"], ret["hook_leak_pct"]))
    else:
        lines.append("الاحتفاظ: لم يُقيَّم (بلا تصدير Studio)")
    ssec = result["sections"]["seo"]
    if ssec:
        lines.append("SEO الأخير: %s" % (
            "سليم" if ssec["ok"] else "فيه ملاحظات"))
    else:
        lines.append("SEO الأخير: لم يُقيَّم (بلا بيانات نشر)")
    lines.append("ما يعمل فعلًا:")
    if result["working"]:
        for item in result["working"]:
            lines.append("  - %s" % item)
    else:
        lines.append("  - لا شيء مقاس يعمل بعد — زوّد المدخلات")
    lines.append("ما لا يُفعل بعد: %s — %s" % (
        result["not_yet"]["text"], result["not_yet"]["why"]))
    return "\n".join(lines)
