#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""النسخة الطويلة اليومية لـ TikTok — دمج فيديوهين منتَجين أصلًا.

خطة الـ30 يومًا (PLAN-AR.md §1، الخيار ج): شورتات القصص 40–60
ثانية لا تفي بشرط Creator Rewards (فيديوهات لا تقل عن دقيقة)،
ويوتيوب Shorts لا يقبل أكثر من 60 ثانية — فالحل دمج فيديوهين
منتَجين أصلًا في فيديو TikTok واحد 65–110 ثوانٍ: «القصة كاملة»
(جزآ قصة واحدة) أو «قصتان مؤثرتان» (قصتان منفردتان). صفر وحدات
Veo — دمج ffmpeg فقط، بلا مشاهد جديدة وبلا أي نشر من هنا.

القواعد المطبقة:
- كل مدخل: ملف mp4 عمودي 720×1280، مدته 40–60 ثانية، بصوت —
  نفس مواصفات الشورت المنشور على فيسبوك/يوتيوب.
- الدمج بمرشح concat مع إعادة ترميز (libx264 + aac) لتطبيع
  معدل الإطارات (30) ومعدل عيّنة الصوت (48k) — لأن المدخلين قد
  يختلفان (Veo 30 إطارًا مقابل OpenMontage 24 إطارًا) ونسخ
  التدفق (stream copy) يفشل أو يفسد المزامنة عند الاختلاف.
- الناتج: عمودي 720×1280، مدته 65–110 ثوانٍ (هامش أمان فوق
  الدقيقة)، بصوت، ويُفحص عبر ffprobe قبل التسليم.
- الكابشن والحزمة: يُعاد استخدام `tiktok_publish` (الوسوم
  الأربعة + فحص `caption_check`) — بلا تكرار لمنطقه.
