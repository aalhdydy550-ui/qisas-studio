#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""استخراج نص منظم وتحويله إلى Markdown — جولة تطبيق الأنماط (W6).

النمط مأخوذ من مسح Unlimited-OCR (``~/workspace/studio-work/repo-
survey-unlimited-ocr/REPORT-AR.md``، §5 بند 2، من ``utils/README.md``
هناك): **فصل الاستخراج الخام عن التحويل إلى Markdown**، مع دمج
الجداول العابرة للصفحات وحذف صفوف الترويسة المكررة والحفاظ على
الصفحات الفارغة حتى لا تنزاح أرقام الصفحات. التنفيذ هنا بايثون من
الصفر بالمكتبة القياسية فقط؛ لا كود منقول من Unlimited-OCR ولا من
أي مستودع آخر، ولا OCR هنا أصلًا — المدخل نص خام من صفحات (صفحة
= عنصر في قائمة) يزوّده المتصل.

المرحلتان منفصلتان تمامًا:
  - ``extract_blocks(pages)`` — خام فقط: يصنّف كل صفحة إلى كتل
    (``heading``/``text``/``table``/``empty``) مع رقم الصفحة، بلا أي
    تنسيق Markdown.
  - ``blocks_to_markdown(blocks)`` — تحويل فقط: يدمج الجداول
    المتتالية العابرة للصفحات، ويحذف صف الترويسة المكرر، ويُبقي
    الصفحات الفارغة كعلامة تعليق برقمها حتى لا تنزاح الصفحات.

الكتلة قاموس عادي:
  {"type": "heading"|"text"|"table"|"empty", "page": int,
   "text": str,                       # heading/text/empty
   "level": int,                      # heading فقط
   "rows": [[str, ...], ...]}         # table فقط (الصف الأول ترويسة)

وفيها أيضًا مخطط JSON ثابت صغير لمراقبة المنافسين
(``COMPETITOR_POST_SCHEMA``) مع ``validate_competitor_post`` —
فكرة من مسح Firecrawl (§3 بند 3): مخطط ثابت بدل تلخيص حرّ،
يُرفض أي حقل مفقود بدل تخمينه.
"""

import json
import re
from datetime import datetime

__all__ = [
    "COMPETITOR_POST_SCHEMA",
    "STORY_TYPES",
    "blocks_to_markdown",
    "extract_blocks",
    "extract_blocks_from_text",
    "validate_competitor_post",
]

# ---------------------------------------------------------------- مخطط المنافسين
STORY_TYPES = frozenset({
    "moral", "crime", "horror", "family", "romance", "history", "other",
})

COMPETITOR_POST_SCHEMA = {
    "type": "object",
    "description": (
        "سجل مراقبة منافس واحد: بيانات معلنة فقط (عنوان، تاريخ، نوع "
        "قصة، مشاهدات معلنة، موضوع). لا يُخمَّن أي حقل مفقود — "
        "validate_competitor_post يرفض السجل الناقص."
    ),
    "required": ["title", "date", "story_type", "views", "topic"],
    "properties": {
        "title": {
            "type": "string",
            "description": "عنوان المنشور/الفيديو كما هو معلن",
        },
        "date": {
            "type": "string",
            "description": "تاريخ النشر بصيغة ISO ‏YYYY-MM-DD",
        },
        "story_type": {
            "type": "string",
            "enum": sorted(STORY_TYPES),
            "description": "نوع القصة",
        },
        "views": {
            "type": "integer",
            "minimum": 0,
            "description": "عدد المشاهدات المعلن (عدد صحيح غير سالب)",
        },
        "topic": {
            "type": "string",
            "description": "موضوع القصة في كلمات قليلة",
        },
    },
}


def validate_competitor_post(data):
    """يتحقق من سجل منافس مقابل ``COMPETITOR_POST_SCHEMA``.

    يقبل قاموسًا أو نص JSON. يعيد نسخة مطبَّعة من السجل عند النجاح.
    يرفع ``ValueError`` يسرد كل حقل مفقود/غير صالح — لا يخمّن
    أي قيمة أبدًا.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError("نص JSON غير صالح: %s" % exc) from exc
    if not isinstance(data, dict):
        raise ValueError("سجل المنافس يجب أن يكون كائن JSON (dict)")
    problems = []
    for field in COMPETITOR_POST_SCHEMA["required"]:
        if field not in data:
            problems.append("حقل مفقود: %s" % field)
    title = data.get("title")
    if title is not None and (not isinstance(title, str)
                              or not title.strip()):
        problems.append("title يجب أن يكون نصًا غير فارغ")
    date = data.get("date")
    if date is not None:
        if not isinstance(date, str):
            problems.append("date يجب أن يكون نصًا بصيغة YYYY-MM-DD")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                problems.append("date غير صالح: %r (المطلوب YYYY-MM-DD)"
                                % date)
    story_type = data.get("story_type")
    if story_type is not None and story_type not in STORY_TYPES:
        problems.append("story_type غير معروف: %r (المسموح: %s)"
                        % (story_type, ", ".join(sorted(STORY_TYPES))))
    views = data.get("views")
    if views is not None and (isinstance(views, bool)
                              or not isinstance(views, int)
                              or views < 0):
        problems.append("views يجب أن يكون عددًا صحيحًا غير سالب")
    topic = data.get("topic")
    if topic is not None and (not isinstance(topic, str)
                              or not topic.strip()):
        problems.append("topic يجب أن يكون نصًا غير فارغ")
    if problems:
        raise ValueError("سجل منافس غير صالح: " + "; ".join(problems))
    return {field: data[field]
            for field in COMPETITOR_POST_SCHEMA["required"]}


