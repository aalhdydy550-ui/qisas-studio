#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قارئ تصدير احتفاظ يوتيوب — قائمة فحص yt-retention (جولة v0.1.57، W5).

يقرأ ملف CSV المصدَّر من YouTube Studio (فيديو ← التحليلات ←
التفاعل ← أيقونة التنزيل ← «احتفاظ الجمهور») ويشخّص ثلاث
مشكلات مختلفة فقط، من الفكرة لا من أي كود منقول:

- **تسرب الهوك**: النسبة المفقودة في أول 30 ثانية. صحي إن كان
  أقل من 25%؛ وإصلاحه دائمًا أول 15 ثانية من النص لا المونتاج.
- **المنحدرات**: هبوط حاد مفرد بين نقطتين متتاليتين. مع نص
  مكتوب (SRT أو ASS) يُطبع ما كان يُقال عند كل منحدر فيصبح
  التقرير قابلًا للتنفيذ.
- **الانزلاق**: النزيف الثابت عبر الثلث الأوسط؛ انزلاق مسطح
  يعني الإيقاع، وإصلاحه القص لا إعادة الكتابة.

الناتج: أكبر تسرب + تغيير واحد فقط. وإن كان تسرب الهوك صحيًا
ولا منحدرات والانزلاق مسطحًا فالفيديو سليم والمشكلة في التغليف
(العنوان/المصغرة) لا في المحتوى.

