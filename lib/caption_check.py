#!/usr/bin/env python3
"""فحص امتثال كابشن فيسبوك — `studio.py publish` (فحص مسبق).

يطبّق قواعد مهارة facebook_caption_compliance_check ككود:

- تُرفض أي جملة تجعل الجزء التالي مشروطًا بالمتابعة أو التعليق
  (أو بأي تفاعل/مكافأة)، أو تحجب الجزء التالي كعقاب.
- تُسمح الدعوة اللطيفة المرتبطة بوقت معلن فقط («الجزء الثاني
  بكرة 7 مساءً — اعمل متابعة عشان يوصلك أول ما ينزل») لأن الجزء
  سينشر في وقته سواء تابع القارئ أم لا.
- يُسمح سطر «عندك قصة حصلتلك؟ ابعتها في رسائل الصفحة…» (طلب
  القصة عبر الرسائل لا التعليقات).
- الإصلاح: استبدال الجملة المحظورة بالدعوة اللطيفة (أو بسطر طلب
  القصة)؛ وإن كانت الجملة المحظورة في الهوك نفسه (أول سطر) فلا
  إصلاح تلقائي — يجب إعادة كتابة الكابشن كاملًا.
"""
import re

APPROVED_STORY_LINE = ("عندك قصة حصلتلك؟ ابعتها في رسائل الصفحة "
                       "وهنحكيها باسمك أو بدون اسم.")
DEFAULT_NEXT_PART_TIME = "بكرة 7 مساءً"

_TIME_RE = re.compile(r"بكرة|غدًا|غدا|غداً|مساء|الساعة|الساعه")
_FOLLOW_RE = re.compile(r"متابعة|فولو|follow|تابع|تابعونا|تابعنا")
_PART_RE = re.compile(r"الجزء")
_COMMENT_RE = re.compile(r"التعليقات|تعليق|كومنت|comment")
_COND_RE = re.compile(r"(لو|إذا|اذا)\s+"
                      r"(عايز|عاوز|تبغى|تريد|بدك|حابب|حابة|نفسك|عاوزين)")
_WRITE_COMMENT_RE = re.compile(r"اكتب|علّق|علق|كومنت")
_WITHHOLD_RE = re.compile(r"مش\s+هينزل|لن\s+ينزل|ما\s+هينزل|"
                          r"لن\s+يُنشر|لن\s+ينشر")
_ENGAGE_RE = re.compile(r"لايك|شارك|شير|share")
_REWARD_RE = re.compile(r"تكسب|هدية|جائزة|مقابل|تربح")
_SEND_STORY_RE = re.compile(r"ابعت|أرسل|ارسل|اكتب")


def approved_invite(next_part_time=DEFAULT_NEXT_PART_TIME):
    """الدعوة اللطيفة المعتمدة لجزء تالٍ بوقت معلن."""
    return ("الجزء الثاني %s — اعمل متابعة عشان يوصلك أول ما ينزل"
            % next_part_time)


def split_sentences(text):
    """قسّم نصًا إلى جمل (على الأسطر وعلامات . ! ؟)."""
    out = []
    for line in (text or "").splitlines():
        for piece in re.split(r"(?<=[.!؟])\s*", line):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def sentence_issue(sentence):
    """افحص جملة واحدة. يرجع (الفئة، السبب) أو None إن سليمة.

    الفئة "next_part" لجملة تجعل الجزء التالي مشروطًا، و"story"
    لطلب قصة مشروط بالتعليق.
    """
    s = sentence or ""
    if not s.strip():
        return None
    # الدعوة اللطيفة المسموحة: وقت معلن + متابعة + يوصلك.
    if (_TIME_RE.search(s) and _FOLLOW_RE.search(s)
            and ("يوصلك" in s or "هيوصلك" in s)):
        return None
    # سطر طلب القصة المعتمد (عبر رسائل الصفحة).
    if "رسائل الصفحة" in s:
        return None
    if _COND_RE.search(s) and _PART_RE.search(s):
        return ("next_part",
                "الجزء التالي مشروط بالمتابعة أو التعليق")
    if _FOLLOW_RE.search(s) and "عشان" in s and _PART_RE.search(s):
        return ("next_part",
                "المتابعة مشروطة لاستلام الجزء التالي")
    if (_WRITE_COMMENT_RE.search(s) and _COMMENT_RE.search(s)
            and _PART_RE.search(s)):
        return ("next_part",
                "التعليق مشروط لاستلام الجزء التالي")
    if _FOLLOW_RE.search(s) and _WRITE_COMMENT_RE.search(s):
        return ("next_part",
                "المتابعة والتعليق مشروطان للجزء التالي")
    if _PART_RE.search(s) and _WITHHOLD_RE.search(s):
        return ("next_part", "حجب الجزء التالي كعقاب")
    if (_ENGAGE_RE.search(s) and "عشان" in s
            and (_PART_RE.search(s) or "القصة" in s)):
        return ("next_part",
                "التفاعل مشروط لاستلام الجزء التالي")
    if _FOLLOW_RE.search(s) and _REWARD_RE.search(s):
        return ("next_part", "المتابعة مشروطة بمكافأة")
    if (_SEND_STORY_RE.search(s) and "قصت" in s
            and _COMMENT_RE.search(s)):
        return ("story", "طلب القصة مشروط بالتعليق")
    return None


def find_issues(caption):
    """كل الجمل المحظورة في الكابشن مع سبب كل منها.

    يرجع قائمة {"sentence", "reason", "category", "in_hook"} —
    in_hook صحيحة إن كانت الجملة في أول سطر غير فارغ (الهوك).
    """
    lines = [ln for ln in (caption or "").splitlines() if ln.strip()]
    hook_line = lines[0] if lines else ""
    issues = []
    for line in (caption or "").splitlines():
        for sentence in split_sentences(line):
            found = sentence_issue(sentence)
            if found:
                category, reason = found
                issues.append({"sentence": sentence,
                               "reason": reason,
                               "category": category,
                               "in_hook": line.strip() == hook_line.strip()})
    return issues


def fix_caption(caption, next_part_time=DEFAULT_NEXT_PART_TIME):
    """استبدل الجمل المحظورة بالبدائل المعتمدة.

    يرجع الكابشن المصحح، أو None إن كانت جملة محظورة في الهوك
    نفسه (فيُعاد كتابة الكابشن كاملًا بدل الإصلاح الجزئي).
    """
    lines = (caption or "").splitlines()
    first = next((ln for ln in lines if ln.strip()), "")
    fixed_lines = []
    for line in lines:
        sentences = split_sentences(line)
        if not sentences:
            fixed_lines.append(line)
            continue
        fixed_parts = []
        for sentence in sentences:
            found = sentence_issue(sentence)
            if not found:
                fixed_parts.append(sentence)
                continue
            if line.strip() == first.strip():
                return None
            category, _reason = found
            if category == "story":
                fixed_parts.append(APPROVED_STORY_LINE)
            else:
                fixed_parts.append(
                    approved_invite(next_part_time))
        fixed_lines.append(" ".join(fixed_parts))
    return "\n".join(fixed_lines)


def check_caption(caption, next_part_time=DEFAULT_NEXT_PART_TIME):
    """افحص كابشنًا كاملًا.

    يرجع {"ok", "issues", "fixed"} — fixed هو الكابشن المصحح
    (أو None إن لزم إعادة كتابة كاملة أو لا مشاكل أصلًا).
    """
    issues = find_issues(caption)
    if not issues:
        return {"ok": True, "issues": [], "fixed": None}
    return {"ok": False, "issues": issues,
            "fixed": fix_caption(caption, next_part_time)}
