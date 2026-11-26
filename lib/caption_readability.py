#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""قياس مقروئية عبارات الكابشن (ASS) — سرعة القراءة بالحرف/ثانية.

ينقل منطق ``~/workspace/studio-work/scarlet-survey/measure-captions.py``
بعد مراجعته، مع اختلافين موثّقين:

- ``\\N`` (وفاصل السطر ``\\n``) يُعامل كمسافة واحدة قبل العد، لا كحرفين.
- الوسيط هو الوسيط الإحصائي القياسي (``statistics.median``) لا العنصر
  الأوسط العلوي الذي يستخدمه سكربت المرجع للقوائم زوجية الطول.

العتبتان من قاعدة Scarlet اللاتينية (15–17 حرف/ث) وقابلتان للتعديل
عند الدمج بنتيجة المعايرة العربية (جولة caption-readability):

- ``FLASH_CPS``: فوقها العبارة «وامضة» — أسرع من أن تُقرأ براحة.
- ``BORDERLINE_CPS``: فوقها (حتى ``FLASH_CPS``) العبارة «حدّية».

القاعدة: ``borderline`` هي ``BORDERLINE_CPS < cps <= FLASH_CPS`` —
عبارة بسرعة 15.0 حرف/ث بالضبط سليمة لا حدّية، وعبارة بسرعة 17.0
بالضبط حدّية لا وامضة (مطابق لسكربت المرجع).

الوحدة قراءة فقط: تحلل نص/ملف ASS وتعيد تقريرًا، بلا كتابة ملفات
وبلا أي تغيير في مسار الريندر.
"""
import re
import statistics
from pathlib import Path

# العتبتان في موضع واحد — قابلتان للتعديل عند الدمج بنتيجة المعايرة.
FLASH_CPS = 17.0
BORDERLINE_CPS = 15.0

_TAG_RE = re.compile(r"\{[^}]*\}")
_BREAK_RE = re.compile(r"\\[Nn]")


def _parse_time(s: str) -> float:
    """تحويل وقت ASS (``H:MM:SS.cc``) إلى ثوانٍ (عدد عشري)."""
    h, m, rest = s.strip().split(":")
    if "." in rest:
        sec, cs = rest.split(".", 1)
        frac = int(cs) / (10 ** len(cs))
    else:
        sec, frac = rest, 0.0
    return int(h) * 3600 + int(m) * 60 + int(sec) + frac


def _format_time(seconds: float) -> str:
    """تنسيق ثوانٍ كوقت ASS (``H:MM:SS.cc``) لعرض موضع العبارة."""
    total_cs = int(round(seconds * 100))
    h, rem = divmod(total_cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean_text(raw: str) -> str:
    """حذف وسوم التجاوز وتحويل فواصل الأسطر إلى مسافات."""
    text = _TAG_RE.sub("", raw)
    text = _BREAK_RE.sub(" ", text)
    return text.strip()


def _parse_dialogue(line: str):
    """تحليل سطر ``Dialogue:`` واحد إلى عبارة، أو ``None`` إن تالف/يُتخطى.

    يُتخطى بصمت: سطر ناقص الحقول، وقت تالف، مدة ``<= 0``، نص فارغ
    بعد حذف الوسوم.
    """
    parts = line[len("Dialogue:"):].split(",", 9)
    if len(parts) < 10:
        return None
    try:
        start = _parse_time(parts[1])
        end = _parse_time(parts[2])
    except (ValueError, IndexError):
        return None
    text = _clean_text(parts[9])
    dur = end - start
    if dur <= 0 or not text:
        return None
    chars = len(text)
    chars_no_spaces = len(text.replace(" ", ""))
    return {
        "text": text,
        "start": start,
        "end": end,
        "cps": chars / dur,
        "cps_no_spaces": chars_no_spaces / dur,
    }


def analyze_ass_text(text: str) -> dict:
    """تحليل نص ASS كامل وإعادة تقرير المقروئية.

    التقرير dict بمفاتيح: ``phrases`` (قائمة dict: ``text``، ``start``،
    ``end``، ``cps``، ``cps_no_spaces``)، ``total``، ``flashing``
    (العبارات ``> FLASH_CPS``)، ``borderline``
    (``BORDERLINE_CPS < cps <= FLASH_CPS``)، ``max_cps``، ``median_cps``.
    """
    phrases = []
    for line in text.splitlines():
        if not line.lstrip().startswith("Dialogue:"):
            continue
        phrase = _parse_dialogue(line.lstrip())
        if phrase is not None:
            phrases.append(phrase)
    speeds = [p["cps"] for p in phrases]
    return {
        "phrases": phrases,
        "total": len(phrases),
        "flashing": [p for p in phrases if p["cps"] > FLASH_CPS],
        "borderline": [
            p for p in phrases
            if BORDERLINE_CPS < p["cps"] <= FLASH_CPS
        ],
        "max_cps": max(speeds) if speeds else 0.0,
        "median_cps": statistics.median(speeds) if speeds else 0.0,
    }


def analyze_ass_file(path) -> dict:
    """تحليل ملف ASS من القرص وإعادة تقرير المقروئية نفسه.

    ملف بلا عبارات قابلة للقياس يعيد تقريرًا فارغًا (``total=0``)
    لا خطأ. ملف غير موجود يرفع ``FileNotFoundError`` كالمعتاد.
    """
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    return analyze_ass_text(text)


def format_report(report: dict) -> str:
    """ملخص عربي سطر واحد + سطر لكل عبارة وامضة (نصها وسرعتها وموضعها)."""
    total = report["total"]
    if total == 0:
        return "0 عبارة — بلا عبارات قابلة للقياس."
    lines = [
        f"{total} عبارة — الوسيط {report['median_cps']:.1f} حرف/ث — "
        f"الأقصى {report['max_cps']:.1f} — "
        f"وامضة (>{FLASH_CPS:g}): {len(report['flashing'])} — "
        f"حدّية ({BORDERLINE_CPS:g}–{FLASH_CPS:g}): "
        f"{len(report['borderline'])}"
    ]
    for p in report["flashing"]:
        lines.append(
            f"  وامضة {p['cps']:.1f} حرف/ث "
            f"({_format_time(p['start'])}–{_format_time(p['end'])}): "
            f"{p['text']}"
        )
    return "\n".join(lines)
