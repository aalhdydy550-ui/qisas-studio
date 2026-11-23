#!/usr/bin/env python3
"""تحليل DNA الفيروسي — `studio.py analyze --dna` (الجولة 7، v0.1.31).

لفيديو واحد: درجة الهوك (جدول maquina 0–10)، والإيقاع (متوسط
طول اللقطة عبر كشف تغيير المشهد)، وفواصل الصمت (إعادة استخدام
`check`)، وكثافة الكلمات (من ملفات ASS إن وُجدت)، وحكم «ليه نجح /
إيه الناقص» مربوطًا بأرقام فيسبوك/يوتيوب الحقيقية لنفس الفيديو.

صراحة مهمة (نمط المشروع): أي مقياس لا يُقاس يُطبع «غير مقاس» —
لا صفر مخترع ولا رقم محسوب من فراغ. درجة الهوك من إشارات نصية
حتمية (موثقة أدناه)، لا من نموذج؛ ومعيار «العائد داخل المقطع»
يحتاج نص القصة (--story-text) وإلا يبقى غير مقاس والمجموع
الأقصى 9 مع تنبيه.
"""
import json
import os
import re
import subprocess
import time

from lib import check as check_lib

QUESTION_WORDS = ("لماذا", "كيف", "ماذا", "هل", "إيه", "ليه", "متى",
                  "أين", "فين", "مين")
SUSPENSE_WORDS = ("لكن", "فجأة", "سر", "مفاجأة", "لم يتوقع",
                  "ما حدش", "صدمة", "انكشف", "الحقيقة")
CONFLICT_WORDS = ("ظلم", "خان", "كذب", "أنكر", "سرق", "غضب", "رفض",
                  "خدع", "غدر", "قسى")
VERDICT_WORDS = ("أبدًا", "مستحيل", "لا يمكن", "أبدا")
WARMUP_WORDS = ("يا جماعة", "تعالوا", "هنتكلم", "النهاردة هحكي",
                "في البداية أحب")
NUMBER_WORDS = ("واحد", "اثنان", "اثنين", "ثلاثة", "أربعة", "خمسة",
                "ستة", "سبعة", "ثمانية", "تسعة", "عشرة", "مئة", "ألف",
                "مليون")
SCENE_THRESHOLD = 0.4  # عتبة كشف تغيير المشهد (ffmpeg scene)

HOOK_MAX = 10

# لواحق صرفية تُقبل بعد الكلمة المفتاحية (ضمائر متصلة
# ولواحق تأنيث/جمع): «لكنه» = لكن + ه، «انكشفت» = انكشف + ت.
_WORD_SUFFIXES = ("هما", "ها", "هم", "هن", "كم", "كن", "نا",
                  "ك", "ي", "ه", "ت", "وا", "ون", "ين", "ات",
                  "ة", "ا")
_WORD_PREFIXES = ("وال", "فال", "بال", "لل", "و", "ف", "ب", "ل",
                  "ك")


def _norm_word(word):
    """جرّد كلمة من سوابقها (و/ف/ب/ل/ك + ال) للمقارنة."""
    w = (word or "").strip()
    changed = True
    while changed:
        changed = False
        for p in _WORD_PREFIXES:
            if w.startswith(p) and len(w) > len(p):
                w = w[len(p):]
                changed = True
                break
        if w.startswith("ال") and len(w) > 2:
            w = w[2:]
            changed = True
    return w


def _word_in(text, word):
    """هل تظهر `word` كلمةً مستقلة في `text`؟

    المطابقة الجزئية القديمة (`w in hook`) كانت تعطي إيجابيات
    كاذبة: «ليه» داخل «عليه»، و«سر» داخل «سريع»/«سرق»،
    و«هل» داخل «أهل»، و«مين» داخل «يمين» — فهوك بلا أي فجوة
    فضول كان يسجّل 3/3. العبارات متعددة الكلمات («لم يتوقع»،
    «ما حدش») تبقى مطابقة جزئية — مميزة بما يكفي.
    """
    word = (word or "").strip()
    if not word:
        return False
    if " " in word:
        return word in (text or "")
    target = _norm_word(word)
    tokens = re.split(r"[\s،؛:()\"'«»!?؟.\-…/]+", text or "")
    for tok in tokens:
        if not tok:
            continue
        for cand in (tok, _norm_word(tok)):
            if cand == target:
                return True
            for suf in _WORD_SUFFIXES:
                if cand == target + suf:
                    return True
    return False


