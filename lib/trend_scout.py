#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مساعد بحث ترندات أسبوعي يغذّي طابور القصص — جولة v0.1.58 (W1).

الفكرة (من نمط «استكشاف الترندات» في ViralMint فقط، بلا نسخ كود):
المشغّل يزوّد قائمة عامة JSON بفيديوهات قصص رائجة (من بحث
متصفح أو yt-dlp)، والوحدة ترتّبها بإشارات اكتشاف حقيقية
وتقترح إدخالات طابور — بلا شبكة وبلا LLM وبلا عشوائية.

قواعد الوحدة:
- المدخل قائمة قواميس {platform, channel, title, views?,
  likes, comments, saves, shares, url, duration?} — يزوّدها
  المشغّل جاهزة. قراءة فقط: بلا شبكة وبلا جلب.
- التقييم حتمي من ثلاث إشارات فقط:
  1. نسبة الحفظ: saves/likes، وعند غياب الإعجابات
     saves/views — إشارة الاكتشاف الأولى من تحليل ترند
     2026-11-26 (المفضلات 9.5%–20.9%).
  2. نسبة المشاركة: shares/likes — الإشارة الثانية
     (المشاركات حتى 37%).
  3. مضاعف القناة على وسيطها عند توفر مشاهدات ≥4
     فيديوهات للقناة (مفهوم ``lib/viral_rank.py`` — لا
     يعيد كتابته، ويحسب وسيطه هنا من المشاهدات المزوّدة
     فقط). قناة بأقل من 4 فيديوهات بمشاهدات تُتخطى مع
     ذكر ذلك — والمضاعف عندها «غير مقاس».
- الدرجة 0–100: الحفظ حتى 45 نقطة (مقياسًا على 20.9%،
  أعلى نسبة حفظ مقاسة)، والمشاركة حتى 35 نقطة (مقياسًا
  على 37%، أعلى نسبة مشاركة مقاسة)، والمضاعف حتى 20
  نقطة (مقياسًا على ×2). أي إشارة بلا مصدر تساهم بصفر
  وتُذكر «غير مقاس» في السبب — لا تُخترع أرقام.
- تصنيف نمط الهوك بالكلمات فقط — ليس ادعاءً بسبب
  النجاح. ترتيب القواعد (أول مطابقة تفوز):
  1. سلسلة مرقمة — «جزء N» في العنوان.
  2. رعب ريفي/غامض — «غيط/قصب/ضلمة/رعب/غامض/ملهاش
     تفسير/...» — يُوسم «مستبعد» صراحة ولا يُقترح أبدًا
     (الرعب خارج الخط بانتظار قرار المستخدم).
  3. إطار ديني/أخلاقي — «صلاة/النبي/القرآن/الله/توبة/
     عبرة/...».
  4. عنوان صادم/مفارقة — «لكن/بقى/لن تصدق/صدمة/
     القصة الكاملة/...».
  5. وإلا «أخرى».
- المخرج: مرشحون مرتبون + اقتراحات إدخالات طابور
  {title, hook, moral_angle, source_url, pattern, score,
  reason} كـ JSON + تقرير عربي. **لا يكتب في ملف الطابور
  إطلاقًا** — الاقتراح فقط، والكتابة قرار المشغّل.
- عنوان الاقتراح يُجرَّد من بادئة «جزء N» (ترقيم المصدر
  لا يُنسخ إلى طابورنا)؛ والهوك هو عنوان المصدر كما هو
  (الهوك مقاس من العنوان والإطار الأول)؛ و``moral_angle``
  اقتراح إطار عام من النمط، لا ادعاء بعبرة الفيديو
  المصدر.
- كل تقرير يطبع سطر: «تصنيف بالكلمات فقط — ليس ادعاءً
  بسبب النجاح» وسطر: «أي نسبة بلا مصدر تظهر «غير مقاس»».
