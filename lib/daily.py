#!/usr/bin/env python3
"""الأمر اليومي الواحد — `studio.py daily`.

دورة اليوم كاملة في أمر واحد: إنتاج فيديو اليوم من القصة
التالية في الطابور + فحص `check` عليه + مصغرة + نشر
المنصتين + تجهيز نص أول تعليق (العبرة + سؤال المعضلة +
موعد الجزء التالي).

- الافتراضي `--dry-run`: يطبع الخطة والحمولات بلا ريندر
  وبلا نشر وبلا كتابة أي ملف.
- النشر الحقيقي فقط مع `--execute` صريح.
- مسار الصباح Veo مع فحص رصيد ≥120 وحدة (وبديل OpenMontage
  عند النقص)؛ ومسار المساء OpenMontage دائمًا.
- إنتاج Veo نفسه يتم في Google Flow يدويًا (خارج studio) —
  فإن كان مسار الصباح Veo وبلا فيديو جاهز (`--video`)، يطبع
  الأمر خطة الإنتاج في Flow ويتوقف بلا ادعاء إنتاج.
- بطاقات الاقتباس لا تُلحق بأي فيديو أبدًا (القاعدة الدائمة).
- نص أول تعليق يُجهَّز ويُطبع ويُحفظ فقط — نشره يحتاج
  المتصفح (بطاقة موافقة)، فالأمر لا يدّعي نشره.
"""
import json
import os
import re
import time

from lib import publish

VEO_MIN_BALANCE = 120  # حد فحص الرصيد الصباحي (وحدة)

DEFAULT_QUESTION = "لو كنت مكانه، كنت عملت إيه؟"
NEXT_PART_LINE = ("الجزء الثاني بكرة 7 مساءً — اعمل متابعة "
                  "عشان يوصلك أول ما ينزل")
FINAL_PART_LINE = ("عندك قصة حصلتلك؟ ابعتها في رسائل الصفحة "
                   "وهنحكيها باسمك أو بدون اسم.")


class DailyError(Exception):
    """خطأ في الأمر اليومي (رسالته عربية)."""


def story_parts(note):
    """عدد الأجزاء من ملاحظة الطابور: «تحتاج/يحتاج N أجزاء»
    أو «تحتاج جزأين» (صيغة المثنى بالكلمات لا بالأرقام) أو
    «منشور واحد» (1)."""
    note = note or ""
    m = re.search(r"[تي]حتاج\s+(\d+)\s+أجزاء", note)
    if m:
        return max(1, int(m.group(1)))
    if re.search(r"[تي]حتاج\s+جز[أء](ين|ان)", note):
        return 2
    return 1


def decide_path(slot, balance_units):
    """مسار الإنتاج للموعد: الصباح Veo إن كان الرصيد ≥120
    وإلا OpenMontage كبديل؛ والمساء OpenMontage دائمًا.
    يرجع (المسار، السبب)."""
    if slot == "evening":
        return "openmontage", "موعد المساء OpenMontage بلا رصيد دائمًا"
    if balance_units is None:
        return "openmontage", "الرصيد غير مسجَّل — البديل OpenMontage"
    if balance_units >= VEO_MIN_BALANCE:
        return "veo", ("الرصيد %d وحدة (≥%d) — مسار Veo"
                       % (balance_units, VEO_MIN_BALANCE))
    return "openmontage", ("الرصيد %d وحدة (<%d) — بديل OpenMontage"
                           % (balance_units, VEO_MIN_BALANCE))


def build_first_comment(title, moral, question, parts):
    """نص أول تعليق المثبّت: العبرة في جملة + سؤال المعضلة +
    موعد الجزء التالي (أو سطر «ابعت قصتك» للقصة الكاملة)."""
    lines = []
    if moral:
        lines.append("«%s»" % moral.strip())
    lines.append((question or DEFAULT_QUESTION).strip())
    lines.append(NEXT_PART_LINE if parts > 1 else FINAL_PART_LINE)
    return "\n".join(lines)


