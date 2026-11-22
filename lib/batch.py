#!/usr/bin/env python3
"""دفعات جماعية — `studio.py batch` (الجولة 7، v0.1.31).

ينتج القصص التالية من الطابور في تشغيل واحد: لكل قصة جاهزة
(إنتاج + فحص `check` + مصغرة + تسجيل في run-log).

- الوضع التجريبي افتراضي: يطبع الخطة بلا أي تنفيذ وبلا كتابة
  أي ملف. التنفيذ الحقيقي فقط مع `--execute` (نمط `daily`).
- `--source veo|openmontage`: مسار Veo يفحص الرصيد ≥120 أولًا
  ويخضع لسقف الإنفاق (`balance.check_cap` — 120 وحدة متوقعة
  للفيديو: 6 مقاطع × 20)؛ وإن نقص الرصيد يُرفض مسار Veo
  برسالة عربية (البديل الصريح `--source openmontage`).
- إنتاج Veo نفسه في Google Flow يدويًا خارج studio — فقصة Veo
  بلا فيديو جاهز (`<slug>-batch.mp4` في videos_dir) تُسجَّل
  `needs-flow` وتُتخطى، بلا ادعاء إنتاج.
- لا نشر في batch (الإنتاج فقط)؛ والنتائج في
  `runs/batch-<تاريخ>.json` فقط — بلا إلحاق بخلاصة الطابور.
- الجاهزية عبر `ready_fn` محقونة (نفس `check_story_ready` في
  studio.py) — قابلة للاختبار بلا مشاريع حقيقية.
"""
import json
import os
import time

from lib import balance as balance_lib
from lib import queue as queue_lib
from lib import scene_plan as scene_plan_lib

VEO_MIN_BALANCE = 120
VEO_UNITS_PER_VIDEO = 120


class BatchError(Exception):
    """خطأ في الدفعة (رسالته عربية)."""