"""
import json
import math
import re
import statistics

__all__ = [
    "classify_hook_pattern",
    "scout_trends",
    "format_report",
    "to_json",
    "load_videos_json",
]

# أنماط الهوك (قيم الإخراج — عربية).
PATTERN_SERIES = "سلسلة مرقمة"
PATTERN_HORROR = "رعب ريفي/غامض"
PATTERN_RELIGIOUS = "إطار ديني/أخلاقي"
PATTERN_SHOCK = "عنوان صادم/مفارقة"
PATTERN_OTHER = "أخرى"

# حالات المرشح.
STATUS_CANDIDATE = "مرشح"
STATUS_EXCLUDED = "مستبعد"

# المراجع المقاسة من تحليل ترند TikTok 2026-11-26
# (~/workspace/studio-work/tiktok-trends/2026-11-26-ANALYSIS-AR.md):
# أعلى نسبة حفظ 20.9%، وأدنى نسبة حفظ مقاسة 9.5%، وأعلى
# نسبة مشاركة 37%.
SAVE_RATE_REF = 0.209
SAVE_RATE_LOW = 0.095
SHARE_RATE_REF = 0.37
MULTIPLIER_REF = 2.0

# أوزان الدرجة (المجموع 100).
SAVE_WEIGHT = 45.0
SHARE_WEIGHT = 35.0
MULTIPLIER_WEIGHT = 20.0

# سطور تُطبع في كل تقرير.
DISCLAIMER = "تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح."
NO_INVENTED_NUMBERS = ("لا أرقام مخترعة: أي نسبة بلا مصدر "
                       "تظهر «غير مقاس».")

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) + إزالة التشكيل.
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


_SERIES_RE = re.compile(r"جزء\s*[0-9٠-٩]+")
_SERIES_PREFIX_RE = re.compile(r"^\s*جزء\s*[0-9٠-٩]+\s*[|—\-–:،]?\s*")
_HORROR_WORDS = (
    "غيط", "قصب", "ضلمه", "ظلمه", "رعب", "ارعب", "مرعب",
    "جن", "عفريت", "مقبره", "غامض", "ملهاش تفسير",
    "بلا تفسير", "جيش", "صعيد",
)
_RELIGIOUS_WORDS = (
    "صلاه", "نبي", "قران", "الله", "رزق", "توبه", "تايب",
    "عبره", "صدقه", "دعاء", "استغفار", "صبر", "امانه",
)
_SHOCK_WORDS = (
    "لكن", "بقي", "لن تصدق", "لا يصدق", "صدمه", "مفاجاه",
    "الكامله", "قفل", "قتل", "سرق", "خدع", "هرب",
)

# زاوية العبرة المقترحة لكل نمط — إطار عام، لا ادعاء بعبرة المصدر.
_MORAL_ANGLE = {
    PATTERN_SERIES: "سلسلة مرقمة — جزء جديد بنفس الموضوع؛ "
                   "العبرة تُستخلص من الأحداث لا وعظًا",
    PATTERN_RELIGIOUS: "إطار ديني/أخلاقي — عبرة واضحة قابلة للمشاركة",
    PATTERN_SHOCK: "مفارقة/صدمة تُروى كعبرة — بلا تفاصيل مؤلمة",
    PATTERN_OTHER: "عبرة تُستخلص من الأحداث",
}


def classify_hook_pattern(title):
    """صنّف نمط هوك عنوان من كلماته فقط.

    ترتيب القواعد موثّق في مقدّمة الوحدة. يرفع ``ValueError``
    عربيًا إن كان العنوان فارغًا أو غير نص.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("عنوان الفيديو فارغ أو غير نص — أعطِ عنوانًا نصيًا.")
    text = _normalize(title.strip())
    if _SERIES_RE.search(text):
        return PATTERN_SERIES
    if any(word in text for word in _HORROR_WORDS):
        return PATTERN_HORROR
    if any(word in text for word in _RELIGIOUS_WORDS):
        return PATTERN_RELIGIOUS
    if any(word in text for word in _SHOCK_WORDS):
        return PATTERN_SHOCK
    return PATTERN_OTHER


