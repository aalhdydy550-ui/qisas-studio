#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""موجز بحث للموضوع قبل الكتابة — جولة v0.1.58 (W5، من مرحلة
«البحث» في OpenReels: الفكرة فقط، بلا نسخ كود إطلاقًا).

الفكرة: `ideas.py` يولّد من موضوع عارٍ؛ والموجز يغذّي كتابة
القصة بأدلة — أنماط الترند الرابحة للموضوع + هوكات ناجحة +
عناوين موجودة في الطابور (منع تكرار) + زوايا غير مغطاة — فيرفع
جودة السكريبت من أول مسودة بدل التوليد الأعمى.

قواعد الوحدة:
- المدخل بيانات JSON جاهزة فقط بصيغة مخرجات مساعد الترند
  (W1): مرشحون مرتبون باقتراحات
  ``{title, hook, moral_angle, source_url, pattern, score,
  reason}`` + عناوين الطابور الحالية. **بلا استيراد كود W1
  إطلاقًا** — البيانات فقط.
- حتمي بلا شبكة وبلا LLM وبلا عشوائية: تجميع وترتيب وصياغة
  من المدخلات فقط.
- لا اختراع أرقام: أي رقم بلا مصدر يُذكر «غير مقاس» — فالدرجة
  الغائبة لمرشح تُعرض «غير مقاسة» ولا تُخترع لها قيمة.
- الرعب مستبعد دائمًا: مرشح نمطه رعب/غامض لا يدخل الأنماط
  الرابحة ولا الهوكات الناجحة أبدًا، ويُذكر في الموجز
  كمستبعد صراحة (الرعب خارج الخط بانتظار قرار المستخدم).
- الموجز نص عربي جاهز يُلصق في برومبت كتابة القصة، ويحمل
  ما يُتجنَّب دائمًا: رعب مستبعد، موسيقى، بوابة متابعة
  (الدعوة لطيفة فقط)، راوٍ رجالي، كتابة أسفل الصورة فقط.
