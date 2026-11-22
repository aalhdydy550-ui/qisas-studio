#!/usr/bin/env python3
"""لقطة خام لبيانات الأداء قبل تلخيصها — جولة v0.1.37 (مقترح tinker رقم 11).

قاعدة «حلّل أداء الفيديو السابق قبل الرفع» تعتمد على أرقام قد
تختفي من نافذة الـAPI؛ لقطة خام محفوظة تحفظ الدليل. أمر `analyze`
يحفظ الاستجابتين الخام حرفيًا في `runs/insights-<YYYYMMDD-HHMMSS>.json`
مع `sha256` وطابع زمني (القاهرة) قبل حساب أي ملخص؛ والملخص
(analyze-<وقت>.json) يشير إلى ملف اللقطة.

ملاحظة خصوصية: الاستجابة الخام قد تحوي معرّفات (معرّف الصفحة/
القناة وأرقام المنشورات) — تبقى في `runs/` محليًا فقط، وهي
مستثناة من النشر على GitHub.
"""
import hashlib
import json
import os
import time

from lib import analyze as analyze_lib
from lib import run_record


def canonical_bytes(raw):
    """بايتات JSON القانونية للبصمة (مفاتيح مرتبة، بلا ASCII هارب)."""
    return json.dumps(raw, ensure_ascii=False, sort_keys=True).encode("utf-8")


def snapshot_sha256(raw):
    """بصمة القسم الخام (تُحسب على raw وحده، لا على السجل كله)."""
    return hashlib.sha256(canonical_bytes(raw)).hexdigest()


def save_snapshot(runs_dir, facebook_raw=None, youtube_raw=None):
    """احفظ اللقطة الخام. يرجع المسار الكامل للملف.

    youtube_raw: {"playlist": ..., "info": ...} أو None.
    """
    runs_dir = os.path.abspath(os.path.expanduser(runs_dir))
    os.makedirs(runs_dir, exist_ok=True)
    raw = {"facebook": facebook_raw, "youtube": youtube_raw}
    record = {
        "captured_at": run_record.now_cairo_iso(),
        "sha256": snapshot_sha256(raw),
        "raw": raw,
    }
    name = "insights-%s.json" % time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(runs_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(path):
    """اقرأ لقطة من ملف. يرجع السجل القاموسي."""
    with open(os.path.abspath(os.path.expanduser(path)),
              encoding="utf-8") as f:
        return json.load(f)


def verify_snapshot(record):
    """تحقق من بصمة اللقطة: (سليمة؟، تفصيل عربي)."""
    try:
        raw = record["raw"]
        expected = record["sha256"]
    except (KeyError, TypeError):
        return False, "بنية اللقطة ناقصة (بلا raw أو sha256)"
    if snapshot_sha256(raw) == expected:
        return True, "بصمة اللقطة مطابقة للخام"
    return False, "بصمة اللقطة لا تطابق الخام — الملف عُدّل بعد الحفظ"


def summarize(record):
    """أعد اشتقاق ملخص الأرقام من اللقطة وحدها.

    يرجع {"facebook": fb أو None, "youtube": yt أو None} بنفس
    دوال التحليل الحية — إعادة التحليل من اللقطة تعطي نفس
    الملخص الحي (مثبت باختبار).
    """
    raw = (record or {}).get("raw") or {}
    fb = None
    fb_data = raw.get("facebook") or {}
    results = fb_data.get("results") or []
    if results:
        parsed = [analyze_lib._fb_entry_metrics(r) for r in results]
        videos = [p for p in parsed if p["is_video"]]
        fb = videos[0] if videos else parsed[0]
    yt = None
    yt_data = raw.get("youtube") or {}
    playlist = yt_data.get("playlist") or {}
    info = yt_data.get("info") or {}
    entries = playlist.get("entries") or []
    if entries and entries[0].get("id") and info:
        yt = analyze_lib._yt_video_metrics(entries[0]["id"], info)
    return {"facebook": fb, "youtube": yt}