class DnaError(Exception):
    """خطأ في تحليل DNA (رسالته عربية)."""


def _words(text):
    return (text or "").split()


# أرقام بداية الهوك تُكتب كلمات (قاعدة دائمة: الهوك لا يبدأ
# برقم — خلل اتجاه ثنائي الاتجاه يجعل الرقم يقفز لآخر السطر).
# 1–10 فقط؛ الأكبر يُترك للكاتب (لا تهجئة موثوقة فوق العشرة
# بلا قواعد إعراب)، والصفر يُترك كما هو.
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_HOOK_NUMBER_WORDS = {
    1: "واحد", 2: "اثنان", 3: "ثلاثة", 4: "أربعة", 5: "خمسة",
    6: "ستة", 7: "سبعة", 8: "ثمانية", 9: "تسعة", 10: "عشرة",
}


def normalize_hook(hook):
    """أعد كتابة رقم بداية الهوك كلمات (1–10، غربي أو مشرقي).

    «3 أخطاء…» → «ثلاثة أخطاء…»؛ و«٣ أخطاء» مثلها. يرجع الهوك
    كما هو إن لم يبدأ برقم، أو كان الرقم صفرًا أو فوق 10.
    """
    hook = (hook or "").strip()
    if not hook:
        return hook
    m = re.match(r"^([0-9٠-٩]+)[\s.\-–—:؛،,]*", hook)
    if not m:
        return hook
    digits = "".join(
        str(_ARABIC_INDIC_DIGITS.index(ch)) if ch in _ARABIC_INDIC_DIGITS
        else ch for ch in m.group(1))
    try:
        number = int(digits)
    except ValueError:
        return hook
    word = _HOOK_NUMBER_WORDS.get(number)
    if word is None:
        return hook
    rest = hook[m.end():].strip()
    return (word + " " + rest).strip() if rest else word


