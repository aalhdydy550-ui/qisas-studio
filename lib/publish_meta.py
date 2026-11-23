#!/usr/bin/env python3
"""عنوان/وسوم/وصف نشر مولّدة — `lib/publish_meta.py` (الجولة v0.1.39).

`generate_publish_meta(story, part=1, parts=1, chat_fn=None)` ترجع
{"title", "description", "tags", "hashtags", "source"}:

- مع `chat_fn(prompt) -> نص` (نمط `lib/script_meta.py` نفسه:
  المنسّق يمرّر غلافًا حول سلسلة LLM الحالية في studio.py —
  ddgw ثم Groq ثم Gemini عبر `_llm_chat` — فيُستدعى النموذج
  مرة واحدة) يُحلَّل الرد إلى عنوان + وصف قصير + وسوم.
- بلا `chat_fn` أو عند فشل الاستدعاء أو رد فارغ/غير صالح:
  بديل محلي صارم بلا شبكة — العنوان «اسم القصة | الجزء X من Y»
  (أو «اسم القصة | قصة حقيقية» للقصة من جزء واحد)، والوصف
  يبدأ بـ «قصة حقيقية»، والوسوم الحزمة الثابتة نفسها في
  `lib/publish.py` (HASHTAGS) + وسم من العنوان.

الضوابط (تُطبَّق على مسار النموذج والبديل معًا):
- عنوان يوتيوب ≤ 100 حرف (حد `lib/publish.py` YT_TITLE_LIMIT).
- وسوم يوتيوب مجمّعة ≤ 500 حرف (حد YT_TAGS_LIMIT).
- بلا بوابة متابعة/تعليق أبدًا: أي جملة يرفضها
  `lib.caption_check.sentence_issue` تُحذف، وإن فرغ الوصف
  يُستخدم البديل المحلي.
- `format_for_publish(meta)` يرجع القيم جاهزة لأمر النشر:
  {"title", "caption", "tags"} حيث tags نص مفصول بفواصل
  يُمرَّر لـ `publish --tags` (أو يُترك None فيُستخدم
  الافتراضي في `cmd_publish`).

هذه الوحدة مستقلة: لا تعدّل `lib/publish.py` ولا تستدعي أي
شبكة بنفسها — `chat_fn` هو المدخل الوحيد للنموذج.
"""
import re

from lib import caption_check

FIXED_HASHTAGS = ["#قصص_وعبر", "#قصص_واقعية",
                  "#قصص_مؤثرة", "#حكايات"]
FIXED_TAGS = ["قصص وعبر", "قصص واقعية", "قصص مؤثرة", "حكايات"]

YT_TITLE_LIMIT = 100
YT_TAGS_LIMIT = 500
MAX_DESCRIPTION_CHARS = 400

META_PROMPT = (
    "لصفحة فيسبوك «قصص وعبر» باللهجة المصرية: اكتب بيانات نشر "
    "لفيديو قصة بعنوان «{title}» عن: {story}. "
    "السطر الأول: عنوان يوتيوب جذاب (≤ 100 حرف، بلا علامات "
    "تنصيص، ويتضمن «قصة حقيقية»). "
    "السطر الثاني: وصف قصير جملة أو جملتان تشوّقان للقصة بلا "
    "كشف النهاية. "
    "السطر الثالث: وسوم يوتيوب مفصولة بفواصل. "
    "لا تجعل أي جزء مشروطًا بالمتابعة أو التعليق أبدًا. "
    "اكتب الأسطر الثلاثة فقط، بلا أي نص آخر."
)