def plan_daily(cfg, slot, video=None, moral="", question="",
               ready_fn=None):
    """خطط ليوم واحد بلا أي تنفيذ: القصة التالية + المسار +
    الكابشن + نص أول تعليق + الحمولات (إن وُجد فيديو جاهز).
    يرجع قاموس الخطة. يرفع DailyError إن لم توجد قصة انتظار."""
    if slot not in ("morning", "evening"):
        raise DailyError("الموعد غير صالح: %s (المسموح: morning/evening)"
                         % slot)
    queue_path = os.path.expanduser(
        (cfg.get("paths") or {}).get("queue_file") or "")
    stories = []
    if os.path.isfile(queue_path):
        from lib import queue as queue_lib
        with open(queue_path, encoding="utf-8") as f:
            text = f.read()
        stories = queue_lib.parse_waiting_entries(text)
    if not stories:
        raise DailyError("لا توجد قصص في الانتظار في ملف الطابور")
    story = stories[0]
    ready, slug, project, reason = (True, None, None, "")
    if ready_fn is not None:
        ready, slug, project, reason = ready_fn(story)
    parts = story_parts(story.get("note") or "")
    balance = ((cfg.get("veo") or {}).get("balance_units")
               if isinstance(cfg.get("veo"), dict) else None)
    path, path_reason = decide_path(slot, balance)
    title = story["title"]
    caption_text = (moral or "").strip()
    fb_caption = publish.build_caption(title, caption_text)
    yt_desc = publish.build_youtube_description(title, caption_text,
                                                moral=caption_text)
    first_comment = build_first_comment(
        title, caption_text, question, parts)
    videos_dir = os.path.expanduser(
        (cfg.get("paths") or {}).get("videos_dir") or "~/workspace/videos")
    planned_video = None
    if video:
        planned_video = os.path.abspath(os.path.expanduser(video))
    elif slug:
        planned_video = os.path.join(videos_dir, "%s-daily.mp4" % slug)
    plan = {
        "slot": slot,
        "story": {"number": story["number"], "title": title,
                  "note": story.get("note") or "", "parts": parts},
        "ready": ready, "slug": slug, "project": project,
        "reason": reason,
        "path": path, "path_reason": path_reason,
        "balance_units": balance,
        "video": planned_video,
        "video_ready": bool(planned_video
                            and os.path.isfile(planned_video)),
        "title": title,
        "caption": fb_caption,
        "youtube_description": yt_desc,
        "first_comment": first_comment,
        "fb_argv": None,
        "yt_payload": None,
    }
    if planned_video and os.path.isfile(planned_video):
        page_id = ((cfg.get("publish") or {}).get("page_id") or "")
        try:
            plan["fb_argv"] = publish.facebook_argv(
                page_id, planned_video, fb_caption)
        except publish.PublishError as e:
            plan["fb_argv"] = None
            plan["fb_argv_error"] = str(e)
        plan["yt_payload"] = publish.youtube_payload(
            publish.build_youtube_title(title), yt_desc,
            ["قصص وعبر", "قصص واقعية", "قصص مؤثرة", "حكايات"],
            "public")
    return plan


def format_plan(plan):
    """نص عربي للخطة اليومية (وضع تجريبي)."""
    s = plan["story"]
    lines = ["== خطة اليوم — موعد %s =="
             % ("الصباح 09:00" if plan["slot"] == "morning"
                else "المساء 19:00"),
             "القصة: %d. %s%s" % (
                 s["number"], s["title"],
                 (" (%d أجزاء)" % s["parts"]) if s["parts"] > 1 else ""),
             "المسار: %s — %s" % (
                 "Veo (في Google Flow)" if plan["path"] == "veo"
                 else "OpenMontage (بلا رصيد)",
                 plan["path_reason"]),
             "الجاهزية: %s" % (
                 "جاهزة (مشروع %s)" % plan["project"] if plan["ready"]
                 else "غير جاهزة: %s" % plan["reason"]),
             "الفيديو: %s%s" % (
                 plan["video"] or "—",
                 " (جاهز)" if plan["video_ready"] else " (سيُنتَج)"),
             "",
             "-- الكابشن (فيسبوك) --",
             plan["caption"],
             "",
             "-- نص أول تعليق (يُنسخ ويُنشر من المتصفح) --",
             plan["first_comment"],
             ""]
    if plan["fb_argv"]:
        import shlex
        lines.append("-- أمر فيسبوك الدقيق --")
        lines.append(" ".join(shlex.quote(a) for a in plan["fb_argv"]))
        lines.append("")
    if plan["yt_payload"]:
        lines.append("-- حمولة يوتيوب --")
        lines.append(json.dumps(plan["yt_payload"], ensure_ascii=False,
                                indent=2))
        lines.append("")
    if plan["path"] == "veo" and not plan["video_ready"]:
        lines.append("تنبيه: مسار Veo — أنتج المشاهد في Google Flow "
                     "أولًا ثم أعد الأمر مع --video <الملف>.")
    return "\n".join(lines)