بايثون بالمكتبة القياسية فقط، حتمي، بلا شبكة وبلا LLM.
"""
import csv
import io
import os
import re

# --- ثوابت موثقة (اختيارات إرشادية لا قياسات من يوتيوب) ---
#
# HOOK_WINDOW_SECONDS = 30: نافذة تسرب الهوك من قائمة الفحص نفسها.
# HOOK_HEALTHY_MAX_PCT = 25: حد الصحة من قائمة الفحص نفسها
# (أقل من 25% مفقودًا في أول 30 ثانية صحي).
#
# CLIFF_DROP_MIN_PCT = 10: منحدر = هبوط >= 10 نقاط احتفاظ في
# خطوة واحدة بين نقطتين متتاليتين. السبب: منحنى الاحتفاظ
# الطبيعي ينجرف نقطة أو نقطتين أو ثلاثًا في كل خطوة على بيانات
# Studio (ثانية بثانية أو نقطة كل بضع ثوانٍ)؛ فهبوط 10 نقاط
# دفعة واحدة أبعد بكثير من الانجراف والضجيج، ويميز لحظة واحدة
# (تغيير موضوع بلا تمهيد، قراءة راعٍ، إعداد طويل) عن النزيف
# التدريجي. حد أقل (مثل 5) كان سيُصنّف الانجراف العادي منحدرات.
# ملاحظة: مع عيّنة خشنة (نقطة كل 5 ثوانٍ مثلًا) قد يغطي الهبوط
# عدة ثوانٍ؛ يُبلَّغ عند نقطة الهبوط نفسها كما هي في البيانات.
#
# SLIDE_FLAT_MAX_PCT = 8: انزلاق حقيقي = خسارة متوقعة >= 8 نقاط
# عبر الثلث الأوسط كاملًا (من ميل الانحدار الخطي). السبب: خسارة
# أقل من ذلك عبر ثلث كامل هي انجراف عادي لا تستدعي قصًا؛ و8
# نقاط خسارة ملموسة يلاحظها المشاهد إيقاعًا بطيئًا.
# الانزلاق يُحسب كانحدار خطي (least squares) على نقاط الثلث
# الأوسط، لا فرق متوسطين، لأن الميل يقاوم نقطة شاذة واحدة
# أفضل من فرق المتوسطين — وبعد إزالة قفزات المنحدرات من
# السلسلة أولًا، حتى لا يُحسب هبوط لحظة واحدة نزيفًا ثابتًا.
HOOK_WINDOW_SECONDS = 30.0
HOOK_HEALTHY_MAX_PCT = 25.0
CLIFF_DROP_MIN_PCT = 10.0
SLIDE_FLAT_MAX_PCT = 8.0

_VERDICT_HOOK = "تسرب الهوك"
_VERDICT_CLIFF = "منحدر"
_VERDICT_SLIDE = "انزلاق"
_VERDICT_HEALTHY = "سليم"

_FIX_HOOK = ("أعد كتابة أول 15 ثانية من النص: افتح بسؤال لا يُغلق "
             "وثبّت العائد فورًا، بلا مقدمات ولا تمهيد.")
_FIX_SLIDE = ("قصّ الوسط: احذف كل جملة لا تدفع القصة للأمام، "
              "ولا تعيد كتابة النص.")
_FIX_HEALTHY = ("لا تغيّر النص ولا المونتاج — راجع التغليف أولًا: "
                "العنوان والمصغرة.")
_PACKAGING_NOTE = ("الفيديو سليم: تسرب الهوك صحي ولا منحدرات ولا "
                   "انزلاق مسطح؛ المشكلة غالبًا في التغليف "
                   "(العنوان/المصغرة) لا في المحتوى.")

# أسماء أعمدة شائعة في تصدير Studio (إنجليزي وعربي). التطبيع:
# صغير + إزالة «%» والأقواس والمسافات الزائدة.
_TIME_NAMES = (
    "time", "timestamp", "second", "seconds", "elapsed",
    "video time", "videotime", "time (s)", "time (seconds)",
    "time sec", "t", "الوقت", "الثانية", "الثواني", "زمن",
)
_RETENTION_NAMES = (
    "retention", "audience retention", "percentage viewed",
    "percent viewed", "% viewed", "viewed", "average percentage viewed",
    "average percentage", "retention (%)", "retention %",
    "الاحتفاظ", "احتفاظ الجمهور", "نسبة المشاهدة",
    "نسبة المشاهدة %", "متوسط نسبة المشاهدة",
)

_SRT_TIME_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")
_ASS_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[.:](\d{2,3})")
_ASS_STYLE_RE = re.compile(r"\{[^}]*\}")


class RetentionError(ValueError):
    """خطأ عربي واضح في مدخلات قارئ الاحتفاظ."""


def _norm_header(name):
    """تطبيع اسم عمود للمقارنة: صغير، بلا % وأقواس ومسافات زائدة."""
    name = (name or "").strip().lower()
    name = name.replace("%", "").replace("(", " ").replace(")", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _parse_time(raw):
    """تحويل وقت إلى ثوانٍ: عدد صريح، أو mm:ss، أو hh:mm:ss.

    يرجع float أو None إن تعذّر الفهم.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = text.rstrip("sSث").strip()
    if ":" in text:
        parts = text.split(":")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            return None
        total = 0.0
        for n in nums:
            total = total * 60.0 + n
        return total
    try:
        return float(text)
    except ValueError:
        return None