def _story_parts(story):
    """(العنوان، نص القصة، الهوك، الجزء، الأجزاء) من سلسلة أو قاموس.

    القاموس يقبل {"title", "text"|"story", "hook", "part", "parts"}.
    """
    part, parts = 1, 1
    hook = ""
    if isinstance(story, dict):
        title = (story.get("title") or "").strip()
        text = (story.get("text") or story.get("story") or "").strip()
        hook = (story.get("hook") or "").strip()
        part = story.get("part", 1)
        parts = story.get("parts", 1)
        return (title or text or str(story), text or title, hook,
                part, parts)
    text = (story or "").strip()
    return text, text, hook, part, parts


def _validate_parts(part, parts):
    """تحقق من أرقام الأجزاء؛ ValueError عربي عند الخطأ."""
    if isinstance(part, bool) or not isinstance(part, int) \
            or isinstance(parts, bool) or not isinstance(parts, int):
        raise ValueError("أرقام الأجزاء يجب أن تكون أعدادًا صحيحة")
    if parts < 1:
        raise ValueError("عدد الأجزاء يجب أن يكون 1 على الأقل")
    if part < 1 or part > parts:
        raise ValueError(
            "رقم الجزء يجب أن يكون بين 1 و%d (وصل: %s)"
            % (parts, part))
    return part, parts


def _title_hashtag(title):
    """وسم من عنوان القصة: كلمات العنوان موصولة بـ _."""
    words = re.findall(r"[\w\u0600-\u06FF]+", title or "")
    if not words:
        return None
    return "#" + "_".join(words)


def _fit_title(base, part, parts):
    """عنوان محلي ضمن حد يوتيوب (100 حرف): «الاسم | الجزء X من Y».

    لقصة من جزء واحد: «الاسم | قصة حقيقية». الاسم الطويل
    يُقصَّر من آخره ليتسع اللاحق.
    """
    base = (base or "").strip() or "قصة جديدة"
    suffix = (" | الجزء %d من %d" % (part, parts)) if parts > 1 \
        else " | قصة حقيقية"
    room = YT_TITLE_LIMIT - len(suffix)
    if len(base) > room:
        base = base[:max(room - 1, 1)].rstrip() + "…"
    return base + suffix


def _local_meta(title, story_text, hook, part, parts):
    """البديل المحلي: عنوان + وصف + وسوم — بلا شبكة."""
    title = (title or "").strip() or "قصة جديدة"
    snippet = (hook or "").strip()
    if not snippet:
        sentences = caption_check.split_sentences(story_text or title)
        snippet = sentences[0] if sentences else title
    if len(snippet) > 200:
        snippet = snippet[:200].rstrip() + "…"
    description = ("قصة حقيقية عن %s — والنهاية أغرب مما تتخيل.\n%s"
                   % (snippet, caption_check.APPROVED_STORY_LINE))
    tags = list(FIXED_TAGS)
    plain_title = re.sub(r"\s+", " ", title).strip()
    if plain_title and len(plain_title) <= 30 \
            and plain_title not in tags:
        tags.append(plain_title)
    hashtags = list(FIXED_HASHTAGS)
    tag = _title_hashtag(title)
    if tag and tag not in hashtags:
        hashtags.append(tag)
    return {"title": _fit_title(title, part, parts),
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
            "source": "local"}


def _clean_title_line(line):
    """نظّف سطر عنوان النموذج: احذف التسمية وعلامات التنصيص."""
    text = (line or "").strip()
    text = re.sub(r"^(العنوان|عنوان|Title)\s*[:：-]\s*", "", text)
    text = text.strip("«»\"'“”").strip()
    return text


def _clean_description(lines):
    """وصف النموذج: احذف التسمية والجمل المحظورة؛ "" إن فرغ."""
    kept = []
    for line in lines:
        text = re.sub(r"^(الوصف|وصف|Description)\s*[:：-]\s*",
                      "", (line or "").strip())
        for sentence in caption_check.split_sentences(text):
            if caption_check.sentence_issue(sentence) is None:
                kept.append(sentence)
    description = " ".join(kept).strip()
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS].rstrip() + "…"
    return description