- بلا شبكة إطلاقًا: دمج محلي + كتابة حزمة فقط.
"""
import json
import os
import subprocess

from lib import check as check_lib
from lib import tiktok_publish as tiktok_lib

LONG_MIN_SECONDS = 65.0
LONG_MAX_SECONDS = 110.0
SHORT_MIN_SECONDS = 40.0
SHORT_MAX_SECONDS = 60.0
LONG_WIDTH = 720
LONG_HEIGHT = 1280
LONG_FPS = 30
LONG_AUDIO_RATE = 48000
LONG_VIDEO_BITRATE = "2500k"
LONG_AUDIO_BITRATE = "128k"
LONG_CRF = 20
# تسامح فرق مدة الناتج عن مجموع المدخلين (إطار أو إطاران +
# تهيئة الصوت عند إعادة الترميز).
DURATION_TOLERANCE = 2.0


class TikTokLongError(Exception):
    """خطأ في بناء النسخة الطويلة لـ TikTok (رسالته عربية)."""


def probe_short(path, min_seconds=SHORT_MIN_SECONDS,
                max_seconds=SHORT_MAX_SECONDS):
    """افحص مدخلًا قصيرًا: موجود، mp4، عمودي 720×1280،
    مدته min_seconds–max_seconds (افتراضيًا 40–60 ثانية)،
    بصوت. يرجع معلومات probe من `check.probe`
    مع مسار الفيديو. يرفع TikTokLongError برسالة عربية عند أي نقص.
    """
    if not os.path.isfile(path):
        raise TikTokLongError("ملف الفيديو غير موجود: %s" % path)
    if not path.lower().endswith(".mp4"):
        raise TikTokLongError(
            "النسخة الطويلة تقبل mp4 فقط: %s" % path)
    try:
        info = check_lib.probe(path)
    except check_lib.CheckError as e:
        raise TikTokLongError(str(e))
    width, height = info.get("width") or 0, info.get("height") or 0
    if width and height:
        ratio = width / height
        if abs(ratio - 9.0 / 16.0) > 0.02:
            raise TikTokLongError(
                "أبعاد الفيديو ليست عمودية 9:16 (%d×%d): %s"
                % (width, height, path))
    elif width != LONG_WIDTH or height != LONG_HEIGHT:
        raise TikTokLongError(
            "أبعاد الفيديو غير مقروءة في: %s" % path)
    duration = info.get("duration") or 0
    if duration < min_seconds or duration > max_seconds:
        raise TikTokLongError(
            "مدة الفيديو (%.1f ثانية) خارج نطاق الشورت %.0f–%.0f ثانية: %s"
            % (duration, min_seconds, max_seconds, path))
    if info.get("has_audio") is False:
        raise TikTokLongError(
            "الفيديو بلا مسار صوتي — النسخة الطويلة تحتاج سردًا مسموعًا: %s"
            % path)
    return {"video": os.path.abspath(path),
            "duration": duration, "width": width, "height": height,
            "has_audio": info.get("has_audio"),
            "size": os.path.getsize(path)}


def _ffmpeg_filter():
    """مرشح الدمج: تطبيع كل مدخل (30 إطارًا، 720×1280، صوت
    48k ستيريو) ثم concat بلا أي انتقالات — قصّ مباشر."""
    video = ("[0:v]fps=%d,scale=%d:%d:force_original_aspect_ratio=decrease,"
             "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,"
             "format=yuv420p[v0];"
             "[1:v]fps=%d,scale=%d:%d:force_original_aspect_ratio=decrease,"
             "pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1,"
             "format=yuv420p[v1];"
             % (LONG_FPS, LONG_WIDTH, LONG_HEIGHT,
                LONG_WIDTH, LONG_HEIGHT,
                LONG_FPS, LONG_WIDTH, LONG_HEIGHT,
                LONG_WIDTH, LONG_HEIGHT))
    audio = ("[0:a]aresample=%d,aformat=channel_layouts=stereo[a0];"
             "[1:a]aresample=%d,aformat=channel_layouts=stereo[a1];"
             % (LONG_AUDIO_RATE, LONG_AUDIO_RATE))
    join = "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    return video + audio + join


def merge_long_version(video_a, video_b, out_path, ffmpeg="ffmpeg",
                       min_seconds=LONG_MIN_SECONDS,
                       max_seconds=LONG_MAX_SECONDS, timeout=900,
                       short_min_seconds=SHORT_MIN_SECONDS,
                       short_max_seconds=SHORT_MAX_SECONDS):
    """ادمج فيديوهين قصيرين في نسخة طويلة واحدة.

    يفحص المدخلين أولًا (`probe_short`)، ثم يرفض المجموع
    الخارج عن [min_seconds, max_seconds] قبل أي ترميز، ثم
    يدمج بمرشح concat مع إعادة ترميز، ثم يفحص الناتج عبر
    ffprobe (المدة ≈ مجموع المدخلين، الأبعاد 720×1280،
    صوت موجود). يرجع معلومات الناتج. يرفع TikTokLongError
    برسالة عربية عند أي فشل — بلا ملف ناتج ناقص.
    """
    info_a = probe_short(video_a, short_min_seconds, short_max_seconds)
    info_b = probe_short(video_b, short_min_seconds, short_max_seconds)
    total = info_a["duration"] + info_b["duration"]
    if total < min_seconds or total > max_seconds:
        raise TikTokLongError(
            "مجموع المدتين (%.1f ثانية) خارج نطاق النسخة الطويلة "
            "%.0f–%.0f ثانية — اختر زوجًا آخر"
            % (total, min_seconds, max_seconds))
    out_path = os.path.abspath(out_path)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", info_a["video"], "-i", info_b["video"],
           "-filter_complex", _ffmpeg_filter(),
           "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "veryfast",
           "-crf", str(LONG_CRF), "-pix_fmt", "yuv420p",
           "-r", str(LONG_FPS),
           "-c:a", "aac", "-b:a", LONG_AUDIO_BITRATE,
           "-movflags", "+faststart", out_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise TikTokLongError("الأمر غير موجود: %s" % ffmpeg)
    except subprocess.TimeoutExpired:
        raise TikTokLongError(
            "انتهت المهلة أثناء دمج الفيديوهين (أكثر من %d ثانية)"
            % timeout)
    if proc.returncode != 0:
        raw = (proc.stderr or "").strip()
        tail = raw[-400:] if raw else "بلا تفاصيل"
        raise TikTokLongError(
            "فشل دمج الفيديوهين عبر ffmpeg: %s" % tail)
    try:
        out_info = check_lib.probe(out_path)
    except check_lib.CheckError as e:
        raise TikTokLongError(
            "الناتج غير صالح بعد الدمج: %s" % e)
    if abs(out_info["duration"] - total) > DURATION_TOLERANCE:
        raise TikTokLongError(
            "مدة الناتج (%.1f ثانية) لا تطابق مجموع المدخلين "
            "(%.1f ثانية): %s"
            % (out_info["duration"], total, out_path))
    if out_info.get("width") != LONG_WIDTH or \
            out_info.get("height") != LONG_HEIGHT:
        raise TikTokLongError(
            "أبعاد الناتج ليست 720×1280 (%s×%s): %s"
            % (out_info.get("width"), out_info.get("height"), out_path))
    if out_info.get("has_audio") is False:
        raise TikTokLongError(
            "الناتج بلا مسار صوتي: %s" % out_path)
    return {"video": out_path, "duration": out_info["duration"],
            "width": out_info["width"], "height": out_info["height"],
            "has_audio": out_info["has_audio"],
            "size": os.path.getsize(out_path),
            "sources": [info_a, info_b]}


def long_title(story_title, kind="full"):
    """عنوان النسخة الطويلة: «القصة كاملة: <القصة>» لجزأي قصة
    واحدة، أو «قصتان مؤثرتان» لقصتين منفردتين (حينها story_title
    هو وصف الزوج، مثل «عناد الأم + غيرة الضرة»)."""
    kind = (kind or "full").strip().lower()
    if kind not in ("full", "two"):
        raise TikTokLongError(
            "نوع النسخة الطويلة غير معروف: %s (المسموح: full أو two)"
            % kind)
    if kind == "two":
        return "قصتان مؤثرتان"
    title = (story_title or "").strip()
    if not title:
        raise TikTokLongError(
            "النسخة الطويلة «القصة كاملة» تحتاج عنوان القصة")
    return "القصة كاملة: %s" % title


def normalize_part_tags(part_tags):
    """طبّع وسوم الأجزاء: تقبل سلسلة مفصولة بمسافات أو قائمة،
    وتعيد قائمة وسوم تبدأ كل منها بـ # بلا تكرار وبلا فراغات."""
    if not part_tags:
        return []
    if isinstance(part_tags, str):
        raw = part_tags.split()
    else:
        raw = list(part_tags)
    tags = []
    for item in raw:
        tag = str(item).strip()
        if not tag:
            continue
        if not tag.startswith("#"):
            tag = "#" + tag
        if tag not in tags:
            tags.append(tag)
    return tags