def _parse_retention(raw, force_percent):
    """تحويل قيمة احتفاظ إلى نسبة 0-100.

    يقبل «85» و«85%» و«0.85». إن كان العمود كلّه <= 1 بلا علامة %
    يُفهم كسرًا (0.85 تعني 85%)؛ وإلا فهو نسبة مئوية مباشرة.
    يرجع float أو None إن تعذّر الفهم.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace(",", "").strip()
    is_percent_marked = "%" in text
    text = text.replace("%", "").strip()
    try:
        value = float(text)
    except ValueError:
        return None
    if not force_percent and not is_percent_marked and value <= 1.0:
        # كسر 0-1 — لكن قيمة 0 أو 1 وحدها غامضة؛ القاعدة موثقة
        # أعلاه: عمود كله <= 1 يُقرأ كسرًا. يضبطه المتصل بعد
        # فحص العمود كاملًا عبر force_percent.
        return value * 100.0
    return value


def _read_csv_text(csv_text_or_path):
    """إرجاع نص CSV من نص مباشر أو مسار ملف.

    مسار غير موجود -> خطأ عربي واضح.
    """
    if isinstance(csv_text_or_path, (os.PathLike,)):
        csv_text_or_path = os.fspath(csv_text_or_path)
    if isinstance(csv_text_or_path, str):
        stripped = csv_text_or_path.strip()
        looks_like_path = ("\n" not in stripped and "\r" not in stripped
                           and len(stripped) < 4096)
        if looks_like_path and (stripped.endswith(".csv")
                                or os.path.sep in stripped
                                or os.path.exists(stripped)):
            if not os.path.exists(stripped):
                raise RetentionError(
                    "الملف غير موجود: %s — تأكد من مسار تصدير "
                    "الاحتفاظ (CSV) من YouTube Studio." % stripped)
            with open(stripped, "r", encoding="utf-8-sig",
                      newline="") as fh:
                return fh.read()
        return csv_text_or_path
    raise RetentionError("مدخل CSV غير صالح: متوقع نص CSV أو مسار ملف.")


def _detect_columns(rows):
    """اكتشاف عمودي الوقت والاحتفاظ من صف الترويسة.

    يرجع (time_idx, retention_idx) أو (None, None) إن لم توجد
    ترويسة معروفة.
    """
    if not rows:
        return None, None
    header = [_norm_header(c) for c in rows[0]]
    time_idx = None
    retention_idx = None
    for idx, name in enumerate(header):
        if time_idx is None and name in _TIME_NAMES:
            time_idx = idx
        if retention_idx is None and name in _RETENTION_NAMES:
            retention_idx = idx
    return time_idx, retention_idx


def _parse_points(csv_text):
    """تحليل CSV إلى قائمة [(ثوانٍ، احتفاظ %)] مرتبة بالوقت.

    متسامح: يكتشف الترويسة أو يفترض عمودين رقميين بلا ترويسة،
    ويقبل الفاصلة أو الفاصلة المنقوطة أو التبويب كفاصل.
    """
    text = (csv_text or "").lstrip("\ufeff")
    if not text.strip():
        raise RetentionError(
            "ملف CSV فارغ — صدّر «احتفاظ الجمهور» من YouTube Studio "
            "(فيديو ← التحليلات ← التفاعل ← أيقونة التنزيل) وحاول مجددًا.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [row for row in reader if row and any(c.strip() for c in row)]
    if not rows:
        raise RetentionError(
            "ملف CSV فارغ — لا توجد صفوف بيانات فيه.")
    time_idx, retention_idx = _detect_columns(rows)
    data_rows = rows[1:] if time_idx is not None else rows
    if time_idx is None and retention_idx is None:
        # بلا ترويسة معروفة: أول عمودين رقميين.
        time_idx, retention_idx = 0, 1
    if time_idx is None:
        time_idx = 0
    if retention_idx is None:
        retention_idx = 1 if time_idx == 0 else 0
    raw_values = []
    for row in data_rows:
        if max(time_idx, retention_idx) >= len(row):
            continue
        t = _parse_time(row[time_idx])
        if t is None:
            continue
        raw_values.append((t, row[retention_idx]))
    if len(raw_values) < 2:
        raise RetentionError(
            "لا توجد أعمدة صالحة في CSV: لم أجد عمود وقت وعمود "
            "احتفاظ بأسماء شائعة، ولا صفين رقميين صالحين. تأكد أن "
            "الملف هو تصدير «احتفاظ الجمهور» من YouTube Studio.")
    # الكسر أم النسبة؟ إن كانت كل القيم <= 1 وبلا علامة % فهي كسور.
    numeric = []
    for _t, raw in raw_values:
        txt = str(raw).strip().replace("%", "").strip()
        try:
            numeric.append(float(txt))
        except ValueError:
            numeric.append(None)
    valid_nums = [v for v in numeric if v is not None]
    if not valid_nums:
        raise RetentionError(
            "لا توجد أعمدة صالحة في CSV: عمود الاحتفاظ بلا قيم رقمية.")
    force_percent = (max(valid_nums) > 1.0
                     or any("%" in str(raw) for _t, raw in raw_values))
    points = []
    for (t, raw), num in zip(raw_values, numeric):
        if num is None:
            continue
        value = _parse_retention(raw, force_percent)
        if value is None:
            continue
        points.append((t, value))
    if len(points) < 2:
        raise RetentionError(
            "لا توجد أعمدة صالحة في CSV: أقل من نقطتين صالحتين "
            "للوقت والاحتفاظ.")
    points.sort(key=lambda p: p[0])
    deduped = []
    for t, v in points:
        if deduped and abs(t - deduped[-1][0]) < 1e-9:
            deduped[-1] = (t, v)
        else:
            deduped.append((t, v))
    return deduped


def _value_at(points, when):
    """قيمة الاحتفاظ عند لحظة (استيفاء خطي بين نقطتين)."""
    if when <= points[0][0]:
        return points[0][1]
    if when >= points[-1][0]:
        return points[-1][1]
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        if t0 <= when <= t1:
            if t1 == t0:
                return v1
            frac = (when - t0) / (t1 - t0)
            return v0 + frac * (v1 - v0)
    return points[-1][1]


def _srt_seconds(match_groups):
    """ثوانٍ من مجموعات طابع SRT (ساعات، دقائق، ثوانٍ، أجزاء)."""
    h, m, s, ms = (int(g) for g in match_groups)
    return h * 3600.0 + m * 60.0 + s + ms / 1000.0


def _parse_transcript(transcript_text):
    """تحليل نص مكتوب إلى إشارات [(بداية، نهاية، نص)].

    يقبل SRT (طوابع 00:00:05,000) وASS مبسط (أسطر Dialogue:
    بالصيغة H:MM:SS.cc). أي نص بلا طوابع يُتجاهل بصمت.
    """
    if transcript_text is None:
        return []
    if isinstance(transcript_text, (os.PathLike,)):
        transcript_text = os.fspath(transcript_text)
    if isinstance(transcript_text, str):
        stripped = transcript_text.strip()
        if ("\n" not in stripped and os.path.exists(stripped)):
            with open(stripped, "r", encoding="utf-8-sig") as fh:
                transcript_text = fh.read()
    text = str(transcript_text or "")
    cues = []
    # SRT: كتل مفصولة بسطر فارغ، كل كتلة فيها طابع --> ونص.
    for block in re.split(r"\n\s*\n", text):
        match = _SRT_TIME_RE.search(block)
        if not match:
            continue
        start = _srt_seconds(match.groups()[:4])
        end = _srt_seconds(match.groups()[4:])
        lines = block[match.end():].strip().splitlines()
        lines = [ln.strip() for ln in lines if ln.strip()
                 and not ln.strip().isdigit()]
        if lines:
            cues.append((start, end, " ".join(lines)))
    if cues:
        cues.sort(key=lambda c: c[0])
        return cues
    # ASS مبسط: أسطر Dialogue: — الحقول مفصولة بفواصل،
    # الترتيب: Layer, Start, End, Style, Name, MarginL, MarginR,
    # MarginV, Effect, Text (النص قد يحوي فواصل).
    for line in text.splitlines():
        if not line.strip().lower().startswith("dialogue:"):
            continue
        body = line.split(":", 1)[1]
        fields = body.split(",", 9)
        if len(fields) < 10:
            continue
        start_m = _ASS_TIME_RE.match(fields[1].strip())
        end_m = _ASS_TIME_RE.match(fields[2].strip())
        if not start_m or not end_m:
            continue
        def _ass_seconds(m):
            h, mi, s, frac = m.groups()
            div = 1000.0 if len(frac) == 3 else 100.0
            return (int(h) * 3600.0 + int(mi) * 60.0 + int(s)
                    + int(frac) / div)
        spoken = _ASS_STYLE_RE.sub("", fields[9])
        spoken = spoken.replace("\\N", " ").replace("\\n", " ").strip()
        if spoken:
            cues.append((_ass_seconds(start_m), _ass_seconds(end_m),
                         spoken))
    cues.sort(key=lambda c: c[0])
    return cues


def _said_at(cues, when):
    """ما كان يُقال عند لحظة: الإشارة النشطة، أو آخر إشارة بدأت قبلها."""
    said = None
    for start, end, text in cues:
        if start <= when < end:
            return text
        if start <= when:
            said = text
        else:
            break
    return said


def _linear_slope(points):
    """ميل الانحدار الخطي (نقاط احتفاظ/ثانية) لمجموعة نقاط."""
    n = len(points)
    if n < 2:
        return 0.0
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    num = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)
    den = sum((p[0] - mean_x) ** 2 for p in points)
    if den == 0:
        return 0.0
    return num / den


def read_retention(csv_text_or_path, duration=None, transcript_text=None):
    """اقرأ تصدير احتفاظ Studio وشخّص أكبر تسرب.

    csv_text_or_path: نص CSV أو مسار ملف CSV.
    duration: مدة الفيديو بالثواني (اختياري؛ تُستنتج من آخر نقطة).
    transcript_text: نص مكتوب اختياري (SRT أو ASS مبسط) لطباعة
        ما كان يُقال عند كل منحدر.

    يرجع قاموسًا:
        hook_leak_pct: النسبة المفقودة في أول 30 ثانية.
        healthy: True إن كان التسرب صحيًا (<25%) بلا منحدرات
            وانزلاق مسطح.
        cliffs: [{at_seconds, drop, said?}] — said فقط عند توفر
            نص مكتوب يغطي اللحظة.
        slide: ميل الانحدار الخطي عبر الثلث الأوسط (نقاط/ثانية؛
            سالب = نزيف).
        slide_total_pct: الخسارة المتوقعة عبر الثلث الأوسط كاملًا.
        duration_seconds, n_points: بيانات وصفية.
        verdict: أكبر تسرب («تسرب الهوك»/«منحدر»/«انزلاق»/«سليم»).
        fix: تغيير واحد بالعربية.
        packaging_note: نص عند السلامة فقط، وإلا None.

    ملف مفقود أو CSV فارغ أو بلا أعمدة صالحة يرفع RetentionError
    برسالة عربية واضحة.
    """
    text = _read_csv_text(csv_text_or_path)
    points = _parse_points(text)
    if duration is None:
        duration = points[-1][0]
    duration = float(duration)
    if duration <= 0:
        raise RetentionError("مدة الفيديو غير صالحة: يجب أن تكون أكبر من صفر.")

    # تسرب الهوك: من أول نقطة إلى قيمة الثانية 30 (استيفاء خطي).
    start_value = points[0][1]
    at_30 = _value_at(points, HOOK_WINDOW_SECONDS)
    hook_leak = max(0.0, start_value - at_30)

    # المنحدرات: هبوط >= 10 نقاط في خطوة واحدة.
    cues = _parse_transcript(transcript_text)
    cliffs = []
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        drop = v0 - v1
        if drop >= CLIFF_DROP_MIN_PCT:
            cliff = {"at_seconds": round(t1, 3), "drop": round(drop, 2)}
            said = _said_at(cues, t1)
            if said:
                cliff["said"] = said
            cliffs.append(cliff)

    # الانزلاق: ميل الانحدار الخطي على نقاط الثلث الأوسط بعد
    # إزالة قفزات المنحدرات (تُرفع النقاط التالية لكل منحدر
    # بمقدار هبوطه) حتى يقيس النزيف الثابت وحده.
    cliff_drops = {c["at_seconds"]: c["drop"] for c in cliffs}
    adjusted = [points[0]]
    offset = 0.0
    for (t0, _v0), (t1, v1) in zip(points, points[1:]):
        offset += cliff_drops.get(round(t1, 3), 0.0)
        adjusted.append((t1, v1 + offset))
    mid_start = duration / 3.0
    mid_end = 2.0 * duration / 3.0
    mid_points = [p for p in adjusted if mid_start <= p[0] <= mid_end]
    if len(mid_points) >= 2:
        slope = _linear_slope(mid_points)
    else:
        # نقاط وسط غير كافية — يُعامل كمسطح ولا يُخترع ميل.
        slope = 0.0
    slide_total = abs(slope) * (mid_end - mid_start) if slope < 0 else 0.0

    biggest_cliff = max((c["drop"] for c in cliffs), default=0.0)
    healthy = (hook_leak < HOOK_HEALTHY_MAX_PCT
               and not cliffs
               and slide_total < SLIDE_FLAT_MAX_PCT)

    if healthy:
        verdict = _VERDICT_HEALTHY
        fix = _FIX_HEALTHY
        packaging_note = _PACKAGING_NOTE
    else:
        # أكبر تسرب؛ التعادل يُحسم بالترتيب: الهوك ثم المنحدر ثم الانزلاق.
        if hook_leak >= biggest_cliff and hook_leak >= slide_total:
            verdict = _VERDICT_HOOK
            fix = _FIX_HOOK
        elif biggest_cliff >= slide_total:
            verdict = _VERDICT_CLIFF
            top = max(cliffs, key=lambda c: c["drop"])
            fix = ("عند الثانية %s هبط الاحتفاظ %s نقطة دفعة واحدة — "
                   % (int(top["at_seconds"]) if float(top["at_seconds"]).is_integer()
                      else top["at_seconds"], _fmt_num(top["drop"])))
            if "said" in top:
                fix += "ما كان يُقال هناك: «%s» — " % top["said"]
            fix += ("مهّد للانتقال قبلها بجملة واحدة، أو احذف "
                    "الإعداد الطويل الذي سبقها.")
        else:
            verdict = _VERDICT_SLIDE
            fix = _FIX_SLIDE
        packaging_note = None

    return {
        "hook_leak_pct": round(hook_leak, 2),
        "healthy": healthy,
        "cliffs": cliffs,
        "slide": round(slope, 4),
        "slide_total_pct": round(slide_total, 2),
        "duration_seconds": round(duration, 3),
        "n_points": len(points),
        "verdict": verdict,
        "fix": fix,
        "packaging_note": packaging_note,
    }


def _fmt_num(value):
    """رقم بلا .0 زائدة للعرض العربي."""
    if float(value).is_integer():
        return str(int(value))
    return str(round(value, 2))


def _fmt_time(seconds):
    """ثوانٍ بصيغة mm:ss للعرض."""
    total = int(round(seconds))
    return "%d:%02d" % (total // 60, total % 60)


def format_report(result):
    """تقرير عربي مختصر من نتيجة read_retention."""
    lines = ["تقرير احتفاظ الجمهور",
             "تسرب الهوك (أول 30 ثانية): %s%% — %s"
             % (_fmt_num(result["hook_leak_pct"]),
                "صحي (أقل من 25%)" if result["hook_leak_pct"] < HOOK_HEALTHY_MAX_PCT
                else "غير صحي (25% أو أكثر)")]
    if result["cliffs"]:
        lines.append("المنحدرات (%d):" % len(result["cliffs"]))
        for cliff in result["cliffs"]:
            line = ("  - عند %s: هبوط %s نقطة"
                    % (_fmt_time(cliff["at_seconds"]),
                       _fmt_num(cliff["drop"])))
            if "said" in cliff:
                line += " — كان يُقال: «%s»" % cliff["said"]
            lines.append(line)
    else:
        lines.append("المنحدرات: لا توجد.")
    slide = result["slide"]
    if slide < 0:
        lines.append("الانزلاق (الثلث الأوسط): نزيف %s نقطة/ثانية "
                     "(خسارة متوقعة %s نقطة عبر الثلث الأوسط)"
                     % (_fmt_num(abs(slide)),
                        _fmt_num(result["slide_total_pct"])))
    else:
        lines.append("الانزلاق (الثلث الأوسط): مسطح.")
    lines.append("الحكم: %s" % result["verdict"])
    lines.append("التغيير الواحد: %s" % result["fix"])
    if result.get("packaging_note"):
        lines.append("ملاحظة التغليف: %s" % result["packaging_note"])
    return "\n".join(lines)