def _check_number(value, name):
    """تحقّق أن القيمة عدد حقيقي منتهٍ غير سالب (بلا bool) أو None."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if value < 0:
        raise ValueError(f"«{name}» سالبة — العدّادات لا تكون سالبة.")
    return value


def _clean_video(video):
    """تحقّق من فيديو واحد وأعده منظّفًا؛ وإلا ``ValueError`` عربي."""
    if not isinstance(video, dict):
        raise ValueError("كل فيديو يجب أن يكون قاموسًا فيه channel وtitle.")
    channel = video.get("channel")
    title = video.get("title")
    if not isinstance(channel, str) or not channel.strip():
        raise ValueError("فيديو بلا قناة — كل فيديو يحتاج channel نصيًا غير فارغ.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("فيديو بلا عنوان — كل فيديو يحتاج title نصيًا غير فارغ.")
    platform = video.get("platform", "")
    if platform is None:
        platform = ""
    if not isinstance(platform, str):
        raise ValueError("منصة الفيديو (platform) يجب أن تكون نصًا.")
    url = video.get("url", "")
    if url is None:
        url = ""
    if not isinstance(url, str):
        raise ValueError("رابط الفيديو (url) يجب أن يكون نصًا.")
    return {
        "platform": platform.strip(),
        "channel": channel.strip(),
        "title": title.strip(),
        "views": _check_number(video.get("views"), "المشاهدات"),
        "likes": _check_number(video.get("likes"), "الإعجابات"),
        "comments": _check_number(video.get("comments"), "التعليقات"),
        "saves": _check_number(video.get("saves"), "الحفظ"),
        "shares": _check_number(video.get("shares"), "المشاركات"),
        "url": url.strip(),
        "duration": _check_number(video.get("duration"), "المدة"),
    }


def _check_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"«{name}» يجب أن تكون عددًا صحيحًا موجبًا.")
    return value


def _rate(numerator, denominator):
    """نسبة عدد/عدد — أو None إن غاب أحد الطرفين أو كان المقام صفرًا."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _pct(rate):
    """نسّق نسبة كـ «12.5%» — أو «غير مقاس» إن كانت None."""
    if rate is None:
        return "غير مقاس"
    return f"{rate * 100:.1f}%"


def _suggest_title(title):
    """عنوان اقتراح الطابور: عنوان المصدر بلا بادئة «جزء N»."""
    return _SERIES_PREFIX_RE.sub("", title).strip() or title.strip()


def _score(save_rate, share_rate, multiplier):
    """درجة 0–100 من الإشارات المقاسة فقط (غير المقاس = صفر)."""
    total = 0.0
    if save_rate is not None:
        total += SAVE_WEIGHT * min(save_rate / SAVE_RATE_REF, 1.0)
    if share_rate is not None:
        total += SHARE_WEIGHT * min(share_rate / SHARE_RATE_REF, 1.0)
    if multiplier is not None:
        if multiplier == float("inf"):
            total += MULTIPLIER_WEIGHT
        else:
            total += MULTIPLIER_WEIGHT * min(multiplier / MULTIPLIER_REF, 1.0)
    return round(total, 1)


def _reason(save_rate, save_basis, share_rate, multiplier):
    """سبب عربي بالقياسات — «غير مقاس» لأي إشارة بلا مصدر."""
    save_text = _pct(save_rate)
    if save_rate is not None:
        basis = "الإعجابات" if save_basis == "likes" else "المشاهدات"
        save_text += f" (من {basis})"
    share_text = _pct(share_rate)
    if multiplier is None:
        mult_text = "غير مقاس"
    elif multiplier == float("inf"):
        mult_text = "بلا حد (وسيط القناة صفر)"
    else:
        mult_text = f"×{multiplier:.2f}"
    return (f"حفظ {save_text}؛ مشاركة {share_text}؛ "
            f"مضاعف القناة {mult_text}")


def load_videos_json(text):
    """اقرأ مدخل JSON نصيًا إلى قائمة فيديوهات منظّفة.

    يرفع ``ValueError`` عربيًا عند JSON تالف أو مدخل ليس
    قائمة أو فيديو فاسد — بلا أي كتابة.
    """
    if not isinstance(text, str):
        raise ValueError("مدخل JSON يجب أن يكون نصًا.")
    try:
        data = json.loads(text)
    except ValueError:
        raise ValueError("مدخل JSON تالف — أعطِ قائمة فيديوهات JSON صالحة.")
    if not isinstance(data, list):
        raise ValueError("مدخل الترند يجب أن يكون قائمة فيديوهات.")
    if len(data) == 0:
        raise ValueError("قائمة الفيديوهات فارغة — أعطِ فيديوًا واحدًا على الأقل.")
    return [_clean_video(video) for video in data]


