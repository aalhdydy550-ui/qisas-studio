#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""منظّف HTML ← Markdown للصفحات العامة — جولة تطبيق الأنماط (W6).

النمط مأخوذ من مسح Firecrawl (``~/workspace/studio-work/repo-survey-
firecrawl/REPORT-AR.md``، §3 بند 1): تنظيف HTML إلى Markdown جاهز
للنماذج — إسقاط القوالب (ترويسات/تنقّل/تذييلات/سكربتات) قبل توليد
Markdown. التنفيذ هنا بايثون من الصفر بالمكتبة القياسية فقط
(``html.parser`` + ``urllib``)؛ لا كود منقول من Firecrawl ولا من أي
مستودع آخر.

القواعد:
  - تُسقَط ``script`` و``style`` و``nav`` و``header`` و``footer``
    (مع كل محتواها، ولو تداخلت).
  - تُحوَّل ``h1``–``h3`` و``p`` و``a`` و``ul/li`` (و``ol``) إلى
    Markdown؛ مع دعم صغير إضافي لـ``strong``/``em`` و``code`` و``pre``
    و``blockquote`` و``hr`` و``br`` و``img`` (نص بديل فقط).
  - سقف طول للمخرجات (``max_chars``، الافتراضي 200_000 حرف) مع
    علامة قطع صريحة بدل قصّ صامت.
  - الروابط النسبية تُحلّ إلى مطلقة عند تمرير ``base_url``.

الاستخدام المشروع فقط: صفحات عامة مفتوحة (توثيق أدوات ومدونات
عامة). لا صفحات فيسبوك/يوتيوب ولا أي صفحة تتطلب تسجيل دخول،
ولا كشط قصص أو نصوص محمية — المنظّف أداة تنظيف نص، لا إذن كشط.

الدوال:
  - ``html_to_markdown(html, base_url=None, max_chars=...)`` — التحويل.
  - ``fetch_page_html(url, timeout=..., max_bytes=...)`` — جلب صفحة
    عامة عبر ``urllib`` (مع فحص نوع المحتوى وسقف حجم).
  - ``estimate_tokens(text)`` — تقدير تقريبي للرموز (طول/4) لقياس
    نسبة الاختصار قبل/بعد؛ تقدير خشن متسق، لا عدّ دقيق لنموذج ما.