def _caption_with_part_tags(caption, part_tags):
    """ألحق وسوم الأجزاء سطرًا مستقلًا في نص القصة (قبل العبرة
    والوسوم الأربعة التي يضيفها `build_tiktok_caption` أخيرًا)."""
    tags = normalize_part_tags(part_tags)
    text = (caption or "").strip()
    if tags:
        text = (text + "\n" + " ".join(tags)) if text else " ".join(tags)
    return text


def build_long_caption(title, caption, moral="", kind="full",
                       part_tags=None):
    """ابنِ كابشن النسخة الطويلة — مفوَّض كاملًا إلى
    `tiktok_publish.build_tiktok_caption` (الوسوم الأربعة
    #قصص #قصص_حقيقية #قصص_واقعية #قصة_وعبرة + فحص
    `caption_check`)، وعنوانه من `long_title`.

    وسوم الأجزاء (مثل #الجزء_الأول #الجزء_الثاني) تُلحق سطرًا
    مستقلًا في نص القصة قبل العبرة، فتبقى الوسوم الأربعة
    هي السطر الأخير دائمًا.
    """
    return tiktok_lib.build_tiktok_caption(
        long_title(title, kind),
        _caption_with_part_tags(caption, part_tags), moral=moral)


def write_long_bundle(bundle_dir, video_a, video_b, title, caption,
                      moral="", kind="full", out_name="long.mp4",
                      ffmpeg="ffmpeg", part_tags=None,
                      min_seconds=LONG_MIN_SECONDS,
                      max_seconds=LONG_MAX_SECONDS, timeout=900):
    """ابنِ حزمة النسخة الطويلة كاملة: ادمج الفيديوهين في
    `<bundle_dir>/<out_name>`، ثم اكتب حزمة رفع TikTok
    (metadata.json + caption.txt + steps.txt) عبر
    `tiktok_publish.write_tiktok_bundle`، ثم اكتب `long.json`
    بتفاصيل الدمج (النوع والمصدرين والمدد).

    لا ينسخ الفيديوين الأصليين ولا يمسّ الطابور ولا أي ملف
    خارج مجلد الحزمة. يرجع قاموسًا فيه {bundle_dir, caption,
    metadata_path, steps_path, long_path, video_info, sources}.
    """
    bundle_dir = os.path.abspath(bundle_dir)
    os.makedirs(bundle_dir, exist_ok=True)
    merged_path = os.path.join(bundle_dir, out_name)
    merged = merge_long_version(video_a, video_b, merged_path,
                                ffmpeg=ffmpeg, min_seconds=min_seconds,
                                max_seconds=max_seconds, timeout=timeout)
    display_title = long_title(title, kind)
    result = tiktok_lib.write_tiktok_bundle(
        bundle_dir, merged_path, display_title,
        _caption_with_part_tags(caption or "", part_tags),
        moral=moral)
    long_path = os.path.join(bundle_dir, "long.json")
    long_info = {
        "kind": (kind or "full").strip().lower(),
        "title": display_title,
        "part_tags": normalize_part_tags(part_tags),
        "video": merged["video"],
        "duration": merged["duration"],
        "width": merged["width"],
        "height": merged["height"],
        "sources": [
            {"video": s["video"], "duration": s["duration"]}
            for s in merged["sources"]],
    }
    with open(long_path, "w", encoding="utf-8") as f:
        json.dump(long_info, f, ensure_ascii=False, indent=2)
    result["long_path"] = long_path
    result["video_info"] = merged
    result["sources"] = merged["sources"]
    return result