def score_hook(hook, story_text=None):
    """سجّل هوكًا بجدول maquina 0–10. يرجع قاموسًا بالتفصيل.

    المعايير (من مهارة maquina-cortes-gta):
    - فجوة فضول 0–3: أداة استفهام +2، كلمة تشويق +1.
    - حقيقة محددة 0–2: رقم/كلمة عددية/اسم علم +1 لكل إشارة حتى 2.
    - صراع/رأي قوي 0–2: كلمة صراع +1، صيغة حكم قاطع +1.
    - دخول مباشر 0–1: ≤12 كلمة وبلا كلمات تمهيد.
    - عائد داخل المقطع 0–1: يُقاس فقط مع نص قصة — العبرة/الختام
      في آخر ثلث النص؛ وبدونه «غير مقاس».
    - قائم بذاته 0–1: فيه فعل وفاعل ولا يحيل لـ«الجزء اللي فات».
    """
    hook = (hook or "").strip()
    if not hook:
        raise DnaError("الهوك فارغ — مرّر --hook أو --title")
    words = _words(hook)
    bd = {}
    # فجوة فضول 0–3
    gap = 0
    if "؟" in hook or "?" in hook or any(
            _word_in(hook, w) for w in QUESTION_WORDS):
        gap += 2
    if any(_word_in(hook, w) for w in SUSPENSE_WORDS):
        gap += 1
    bd["curiosity_gap"] = min(3, gap)
    # حقيقة محددة 0–2
    fact = 0
    if re.search(r"[0-9٠-٩]", hook):
        fact += 1
    if any(_word_in(hook, w) for w in NUMBER_WORDS):
        fact += 1
    bd["specific_fact"] = min(2, fact)
    # صراع/رأي قوي 0–2
    conflict = 0
    if any(_word_in(hook, w) for w in CONFLICT_WORDS):
        conflict += 1
    if any(_word_in(hook, w) for w in VERDICT_WORDS):
        conflict += 1
    bd["conflict"] = min(2, conflict)
    # دخول مباشر 0–1
    bd["direct_entry"] = 1 if (len(words) <= 12 and not any(
        _word_in(hook, w) for w in WARMUP_WORDS)) else 0
    # عائد داخل المقطع 0–1 (يحتاج نص القصة)
    if story_text:
        sents = [s.strip() for s in re.split(r"[.!؟\n]+", story_text)
                 if s.strip()]
        last_third = sents[len(sents) * 2 // 3:] if sents else []
        tail = " ".join(last_third)
        bd["payoff"] = 1 if any(
            w in tail for w in ("العبرة", "الدرس", "تعلم", "فهم",
                                "عرف", "ندم", "تاب", "رجع", "حصد")) else 0
    else:
        bd["payoff"] = None
    # قائم بذاته 0–1
    bd["self_contained"] = 0 if "الجزء اللي فات" in hook \
        or "زي ما قلنا" in hook else 1
    measured = [v for v in bd.values() if v is not None]
    total = sum(measured)
    max_total = HOOK_MAX if bd["payoff"] is not None else HOOK_MAX - 1
    if total >= 9:
        verdict = "قوي — استخدمه"
    elif total >= 6:
        verdict = "جيد"
    else:
        verdict = "ضعيف — يُستبعد (أقل من 6)"
    return {"hook": hook, "total": total, "max": max_total,
            "breakdown": bd, "verdict": verdict}


def detect_cuts(video):
    """كشف تغيير المشهد عبر ffmpeg (scene 0.4).

    يرجع {"cuts": [أزمنة القطع بالثواني], "shot_count": N,
    "avg_shot_seconds": float, "duration": float}.
    يرفع DnaError إن تعذرت القراءة.
    """
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise DnaError("ملف الفيديو غير موجود: %s" % video)
    try:
        info = check_lib.probe(video)
    except check_lib.CheckError as e:
        raise DnaError(str(e))
    duration = info["duration"]
    cmd = ["ffmpeg", "-v", "info", "-i", video, "-vf",
           "select='gt(scene,%.2f)',showinfo" % SCENE_THRESHOLD,
           "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=600)
    except FileNotFoundError:
        raise DnaError("ffmpeg غير متاح")
    except subprocess.TimeoutExpired:
        raise DnaError("انتهت مهلة كشف تغيير المشهد")
    out = proc.stderr or ""
    times = [float(m) for m in
             re.findall(r"pts_time:([0-9.]+)", out)]
    # أول إطار (زمن 0) ليس قطعًا — يُستبعد.
    cuts = [t for t in times if t > 0.05]
    shot_count = len(cuts) + 1
    return {"cuts": [round(t, 2) for t in cuts],
            "shot_count": shot_count,
            "avg_shot_seconds": round(duration / shot_count, 2),
            "duration": round(duration, 1)}


def _ass_words(ass_path):
    """كلمات ملف ASS + زمنه: (عدد الكلمات، بداية أول عبارة،
    نهاية آخر عبارة). تُزال وسوم {..} وفواصل \\N."""
    words = 0
    start = None
    end = None
    time_re = re.compile(r"^(\d+):(\d\d):(\d\d)\.(\d\d)$")

    def _secs(text):
        m = time_re.match(text.strip())
        if not m:
            return None
        h, mi, s, cs = (int(g) for g in m.groups())
        return h * 3600 + mi * 60 + s + cs / 100.0

    with open(ass_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("Dialogue:"):
                continue
            parts = line.rstrip("\n").split(",", 9)
            if len(parts) < 10:
                continue
            s = _secs(parts[1])
            e = _secs(parts[2])
            if s is not None and (start is None or s < start):
                start = s
            if e is not None and (end is None or e > end):
                end = e
            text = re.sub(r"\{[^}]*\}", "", parts[9])
            text = text.replace("\\N", " ").replace("\\n", " ")
            words += len(text.split())
    return words, start, end


def word_density(video, subs_dir=None, slug=None):
    """كثافة الكلمات (كلمة/دقيقة) من ملفات ASS إن وُجدت.

    يبحث في subs_dir (أو videos/subs/) عن ملفات
    `<slug>-scene*.ass` أو أي `*.ass` فيه. بلا ملفات: يرجع
    {"wpm": None, "words": 0, "source": None}.

    كل ملف ASS يخص مشهدًا بخط زمني محلي (0–8 ثوانٍ) — فالزمن
    الكلي هو مجموع أزمنة الملفات (نهاية−بداية كل ملف)، لا
    الفرق بين أول بداية وآخر نهاية عبر كل الملفات (كان يعطي
    757 كلمة/دقيقة للنجار بدل ~126 — خطأ صحح في الجولة 7).
    """
    if subs_dir:
        search_dir = os.path.expanduser(subs_dir)
    else:
        search_dir = os.path.join(
            os.path.dirname(os.path.abspath(os.path.expanduser(video))),
            "subs")
    files = []
    if os.path.isdir(search_dir):
        for name in sorted(os.listdir(search_dir)):
            if not name.endswith(".ass"):
                continue
            if slug and not name.startswith(slug):
                continue
            files.append(os.path.join(search_dir, name))
    if not files:
        return {"wpm": None, "words": 0, "files": 0, "source": None}
    total_words = 0
    total_span = 0.0
    for path in files:
        w, s, e = _ass_words(path)
        total_words += w
        if s is not None and e is not None and e > s:
            total_span += e - s
    if total_words == 0 or total_span <= 0:
        return {"wpm": None, "words": total_words,
                "files": len(files), "source": "ass"}
    minutes = total_span / 60.0
    return {"wpm": round(total_words / minutes, 1),
            "words": total_words, "files": len(files), "source": "ass"}


def _slug_for_video(video):
    """اشتق بادئة ملفات ASS من اسم ملف الفيديو.

    بادئات الملفات الفعلية في videos/subs/ هي slugs القصص
    (najjar / hamati / aisha2 / aisha1 / anza)؛ واسم الفيديو
    يحملها بصيغة أخرى (aisha-part2-main.mp4 مثلًا) — فالمطابقة
    على الحروف + رقم الجزء («part2» في الاسم = «aisha2» في
    الملفات). بلا تطابق يرجع None (الكثافة «غير مقاسة»).
    """
    base = os.path.splitext(os.path.basename(video))[0].lower()
    for cand in ("aisha2", "aisha1", "anza", "najjar", "hamati"):
        letters = re.sub(r"\d+$", "", cand)
        digit = cand[len(letters):]
        if letters not in base:
            continue
        if digit and ("part%s" % digit) not in base \
                and (letters + digit) not in base \
                and digit not in base.split("-"):
            continue
        return cand
    return None


def analyze_dna(video, title=None, hook=None, subs_dir=None,
                story_text=None, fb=None, yt=None,
                check_fn=None, slug=None):
    """حلّل DNA فيديو واحد. يرجع قاموس التقرير الكامل.

    fb/yt: قاموسا أرقام المنصتين لنفس الفيديو (أو None إن لم
    تُعرفا). check_fn: دالة فحص الصمت (افتراضيًا check_lib).
    slug: بادئة ملفات ASS لكثافة الكلمات (افتراضيًا تُشتق من
    اسم الفيديو عبر _slug_for_video).
    """
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise DnaError("ملف الفيديو غير موجود: %s" % video)
    hook_text = (hook or title or "").strip()
    hook_score = score_hook(hook_text, story_text=story_text) \
        if hook_text else None
    cuts = detect_cuts(video)
    check = (check_fn or check_lib.run_checks)
    try:
        qc = check(video)
        silences = [c for c in qc.get("checks", [])
                    if c["name"] == "الصمت عند الفواصل"]
        # بلا نتيجة فحص صمت: «غير مقاس» صراحةً — كان التقرير
        # يطبع None حرفيًا في موضع التفصيل.
        silence_detail = (silences[0]["detail"] if silences
                          else "غير مقاس (لا نتيجة فحص صمت)")
        silence_ok = silences[0]["ok"] if silences else None
    except check_lib.CheckError as e:
        silence_detail = "تعذر فحص الصمت: %s" % e
        silence_ok = None
    slug = slug or _slug_for_video(video)
    density = word_density(video, subs_dir=subs_dir, slug=slug)
    fb_views = (fb or {}).get("views") if fb else None
    yt_views = (yt or {}).get("views") if yt else None
    verdict = build_verdict(hook_score, cuts, silence_ok,
                            density, fb_views, yt_views)
    return {
        "video": video,
        "title": title or "",
        "duration": cuts["duration"],
        "hook": hook_score,
        "pacing": cuts,
        "silence": {"ok": silence_ok, "detail": silence_detail},
        "word_density": density,
        "facebook_views": fb_views,
        "youtube_views": yt_views,
        "verdict": verdict,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def build_verdict(hook_score, cuts, silence_ok, density,
                  fb_views, yt_views):
    """حكم «ليه نجح / إيه الناقص» من المقاييس + الأرقام الحقيقية."""
    lines = []
    if hook_score is not None:
        lines.append("الهوك %d/%d (%s) — %s"
                     % (hook_score["total"], hook_score["max"],
                        hook_score["verdict"], hook_score["hook"][:60]))
        if hook_score["total"] < 6:
            lines.append("أول ما يُصلح: الهوك — أقل من 6 يعني يُستبعد "
                         "حسب جدول maquina؛ أعد صياغته بفجوة فضول "
                         "وحقيقة محددة.")
    avg = cuts["avg_shot_seconds"]
    if avg <= 4:
        pace = "سريع (متوسط اللقطة %.1f ث)" % avg
    elif avg <= 8:
        pace = "متوازن (متوسط اللقطة %.1f ث)" % avg
    else:
        pace = ("بطيء (متوسط اللقطة %.1f ث — مشاهد Veo 8 ثوانٍ "
                "بالتصميم، فالبطء هنا بنيوي لا عيب مونتاج)") % avg
    lines.append("الإيقاع: %d لقطة — %s" % (cuts["shot_count"], pace))
    if silence_ok is False:
        lines.append("فجوات صمت عند الفواصل — أصلحها بـ fix-audio قبل "
                     "النشر (وصفة عائشة ج2).")
    elif silence_ok is True:
        lines.append("لا صمت مزعج عند الفواصل.")
    wpm = (density or {}).get("wpm")
    if wpm is not None:
        lines.append("كثافة السرد: %.0f كلمة/دقيقة (%d كلمة)"
                     % (wpm, density["words"]))
        if wpm < 100:
            lines.append("السرد بطيء نسبيًا — إيقاع Kwai (~109 "
                         "كلمة/دقيقة) أسرع؛ جرّب atempo 1.25.")
    else:
        lines.append("كثافة السرد: غير مقاسة (لا ملفات ASS متاحة).")
    known = [v for v in (fb_views, yt_views)
             if isinstance(v, (int, float))]
    if known:
        total = sum(known)
        lines.append("المشاهدات الحقيقية: فيسبوك %s — يوتيوب %s"
                     % (fb_views if fb_views is not None else "غير معروف",
                        yt_views if yt_views is not None else "غير معروف"))
        if hook_score is not None and hook_score["total"] >= 9 \
                and total >= 500:
            lines.append("الخلاصة: الهوك القوي (9+) مرجّح أن يكون سبب "
                         "الأداء — حافظ على نفس الصيغة في الفيديو التالي.")
        elif hook_score is not None and hook_score["total"] < 6 \
                and total < 500:
            lines.append("الخلاصة: الأداء الضعيف يتسق مع هوك ضعيف — "
                         "ابدأ بإصلاح الهوك قبل أي تغيير آخر.")
        else:
            lines.append("الخلاصة: الأرقام لا تحسم وحدها — قارن الهوك "
                         "والإيقاع بالفيديو السابق قبل الفيديو التالي.")
    else:
        lines.append("المشاهدات الحقيقية: غير معروفة — انشر الفيديو "
                     "أولًا ثم أعد analyze --dna لمطابقته بأرقامه.")
    return lines


def build_rebuild_proposal(report, story_text):
    """اقتراح إعادة بناء فيديو جديد على نمط فيديو مرجعي.

    تأخذ تقرير DNA (ناتج analyze_dna) ونص قصة عربية، وترجع
    نصًا عربيًا من 4 أقسام: قالب الهوك المقترح (من نمط هوك
    المرجع + تفصيل درجته)، وهدف إيقاع اللقطات (من متوسط طول
    لقطة المرجع)، وتوجيه الصمت (من فجوات صمت المرجع)، وهدف
    كثافة الكلمات. كل قسم برقم المرجع الحقيقي أو «غير مقاس»
    إن غاب — لا أرقام مخترعة أبدًا.
    """
    report = report or {}
    hook = report.get("hook") or {}
    pacing = report.get("pacing") or {}
    silence = report.get("silence") or {}
    density = report.get("word_density") or {}
    lines = ["== اقتراح إعادة بناء ==",
             "المرجع: %s" % (report.get("video") or "غير معروف"),
             ""]
    # 1) قالب الهوك — من تفصيل درجة هوك المرجع.
    lines.append("-- 1) قالب الهوك المقترح --")
    bd = hook.get("breakdown") or {}
    total = hook.get("total")
    mx = hook.get("max")
    if total is not None:
        lines.append("هوك المرجع: «%s» — الدرجة %s/%s (%s)"
                     % (hook.get("hook", "")[:80], total, mx,
                        hook.get("verdict") or ""))
        strong = []
        if (bd.get("curiosity_gap") or 0) >= 2:
            strong.append("فجوة فضول قوية (سؤال + تشويق)")
        elif (bd.get("curiosity_gap") or 0) >= 1:
            strong.append("فجوة فضول (تشويق بلا سؤال)")
        if (bd.get("specific_fact") or 0) >= 1:
            strong.append("حقيقة محددة (رقم/اسم)")
        if (bd.get("conflict") or 0) >= 1:
            strong.append("صراع/رأي قوي")
        if bd.get("direct_entry"):
            strong.append("دخول مباشر بلا تمهيد")
        if bd.get("payoff"):
            strong.append("عائد داخل المقطع")
        if bd.get("self_contained"):
            strong.append("قائم بذاته")
        if total < 6:
            lines.append("تنبيه: هوك المرجع نفسه ضعيف (أقل من 6) — "
                         "القالب أدناه من أقوى عناصره فقط، لا من "
                         "صيغته كاملة.")
        if strong:
            lines.append("أقوى عناصر هوك المرجع: %s."
                         % "، ".join(strong))
        else:
            lines.append("هوك المرجع بلا عنصر قوي واحد — لا تُقلّد "
                         "صيغته؛ ابنِ الهوك الجديد من الصفر.")
        lines.append("القالب المقترح: «ليه [الشخص] [فعل صادم]؟ "
                     "[حقيقة محددة] — [مفاجأة/صراع]»")
        lines.append("مثال على القالب (من عناصر المرجع لا من نصه): "
                     "سؤال يفتح فجوة فضول، ثم رقم أو اسم محدد، ثم "
                     "كلمة صراع أو مفاجأة — في جملة واحدة ≤140 حرفًا "
                     "بلا رقم في البداية.")
    else:
        lines.append("هوك المرجع: غير مقاس — لا قالب هوك من المرجع؛ "
                     "استخدم جدول maquina (سؤال + حقيقة محددة + "
                     "صراع) لبناء هوك جديد.")
    # العائد داخل المقطع — من نص القصة الجديدة نفسها.
    if story_text:
        sents = [s.strip() for s in re.split(r"[.!؟\n]+", story_text)
                 if s.strip()]
        last_third = sents[len(sents) * 2 // 3:] if sents else []
        tail = " ".join(last_third)
        if any(w in tail for w in ("العبرة", "الدرس", "تعلم", "فهم",
                                   "عرف", "ندم", "تاب", "رجع", "حصد")):
            lines.append("نص القصة الجديدة: العبرة/الختام موجودة في "
                         "آخر ثلث النص — معيار العائد محقق.")
        else:
            lines.append("نص القصة الجديدة: لا عبرة/ختام واضح في آخر "
                         "ثلث النص — أضف العبرة في آخر ثلث ليُقاس "
                         "معيار العائد.")
    else:
        lines.append("نص القصة غير متاح — معيار العائد غير مقاس.")
    lines.append("")
    # 2) هدف إيقاع اللقطات — من متوسط طول لقطة المرجع.
    lines.append("-- 2) هدف إيقاع اللقطات --")
    avg = pacing.get("avg_shot_seconds")
    shots = pacing.get("shot_count")
    duration = report.get("duration")
    if avg is not None:
        lines.append("متوسط لقطة المرجع: %.1f ثانية (%s لقطة في "
                     "فيديو مدته %s ثانية) — استهدف نفس المتوسط "
                     "في إعادة البناء (قطع كل ~%.1f ث)."
                     % (avg, shots if shots is not None else "غير معروف",
                        duration if duration is not None else "غير معروف",
                        avg))
    else:
        lines.append("إيقاع المرجع: غير مقاس — لا هدف إيقاع رقمي؛ "
                     "قس الإيقاع بـ analyze --dna على المرجع أولًا.")
    lines.append("")
    # 3) توجيه الصمت — من فجوات صمت المرجع.
    lines.append("-- 3) توجيه الصمت --")
    detail = silence.get("detail") or ""
    ok = silence.get("ok")
    if ok is True:
        lines.append("المرجع بلا صمت مزعج عند الفواصل — حافظ على "
                     "نفس المعالجة في إعادة البناء (لا صمت ≥1 ثانية "
                     "عند الفاصل).")
        if detail and "غير مقاس" not in detail:
            lines.append("  تفصيل المرجع: %s" % detail)
    elif ok is False:
        lines.append("المرجع فيه فجوات صمت عند الفواصل — أصلحها في "
                     "إعادة البناء بـ fix-audio قبل النشر.")
        if detail:
            lines.append("  تفصيل المرجع: %s" % detail)
    else:
        lines.append("صمت المرجع: غير مقاس — لا توجيه صمت رقمي؛ "
                     "افحص الصمت بـ check قبل النشر.")
    lines.append("")
    # 4) هدف كثافة الكلمات — من كثافة سرد المرجع.
    lines.append("-- 4) هدف كثافة الكلمات --")
    wpm = density.get("wpm")
    if wpm is not None:
        lines.append("كثافة سرد المرجع: %.0f كلمة/دقيقة (%d كلمة) — "
                     "استهدف نفس الكثافة في إعادة البناء."
                     % (wpm, density.get("words") or 0))
    else:
        lines.append("كثافة سرد المرجع: غير مقاسة (لا ملفات ASS "
                     "متاحة) — لا هدف كثافة رقمي.")
    return "\n".join(lines) + "\n"


def format_report(dna):
    """نص عربي لتقرير DNA."""
    lines = ["== تحليل DNA الفيروسي ==",
             "الفيديو: %s" % dna["video"],
             "المدة: %.1f ثانية" % dna["duration"],
             ""]
    h = dna["hook"]
    if h is not None:
        lines.append("-- الهوك: %d/%d (%s) --" % (
            h["total"], h["max"], h["verdict"]))
        for key, label in (("curiosity_gap", "فجوة فضول (0–3)"),
                           ("specific_fact", "حقيقة محددة (0–2)"),
                           ("conflict", "صراع/رأي قوي (0–2)"),
                           ("direct_entry", "دخول مباشر (0–1)"),
                           ("payoff", "عائد داخل المقطع (0–1)"),
                           ("self_contained", "قائم بذاته (0–1)")):
            v = h["breakdown"][key]
            lines.append("  %s: %s" % (
                label, "غير مقاس (يحتاج نص القصة)" if v is None else v))
        lines.append("")
    p = dna["pacing"]
    lines.append("-- الإيقاع: %d لقطة — متوسط اللقطة %.1f ثانية --"
                 % (p["shot_count"], p["avg_shot_seconds"]))
    lines.append("  أزمنة القطع: %s"
                 % (", ".join("%.1f" % t for t in p["cuts"])
                    or "بلا قطع داخلية"))
    lines.append("")
    lines.append("-- الصمت عند الفواصل: %s --"
                 % (dna["silence"]["detail"] or "غير مقاس"))
    lines.append("")
    d = dna["word_density"]
    lines.append("-- كثافة السرد: %s --"
                 % (("%.0f كلمة/دقيقة (%d كلمة، %d ملف ASS)"
                     % (d["wpm"], d["words"], d["files"]))
                    if d["wpm"] is not None
                    else "غير مقاسة (لا ملفات ASS متاحة)"))
    lines.append("")
    lines.append("-- الحكم --")
    for v in dna["verdict"]:
        lines.append("  - %s" % v)
    ap = dna.get("audio_profile")
    if ap:
        # ملف أداء الصوت (جولة v0.1.38 §2) — يظهر فقط عند
        # وجود المفتاح (analyze --dna --audio-profile).
        lines.append("")
        lines.append("-- أداء الصوت --")
        lines.append("  الملف: %s" % ap["audio"])
        lines.append("  المدة: %.1f ثانية — متوسط %.1f dB — "
                     "أقصى %.1f dB"
                     % (ap["duration_seconds"], ap["mean_db"],
                        ap["max_db"]))
        lines.append("  نسبة الصمت: %.3f (%d فترة صمت)"
                     % (ap["silence_ratio"], len(ap["silences"])))
        emphasized = [e.get("text") for e in (ap.get("emphasized")
                                              or []) if e.get("text")]
        lines.append("  عبارات مؤكَّدة: %s"
                     % (", ".join(emphasized) if emphasized else "بلا"))
    return "\n".join(lines) + "\n"


def save_report(dna, runs_dir):
    """احفظ تقرير DNA JSON في runs/. يرجع مسار الملف."""
    os.makedirs(runs_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(runs_dir, "dna-%s.json" % ts)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dna, f, ensure_ascii=False, indent=2)
    return path