def scout_trends(videos, top_n=5, min_videos=4):
    """رتّب فيديوهات ترند واقترح إدخالات طابور.

    ``videos``: قائمة قواميس {platform, channel, title,
    views?, likes, comments, saves, shares, url, duration?}
    (العدّادات كلها اختيارية؛ والقناة والعنوان إلزاميان).
    ``top_n``: عدد اقتراحات الطابور المطلوبة. ``min_videos``:
    أقل عدد فيديوهات بمشاهدات للقناة حتى يُحسب مضاعفها.

    ترجع قاموسًا: ``candidates`` (كل الفيديوهات مرتبة
    بالدرجة: المنصة والقناة والعنوان والرابط والمدة
    والعدّادات ونسبتا الحفظ والمشاركة وأساس الحفظ
    والمضاعف والنمط والحالة والدرجة والسبب)، و``suggestions``
    (أول ``top_n`` مرشح غير مستبعد بصيغة إدخال الطابور)،
    و``skipped_channels`` (قناة → عدد فيديوهاتها بمشاهدات،
    لمن دون ``min_videos``)، و``excluded`` (عناوين المستبعدين)،
    و``reference`` (المراجع المقاسة).

    مدخلات فاسدة (قائمة فارغة، عدّاد سالب/غير رقمي، فيديو
    بلا قناة/عنوان) → ``ValueError`` عربي.
    """
    top_n = _check_positive_int(top_n, "top_n")
    min_videos = _check_positive_int(min_videos, "min_videos")
    if isinstance(videos, str):
        videos = load_videos_json(videos)
    if not isinstance(videos, (list, tuple)):
        raise ValueError("مدخل الترند يجب أن يكون قائمة فيديوهات.")
    if len(videos) == 0:
        raise ValueError("قائمة الفيديوهات فارغة — أعطِ فيديوًا واحدًا على الأقل.")
    cleaned = [_clean_video(video) for video in videos]

    by_channel = {}
    for video in cleaned:
        by_channel.setdefault(video["channel"], []).append(video)

    medians = {}
    skipped_channels = {}
    for channel in sorted(by_channel):
        views = [v["views"] for v in by_channel[channel]
                 if v["views"] is not None]
        if len(views) < min_videos:
            skipped_channels[channel] = len(views)
            continue
        medians[channel] = statistics.median(views)

    candidates = []
    for video in cleaned:
        save_rate = _rate(video["saves"], video["likes"])
        save_basis = "likes" if save_rate is not None else None
        if save_rate is None:
            save_rate = _rate(video["saves"], video["views"])
            save_basis = "views" if save_rate is not None else None
        share_rate = _rate(video["shares"], video["likes"])
        median = medians.get(video["channel"])
        if median is None or video["views"] is None:
            multiplier = None
        elif median == 0:
            multiplier = float("inf") if video["views"] > 0 else 0.0
        else:
            multiplier = round(video["views"] / median, 2)
        pattern = classify_hook_pattern(video["title"])
        status = (STATUS_EXCLUDED if pattern == PATTERN_HORROR
                  else STATUS_CANDIDATE)
        score = _score(save_rate, share_rate, multiplier)
        candidates.append({
            "platform": video["platform"],
            "channel": video["channel"],
            "title": video["title"],
            "url": video["url"],
            "duration": video["duration"],
            "views": video["views"],
            "likes": video["likes"],
            "comments": video["comments"],
            "saves": video["saves"],
            "shares": video["shares"],
            "save_rate": (round(save_rate, 4)
                          if save_rate is not None else None),
            "save_basis": save_basis,
            "share_rate": (round(share_rate, 4)
                           if share_rate is not None else None),
            "multiplier": multiplier,
            "pattern": pattern,
            "status": status,
            "score": score,
            "reason": _reason(save_rate, save_basis, share_rate,
                              multiplier),
        })
    # الدرجة تنازليًا، ثم الإعجابات، ثم العنوان — حتمي بلا عشوائية.
    candidates.sort(key=lambda e: (-e["score"],
                                   -(e["likes"] if e["likes"] is not None
                                     else -1),
                                   e["title"]))

    suggestions = []
    for entry in candidates:
        if entry["status"] == STATUS_EXCLUDED:
            continue
        suggestions.append({
            "title": _suggest_title(entry["title"]),
            "hook": entry["title"],
            "moral_angle": _MORAL_ANGLE.get(entry["pattern"],
                                            _MORAL_ANGLE[PATTERN_OTHER]),
            "source_url": entry["url"],
            "pattern": entry["pattern"],
            "score": entry["score"],
            "reason": entry["reason"],
        })
        if len(suggestions) >= top_n:
            break

    return {
        "candidates": candidates,
        "suggestions": suggestions,
        "skipped_channels": skipped_channels,
        "excluded": [e["title"] for e in candidates
                     if e["status"] == STATUS_EXCLUDED],
        "total": len(candidates),
        "reference": {
            "save_rate_range": [SAVE_RATE_LOW, SAVE_RATE_REF],
            "share_rate_max": SHARE_RATE_REF,
            "source": "تحليل ترند TikTok 2026-11-26",
        },
    }


