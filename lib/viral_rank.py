#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""ترتيب الشواذ بمضاعف القناة — جولة v0.1.57 (W4، من قائمة فحص yt-viral).

الفكرة (من القائمة فقط، بلا نسخ كود):
عدد المشاهدات الخام يرتّب حجم القناة لا الأفكار. الترتيب الصحيح
بمضاعف كل فيديو على **وسيط قناته الخاص** — وهي الصيغة الوحيدة
للسؤال التي تخص الفيديو نفسه.

قواعد الوحدة:
- المدخل قائمة جاهزة فقط [{channel, title, views, url, duration}]
  يجمعها المستخدم (صفحة عامة أو ``yt-dlp --flat-playlist -J`` أو
  يدويًا). قراءة فقط: بلا شبكة وبلا تسجيل دخول وبلا جلب وبلا LLM.
- القناة تحتاج 4 فيديوهات على الأقل (``min_videos``) وإلا فالوسيط
  بلا معنى — والقناة الأقل تُتخطى مع ذكر ذلك في الناتج.
- المضاعف = مشاهدات الفيديو / وسيط مشاهدات قناته. وسيط 0 يعني أن
  الفيديو النمطي للقناة بلا مشاهدات؛ فأي فيديو بمشاهدات يُضاعف
  بلا حد (``inf``) وفيديو بلا مشاهدات مضاعفه 0.
- تصنيف صيغة العنوان حكم على الكلمات فقط — ليس ادعاءً بسبب
  النجاح. ترتيب القواعد (أول مطابقة تفوز):
  1. «الجزء X من Y» — ``الجزء <رقم> من <رقم>``.
  2. «قصة حقيقية» — العبارة حرفيًا في العنوان.
  3. سؤال — علامة «؟» أو البدء بـ «كيف/لماذا/ماذا/هل».
  4. رقم في البداية — أول كلمة رقم (عربي أو غربي).
  5. فضول — «السر/الحقيقة/كشف/لن تصدق» (وصيغها).
  6. وإلا «أخرى».
- النمط المشترك يُحسب بصدق: الصيغة الأكثر شيوعًا بين المرتبين
  الأوائل + المدة الوسيطة ونطاقها. ولا يُعدّ مشتركًا واضحًا إلا
  بأغلبية (أكثر من نصف المرتبين)؛ وإن لم توجد أغلبية فالناتج
  «لا نمط واحد واضح» بدل اختراع نمط.
- كل تقرير يطبع سطر: «تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح».
"""
import math
import re
import statistics

__all__ = ["rank_outliers", "format_report", "classify_title_format"]

# صيغ العناوين (قيم الإخراج — عربية).
FORMAT_PART = "جزء من سلسلة"
FORMAT_TRUE_STORY = "قصة حقيقية"
FORMAT_QUESTION = "سؤال"
FORMAT_NUMBER_FIRST = "رقم في البداية"
FORMAT_CURIOSITY = "فضول"
FORMAT_OTHER = "أخرى"

NO_CLEAR_PATTERN = "لا نمط واحد واضح"

# سطر يُطبع في كل تقرير — تصنيف الصيغة حكم على الكلمات لا ادعاء
# بسبب النجاح.
DISCLAIMER = "تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح."

# تطبيع حروف عربية قبل المطابقة (ة↔ه، أ/إ/آ↔ا، ى↔ي) + إزالة التشكيل.
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})


def _normalize(text):
    """تطبيع نص عربي للمطابقة فقط (لا يغيّر النص المعروض)."""
    text = _DIACRITICS_RE.sub("", text)
    return text.translate(_NORMALIZE_TABLE)


# الأرقام العربية المشرقية تُعامل كأرقام في «رقم في البداية».
_NUMBER_FIRST_RE = re.compile(r"^\s*[0-9٠-٩]+")
_PART_RE = re.compile(r"الجزء\s*[0-9٠-٩]+\s*من\s*[0-9٠-٩]+")
_QUESTION_WORDS = ("كيف", "لماذا", "ماذا", "هل")
_CURIOSITY_WORDS = ("السر", "الحقيقه", "كشف", "لن تصدق")


def classify_title_format(title):
    """صنّف صيغة عنوان من كلماته فقط.

    ترتيب القواعد موثّق في مقدّمة الوحدة. يرفع ``ValueError``
    عربيًا إن كان العنوان فارغًا أو غير نص.
    """
    if not isinstance(title, str) or not title.strip():
        raise ValueError("عنوان الفيديو فارغ أو غير نص — أعطِ عنوانًا نصيًا.")
    text = _normalize(title.strip())
    if _PART_RE.search(text):
        return FORMAT_PART
    if "قصه حقيقيه" in text:
        return FORMAT_TRUE_STORY
    if "؟" in text or text.startswith(_QUESTION_WORDS):
        return FORMAT_QUESTION
    if _NUMBER_FIRST_RE.match(text):
        return FORMAT_NUMBER_FIRST
    if any(word in text for word in _CURIOSITY_WORDS):
        return FORMAT_CURIOSITY
    return FORMAT_OTHER


def _check_number(value, name):
    """تحقّق أن القيمة عدد حقيقي منتهٍ غير سالب (بلا bool)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا — وصلت قيمة غير رقمية.")
    if not math.isfinite(value):
        raise ValueError(f"«{name}» يجب أن تكون رقمًا منتهيًا.")
    if value < 0:
        raise ValueError(f"«{name}» سالبة — المشاهدات والمدة لا تكونان سالبتين.")
    return value