def plan_batch(cfg, count, source="openmontage", ready_fn=None,
               queue_file=None):
    """خطط لدفعة بلا أي تنفيذ. يرجع قاموس الخطة.

    يرفع BatchError عند: عدد غير صالح، مصدر غير معروف، ملف
    طابور غائب، لا قصص انتظار، أو رصيد Veo أقل من 120 (مع
    --source veo)، أو تجاوز الإنفاق المتوقع السقف.
    """
    if isinstance(count, bool) or not isinstance(count, int) \
            or count < 1:
        raise BatchError("عدد القصص يجب أن يكون 1 أو أكثر (وصل: %s)"
                         % (count,))
    if source not in ("veo", "openmontage"):
        raise BatchError("المصدر غير صالح: %s (المسموح: veo/openmontage)"
                         % source)
    queue_path = os.path.expanduser(
        queue_file or (cfg.get("paths") or {}).get("queue_file") or "")
    if not os.path.isfile(queue_path):
        raise BatchError("ملف الطابور غير موجود: %s" % queue_path)
    with open(queue_path, encoding="utf-8") as f:
        text = f.read()
    entries = queue_lib.parse_waiting_entries(text)
    if not entries:
        raise BatchError("لا توجد قصص في الانتظار في ملف الطابور")
    entries = entries[:count]
    veo_cfg = (cfg.get("veo") or {}) if isinstance(cfg, dict) else {}
    if source == "veo":
        balance = veo_cfg.get("balance_units")
        if balance is None:
            raise BatchError(
                "رصيد Veo غير مسجَّل — حدّث veo.balance_units في "
                "config.yaml أو استخدم --source openmontage")
        try:
            balance = balance_lib._as_int(balance, "الرصيد")
        except ValueError:
            raise BatchError("رصيد Veo غير صالح: %s" % (balance,))
        if balance < VEO_MIN_BALANCE:
            raise BatchError(
                "رصيد Veo %d وحدة (أقل من %d) — مسار Veo مرفوض؛ "
                "استخدم --source openmontage" % (balance, VEO_MIN_BALANCE))
        ok, reason = balance_lib.check_cap(VEO_UNITS_PER_VIDEO, veo_cfg)
        if not ok:
            raise BatchError(reason)
    videos_dir = os.path.expanduser(
        (cfg.get("paths") or {}).get("videos_dir") or "~/workspace/videos")
    stories = []
    for entry in entries:
        ready, slug, project, reason = ((True, None, None, "")
                                         if ready_fn is None
                                         else ready_fn(entry))
        video = None
        video_ready = False
        if slug:
            video = os.path.join(videos_dir, "%s-batch.mp4" % slug)
            video_ready = os.path.isfile(video)
        item = {"number": entry["number"], "title": entry["title"],
                "note": entry.get("note") or "",
                "ready": bool(ready), "slug": slug, "project": project,
                "reason": reason,
                "video": video, "video_ready": video_ready,
                "scene_plan": None}
        if source == "veo" and ready:
            try:
                item["scene_plan"] = scene_plan_lib.build_scene_plan(
                    cfg, entry)
            except scene_plan_lib.CapError as e:
                item["ready"] = False
                item["reason"] = str(e)
                item["scene_plan"] = None
        stories.append(item)
    total_expected = (VEO_UNITS_PER_VIDEO
                      * len([s for s in stories if s["ready"]])
                      if source == "veo" else 0)
    if source == "veo":
        # فحص الرصيد مقابل إجمالي الدفعة لا فيديو واحد: كان
        # الفحص المسبق يقبل أي دفعة برصيد ≥120 ولو كان الإجمالي
        # (مثلًا 3 قصص = 360 وحدة) فوق الرصيد — فتُخطط دفعة
        # لا يمكن توليدها. السقف يبقى لكل فيديو (الفحص المسبق
        # أعلاه)؛ أما الرصيد فيُقاس على الإجمالي.
        balance = veo_cfg.get("balance_units")
        if balance is not None:
            try:
                balance = balance_lib._as_int(balance, "الرصيد")
            except ValueError:
                raise BatchError("رصيد Veo غير صالح: %s" % (balance,))
            if total_expected > balance:
                raise BatchError(
                    "الإنفاق المتوقع للدفعة (%d وحدة لـ%d قصص جاهزة) "
                    "يتجاوز الرصيد المسجَّل (%d وحدة) — قلّل العدد "
                    "بـ --count أو استخدم --source openmontage"
                    % (total_expected,
                       len([s for s in stories if s["ready"]]),
                       balance))
    return {
        "count": len(stories),
        "source": source,
        "balance_units": veo_cfg.get("balance_units"),
        "cap_units": veo_cfg.get("cap_units"),
        "expected_units_per_video": (VEO_UNITS_PER_VIDEO
                                     if source == "veo" else 0),
        "total_expected_units": total_expected,
        "stories": stories,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_plan(plan):
    """نص عربي للخطة (وضع تجريبي)."""
    lines = ["== خطة الدفعة — %d قصص (المصدر: %s) =="
             % (plan["count"],
                "Veo (في Google Flow)" if plan["source"] == "veo"
                else "OpenMontage (بلا رصيد)")]
    if plan["source"] == "veo":
        lines.append("الرصيد المسجَّل: %s وحدة — السقف: %s — المتوقع "
                     "للفيديو: %d وحدة"
                     % (plan["balance_units"],
                        ("%d وحدة" % plan["cap_units"])
                        if plan["cap_units"] is not None else "بلا سقف",
                        plan["expected_units_per_video"]))
        lines.append("المجموع المتوقع للدفعة: %d وحدة"
                     % plan["total_expected_units"])
    lines.append("")
    for s in plan["stories"]:
        if not s["ready"]:
            status = "تُتخطى: %s" % s["reason"]
        elif plan["source"] == "veo" and not s["video_ready"]:
            status = "تحتاج توليدًا في Flow أولًا (بلا فيديو جاهز)"
        else:
            status = "جاهزة%s" % (
                " (مشروع %s)" % s["project"] if s["project"] else "")
        lines.append("  %d. %s — %s" % (s["number"], s["title"], status))
    lines.append("")
    if plan["source"] == "veo":
        lines.append("تنبيه: إنتاج Veo يتم في Google Flow يدويًا — "
                     "الدفعة تنتج فقط القصص التي لها فيديو جاهز.")
    return "\n".join(lines) + "\n"


def execute_batch(cfg, plan, produce_fn, check_fn, thumbnail_fn,
                  runs_dir, continue_on_error=False,
                  record_spend_fn=None):
    """نفّذ خطة الدفعة (بعد --execute الصريح).

    الدوال المحقونة (قابلة للاختبار بلا تنفيذ حقيقي):
      produce_fn(cfg, slug, project, out_path) -> 0/1
      check_fn(video) -> قاموس run_checks (فيه "passed")
      thumbnail_fn(video, hook, out_path) -> مسار المصغرة
      record_spend_fn(units) -> الرصيد الجديد أو None: تُستدعى
        بعد كل فيديو Veo مكتمل فقط (الجولة 8) — لا خصم لقصة
        متخطاة أو فاشلة، ولا خصم أبدًا في وضع تجريبي.
    يرجع (رمز الخروج، قاموس النتائج المحفوظ في runs/batch-*.json).
    """
    result = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
              "count": plan["count"], "source": plan["source"],
              "stories": [], "total_spent_units": 0}
    overall = 0
    for item in plan["stories"]:
        entry = {"number": item["number"], "title": item["title"],
                 "ready": item["ready"], "project": item["project"]}
        if not item["ready"]:
            entry["status"] = "skipped"
            entry["reason"] = item["reason"]
            result["stories"].append(entry)
            continue
        if plan["source"] == "veo" and not item["video_ready"]:
            entry["status"] = "needs-flow"
            entry["reason"] = ("مسار Veo بلا فيديو جاهز — أنتج "
                               "المشاهد في Google Flow أولًا")
            entry["scene_plan"] = item.get("scene_plan")
            result["stories"].append(entry)
            continue
        video = item["video"]
        print("قصة %d (%s): الإنتاج (%s)…"
              % (item["number"], item["title"], plan["source"]))
        t0 = time.time()
        rc = produce_fn(cfg, item["slug"], item["project"], video)
        entry["produce"] = "done" if rc == 0 else "failed"
        if rc != 0:
            entry["status"] = "failed"
            entry["seconds"] = round(time.time() - t0, 1)
            result["stories"].append(entry)
            overall = 1
            print("  فشل الإنتاج")
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
            continue
        print("  فحص الجودة…")
        check = check_fn(video)
        entry["check_passed"] = bool(check.get("passed"))
        if not check.get("passed"):
            entry["status"] = "failed"
            entry["reason"] = "فشل فحص الجودة"
            entry["seconds"] = round(time.time() - t0, 1)
            result["stories"].append(entry)
            overall = 1
            print("  فشل فحص الجودة")
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
            continue
        print("  الصورة المصغرة…")
        thumb = thumbnail_fn(video, item["title"],
                             os.path.splitext(video)[0] + "-thumbnail.jpg")
        entry["thumbnail"] = thumb
        entry["output"] = video
        entry["status"] = "done"
        # الجولة 8: فيديو Veo مكتمل فعلًا — يُخصم إنفاقه (120
        # وحدة) من الرصيد المسجَّل ويُختم الوقت.
        if plan["source"] == "veo" and record_spend_fn is not None:
            entry["units_spent"] = VEO_UNITS_PER_VIDEO
            entry["new_balance"] = record_spend_fn(
                VEO_UNITS_PER_VIDEO)
            result["total_spent_units"] += VEO_UNITS_PER_VIDEO
        entry["seconds"] = round(time.time() - t0, 1)
        result["stories"].append(entry)
        print("  تمت: %s" % video)
    os.makedirs(runs_dir, exist_ok=True)
    out_path = os.path.join(
        runs_dir, "batch-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("سُجّلت نتائج الدفعة في: %s" % out_path)
    return overall, result
