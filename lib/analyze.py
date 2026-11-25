#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
r"""تحليل الأداء — `studio.py analyze`: آخر فيديو منشور بالأرقام الحقيقية.

مصدران عامّان فقط، بلا Analytics API وبلا مفاتيح جديدة:
- فيسبوك: `facebook-cli pages posts list` — آخر منشور فيديو على
  الصفحة (views/engagements/reactions/shares/comment_count).
- يوتيوب: `yt-dlp` على قائمة رفع القناة — آخر فيديو (views/likes/
  comments).

قاعدة صارمة: لا يُخترع أي رقم. المقياس الذي لا يصل يُطبع «غير
معروف». وأرقام فيسبوك تصل كـ rendered_text (value ‏null في
المخرجات) — تُقبل كعدد فقط إن كانت أرقامًا صحيحة صريحة
(`^\d+$`)، وإلا تُعامل كمجهولة (مثل «1.2K» المختصرة — لا تُحسب
منها نسب أبدًا).

الاقتراحات (2–3) مشتقة من الأرقام نفسها، لا من قوالب عامة:
نسبة إعجاب منخفضة → هوك أقوى؛ صفر تعليقات → سؤال معضلة؛
صفر مشاركات → مشاركة في مجموعة؛ فجوة مشاهدات بين المنصتين → تُذكر.
"""
import json
import re
import subprocess

FB_BIN_CANDIDATES = ("facebook-cli", "/opt/hatch/bin/facebook-cli")
INT_RE = re.compile(r"^\d+$")


class AnalyzeError(Exception):
    """خطأ في تحليل الأداء (رسالته عربية)."""


def _parse_int_display(text):
    """حوّل نصًا معروضًا إلى عدد صحيح، أو None إن لم يكن صريحًا."""
    if text is None:
        return None
    text = str(text).strip().replace(",", "")
    if INT_RE.match(text):
        return int(text)
    return None


def _fb_entry_metrics(entry):
    """استخرج أرقام منشور فيسبوك واحد من مخرجات facebook-cli."""
    out = {"object_id": entry.get("object_id"),
           "published_time": entry.get("published_time"),
           "caption": ((entry.get("metadata") or {}).get("caption_excerpt")
                       or ""),
           "is_video": "Video" in ((entry.get("metadata") or {})
                                    .get("metadata_text") or ""),
           "views": None, "engagements": None, "reactions": None,
           "shares": None, "comments": None}
    for m in entry.get("metrics") or []:
        value = _parse_int_display(m.get("rendered_text"))
        if value is None and m.get("value") is not None:
            try:
                value = int(m["value"])
            except (TypeError, ValueError):
                value = None
        if m.get("field") == "views":
            out["views"] = value
        elif m.get("field") == "engagements":
            out["engagements"] = value
    for a in entry.get("activity") or []:
        value = _parse_int_display(a.get("rendered_text"))
        if value is None and a.get("value") is not None:
            try:
                value = int(a["value"])
            except (TypeError, ValueError):
                value = None
        if a.get("field") == "reactions":
            out["reactions"] = value
        elif a.get("field") == "shares":
            out["shares"] = value
        elif a.get("field") == "comment_count":
            out["comments"] = value
    return out


def fb_last_video(facebook_bin, page_id, run=None, raw_sink=None):
    """آخر منشور فيديو على الصفحة مع أرقامه، أو (None, السبب).

    run: دالة تشغيل قابلة للحقن في الاختبارات (افتراضيًا
    subprocess.run). تعيد (entry, None) أو (None, reason).
    raw_sink: قاموس اختياري تُحفظ فيه الاستجابة الخام حرفيًا
    (لقطة insights — جولة v0.1.37) تحت مفتاح "facebook".
    """
    runner = run or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, **kw))
    try:
        proc = runner([facebook_bin, "pages", "posts", "list",
                       "--page-id", str(page_id), "--limit", "5"])
    except FileNotFoundError:
        return None, "facebook-cli غير متاح"
    except subprocess.TimeoutExpired:
        return None, "انتهت مهلة قراءة منشورات فيسبوك"
    if proc.returncode != 0:
        return None, ("فشل قراءة منشورات فيسبوك (رمز الخروج %d): %s"
                      % (proc.returncode,
                         (proc.stderr or proc.stdout or "")[-300:]))
    try:
        data = json.loads(proc.stdout or "")
    except ValueError:
        return None, "مخرجات facebook-cli ليست JSON صالحًا"
    if raw_sink is not None:
        raw_sink["facebook"] = data
    results = data.get("results") or []
    videos = [_fb_entry_metrics(r) for r in results if _fb_entry_metrics(r)["is_video"]]
    if videos:
        return videos[0], None
    if results:
        latest = _fb_entry_metrics(results[0])
        return latest, "آخر منشور ليس فيديو — يُعرض بدلًا منه (%s)" % (
            latest["caption"][:40] or latest["object_id"])
    return None, "لا توجد منشورات على الصفحة في آخر 28 يومًا"