def _clean_video(video):
    """تحقّق من فيديو واحد وأعده منظّفًا؛ وإلا ``ValueError`` عربي."""
    if not isinstance(video, dict):
        raise ValueError("كل فيديو يجب أن يكون قاموسًا فيه channel وtitle وviews.")
    channel = video.get("channel")
    title = video.get("title")
    if not isinstance(channel, str) or not channel.strip():
        raise ValueError("فيديو بلا قناة — كل فيديو يحتاج channel نصيًا غير فارغ.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("فيديو بلا عنوان — كل فيديو يحتاج title نصيًا غير فارغ.")
    if "views" not in video:
        raise ValueError("فيديو بلا مشاهدات — كل فيديو يحتاج views رقميًا.")
    views = _check_number(video["views"], "المشاهدات")
    url = video.get("url", "")
    if url is None:
        url = ""
    if not isinstance(url, str):
        raise ValueError("رابط الفيديو (url) يجب أن يكون نصًا.")
    duration = video.get("duration")
    if duration is not None:
        duration = _check_number(duration, "المدة")
    return {
        "channel": channel.strip(),
        "title": title.strip(),
        "views": views,
        "url": url.strip(),
        "duration": duration,
    }


def _check_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"«{name}» يجب أن تكون عددًا صحيحًا موجبًا.")
    return value


def _median_duration_text(durations):
    """نص المدة الوسيطة ونطاقها؛ أو None إن لم توجد مدد."""
    if not durations:
        return None
    median = statistics.median(durations)
    low, high = min(durations), max(durations)
    return f"المدة الوسيطة {_format_seconds(median)} (النطاق {_format_seconds(low)}–{_format_seconds(high)})"


def _format_seconds(seconds):
    """نسّق مدة بالثواني: «45 ث» أو «1:30 د»."""
    total = int(round(seconds))
    if total < 60:
        return f"{total} ث"
    return f"{total // 60}:{total % 60:02d} د"


def _shared_pattern(ranked):
    """الشيء البنيوي الواحد المشترك بين المرتبين الأوائل — بصدق.

    أغلبية صيغة عنوان واحدة (أكثر من نصف المرتبين) + المدة
    الوسيطة ونطاقها. بلا أغلبية: «لا نمط واحد واضح».
    """
    if not ranked:
        return NO_CLEAR_PATTERN
    counts = {}
    for entry in ranked:
        counts[entry["title_format"]] = counts.get(entry["title_format"], 0) + 1
    top_format, top_count = max(counts.items(), key=lambda item: (item[1], item[0]))
    if top_count * 2 <= len(ranked):
        return NO_CLEAR_PATTERN
    durations = [e["duration"] for e in ranked if e["duration"] is not None]
    duration_text = _median_duration_text(durations)
    text = (f"الصيغة الأكثر شيوعًا: {top_format} "
            f"({top_count} من {len(ranked)})")
    if duration_text:
        text += f"؛ {duration_text}"
    else:
        text += "؛ المدة: غير متوفرة"
    return text