# ---------------------------------------------------------------- الاستخراج الخام
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_UPPER_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9 \-'&:;,.()]{2,79}$")


def _split_table_row(line):
    """يعيد خلايا سطر جدول أو None إن لم يكن سطر جدول."""
    stripped = line.strip()
    if "|" in stripped:
        cells = [cell.strip()
                 for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and any(cells):
            return cells
    if "\t" in line:
        cells = [cell.strip() for cell in line.split("\t")]
        if len([c for c in cells if c]) >= 2:
            return cells
    return None


def _classify_line(line):
    """يصنّف سطرًا واحدًا: ('heading', level, text) أو ('text', text)."""
    match = _HEADING_RE.match(line.strip())
    if match:
        return ("heading", len(match.group(1)), match.group(2))
    stripped = line.strip()
    if (len(stripped) >= 3 and _UPPER_HEADING_RE.match(stripped)
            and not stripped.endswith(".")):
        return ("heading", 2, stripped)
    return ("text", None, stripped)


def extract_blocks(pages):
    """يستخرج كتلًا خامًا من صفحات نصية.

    ``pages``: قائمة نصوص، عنصر لكل صفحة (الصفحة 1 = العنصر 0).
    صفحة فارغة (أو بيضاء) تُنتج كتلة ``empty`` برقمها — عمدًا،
    حتى لا تنزاح أرقام الصفحات في التحويل اللاحق.
    لا ينتج أي Markdown هنا؛ التصنيف فقط.
    """
    if isinstance(pages, str) or not hasattr(pages, "__iter__"):
        raise TypeError("pages يجب أن تكون قائمة نصوص (صفحة لكل عنصر)")
    blocks = []
    for index, page in enumerate(pages):
        if not isinstance(page, str):
            raise TypeError("الصفحة %d ليست نصًا" % (index + 1))
        page_no = index + 1
        if not page.strip():
            blocks.append({"type": "empty", "page": page_no, "text": ""})
            continue
        pending_table = None

        def _flush_table():
            nonlocal pending_table
            if pending_table is not None:
                blocks.append(pending_table)
                pending_table = None

        for line in page.splitlines():
            row = _split_table_row(line)
            if row is not None:
                if pending_table is None:
                    pending_table = {"type": "table", "page": page_no,
                                     "rows": [row]}
                else:
                    pending_table["rows"].append(row)
                continue
            _flush_table()
            if not line.strip():
                continue
            kind, level, text = _classify_line(line)
            if kind == "heading":
                blocks.append({"type": "heading", "page": page_no,
                               "text": text, "level": level})
            else:
                blocks.append({"type": "text", "page": page_no,
                               "text": text})
        _flush_table()
    return blocks


def extract_blocks_from_text(text, page_separator="\f"):
    """اختصار: يقسّم نصًا واحدًا على فاصل الصفحات ثم يستخرج الكتل."""
    if not isinstance(text, str):
        raise TypeError("text يجب أن يكون str")
    return extract_blocks(text.split(page_separator))


# ---------------------------------------------------------------- التحويل إلى Markdown
def _table_to_markdown(rows):
    # حذف أي صف داخل الجدول مطابق لصف الترويسة (ترويسة مكررة).
    rows = [rows[0]] + [row for row in rows[1:] if row != rows[0]]
    lines = []
    header = rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows[1:]:
        padded = list(row) + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded[:len(header)]) + " |")
    return lines


def blocks_to_markdown(blocks):
    """يحوّل كتلًا خامًا إلى Markdown.

    القواعد:
      - جداول متتالية (عابرة للصفحات) تُدمج في جدول واحد؛ وصف
        الترويسة المكرر (مطابق لصف ترويسة الجدول المدمج) يُحذف.
      - صف مكرر داخل جدول واحد مطابق لترويسة ذلك الجدول يُحذف.
      - الصفحة الفارغة تُحفَظ كتعليق برقمها حتى لا تنزاح الصفحات.
    """
    if not isinstance(blocks, list):
        raise TypeError("blocks يجب أن تكون قائمة كتل")
    lines = []
    merged_table = None

    def _flush_table():
        nonlocal merged_table
        if merged_table is not None:
            lines.extend(_table_to_markdown(merged_table["rows"]))
            lines.append("")
            merged_table = None

    for block in blocks:
        if not isinstance(block, dict) or "type" not in block \
                or "page" not in block:
            raise ValueError("كتلة غير صالحة: %r" % (block,))
        btype = block["type"]
        if btype == "table":
            rows = block.get("rows")
            if not rows or not isinstance(rows, list):
                raise ValueError("جدول بلا صفوف في الصفحة %s"
                                 % block["page"])
            if merged_table is None:
                merged_table = {"rows": [list(r) for r in rows]}
            else:
                header = merged_table["rows"][0]
                start = 1 if rows[0] == header else 0
                for row in rows[start:]:
                    merged_table["rows"].append(list(row))
            continue
        _flush_table()
        if btype == "heading":
            level = block.get("level", 2)
            lines.append("#" * max(1, min(6, level)) + " "
                         + block.get("text", "").strip())
            lines.append("")
        elif btype == "text":
            lines.append(block.get("text", "").strip())
            lines.append("")
        elif btype == "empty":
            lines.append("<!-- صفحة %d فارغة -->" % block["page"])
            lines.append("")
        else:
            raise ValueError("نوع كتلة غير معروف: %r" % btype)
    _flush_table()
    # حذف صفوف الترويسة المكررة داخل الجدول الواحد يتم في
    # _table_to_markdown عند الإخراج، والدمج عبر الصفحات يسقط
    # صف ترويسة الجزء اللاحق عند مطابقته لترويسة المدمج.
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n" if text.strip() else ""