def _run_ytdlp(args, run=None):
    runner = run or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=180, **kw))
    proc = runner(["yt-dlp"] + args)
    if proc.returncode != 0:
        raise AnalyzeError("فشل yt-dlp (رمز الخروج %d): %s"
                           % (proc.returncode,
                              (proc.stderr or proc.stdout or "")[-300:]))
    try:
        return json.loads(proc.stdout or "")
    except ValueError:
        raise AnalyzeError("مخرجات yt-dlp ليست JSON صالحًا")


def _yt_video_metrics(video_id, info):
    """أرقام فيديو يوتيوب من مخرجات yt-dlp الخام (قابلة لإعادة
    الاشتقاق من لقطة insights)."""
    return {"video_id": video_id,
            "title": info.get("title") or "",
            "upload_date": info.get("upload_date"),
            "duration": info.get("duration"),
            "views": info.get("view_count"),
            "likes": info.get("like_count"),
            "comments": info.get("comment_count")}


def yt_latest_video(channel_id, run=None, raw_sink=None):
    """آخر فيديو على قناة يوتيوب مع أرقامه العامة، أو (None, السبب).

    raw_sink: قاموس اختياري تُحفظ فيه الاستجابتان الخام حرفيًا
    (لقطة insights — جولة v0.1.37) تحت مفتاح "youtube"
    {playlist, info}.
    """
    if not channel_id:
        return None, "معرّف قناة يوتيوب غير مضبوط (publish.youtube_channel_id)"
    # إصلاح اختبار اختراق 2026-11-21: المعرف كان يُدرج خامًا في
    # سلسلة استعلام URL فيحقن معامل list ثانٍ (&list=...).
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{10,}", channel_id):
        return None, "معرّف قناة يوتيوب غير صالح: %s" % channel_id
    # قائمة الرفوعات: "UU" + معرّف القناة بلا بادئة "UC".
    uploads = "UU" + channel_id[2:]
    import urllib.parse
    playlist_url = ("https://www.youtube.com/playlist?"
                    + urllib.parse.urlencode({"list": uploads}))
    try:
        playlist = _run_ytdlp(
            ["--flat-playlist", "-J", playlist_url],
            run=run)
    except (AnalyzeError, FileNotFoundError) as e:
        return None, "تعذرت قراءة قائمة رفع يوتيوب: %s" % e
    except subprocess.TimeoutExpired:
        return None, "انتهت مهلة قراءة قائمة رفع يوتيوب"
    if raw_sink is not None:
        raw_sink["youtube"] = {"playlist": playlist, "info": None}
    entries = playlist.get("entries") or []
    if not entries:
        return None, "قناة يوتيوب بلا فيديوهات"
    video_id = entries[0].get("id")
    if not video_id or not re.fullmatch(r"[A-Za-z0-9_-]{5,}",
                                        str(video_id)):
        return None, "تعذر تحديد آخر فيديو على يوتيوب"
    watch_url = ("https://www.youtube.com/watch?"
                 + urllib.parse.urlencode({"v": video_id}))
    try:
        info = _run_ytdlp(["-J", watch_url], run=run)
    except (AnalyzeError, FileNotFoundError) as e:
        return None, "تعذرت قراءة بيانات الفيديو %s: %s" % (video_id, e)
    except subprocess.TimeoutExpired:
        return None, "انتهت مهلة قراءة بيانات الفيديو"
    if raw_sink is not None:
        raw_sink["youtube"]["info"] = info
    return _yt_video_metrics(video_id, info), None


def _like_rate(likes, views):
    if likes is None or views is None or views <= 0:
        return None
    return likes / views


class Suggestions(list):
    """قائمة اقتراحات تحمل حقل «أقرب فيديو سابق».

    قائمة عادية (كل كود قديم يعمل عليها كما هو) + سمة
    nearest_video: قاموس {hook, title, views, hook_score,
    similarity} أو None عند غياب الفهرس — فيُحذف الحقل
    بصمت (fail-open) بلا تغيير في باقي المخرجات.
    """

    def __init__(self, tips, nearest_video=None):
        super().__init__(tips)
        self.nearest_video = nearest_video


def _nearest_video_for_suggest(fb, yt, index, embed_fn):
    """أقرب فيديو سابق لآخر فيديو (عنوان يوتيوب أو كابشن
    فيسبوك) — أو None. غلاف fail-open: أي فشل يرجع None."""
    query = None
    if yt and (yt.get("title") or "").strip():
        query = yt["title"].strip()
    elif fb and (fb.get("caption") or "").strip():
        query = fb["caption"].strip()
    if not query:
        return None
    try:
        from lib import story_index as story_index_lib
    except Exception:
        return None
    return story_index_lib.nearest_video_for(
        query, index=index, embed_fn=embed_fn)