def rank_outliers(videos, top_n=5, min_videos=4):
    """رتّب الفيديوهات بمضاعف كل فيديو على وسيط قناته الخاص.

    ``videos``: قائمة قواميس {channel, title, views, url, duration}
    (url وduration اختياريان). ``top_n``: عدد الأوائل المطلوب.
    ``min_videos``: أقل عدد فيديوهات للقناة حتى يُحسب وسيطها.

    ترجع قاموسًا: ``ranked`` (الأوائل: title وchannel وviews وmedian
    وmultiplier وurl وduration وtitle_format)، و``skipped_channels``
    (قناة → عدد فيديوهاتها، لمن دون ``min_videos``)، و``shared_pattern``
    (النمط المشترك أو «لا نمط واحد واضح»).

    مدخلات فاسدة (قائمة فارغة، مشاهدات سالبة/غير رقمية، فيديو
    بلا قناة/عنوان/مشاهدات) → ``ValueError`` عربي.
    """
    top_n = _check_positive_int(top_n, "top_n")
    min_videos = _check_positive_int(min_videos, "min_videos")
    if not isinstance(videos, (list, tuple)):
        raise ValueError("مدخل الترتيب يجب أن يكون قائمة فيديوهات.")
    if len(videos) == 0:
        raise ValueError("قائمة الفيديوهات فارغة — أعطِ فيديوًا واحدًا على الأقل.")
    cleaned = [_clean_video(video) for video in videos]

    by_channel = {}
    for video in cleaned:
        by_channel.setdefault(video["channel"], []).append(video)

    skipped_channels = {}
    ranked = []
    for channel in sorted(by_channel):
        group = by_channel[channel]
        if len(group) < min_videos:
            skipped_channels[channel] = len(group)
            continue
        median = statistics.median([v["views"] for v in group])
        for video in group:
            if median == 0:
                multiplier = float("inf") if video["views"] > 0 else 0.0
            else:
                multiplier = round(video["views"] / median, 2)
            ranked.append({
                "title": video["title"],
                "channel": channel,
                "views": video["views"],
                "median": median,
                "multiplier": multiplier,
                "url": video["url"],
                "duration": video["duration"],
                "title_format": classify_title_format(video["title"]),
            })
    # المضاعف تنازليًا، ثم المشاهدات، ثم العنوان — حتمي بلا عشوائية.
    ranked.sort(key=lambda e: (-e["multiplier"], -e["views"], e["title"]))
    ranked = ranked[:top_n]
    return {
        "ranked": ranked,
        "skipped_channels": skipped_channels,
        "shared_pattern": _shared_pattern(ranked),
    }


def format_report(result):
    """نسّق نتيجة ``rank_outliers`` تقريرًا عربيًا.

    يحوي دائمًا سطر «تصنيف بالكلمات فقط — ليس ادعاءً بسبب النجاح»،
    وسطر السؤال الأصعب (قرار بشري: أيّ فيديو يستطيع المستخدم
    صنعه هذا الأسبوع بصوته وبما لديه — الوحدة لا تقرره عنه).
    """
    if not isinstance(result, dict):
        raise ValueError("نتيجة الترتيب يجب أن تكون قاموسًا من rank_outliers.")
    for key in ("ranked", "skipped_channels", "shared_pattern"):
        if key not in result:
            raise ValueError(f"نتيجة الترتيب ناقصة — ينقصها «{key}».")
    ranked = result["ranked"]
    skipped = result["skipped_channels"]
    lines = ["ترتيب الشواذ بمضاعف القناة", "=========================="]
    if not ranked:
        lines.append("لا فيديوهات مرتّبة — كل القنوات دون الحد الأدنى "
                     "لعدد الفيديوهات.")
    for i, entry in enumerate(ranked, 1):
        mult = "∞" if entry["multiplier"] == float("inf") else f"{entry['multiplier']:.2f}"
        duration = (_format_seconds(entry["duration"])
                    if entry["duration"] is not None else "غير مذكورة")
        lines.append(f"{i}. «{entry['title']}» — {entry['channel']}")
        lines.append(f"   المشاهدات: {entry['views']:,} | وسيط القناة: "
                     f"{entry['median']:,} | المضاعف: ×{mult}")
        lines.append(f"   المدة: {duration} | صيغة العنوان: "
                     f"{entry['title_format']}")
        if entry["url"]:
            lines.append(f"   الرابط: {entry['url']}")
    lines.append("")
    lines.append(f"النمط المشترك: {result['shared_pattern']}")
    if skipped:
        lines.append("قنوات تُخطّيت (أقل من 4 فيديوهات — الوسيط بلا معنى):")
        for channel in sorted(skipped):
            lines.append(f"- {channel}: {skipped[channel]} فيديوهات")
    lines.append("")
    lines.append("السطر الأصعب (قرار بشري): أيّ فيديو من الأوائل "
                 "تستطيع صنعه هذا الأسبوع بصوتك وبما لديك؟ "
                 "الوحدة لا تقرر ذلك عنك.")
    lines.append(DISCLAIMER)
    return "\n".join(lines)