"""

import html as _html
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

__all__ = [
    "DEFAULT_MAX_CHARS",
    "DEFAULT_MAX_BYTES",
    "estimate_tokens",
    "fetch_page_html",
    "html_to_markdown",
]

DEFAULT_MAX_CHARS = 200_000
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_TIMEOUT = 20

# وسوم تُسقَط مع كل محتواها.
_DROP_TAGS = frozenset({"script", "style", "nav", "header", "footer"})
# وسوم كتلية تُنهي الفقرة الحالية عند فتحها.
_BLOCK_TAGS = frozenset({
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li",
    "blockquote", "pre", "table", "div", "section", "article", "hr",
})
_HEADING_LEVEL = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

_WS_RE = re.compile(r"[ \t\r\f\v]+")


def estimate_tokens(text):
    """تقدير تقريبي لعدد الرموز: حرف واحد ≈ ربع رمز.

    تقدير خشن (شائع للإنجليزية؛ العربية أثقل رمزيًا) لكنه متسق
    قبل/بعد، فيصلح لقياس نسبة الاختصار لا لعدّ دقيق لنموذج ما.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def fetch_page_html(url, timeout=DEFAULT_TIMEOUT,
                    max_bytes=DEFAULT_MAX_BYTES):
    """يجلب صفحة عامة عبر ``urllib`` ويعيد نص HTML (str).

    يرفض الردود غير النصية/HTML ويرفض تجاوز سقف الحجم.
    لا يتخطى أي حماية ولا يسجّل دخولًا؛ للصفحات العامة فقط.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "qisas-studio-html-to-md/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "html" not in content_type and "text" not in content_type:
            raise ValueError(
                "نوع محتوى غير HTML: %s" % content_type)
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(
            "الصفحة أكبر من سقف %d بايت" % max_bytes)
    charset = "utf-8"
    match = re.search(rb'charset=["\']?([A-Za-z0-9._-]+)',
                      raw[:4096])
    if match:
        charset = match.group(1).decode("ascii", "ignore")
    return raw.decode(charset, "replace")


class _MarkdownConverter(HTMLParser):
    """محوّل HTML ← Markdown: إسقاط القوالب + تحويل الكتل الأساسية."""

    def __init__(self, base_url=None):
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._drop_depth = 0
        self._lines = []
        self._para = []
        self._list_stack = []
        self._link_href = None
        self._link_text = []
        self._inline = []
        self._in_pre = False
        self._blockquote_depth = 0

    # -- أدوات داخلية -------------------------------------------------
    def _flush_para(self):
        raw = "".join(self._para)
        self._para = []
        leading = len(raw) - len(raw.lstrip(" "))
        text = raw.strip()
        if text:
            text = " " * leading + _WS_RE.sub(" ", text)
            if self._blockquote_depth:
                text = "\n".join("> " + line for line in text.splitlines())
            self._lines.append(text)
            self._lines.append("")

    def _flush_inline(self):
        text = "".join(self._inline).strip()
        self._inline = []
        return text

    def _append_text(self, data):
        if self._link_href is not None:
            self._link_text.append(data)
        elif self._in_pre:
            self._para.append(data)
        else:
            self._para.append(_WS_RE.sub(" ", data))

    def _resolve(self, href):
        if not href:
            return ""
        if self._base_url:
            return urllib.parse.urljoin(self._base_url, href)
        return href

    # -- أحداث المحلل --------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in _DROP_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        attrs = dict(attrs)
        if tag in _HEADING_LEVEL:
            self._flush_para()
            level = min(_HEADING_LEVEL[tag], 3)
            self._para.append("\x00H%d\x00" % level)
        elif tag == "p":
            self._flush_para()
        elif tag in ("ul", "ol"):
            self._flush_para()
            self._list_stack.append(tag)
        elif tag == "li":
            self._flush_para()
            depth = max(len(self._list_stack) - 1, 0)
            if self._list_stack and self._list_stack[-1] == "ol":
                marker = "1."
            else:
                marker = "-"
            self._para.append("  " * depth + marker + " ")
        elif tag == "a":
            self._link_href = self._resolve(attrs.get("href", ""))
            self._link_text = []
        elif tag == "strong" or tag == "b":
            self._para.append("**")
        elif tag == "em" or tag == "i":
            self._para.append("*")
        elif tag == "code":
            self._para.append("`")
        elif tag == "pre":
            self._flush_para()
            self._in_pre = True
            self._para.append("```\n")
        elif tag == "blockquote":
            self._flush_para()
            self._blockquote_depth += 1
        elif tag == "br":
            self._para.append("\n")
        elif tag == "hr":
            self._flush_para()
            self._lines.append("---")
            self._lines.append("")
        elif tag == "img":
            alt = (attrs.get("alt") or "").strip()
            src = self._resolve(attrs.get("src", ""))
            if alt or src:
                self._para.append("![%s](%s)" % (alt, src))
        elif tag in _BLOCK_TAGS:
            self._flush_para()

    def handle_endtag(self, tag):
        if tag in _DROP_TAGS:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth:
            return
        if tag in _HEADING_LEVEL:
            text = self._flush_inline()
            para = "".join(self._para)
            level = 0
            marker = re.search(r"\x00H(\d)\x00", para)
            if marker:
                level = int(marker.group(1))
                para = para.replace(marker.group(0), "")
            text = (para + text).strip()
            self._para = []
            if text:
                text = _WS_RE.sub(" ", text)
                self._lines.append("#" * level + " " + text)
                self._lines.append("")
        elif tag == "p":
            self._flush_para()
        elif tag in ("ul", "ol"):
            self._flush_para()
            if self._list_stack:
                self._list_stack.pop()
        elif tag == "li":
            self._flush_para()
        elif tag == "a":
            text = "".join(self._link_text).strip()
            href = self._link_href
            self._link_href = None
            self._link_text = []
            if text and href:
                self._para.append("[%s](%s)" % (text, href))
            elif text:
                self._para.append(text)
        elif tag == "strong" or tag == "b":
            self._para.append("**")
        elif tag == "em" or tag == "i":
            self._para.append("*")
        elif tag == "code":
            self._para.append("`")
        elif tag == "pre":
            self._in_pre = False
            text = "".join(self._para)
            self._para = []
            self._lines.append(text.rstrip("\n") + "\n```")
            self._lines.append("")
        elif tag == "blockquote":
            self._flush_para()
            if self._blockquote_depth:
                self._blockquote_depth -= 1

    def handle_data(self, data):
        if self._drop_depth:
            return
        if not data.strip() and not self._in_pre:
            return
        self._append_text(data)

    def handle_comment(self, data):
        return

    def result(self):
        self._flush_para()
        text = "\n".join(self._lines)
        # طيّ أكثر من سطرين فارغين متتاليين إلى سطرين.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return _html.unescape(text).strip() + "\n" if text.strip() else ""


def html_to_markdown(html, base_url=None, max_chars=DEFAULT_MAX_CHARS):
    """يحوّل HTML إلى Markdown نظيف.

    يسقط ``script``/``style``/``nav``/``header``/``footer`` مع محتواها،
    ويحوّل ``h1``–``h3`` و``p`` و``a`` و``ul/li`` (و``ol``) إلى
    Markdown. إن تجاوز الناتج ``max_chars`` يُقطع مع علامة صريحة.
    """
    if not isinstance(html, str):
        raise TypeError("html يجب أن يكون str")
    if max_chars is not None and max_chars <= 0:
        raise ValueError("max_chars يجب أن يكون موجبًا")
    converter = _MarkdownConverter(base_url=base_url)
    converter.feed(html)
    converter.close()
    text = converter.result()
    if max_chars is not None and len(text) > max_chars:
        cut = text[:max_chars].rstrip()
        text = cut + "\n\n<!-- مُقتطع: تجاوز سقف %d حرفًا -->\n" % max_chars
    return text
