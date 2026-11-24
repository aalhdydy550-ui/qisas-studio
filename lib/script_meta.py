#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""بيانات نشر فيسبوك مولّدة بالـLLM — `studio.py script`.

`generate_publish_meta(story, chat_fn)` ترجع {"description",
"hashtags", "source"}: تستدعي `chat_fn(prompt)` مرة واحدة (نفس
نمط `suggest_hooks` في lib/ab.py: برومبت عربي مصري)، وإن فشل
الاستدعاء أو رجع نصًا فارغًا فبديل محلي بلا شبكة.

الوصف بلا بوابة متابعة أبدًا: أي جملة يرفضها
`lib.caption_check.sentence_issue` تُحذف من وصف النموذج،
والبديل المحلي ينتهي بسطر طلب القصة المعتمد
(«عندك قصة حصلتلك؟ ابعتها في رسائل الصفحة وهنحكيها باسمك أو
بدون اسم.») — والبرومبت يطلب من النموذج أن ينتهي به أيضًا.
"""
import re

from lib import caption_check

FIXED_HASHTAGS = ["#قصص_وعبر", "#قصص_واقعية",
                  "#قصص_مؤثرة", "#حكايات"]

META_PROMPT = (
    "لصفحة فيسبوك «قصص وعبر» باللهجة المصرية: اكتب وصف نشر "
    "لفيديو قصة بعنوان «{title}» عن: {story}. الوصف جملتان "
    "فقط تشوّقان للقصة بلا كشف النهاية، ثم سطر هاشتاغات. "
    "لا تجعل أي جزء مشروطًا بالمتابعة أو التعليق أبدًا، "
    "واختم الوصف بهذا السطر حرفيًا: «{story_line}» "
    "اكتب الوصف في سطرين، ثم سطر الهاشتاغات في سطر ثالث، "
    "بلا أي نص آخر."
)


def _story_parts(story):
    """(العنوان، نص القصة) من سلسلة أو قاموس {"title", "text"}."""
    if isinstance(story, dict):
        title = (story.get("title") or "").strip()
        text = (story.get("text") or story.get("story") or "").strip()
        return title or text or str(story), text or title
    text = (story or "").strip()
    return text, text


def _title_hashtag(title):
    """وسم من عنوان القصة: كلمات العنوان موصولة بـ _."""
    words = re.findall(r"[\w\u0600-\u06FF]+", title or "")
    if not words:
        return None
    return "#" + "_".join(words)


def _local_meta(title, story_text):
    """البديل المحلي: وصف من نص القصة + الحزمة الثابتة."""
    desc = story_text or title
    description = ("قصة قصيرة حقيقية عن %s — والنهاية أغرب مما تتخيل.\n%s"
                   % (desc, caption_check.APPROVED_STORY_LINE))
    hashtags = list(FIXED_HASHTAGS)
    tag = _title_hashtag(title)
    if tag and tag not in hashtags:
        hashtags.append(tag)
    return {"description": description, "hashtags": hashtags,
            "source": "local"}


def _parse_llm(text):
    """افصل وصف النموذج عن هاشتاغاته. None إن بلا وصف."""
    lines = [l.strip() for l in (text or "").splitlines()
             if l.strip()]
    hashtags = []
    desc_lines = []
    for line in lines:
        tags = re.findall(r"#[\w\u0600-\u06FF]+", line)
        if tags and not re.sub(r"#[\w\u0600-\u06FF]+", "", line).strip():
            hashtags.extend(tags)
        else:
            desc_lines.append(line)
            hashtags.extend(tags)
    # بلا بوابة متابعة: احذف أي جملة محظورة من وصف النموذج،
    # مع الحفاظ على تقسيم الأسطر الأصلي.
    kept_lines = []
    for line in desc_lines:
        kept = [s for s in caption_check.split_sentences(line)
                if caption_check.sentence_issue(s) is None]
        if kept:
            kept_lines.append(" ".join(kept))
    description = "\n".join(kept_lines).strip()
    if not description:
        return None
    return {"description": description,
            "hashtags": hashtags or list(FIXED_HASHTAGS),
            "source": "omniroute"}


def generate_publish_meta(story, chat_fn=None):
    """ولّد وصف نشر + هاشتاغات لقصة.

    story سلسلة (اسم/عنوان/نص القصة) أو قاموس {"title", "text"}.
    chat_fn(prompt) -> نص النموذج (مرة واحدة)؛ None أو فشل أو
    نص فارغ = البديل المحلي. يرجع {"description", "hashtags",
    "source"} — source ‏"omniroute" أو "local".
    """
    title, story_text = _story_parts(story)
    if chat_fn is not None:
        prompt = META_PROMPT.format(
            title=title, story=story_text,
            story_line=caption_check.APPROVED_STORY_LINE)
        try:
            parsed = _parse_llm(chat_fn(prompt))
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
    return _local_meta(title, story_text)
