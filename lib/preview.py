#!/usr/bin/env python3
"""معاينة فيديو — صفحة HTML صغيرة قبل النشر (`studio.py preview`).

صفحة مستقلة واحدة (الصور base64 داخلها، بلا أي شبكة): إطارات
عند 25/50/75% من المدة + ملخص مستوى الصوت + أرقام فحص الجودة
من check_lib + نص الكابشن + نص أول تعليق. تُحفظ بجانب الفيديو
افتراضيًا (<اسم>-preview.html) أو في out_dir إن أُعطي.
كل النصوص الحرة تُهرَّب (escape) فلا يحقن كابشن وسوم HTML.
"""
import base64
import html as html_lib
import os
import tempfile

from lib import check as check_lib

FRAME_FRACTIONS = (0.25, 0.50, 0.75)


def _frame_data_uri(video, seconds, tmpdir):
    path = os.path.join(tmpdir, "frame-%.1f.png" % seconds)
    check_lib.extract_frame(video, seconds, path)
    with open(path, "rb") as f:
        return ("data:image/png;base64,"
                + base64.b64encode(f.read()).decode("ascii"))


def _esc(text):
    return html_lib.escape(text or "", quote=True)


def render_html(video, result, frames, audio, caption, first_comment,
                title):
    """صفحة HTML كاملة من بيانات المعاينة (نص فقط — بلا ملفات)."""
    verdict = ("سليم — جاهز للنشر" if result["passed"]
               else "فيه ملاحظات — راجع الفحوصات قبل النشر")
    mean, maxv = audio
    audio_line = ("متوسط %.1f ديسيبل — أقصى %.1f ديسيبل"
                  % (mean, maxv)) if mean is not None else "بلا صوت مقروء"
    rows = "\n".join(
        '<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
        % ("PASS" if c["ok"] else "FAIL", _esc(c["name"]),
           _esc(c["detail"]))
        for c in result["checks"])
    imgs = "\n".join(
        '<figure><img src="%s" alt="إطار %d%%">'
        '<figcaption>%d%% — %.1f ثانية</figcaption></figure>'
        % (uri, int(frac * 100), int(frac * 100), seconds)
        for frac, seconds, uri in frames)
    caption_block = (_esc(caption) if caption
                     else "لم يُحدد كابشن بعد")
    comment_block = (_esc(first_comment) if first_comment
                     else "لم يُحدد أول تعليق بعد — يُكتب قبل النشر")
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>معاينة — %s</title>
<style>body{font-family:sans-serif;max-width:720px;margin:24px auto;
padding:0 16px;color:#222}h1{font-size:20px}h2{font-size:16px;
margin-top:28px;border-bottom:2px solid #d4af37;padding-bottom:4px}
table{border-collapse:collapse;width:100%%}
td,th{border:1px solid #ccc;padding:6px 8px;text-align:right}
figure{display:inline-block;width:30%%;margin:0 1%%;vertical-align:top}
img{width:100%%;border:1px solid #ccc}
figcaption{font-size:13px;color:#555;text-align:center}
pre{white-space:pre-wrap;background:#f6f6f6;padding:12px;
border:1px solid #ddd;border-radius:6px}
.verdict{font-weight:bold}</style></head><body>
<h1>معاينة — %s</h1>
<p>الملف: %s</p>
<p>المدة %.1f ثانية — %dx%d</p>
<p>الصوت: %s</p>
<p class="verdict">الخلاصة: %s</p>
<h2>فحص الجودة</h2>
<table><tr><th>النتيجة</th><th>الفحص</th><th>التفاصيل</th></tr>
%s</table>
<h2>إطارات من الفيديو</h2>
%s
<h2>الكابشن</h2>
<pre>%s</pre>
<h2>أول تعليق</h2>
<pre>%s</pre>
</body></html>""" % (_esc(title), _esc(title), _esc(video),
                     result["duration"], result["width"],
                     result["height"], audio_line, verdict, rows, imgs,
                     caption_block, comment_block)


def build_preview(video, caption=None, first_comment=None, out_dir=None,
                  title=None):
    """ابنِ صفحة معاينة HTML لفيديو. يرجع (مسار الصفحة، تقرير الفحص).

    يرفع CheckError إن لم يكن الملف فيديو صالحًا.
    """
    video = os.path.abspath(os.path.expanduser(video))
    result = check_lib.run_checks(video)
    audio = check_lib.audio_levels(video)
    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for frac in FRAME_FRACTIONS:
            seconds = round(result["duration"] * frac, 1)
            try:
                uri = _frame_data_uri(video, seconds, tmpdir)
                frames.append((frac, seconds, uri))
            except check_lib.CheckError:
                continue
    name = title or os.path.splitext(os.path.basename(video))[0]
    html_text = render_html(video, result, frames, audio, caption,
                            first_comment, name)
    out = os.path.join(out_dir or os.path.dirname(video),
                       "%s-preview.html" % name)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_text)
    return out, result