def execute_daily(cfg, plan, produce_fn, check_fn, thumbnail_fn,
                  publish_fn, runs_dir):
    """نفّذ الخطة اليومية (بعد --execute الصريح).

    الدوال المحقونة (قابلة للاختبار بلا تنفيذ حقيقي):
      produce_fn(cfg, slug, project, out_path) -> 0/1
      check_fn(video) -> قاموس run_checks (فيه "passed")
      thumbnail_fn(video, hook, out_path) -> مسار المصغرة
      publish_fn(cfg, video, title, caption, thumbnail) -> 0/1
    يرجع (رمز الخروج، قاموس النتائج المحفوظ)."""
    result = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "slot": plan["slot"],
              "story": plan["story"],
              "path": plan["path"],
              "steps": {}}
    video = plan["video"]
    if plan["path"] == "veo" and not plan["video_ready"]:
        print("مسار Veo بلا فيديو جاهز — أنتج المشاهد في Google Flow "
              "أولًا ثم أعد الأمر مع --video <الملف>.")
        result["steps"]["produce"] = {"status": "needs-flow",
                                      "reason": plan["path_reason"]}
        return 1, result
    if not plan["video_ready"]:
        if not plan["ready"]:
            print("القصة غير جاهزة: %s" % plan["reason"])
            result["steps"]["produce"] = {"status": "skipped",
                                          "reason": plan["reason"]}
            return 1, result
        print("1) الإنتاج (%s)…" % plan["path"])
        rc = produce_fn(cfg, plan["slug"], plan["project"], video)
        result["steps"]["produce"] = {"status": "done" if rc == 0
                                      else "failed"}
        if rc != 0:
            print("فشل الإنتاج — توقف اليوم")
            return 1, result
    else:
        result["steps"]["produce"] = {"status": "ready-video",
                                      "video": video}
    print("2) فحص الجودة…")
    check = check_fn(video)
    result["steps"]["check"] = {
        "passed": bool(check.get("passed")),
        "checks": check.get("checks"),
    }
    print("   %s" % ("كل الفحوصات ناجحة"
                     if check.get("passed") else "فشل فحص الجودة"))
    if not check.get("passed"):
        return 1, result
    print("3) الصورة المصغرة…")
    thumb = thumbnail_fn(video, plan["title"],
                         os.path.splitext(video)[0] + "-thumbnail.jpg")
    result["steps"]["thumbnail"] = {"path": thumb}
    print("   %s" % thumb)
    print("4) النشر على المنصتين…")
    rc = publish_fn(cfg, video, plan["title"], plan["caption"], thumb)
    result["steps"]["publish"] = {"status": "done" if rc == 0
                                  else "failed"}
    if rc != 0:
        print("فشل النشر — راجع الخطوات أعلاه")
        return 1, result
    result["steps"]["first_comment"] = {
        "text": plan["first_comment"],
        "note": "يُنسخ ويُنشر من المتصفح (بطاقة موافقة) — "
                "الأمر يجهّز النص فقط",
    }
    print("5) نص أول تعليق (انسخه من المتصفح):")
    print(plan["first_comment"])
    os.makedirs(runs_dir, exist_ok=True)
    out_path = os.path.join(
        runs_dir, "daily-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("سُجّلت نتائج اليوم في: %s" % out_path)
    return 0, result