"""
import json
import re
import sys

__all__ = ["build_brief", "titles_from_queue_text", "BriefError",
           "main"]


class BriefError(Exception):
    """خطأ في مدخلات الموجز (رسالته عربية)."""


# أنماط مستبعدة: الرعب/الغموض خارج خط القناة بانتظار قرار
# المستخدم — تُوسم «مستبعد» ولا تُقترح أبدًا.
_EXCLUDED_WORDS = ("رعب", "غامض", "مرعب", "مخيف")

_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670]")
_NORMALIZE_TABLE = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ى": "ي",
})


def _norm(text):
    """طيّ نص عربي للمقارنة: تشكيل وألفات وتاء مربوطة."""
    text = _DIACRITICS_RE.sub("", (text or ""))
    return text.translate(_NORMALIZE_TABLE)


# كلمات تُحذف عند استخراج كلمات الموضوع/الزاوية للمقارنة
# (أدوات وكلمات عامة لا تميّز زاوية عن أخرى) — مطبّعة
# بالتطبيع نفسه (فـ«قصة» تصير «قصه» بعد طيّ التاء).
_STOPWORDS = frozenset(_norm(w) for w in {
    "قصة", "قصص", "حكاية", "حكايات", "عن", "في", "من", "الى",
    "إلى", "على", "ما", "لا", "لم", "لن", "ان", "أن", "إن",
    "هو", "هي", "كان", "كانت", "هذا", "هذه", "ذلك", "تلك",
    "مع", "بعد", "قبل", "عند", "لدى", "بين", "كل", "اي",
    "أي", "و", "او", "أو", "ثم", "قد", "لقد", "جزء",
})

# حد الهوكات المعروضة في نص الموجز (القائمة الكاملة في
# winning_hooks بلا حد).
BRIEF_HOOKS_SHOWN = 5
# حد العناوين الموجودة المعروضة في نص الموجز (القائمة
# الكاملة في existing_titles بلا حد).
BRIEF_TITLES_SHOWN = 10

NOT_MEASURED = "غير مقاس"
NO_CANDIDATES_NOTE = ("لا مرشحي ترند لهذا الموضوع — اكتب من "
                      "الموضوع نفسه بلا أدلة ترند.")


def _fold(text):
    """طيّ كامل للمقارنة: تطبيع + طيّ مسافات + صغير."""
    return re.sub(r"\s+", " ", _norm(text).strip()).lower()


def _tokens(text):
    """كلمات مميزة من نص: تطبيع + حذف «ال» + إسقاط التوقفات."""
    out = set()
    for word in re.findall(r"[\w\u0600-\u06FF]+", _norm(text or "")):
        word = word.strip()
        if word.startswith("ال") and len(word) > 3:
            word = word[2:]
        if len(word) < 2 or word in _STOPWORDS:
            continue
        out.add(word)
    return out


def _is_excluded(candidate):
    """مرشح مستبعد؟ نمطه أو زاويته الأخلاقية رعب/غامض."""
    for field in ("pattern", "moral_angle"):
        text = _fold(candidate.get(field) or "")
        if any(word in text for word in _EXCLUDED_WORDS):
            return True
    return False


def _validate_candidates(candidates):
    """طبّع المرشحين وارفض المدخل الفاسد.

    يرجع قائمة قواميس بحقول نصية مضمونة وscore رقمية أو
    None. يرفع BriefError عند: مرشح ليس قاموسًا، عنوان
    غائب/فارغ، درجة غير رقمية، أو حقل نصي ليس نصًا.
    """
    if not isinstance(candidates, list):
        raise BriefError(
            "مرشحو الترند يجب أن يكونوا قائمة (وصل: %s)"
            % type(candidates).__name__)
    out = []
    for i, raw in enumerate(candidates):
        if not isinstance(raw, dict):
            raise BriefError(
                "المرشح رقم %d ليس قاموسًا (وصل: %s)"
                % (i + 1, type(raw).__name__))
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            raise BriefError(
                "المرشح رقم %d بلا عنوان صالح" % (i + 1))
        clean = {"title": title.strip()}
        for field in ("hook", "moral_angle", "source_url",
                      "pattern", "reason"):
            value = raw.get(field)
            if value is None:
                clean[field] = ""
            elif isinstance(value, str):
                clean[field] = value.strip()
            else:
                raise BriefError(
                    "حقل %s في المرشح «%s» يجب أن يكون نصًا"
                    % (field, title))
        score = raw.get("score")
        if score is None:
            clean["score"] = None
        elif isinstance(score, bool) or not isinstance(
                score, (int, float)):
            raise BriefError(
                "درجة المرشح «%s» يجب أن تكون رقمًا (وصل: %s)"
                % (title, score))
        else:
            clean["score"] = score
        out.append(clean)
    return out


def _validate_titles(existing_titles):
    """طبّع عناوين الطابور: نصوص غير فارغة بلا تكرار."""
    if not isinstance(existing_titles, list):
        raise BriefError(
            "عناوين الطابور يجب أن تكون قائمة (وصل: %s)"
            % type(existing_titles).__name__)
    out = []
    seen = set()
    for title in existing_titles:
        if not isinstance(title, str) or not title.strip():
            raise BriefError(
                "عنوان طابور غير صالح (وصل: %r)" % (title,))
        title = title.strip()
        key = _fold(title)
        if key not in seen:
            seen.add(key)
            out.append(title)
    return out


def _winning_patterns(candidates):
    """اجمع الأنماط الرابحة: عدد + أفضل درجة + مثال.

    مرتبة بعدد المرشحين تنازليًا ثم بأفضل درجة تنازليًا
    (غير المقاسة آخرًا) ثم بالنمط أبجديًا — حتمي تمامًا.
    """
    grouped = {}
    for cand in candidates:
        pattern = cand.get("pattern") or "نمط غير مذكور"
        entry = grouped.setdefault(
            pattern, {"pattern": pattern, "count": 0,
                      "best_score": None, "example_title": ""})
        entry["count"] += 1
        score = cand.get("score")
        if score is not None and (entry["best_score"] is None
                                  or score > entry["best_score"]):
            entry["best_score"] = score
            entry["example_title"] = cand["title"]
        elif not entry["example_title"]:
            entry["example_title"] = cand["title"]
    return sorted(
        grouped.values(),
        key=lambda e: (-e["count"],
                       e["best_score"] is None,
                       -(e["best_score"] or 0),
                       e["pattern"]))


def _winning_hooks(candidates):
    """هوكات ناجحة مرتبة بالدرجة تنازليًا (غير المقاسة آخرًا).

    مكرر الهوك نفسه (بعد الطيّ) يظهر مرة واحدة — بأعلى درجة.
    """
    best = {}
    for cand in candidates:
        hook = (cand.get("hook") or "").strip()
        if not hook:
            continue
        key = _fold(hook)
        score = cand.get("score")
        current = best.get(key)
        if current is None or (
                score is not None
                and (current["score"] is None
                     or score > current["score"])):
            best[key] = {"hook": hook, "title": cand["title"],
                         "pattern": cand.get("pattern") or "",
                         "score": score}
    return sorted(
        best.values(),
        key=lambda h: (h["score"] is None, -(h["score"] or 0),
                       h["hook"]))


def _uncovered_angles(candidates, existing_titles):
    """زوايا أخلاقية غير مغطاة بعناوين الطابور.

    الزاوية مغطاة إن شارك عنوان موجود في الطابور كلمة مميزة
    واحدة على الأقل مع نص الزاوية (أو مع عنوان مرشحها)؛
    وإلا فهي غير مغطاة — زاوية جديدة تستحق الكتابة. مرتبة
    أبجديًا لحتمية الناتج.
    """
    queue_tokens = set()
    for title in existing_titles:
        queue_tokens |= _tokens(title)
    uncovered = set()
    for cand in candidates:
        angle = (cand.get("moral_angle") or "").strip()
        if not angle:
            continue
        angle_tokens = _tokens(angle) | _tokens(cand["title"])
        if not (angle_tokens & queue_tokens):
            uncovered.add(angle)
    return sorted(uncovered)


def _score_text(score):
    """صياغة الدرجة: رقم كما هو، أو «غير مقاس» بلا اختراع."""
    if score is None:
        return NOT_MEASURED
    if isinstance(score, float) and score.is_integer():
        return str(int(score))
    return str(score)


def _format_brief(theme, patterns, hooks, existing_titles,
                  uncovered, excluded, duplicates):
    """نص الموجز العربي الجاهز للصق في برومبت كتابة القصة."""
    lines = ["موجز بحث — الموضوع: %s" % theme, ""]
    if patterns:
        lines.append("الأنماط الرابحة لهذا الموضوع:")
        for entry in patterns:
            lines.append("- %s (في %d مرشحًا، أفضل درجة: %s؛ مثال: «%s»)"
                         % (entry["pattern"], entry["count"],
                            _score_text(entry["best_score"]),
                            entry["example_title"]))
        lines.append("")
    else:
        lines.append(NO_CANDIDATES_NOTE)
        lines.append("")
    if hooks:
        lines.append("هوكات ناجحة جرّب صياغة قريبة منها:")
        for hook in hooks[:BRIEF_HOOKS_SHOWN]:
            lines.append("- «%s» (من «%s» — درجة: %s)"
                         % (hook["hook"], hook["title"],
                            _score_text(hook["score"])))
        lines.append("")
    # لمسة ربط المنسق (جولة v0.1.58): الهوك يظهر أيضًا عنوانًا
    # كبيرًا مكتوبًا أول 3 ثوانٍ (وحدة hook_title) — فليكن
    # قصيرًا يُقرأ بنظرة واحدة.
    lines.append("ملاحظة: الهوك سيظهر أيضًا عنوانًا كبيرًا مكتوبًا "
                 "في أول 3 ثوانٍ من الفيديو — فليكن قصيرًا يُقرأ "
                 "بنظرة واحدة.")
    lines.append("")
    if existing_titles:
        shown = existing_titles[:BRIEF_TITLES_SHOWN]
        lines.append("موجود أصلًا في الطابور — لا تكرره:")
        for title in shown:
            lines.append("- %s" % title)
        extra = len(existing_titles) - len(shown)
        if extra:
            lines.append("… و%d عنوانًا آخر في الطابور." % extra)
        lines.append("")
    else:
        lines.append("الطابور فارغ — لا عناوين موجودة تمنع التكرار.")
        lines.append("")
    if duplicates:
        lines.append("تنبيه تكرار: هذه المرشحات موجودة أصلًا في "
                     "الطابور فلا تُعاد كتابتها:")
        for title in duplicates:
            lines.append("- %s" % title)
        lines.append("")
    if uncovered:
        lines.append("زوايا غير مغطاة في الطابور (فرص جديدة):")
        for angle in uncovered:
            lines.append("- %s" % angle)
        lines.append("")
    if excluded:
        lines.append("مستبعد — لا يُقترح ولا يُكتب:")
        for title in excluded:
            lines.append("- %s (رعب/غامض — خارج الخط)" % title)
        lines.append("")
    lines.append("ما يُتجنَّب في القصة الجديدة:")
    lines.append("- الرعب والغموض مستبعدان (خارج الخط بانتظار "
                 "قرار المستخدم).")
    lines.append("- بلا موسيقى إطلاقًا — الصيغة بلا موسيقى.")
    lines.append("- بلا بوابة متابعة: لا «تابع» ولا «اشترك» شرطًا "
                 "للجزء التالي — الدعوة لطيفة فقط.")
    lines.append("- الراوي رجل دائمًا، والكتابة أسفل الصورة فقط "
                 "ومتزامنة عبارة بعبارة.")
    return "\n".join(lines)


def build_brief(theme, candidates, existing_titles):
    """ابنِ موجز بحث لموضوع قبل الكتابة.

    theme: نص الموضوع (مطلوب غير فارغ).
    candidates: قائمة مرشحي ترند بصيغة W1 (تُمرَّر كبيانات
      JSON — بلا استيراد كود W1).
    existing_titles: قائمة عناوين الطابور الحالية (نصوص).

    يرجع ``{theme, winning_patterns, winning_hooks,
    existing_titles, uncovered_angles, brief_text}``.
    يرفع BriefError عند مدخل فاسد.
    """
    if not isinstance(theme, str) or not theme.strip():
        raise BriefError("موضوع الموجز فارغ أو غير نصي")
    theme = theme.strip()
    candidates = _validate_candidates(candidates)
    existing_titles = _validate_titles(existing_titles)

    excluded = [c["title"] for c in candidates
                if _is_excluded(c)]
    usable = [c for c in candidates if not _is_excluded(c)]
    patterns = _winning_patterns(usable)
    hooks = _winning_hooks(usable)
    uncovered = _uncovered_angles(usable, existing_titles)

    existing_folded = {_fold(t) for t in existing_titles}
    duplicates = []
    for cand in candidates:
        if _fold(cand["title"]) in existing_folded \
                and cand["title"] not in duplicates:
            duplicates.append(cand["title"])

    brief_text = _format_brief(theme, patterns, hooks,
                               existing_titles, uncovered,
                               excluded, duplicates)
    return {"theme": theme,
            "winning_patterns": patterns,
            "winning_hooks": hooks,
            "existing_titles": existing_titles,
            "uncovered_angles": uncovered,
            "brief_text": brief_text}


def titles_from_queue_text(queue_text):
    """عناوين الانتظار من نص ملف طابور (قراءة فقط).

    يغلّف ``lib.queue.parse_waiting_entries`` — بلا أي كتابة
    في الطابور. يرجع قائمة العناوين بالترتيب.
    """
    if not isinstance(queue_text, str):
        raise BriefError("نص الطابور يجب أن يكون نصًا")
    from lib import queue as queue_lib
    return [e["title"]
            for e in queue_lib.parse_waiting_entries(queue_text)]


def main(argv=None):
    """سطر أوامر: اقرأ JSON ``{theme, candidates,
    existing_titles}`` من ملف (أول وسيط) أو stdin، واطبع
    الموجز JSON على stdout. خروج 0 عند النجاح و2 على مدخل
    فاسد.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv:
            with open(argv[0], encoding="utf-8") as f:
                payload = json.load(f)
        else:
            payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise BriefError("المدخل JSON يجب أن يكون قاموسًا")
        brief = build_brief(payload.get("theme"),
                            payload.get("candidates", []),
                            payload.get("existing_titles", []))
    except BriefError as exc:
        print("خطأ في مدخل الموجز: %s" % exc, file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print("خطأ في قراءة المدخل: %s" % exc, file=sys.stderr)
        return 2
    print(json.dumps(brief, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