def _jsonable(value):
    """حوّل نتيجة لصيغة JSON صالحة (inf ← «∞»)."""
    if isinstance(value, float) and value == float("inf"):
        return "∞"
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def to_json(result):
    """سلسل نتيجة ``scout_trends`` إلى JSON عربي (بلا ASCII هارب)."""
    if not isinstance(result, dict):
        raise ValueError("نتيجة الكشّاف يجب أن تكون قاموسًا من scout_trends.")
    return json.dumps(_jsonable(result), ensure_ascii=False, indent=2) + "\n"


def format_report(result):
    """نسّق نتيجة ``scout_trends`` تقريرًا عربيًا.

    يحوي دائمًا سطر «تصنيف بالكلمات فقط — ليس ادعاءً بسبب
    النجاح»، وسطر «لا أرقام مخترعة»، وتنبيهًا أن الاقتراحات
    لا تكتب في ملف الطابور.
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة الكشّاف يجب أن تكون قاموسًا من scout_trends.")
    for key in ("candidates", "suggestions", "skipped_channels",
                "excluded", "total"):
        if key not in result:
            raise ValueError(f"نتيجة الكشّاف ناقصة — ينقصها «{key}».")
    candidates = result["candidates"]
    suggestions = result["suggestions"]
    skipped = result["skipped_channels"]
    lines = ["كشّاف ترندات القصص — مرشحون لطابور الأسبوع",
             "=========================================="]
    if not candidates:
        lines.append("لا مرشحين — القائمة فارغة.")
    for i, entry in enumerate(candidates, 1):
        lines.append(f"{i}. «{entry['title']}» — {entry['channel']}"
                     + (f" ({entry['platform']})" if entry["platform"] else ""))
        lines.append(f"   النمط: {entry['pattern']} | الحالة: {entry['status']} | "
                     f"الدرجة: {entry['score']:.1f}/100")
        lines.append(f"   {entry['reason']}")
        if entry["url"]:
            lines.append(f"   المصدر: {entry['url']}")
    lines.append("")
    lines.append(f"اقتراحات إدخالات الطابور ({len(suggestions)}):")
    if not suggestions:
        lines.append("لا اقتراحات — كل المرشحين مستبعدون أو القائمة فارغة.")
    for i, suggestion in enumerate(suggestions, 1):
        lines.append(f"{i}. «{suggestion['title']}» "
                     f"[{suggestion['pattern']}] — {suggestion['score']:.1f}/100")
        lines.append(f"   الهوك: «{suggestion['hook']}»")
        lines.append(f"   زاوية العبرة: {suggestion['moral_angle']}")
        lines.append(f"   السبب: {suggestion['reason']}")
    if result["excluded"]:
        lines.append("")
        lines.append("مستبعدون (رعب ريفي/غامض — خارج الخط بانتظار "
                     "قرار المستخدم، لا يُقترحون أبدًا):")
        for title in result["excluded"]:
            lines.append(f"- «{title}»")
    if skipped:
        lines.append("")
        lines.append("قنوات بلا مضاعف (أقل من 4 فيديوهات بمشاهدات "
                     "— المضاعف غير محسوب):")
        for channel in sorted(skipped):
            lines.append(f"- {channel}: {skipped[channel]} فيديوهات بمشاهدات")
    lines.append("")
    lines.append("تنبيه: الاقتراحات لا تُكتب في ملف الطابور — "
                 "الإضافة قرار المشغّل.")
    lines.append(NO_INVENTED_NUMBERS)
    lines.append(DISCLAIMER)
    return "\n".join(lines)