def _parse_llm(text, title, part, parts):
    """افصل رد النموذج إلى عنوان/وصف/وسوم. None إن غير صالح.

    الصالح: عنوان غير فارغ ≤ 100 حرف بلا جملة محظورة، ووصف
    غير فارغ بلا جملة محظورة. الوسوم تُكمَّل بالحزمة الثابتة
    دائمًا، والمجموع ≤ 500 حرف.
    """
    lines = [l.strip() for l in (text or "").splitlines()
             if l.strip()]
    if not lines:
        return None
    raw_title = _clean_title_line(lines[0])
    if not raw_title or len(raw_title) > YT_TITLE_LIMIT:
        return None
    if any(caption_check.sentence_issue(s) is not None
           for s in caption_check.split_sentences(raw_title)):
        return None
    desc_lines, tag_texts = [], []
    for line in lines[1:]:
        tags = re.findall(r"#[\w\u0600-\u06FF]+", line)
        plain = re.sub(r"#[\w\u0600-\u06FF]+", "", line).strip()
        plain = re.sub(r"^(الوسوم|وسوم|Tags|الهاشتاغات)\s*[:：-]\s*",
                       "", plain)
        if tags:
            # «#قصص_وعبر» من النموذج هي نفس وسم الحزمة الثابتة
            # «قصص وعبر» — وحّدها (شرطة سفلية ← مسافة) قبل الدمج.
            tag_texts.extend(t.lstrip("#").replace("_", " ")
                             for t in tags)
        if plain:
            desc_lines.append(plain)
        elif not tags and line.strip():
            desc_lines.append(line.strip())
    description = _clean_description(desc_lines)
    if not description:
        return None
    tags = []
    for tag in list(FIXED_TAGS) + tag_texts:
        tag = re.sub(r"\s+", " ", (tag or "").strip())
        if tag and tag not in tags:
            tags.append(tag)
    tags_text = ",".join(tags)
    if len(tags_text) > YT_TAGS_LIMIT:
        tags = list(FIXED_TAGS)
    hashtags = ["#" + re.sub(r"\s+", "_", t) for t in tags]
    return {"title": raw_title,
            "description": description,
            "tags": tags,
            "hashtags": hashtags,
            "source": "llm"}


def generate_publish_meta(story, part=1, parts=1, chat_fn=None):
    """ولّد عنوانًا ووصفًا قصيرًا ووسومًا لنشر قصة.

    story سلسلة (اسم/عنوان/نص القصة) أو قاموس {"title", "text",
    "hook", "part", "parts"}؛ وpart/parts الصريحان يغلّبان
    القاموس. chat_fn(prompt) -> نص النموذج (مرة واحدة)؛ None
    أو فشل أو رد غير صالح = البديل المحلي. يرجع {"title",
    "description", "tags", "hashtags", "source"} — source
    ‏"llm" أو "local".
    """
    title, story_text, hook, d_part, d_parts = _story_parts(story)
    if part == 1 and parts == 1 and isinstance(story, dict):
        part, parts = d_part, d_parts
    part, parts = _validate_parts(part, parts)
    if chat_fn is not None:
        prompt = META_PROMPT.format(title=title or story_text,
                                    story=story_text or title)
        try:
            parsed = _parse_llm(chat_fn(prompt), title, part, parts)
        except Exception:
            parsed = None
        if parsed is not None:
            return parsed
    return _local_meta(title, story_text, hook, part, parts)


def format_for_publish(meta):
    """حوّل نتيجة `generate_publish_meta` إلى وسيطات أمر النشر.

    يرجع {"title", "caption", "tags"} حيث caption هو الوصف
    القصير وtags نص مفصول بفواصل لـ `publish --tags`.
    """
    meta = meta or {}
    tags = meta.get("tags") or list(FIXED_TAGS)
    return {"title": (meta.get("title") or "").strip(),
            "caption": (meta.get("description") or "").strip(),
            "tags": ",".join(tags)}