def suggest(fb, yt, index=None, embed_fn=None):
    """اقتراحات تحسين (2–3) مشتقة من الأرقام — بلا قوالب عامة.

    fb/yt: قاموسا الأرقام أو None (المصدر غير معروف).
    index/embed_fn (اختياريان — جولة v0.1.48): فهرس فيديوهات
    سابقة (كائن StoryIndex أو مسار) + دالة تضمين — التفعيل
    صريح، وبلا تمرير لا بحث ولا تكلفة؛ عند توفّر أقرب فيديو
    سابق يُلحق سطر «أقرب فيديو سابق: …» بالاقتراحات ويظهر في
    سمة nearest_video — وعند غيابه يُحذف الحقل بصمت بلا
    تغيير في باقي الاقتراحات (fail-open).
    """
    if fb is None and yt is None:
        return Suggestions(["لا أرقام متاحة من فيسبوك أو يوتيوب — تعذّرت قراءة "
                "المنصتين، فلا اقتراحات مبنية على أرقام."])
    tips = []
    fb_views = (fb or {}).get("views") if fb else None
    fb_comments = (fb or {}).get("comments") if fb else None
    fb_shares = (fb or {}).get("shares") if fb else None
    fb_likes = (fb or {}).get("reactions") if fb else None
    yt_views = (yt or {}).get("views") if yt else None
    yt_likes = (yt or {}).get("likes") if yt else None
    yt_comments = (yt or {}).get("comments") if yt else None

    fb_rate = _like_rate(fb_likes, fb_views)
    yt_rate = _like_rate(yt_likes, yt_views)
    rates = [r for r in (fb_rate, yt_rate) if r is not None]
    if rates and min(rates) < 0.02:
        tips.append("نسبة الإعجاب منخفضة (أقل من 2%%) — قوِّ الهوك في "
                    "أول ثانيتين من الفيديو التالي، واجعل العبرة في "
                    "أول تعليق.")
    if fb_comments == 0 and yt_comments == 0:
        tips.append("صفر تعليقات على المنصتين — ضع سؤال معضلة شخصيًا "
                    "في أول تعليق مثبّت على فيسبوك وفي وصف يوتيوب، "
                    "واطلب رأي المشاهد لا «اكتب الجزء الثاني».")
    elif fb_comments == 0 or yt_comments == 0:
        where = "فيسبوك" if fb_comments == 0 else "يوتيوب"
        tips.append("صفر تعليقات على %s — سؤال المعضلة في أول تعليق "
                    "مثبّت يفتح التعليقات هناك." % where)
    if fb_shares == 0:
        tips.append("صفر مشاركات على فيسبوك — شارك الريل الأصلي في "
                    "مجموعة قصص واحدة (بحد 2–3 مجموعات في اليوم).")
    if (fb_views is not None and yt_views is not None
            and yt_views > 0 and fb_views < yt_views // 2):
        tips.append("مشاهدات فيسبوك (%d) أقل من نصف يوتيوب (%d) — "
                    "راجع توقيت النشر (9 صباحًا / 7 مساءً) ودعوة "
                    "المتفاعلين من Business Suite."
                    % (fb_views, yt_views))
    if fb_views is not None and fb_views < 100:
        tips.append("مشاهدات فيسبوك أقل من 100 — المشكلة توزيع قبل "
                    "المحتوى: ادعُ المتفاعلين يوميًا وثبّت الريل "
                    "أعلى الصفحة.")
    if not tips:
        tips.append("الأرقام جيدة — واصل نفس الصيغة (هوك صادم، عبرة "
                    "في أول تعليق، وسؤال محيّر في الختام).")
    tips = tips[:3]
    nearest = _nearest_video_for_suggest(fb, yt, index, embed_fn)
    if nearest:
        views = nearest.get("views")
        views_txt = ("%s مشاهدة" % views) if views is not None \
            else "مشاهدات غير معروفة"
        hook_score = nearest.get("hook_score")
        score_txt = (" — درجة الهوك %s" % hook_score) \
            if hook_score is not None else ""
        tips.append("أقرب فيديو سابق: «%s» (%s — %s، تشابه %.2f%s)"
                    % (nearest.get("hook") or nearest.get("title") or "؟",
                       nearest.get("title") or "بلا عنوان",
                       views_txt, nearest.get("similarity") or 0.0,
                       score_txt))
    return Suggestions(tips, nearest_video=nearest)


def format_value(value):
    """اطبع رقمًا أو «غير معروف» — بلا اختراع أرقام."""
    return str(value) if value is not None else "غير معروف"
