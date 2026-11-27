#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""studio — خط إنتاج موحّد لفيديوهات القصص.

المعمارية (طبقة تنسيق فقط — لا كود منسوخ من الأدوات الثلاث):
  OmniRoute  (الذكاء: سيناريو/هوك/عناوين عبر نماذج مجانية)
      ↓
  OpenMontage (الإنتاج: بحث، سيناريو، سرد Piper، صور، تركيب)
      ↓
  Concat     (التجميع النهائي القابل للتعديل + التصدير — الافتراضي)
  headless-editor (تجميع بديل عبر `editor.py render` — اختياري)

الأوامر:
  studio.py status
  studio.py doctor [--fix]   # فحص بيئة studio (PASS/FAIL صادق)
  studio.py run --demo       # القصة التجريبية المدمجة (مسار مجاني فقط)
  studio.py publish --video F --title T [--caption C] [--dry-run]
      # نشر فيديو على صفحة فيسبوك (Reel) ويوتيوب (Data API v3)
  studio.py publish --preflight --video F --title T
      # فحص ما قبل النشر على يوتيوب فقط: التوكن + جلسة رفع
      # قابلة للاستئناف بلا إرسال أي بايت وبلا نشر
  studio.py version
      # إصدار studio + حالة البعيد من سجل المزامنة المحلي
  studio.py debug-config [--profile NAME] [--set KEY=VALUE ...]
      # الإعداد الفعّال ومصدر كل قيمة (قراءة فقط — بلا أي تنفيذ)
  studio.py youtube-auth     # تبادل OAuth ليوتيوب لمرة واحدة
  studio.py script   --story NAME [--allow-fallback]
  studio.py produce  --project NAME [--run RUN_ID]
  studio.py assemble --run RUN_ID [--out PATH] [--backend concat|headless|mlt]
      [--size WxH] [--no-watermark] [--cards-dir DIR] — شعار الصفحة تلقائي، وبطاقات
      # الاقتباس الختامية (3×3 ثوانٍ) إن أُعطي مجلدها.
  studio.py quote-cards --ibra TEXT --hikma TEXT --mawiza TEXT
      [--mawiza-source TEXT] --out-dir DIR
      # توليد بطاقات الاقتباس الثلاث (عبرة/حكمة/موعظة) 720×1280.
  studio.py thumbnail --video PATH --hook TEXT [--time SEC] [--out PATH]
  studio.py whisper-ass --audio PATH --out PATH [--model small]
      # كابشنات من faster-whisper (خيار تجريبي — انظر WHISPER-TEST.md)
  studio.py run      --story NAME --project NAME [--out PATH] [--allow-fallback] [--dry-run] [--backend concat|headless|mlt] [--size WxH]
      [--lang ar|en] [--voice NAME]
      # المقاس الافتراضي 720×1280 (عمودي)؛ --size 1280x720 للأفقي
      # (الفيديو الطويل الأسبوعي ليوتيوب).
  studio.py long-video --out PATH --title TITLE [--story NAME | --project NAME
      | --run RUN_ID | --chapter-dir DIR | --chapter-text TITLE --text-file FILE
      --cover IMG ...] [--chapters-file FILE] [--music PATH] [--atempo X]
      [--motion clips|still|kenburns|youtube-long] [--motion-manifest FILE]
      [--motion-dir DIR] [--improve-motion] [--lang ar|en] [--voice NAME]
      # فيديو طويل أفقي 1280×720 (8–12 دقيقة) من عدة قصص: مقدمة بهوك
      # + فصل لكل قصة (بطاقة عنوان + محتوى بعبرته) + خاتمة باشتراك واحد.
      # --motion الافتراضي kenburns (المسار السريع بلا GPU): صور ثابتة
      # بحركة Ken Burns خفيفة؛ clips = مقاطع حركة مولّدة من مانيفست
      # الحركة (--motion-manifest) مع رجوع لصورة ثابتة بلا Ken Burns
      # عند غياب المقاطع — خيار صريح فقط؛ still = صور ثابتة بلا أي
      # حركة؛ youtube-long = مثل clips لكن الصور الاحتياطية 2.5 ثانية
      # بدل 5 (إيقاع القطع السريع في قصص يوتيوب الطويلة) وبلا Ken Burns
      # أبدًا. --improve-motion يبدّل صور الفصول بمقاطع مولّدة من
      # المانيفست (مع إعادة استخدام الإطارات المجمّدة).
      # فيديو طويل أفقي 1280×720 (8–12 دقيقة) من عدة قصص: مقدمة بهوك
      # + فصل لكل قصة (بطاقة عنوان + محتوى بعبرته) + خاتمة باشتراك واحد.
      # سرد Piper مقسّم، كتابة كلمة-بكلمة، شعار الصفحة تلقائي، وبلا
      # بطاقات اقتباس أبدًا. ينتج أيضًا طوابع الفصول ووصف يوتيوب.
  studio.py long-narration --text TEXT | --text-file FILE --out WAV
      [--gap SEC] [--atempo X] [--lang ar|en] [--voice NAME]
      # سرد طويل مقسّم بصوت Piper (رجل) — نص طويل إلى WAV واحد
      # بفواصل صمت بين الجمل، مع أزمنة كل جملة.
  studio.py quick "عنوان القصة" [--lang ar|en] [--voice NAME] [--out PATH]
      [--allow-fallback] [--dry-run] [--publish]
      # أمر واحد بلا أسئلة: عنوان ← قصة قصيرة بصيغة الاستوديو
      # (هوك صادم جملة واحدة + عبرة + سؤال ختامي محيّر) عبر LLM
      # بالموجّه حسب اللغة، مع رجوع لقالب مدمج عند غياب LLM فقط
      # مع --allow-fallback؛ سرد Piper (رجل) + صور ثابتة بحركة
      # Ken Burns خفيفة عبر المسار السريع (بلا انتظار GPU) +
      # تجميع؛ وبلا نشر تلقائي — النشر فقط مع --publish الصريح.
  studio.py expand-motion-prompts --prompts FILE --out FILE
      # وسّع موجّهات حركة قصيرة إلى موجّهات مفصلة (عبر
      # lib.prompt_expand.expand_motion_prompts)؛ وأي موجّه
      # فشل توسيعه يُحفظ بأصله في الناتج مع سبب الرجوع؛
      # ويُطبع ملخص عربي بعد الكتابة. أمر صريح فقط — لا
      # يُستدعى تلقائيًا من أي مسار قائم.
  studio.py run-queue [--limit N] [--continue-on-error] [--dry-run]
      # دفعة جماعية من ملف الطابور: القصص الجاهزة فقط (مشروع
      # OpenMontage موجود) تُشغَّل بالتتابع؛ بلا مشروع تُتخطى.
  studio.py batch --count N [--source veo|openmontage] [--execute]
      # دفعة جماعية (الجولة 7): القصص التالية من الطابور في تشغيل
      # واحد — إنتاج + فحص + مصغرة + سجل؛ افتراضيًا وضع تجريبي.
  studio.py scene-plan --story N [--clips 6]
      # خطة مشاهد Veo مكتوبة قبل أي إنفاق (موجهات + وحدات) مع
      # فحص السقف — الجولة 7.
  studio.py tiktok-auth [--token TOKEN] / instagram-auth [--token TOKEN]
      # خطوات ربط TikTok/Instagram يدويًا + حفظ التوكن (600).
  studio.py tiktok-bundle --video F --title T [--caption C] [--dry-run]
      # حزمة رفع TikTok لمهمة متصفح (كابشن + خطوات — بلا نشر).
  studio.py tiktok-status
      # حالة إعداد TikTok (قراءة فقط، بلا شبكة).
  studio.py analyze --dna --video F [--title T] [--hook H]
      # تحليل DNA الفيروسي (الجولة 7): درجة الهوك 0–10 + الإيقاع
      # + الصمت + كثافة الكلمات + حكم مربوط بالأرقام الحقيقية.
  studio.py analyze-ref --url URL
      # تحليل فيديو مرجعي (بيانات + تفريغ + هوك/إيقاع/ختام) — تحليل
      # خاص فقط، بلا إعادة نشر أو توزيع (انظر README).
  studio.py ideas [--count N] [--theme THEME] [--add N]
      # مولّد أفكار قصص بأسلوب الصفحة (النموذج أولًا، والبنك
      # المحلي بديلًا) مع منع تكرار أي عنوان في الطابور.
  studio.py daily [--slot morning|evening] [--execute]
      # أمر اليوم الواحد: إنتاج + فحص + مصغرة + نشر المنصتين +
      # نص أول تعليق. افتراضيًا --dry-run (خطة بلا تنفيذ).
  studio.py ab --video F [--hook-a A --hook-b B]
      # اختبار A/B: هوكان ومصغرتان + سجل الزوج في runs/ab-*.
  studio.py ab-results [--ab-file FILE]
      # قارن مشاهدات النسختين (فيسبوك + يوتيوب).
  studio.py update [--dry-run]
      # جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة
      # (مع نسخة احتياطية؛ والملفات المحمية لا تُمسّ).
  studio.py backup [--out-dir DIR]
      # نسخة احتياطية zip: الإعداد + الطابور + الطلبات + السجلات.
  studio.py balance [--balance N] [--renew DATE]
      # توقع رصيد Veo بالأيام — من الرصيد المسجَّل (ليس حيًا).

الخطوات تعمل بالتتابع (الجهاز محدود: 1.5 وحدة CPU و~6 جيجا رام بلا
كارت شاشة). خادم OmniRoute يبقى شغالًا على loopback (127.0.0.1:20128)
لأن أمر `chat` يحتاجه — هو مجرد عميل HTTP للخادم، وبدونه يفشل
بصمت (عيب 2026-11-21، انظر _ensure_omniroute_server).
"""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib import omniroute_client
from lib import llm_state
from lib import openmontage_stage
from lib import concat_mcp
from lib import headless_stage
from lib import autoedit
from lib import moviepy_fx
from lib import capite_captions
from lib import latin_captions
from lib import trim
from lib import mlt_stage
from lib import thumbnail
from lib import whisper_captions
from lib import ref_analyzer
from lib import watermark
from lib import long_narration
from lib import long_video
from lib import motion_clips
from lib import doctor
from lib import protect as protect_lib
from lib import demo
from lib import publish
from lib import queue as queue_lib
from lib import queue_check
from lib import first_scene
from lib import run_record
from lib import run_resume
from lib import manifest as manifest_lib
from lib import coverage as coverage_lib
from lib import autoweek
from lib import analyze
from lib import insights
from lib import help_ar
from lib import license as license_lib
from lib import star_gate as star_gate_lib
from lib import request_flow
from lib import check as check_lib
from lib import fix_audio as fix_audio_lib
from lib import lut_grade as lut_grade_lib
from lib import openreel_render as openreel_lib
from lib import init_wizard
from lib import ideas
from lib import daily
from lib import ab as ab_lib
from lib import update_backup
from lib import balance as balance_lib
from lib import run_log as run_log_lib
from lib import stage_cache as stage_cache_lib
from lib import batch as batch_lib
from lib import dna as dna_lib
from lib import avatar_job as avatar_job_lib
from lib import avatar_profiles as avatar_profiles_lib
from lib import audio_profile as audio_profile_lib
from lib import scene_plan as scene_plan_lib
from lib import social_publish as social_lib
from lib import tiktok_publish as tiktok_lib
from lib import tiktok_long as tiktok_long_lib
from lib import ass_shaping as ass_shaping_lib
from lib import script_meta as script_meta_lib
from lib import schedule_watch as schedule_watch_lib
from lib import publish_meta as publish_meta_lib
from lib import story_templates as story_templates_lib
from lib import job_registry as job_registry_lib
from lib import shorts_cut as shorts_cut_lib
from lib import avatar_aspect as avatar_aspect_lib
from lib import cost_ledger as cost_ledger_lib
from lib import i18n as i18n_lib
from lib import profiles as profiles_lib
from lib import channel_audit as channel_audit_lib
from lib import hook_panel as hook_panel_lib
from lib import retention_read as retention_read_lib
from lib import seo_check as seo_check_lib
from lib import title_lint as title_lint_lib
from lib import viral_rank as viral_rank_lib
from lib import trend_scout as trend_scout_lib
from lib import scene_shorts as scene_shorts_lib
from lib import tiktok_check as tiktok_check_lib
from lib import script_check as script_check_lib
from lib import topic_brief as topic_brief_lib
from lib import hook_title as hook_title_lib
from lib import reliability_report as reliability_report_lib
from lib import failure_classify as failure_classify_lib
from lib import incident_probe as incident_probe_lib
from lib import id_mask as id_mask_lib
from lib import runbook_check as runbook_check_lib
from lib import failure_drill as failure_drill_lib
from lib import keyword_analyze as keyword_analyze_lib
from lib import content_optimizer as content_optimizer_lib
from lib import keyword_generate as keyword_generate_lib
from lib import micro_niche as micro_niche_lib
from lib import page_analyze as page_analyze_lib
from lib import fresh_keywords as fresh_keywords_lib
from lib import topical_authority as topical_authority_lib


def _print_translated(prefix, exc, context, lang="ar"):
    """اطبع خطأً مترجمًا للعربية؛ وإن لم تُعرف فئته اطبع الأصل.

    مع lang="en" (الجولة v0.1.41): بادئة الخطأ تُترجم، ورسالة
    «فشلت كل مزودات الذكاء» تُترجم حرفيًا؛ وجسم الخطأ المترجم
    في lib/errors.py يبقى عربيًا (خارج هذه الحزمة)."""
    from lib import errors as errors_lib
    text = str(exc)
    shown_prefix = i18n_lib.translate_prefix(prefix, lang)
    if i18n_lib.normalize_lang(lang) == "en":
        translated = i18n_lib.translate_llm_all_failed(text, "en")
        if translated != text:
            print("%s: %s" % (shown_prefix, translated))
            return
    if "ماذا حدث:" in text:
        print("%s: %s" % (shown_prefix, text))  # مترجم أصلًا في lib/ — لا تكرر
        return
    explained = errors_lib.explain_error(exc, context)
    if explained["category"] == "unknown":
        print("%s: %s" % (shown_prefix, text))
    else:
        print(errors_lib.format_error(explained))

VERSION = "0.1.63"
# قيد ترخيص الصوت الإنجليزي (الموجة الأولى — W3، مقروء من بطاقة
# الموديل en_US-ryan-medium: CC BY-NC-SA 4.0، انظر docs/voices.md):
# يظهر حرفيًا في نص مساعدة --lang في أوامر run/long-video/
# long-narration/karaoke-ass/quick.
EN_VOICE_LICENSE_NOTE = ("الصوت الإنجليزي للاستخدام الشخصي/التجريبي "
                         "فقط (CC BY-NC-SA 4.0) — لا يُستخدم لفيديوهات "
                         "عملاء مدفوعة")
STUDIO_DIR = os.path.dirname(os.path.abspath(__file__))
# سجل مزامنة GitHub المحلي (يكتبه سكربت الرفع في ~/workspace) —
# مصدر سطر «حالة البعيد» في أمر `version` (قراءة محلية فقط،
# بلا شبكة إجبارية).
SYNC_LOG_PATH = os.path.join(os.path.dirname(STUDIO_DIR),
                             "studio.muse-github-snapshot-sync.json")


def remote_status_line(sync_log=None):
    """سطر حالة البعيد من سجل المزامنة المحلي (بلا شبكة).

    يرجع نصًا عربيًا: آخر إدخال مزامنة (المستودع/الفرع + أول
    8 أحرف من الالتزام + عدد الإدخالات)، أو «غير معروفة» إن
    غاب السجل أو فسد — ولا يفشل أبدًا.
    """
    path = sync_log or SYNC_LOG_PATH
    try:
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)
        if not isinstance(entries, list) or not entries:
            raise ValueError("سجل مزامنة فارغ")
        # إدخالات الالتزام «dddd…» قطع اختبار وهمية يكتبها تشغيل
        # مجموعة الاختبارات في السجل — تُتخطى، وآخر إدخال حقيقي
        # هو المرجع.
        real = [e for e in entries
                if isinstance(e, dict) and e.get("commit_sha")
                and set(str(e["commit_sha"])) != {"d"}]
        if not real:
            raise ValueError("سجل مزامنة بلا إدخالات حقيقية")
        last = real[-1]
        return ("البعيد: آخر مزامنة محفوظة %s/%s@%s (%d إدخالًا "
                "حقيقيًا في السجل المحلي — بلا شبكة)"
                % (last.get("owner"), last.get("repo"),
                   str(last.get("commit_sha") or "?")[:8],
                   len(real)))
    except (OSError, ValueError, TypeError, KeyError):
        return ("حالة البعيد: غير معروفة (بلا شبكة — سجل المزامنة "
                "المحلي غير متاح)")


def cmd_version():
    """اطبع إصدار studio + حالة البعيد (بلا شبكة). يرجع 0."""
    print("studio %s" % VERSION)
    print(remote_status_line())
    return 0
# الموسيقى الخلفية المدمجة (شوبان — ملكية عامة، assets/music/).
DEFAULT_MUSIC = os.path.join(
    STUDIO_DIR, "assets", "music", "calm-piano-chopin-nocturne-20.mp3")
DEFAULTS = {
    "omniroute": {"base_url": "http://localhost:20128",
                  "model": "ddgw/gpt-5.4-mini",
                  "fallback_model": "groq/openai/gpt-oss-120b",
                  "timeout_seconds": 120,
                  "retries": 1,
                  "retry_delay_seconds": 5},
    "openmontage": {"root": "~/workspace/openmontage",
                    "projects_dir": "~/workspace/openmontage/projects"},
    "concat": {"bin": "~/workspace/concat/squashfs-root/usr/bin/concat",
               "projects_dir": "~/workspace/concat/projects"},
    "headless": {"root": "~/workspace/headless-editor",
                 "editor": "~/workspace/headless-editor/editor.py"},
    "openreel": {"root": "~/workspace/openreel-auto",
                 "render": "~/workspace/openreel-auto/render.py"},
    "video": {"width": 720, "height": 1280, "fps": 30,
              "codec": "h264", "crf": 20, "image_clip_seconds": 5},
    "paths": {"workspace": "~/workspace",
              "videos_dir": "~/workspace/videos",
              "runs_dir": "~/workspace/studio/runs",
              "queue_file": "~/workspace/goals/goal/hidden_files/"
                            "story-queue-2026-11-20.md"},
    "publish": {"page_id": "",
                "youtube_client_secrets":
                    "~/workspace/studio/client_secrets.json",
                "youtube_token": "~/workspace/studio/youtube-token.json",
                "youtube_privacy": "public",
                "youtube_channel_id": "UCz5VeqN-eolCaCPGTpiWtJw"},
    "long_video": {"default_music": ""},
    "schedule": {"morning": "09:00", "evening": "19:00"},
    "narration": {"voice": "piper"},
    # رصيد Veo مسجَّل يدويًا (ليس حيًا من API — لا واجهة رسمية
    # لرصيد Flow): يُحدَّث بعد كل توليد في Flow. 750 وحدة
    # تتجدد 13 ديسمبر؛ فيديو Veo اليومي 100–140 وحدة.
    "veo": {"balance_units": 750, "renews": "2026-12-13",
            "daily_cost_min": 100, "daily_cost_max": 140},
}


# قصص الطابور التي لها مشروع OpenMontage جاهز، برقمها في ملف
# الطابور: رقم القصة → (slug القصة في studio، اسم مشروع OpenMontage).
# أي قصة خارج هذه الخريطة بلا مشروع مُعدّ فتُتخطى في run-queue
# (لا يُخترع سيناريو من لا شيء). تُحدَّث الخريطة كلما جُهّز مشروع
# جديد لقصة من الطابور.
KNOWN_PROJECTS = {
    4: ("anza", "anza-part1"),  # العنزة المباركة
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))  # نسخة عميقة
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("config.yaml", "config.yml"):
        path = os.path.join(here, name)
        if not os.path.isfile(path):
            continue
        try:
            import yaml
            with open(path, encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            _deep_update(cfg, user)
        except ImportError:
            print("تحذير: PyYAML غير متاح — يُستخدم الإعداد الافتراضي",
                  file=sys.stderr)
        except Exception as e:
            print("تحذير: تعذر قراءة %s (%s) — يُستخدم الافتراضي"
                  % (path, e), file=sys.stderr)
        break
    # تحقق: أي قسم أُبدل بنوع خاطئ (مثلًا نص بدل قاموس) يُعاد للافتراضي
    for section, default in DEFAULTS.items():
        if not isinstance(cfg.get(section), dict):
            print("تحذير: قسم %s في الإعداد بنوع خاطئ — يُستخدم الافتراضي"
                  % section, file=sys.stderr)
            cfg[section] = json.loads(json.dumps(default))
    return cfg


def _deep_update(base, user):
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v


def parse_size(text):
    """فسّر مقاس فيديو بصيغة WxH (مثال: 1280x720) إلى (عرض، ارتفاع).

    يُستخدم مع --size في run/assemble للفيديو الأفقي (الفيديو الطويل
    الأسبوعي). يرفع ValueError برسالة عربية عند أي صيغة غير صالحة.
    """
    if not isinstance(text, str):
        raise ValueError("المقاس يجب أن يكون نصًا بصيغة WxH مثل 1280x720")
    parts = text.strip().lower().split("x")
    if len(parts) != 2:
        raise ValueError("المقاس بصيغة WxH مثل 1280x720 (وصل: %s)" % text)
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        raise ValueError("المقاس بصيغة WxH بأرقام صحيحة (وصل: %s)" % text)
    if width <= 0 or height <= 0:
        raise ValueError("أبعاد المقاس يجب أن تكون موجبة (وصل: %s)" % text)
    from lib.paths import check_size
    return check_size(width, height, "المقاس")


def expand(p):
    return os.path.expanduser(os.path.expandvars(str(p)))


def validate_run_component(name, what="اسم القصة"):
    r"""تحقق من مكوّن مسار واحد (slug قصة أو معرّف تشغيل) قبل ضمّه إلى مسار.

    يرفض أي قيمة قد تخرج بالمسار من مجلد التشغيل: فواصل مسارات (`/` أو
    `\`)، أو `..`، أو حرف NUL، أو البدء بنقطة أو بشرطة (حقن أعلام).
    القيم الصالحة مثل: anza، aisha-part2، test_1.
    """
    from lib.paths import safe_component
    return safe_component(name, what)


def run_dir_for(runs_dir, run_id):
    """مسار تشغيل داخل runs_dir مع تحقق دفاعي بعد الـresolve.

    يتحقق أولًا من مكوّن المسار، ثم يتأكد بعد حلّ المسار المطلق أن
    الناتج ما زال داخل runs_dir (دفاع بالعمق ضد `..` والروابط الرمزية).
    """
    validate_run_component(run_id, "معرّف التشغيل")
    base = Path(os.path.realpath(runs_dir))
    target = Path(os.path.realpath(os.path.join(str(base), run_id)))
    if not target.is_relative_to(base):
        raise ValueError("معرّف التشغيل يخرج عن مجلد التشغيل: %s" % run_id)
    return str(target)


def new_run(runs_dir, story):
    validate_run_component(story, "اسم القصة")
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_id = "%s-%s" % (story, ts)
    run_dir = run_dir_for(runs_dir, run_id)
    # إصلاح اختبار اختراق 2026-11-22 (L14): الفحص ثم الإنشاء
    # (exists + makedirs exist_ok=True) كان سباقًا نظريًا —
    # تشغيلان متوازيان في نفس الثانية قد يأخذا نفس المجلد.
    # الآن إنشاء ذري: makedirs(..., exist_ok=False) والتعارض
    # (FileExistsError) يعيد المحاولة بلاحقة رقمية.
    n = 2
    for _attempt in range(10000):
        try:
            os.makedirs(run_dir, exist_ok=False)
            return run_id, run_dir
        except FileExistsError:
            run_id = "%s-%s-%d" % (story, ts, n)
            run_dir = run_dir_for(runs_dir, run_id)
            n += 1
    raise OSError("تعذّر إنشاء مجلد تشغيل فريد بعد 10000 محاولة: %s"
                  % story)


def write_log(run_dir, log):
    with open(os.path.join(run_dir, "run-log.json"), "w",
              encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- status
def _omniroute_bind_address(port=20128, lang="ar"):
    """عنوان ربط خادم OmniRoute من /proc/net/tcp.

    يقرأ المنفذ 20128 ويعيد عنوان الاستماع الفعلي؛ تحذير صريح
    إن لم يكن loopback (اختبار اختراق 2026-11-21: الخادم كان
    يربط 0.0.0.0 لأن المتغير الصحيح HOSTNAME لا
    OMNIROUTE_SERVER_HOST).
    """
    try:
        with open("/proc/net/tcp", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                try:
                    local = parts[1]
                    addr, p = local.rsplit(":", 1)
                    port_no = int(p, 16)
                except ValueError:
                    continue
                if port_no != port or parts[3] != "0A":
                    continue
                ip = ".".join(str(int(addr[i:i + 2], 16))
                              for i in (6, 4, 2, 0))
                if ip == "127.0.0.1":
                    return i18n_lib.t("status_loopback", lang)
                return i18n_lib.t("status_bind_warn", lang, ip)
    except OSError:
        pass
    return i18n_lib.t("status_bind_unknown", lang)


def cmd_status(cfg, lang="ar"):
    ok = True
    print(i18n_lib.t("status_llm_section", lang))
    base = cfg["omniroute"]["base_url"]
    try:
        req = urllib.request.Request(base.rstrip("/") + "/")
        with urllib.request.urlopen(req, timeout=8) as resp:
            print(i18n_lib.t("status_server_up", lang, base, resp.status))
    except Exception as e:
        print(i18n_lib.t("status_server_down", lang, base, e))
        ok = False
    print(i18n_lib.t("status_bind", lang,
                      _omniroute_bind_address(lang=lang)))
    try:
        out = subprocess.run(["omniroute", "providers", "list"],
                             capture_output=True, text=True, timeout=30)
        import re as _re
        clean = _re.sub(r"\x1b\[[0-9;]*m", "", out.stdout or "")
        rows = [l.strip() for l in clean.splitlines()
                if l.strip() and not l.strip().startswith(("Loaded", "📋",
                      "STORAGE", "OmniRoute Providers", "⚠"))]
        print(i18n_lib.t("status_providers", lang,
                         ("؛ ".join(rows) if rows
                          else i18n_lib.t("status_no_providers", lang))))
    except Exception as e:
        print(i18n_lib.t("status_providers_error", lang, e))
    print(i18n_lib.t("status_openmontage", lang))
    root = expand(cfg["openmontage"]["root"])
    print("  %s: %s" % (root, i18n_lib.t(
        "status_exists" if os.path.isdir(root) else "status_missing",
        lang)))
    print(i18n_lib.t("status_concat", lang))
    b = expand(cfg["concat"]["bin"])
    print("  %s: %s" % (b, i18n_lib.t(
        "status_exists" if os.path.isfile(b) else "status_missing",
        lang)))
    print(i18n_lib.t("status_headless", lang))
    h = expand(cfg["headless"]["editor"])
    print("  %s: %s" % (h, i18n_lib.t(
        "status_exists" if os.path.isfile(h) else "status_missing",
        lang)))
    print(i18n_lib.t("status_mlt", lang))
    print("  %s" % (i18n_lib.t("status_available", lang)
                     if shutil_which("melt")
                     else i18n_lib.t("status_melt_missing", lang)))
    print(i18n_lib.t("status_ffmpeg", lang))
    print("  %s" % (i18n_lib.t("status_available", lang)
                     if shutil_which("ffmpeg")
                     else i18n_lib.t("status_unavailable", lang)))
    print(i18n_lib.t("status_memory", lang))
    try:
        with open("/proc/meminfo") as f:
            mem = dict(l.split(":") for l in f.read().splitlines())
        free = int(mem["MemAvailable"].split()[0]) // 1024
        print(i18n_lib.t("status_memory_free", lang, free))
    except Exception:
        pass
    return 0 if ok else 1


# أدوات يتوقع خط الإنتاج وجودها في PATH (روابط /usr/local/bin
# لنسخها في الـhome). إن غاب أحدها أو غاب ملف خدمة systemd، يُشغَّل
# سكربت الاستعادة تلقائيًا — إصلاح ذاتي بعد أي مسح كامل.
# (fc-list: أُضيف 2026-11-22 — fontconfig حزمة apt تُمسح مع الريستارت
# وكان فحص الخطوط بلا تغطية إصلاح.)
_EXPECTED_TOOLS = ("ffmpeg", "melt", "yt-dlp", "omniroute", "ollama",
                   "piper", "zstd", "fc-list")
_SETUP_ENV_SCRIPT = os.path.join(os.path.expanduser("~"), "workspace",
                                  "setup-env.sh")
_UNIT_FILE = "/etc/systemd/system/studio-env-restore.service"
# أدوات الحماية (apt) وقاعدة ClamAV — تُمسح مع كل ريستارت، وحارس البيئة
# ensure-env.sh يعيدها في الخلفية (انظر _ensure_protection_tools).
_PROTECTION_TOOLS = ("lynis", "clamscan", "rkhunter", "chkrootkit",
                     "fail2ban-client", "ufw")
_ENSURE_ENV_SCRIPT = os.path.join(os.path.expanduser("~"), "workspace",
                                  "ensure-env.sh")
_CLAMAV_DB_DIR = "/var/lib/clamav"


def _script_safe_to_run(script):
    """هل سكربت الاستعادة آمن للتشغيل التلقائي؟

    سكربتات الاستعادة تُنفَّذ تلقائيًا بصلاحيات المستخدم، فأي عبث
    بها يتحول إلى تنفيذ كود. ارفض التشغيل إن لم يكن السكربت ملفًا
    عاديًا مملوكًا للمستخدم (أو root) أو كان قابلًا للكتابة من
    الجميع. (إصلاح اختبار اختراق 2026-11-21.)
    """
    try:
        st = os.stat(script)
    except OSError:
        return False
    import stat as _stat
    if not _stat.S_ISREG(st.st_mode):
        return False
    if st.st_uid not in (os.getuid(), 0):
        return False
    if st.st_mode & 0o002:
        return False
    return True


def _log_auto_script(script, reason):
    """سجّل كل تشغيل تلقائي لسكربت استعادة (بدل إخفائه في DEVNULL)."""
    try:
        log = os.path.join(os.path.expanduser("~"), "workspace", "studio",
                           "runs", "ensure-env-runs.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write("%s تشغيل تلقائي: %s (%s)\n"
                    % (time.strftime("%Y-%m-%dT%H:%M:%S"), script, reason))
    except OSError:
        pass


# أوامر الموجة ب (جولة v0.1.63) لا تحتاج استعادة البيئة ولا خادم
# OmniRoute: أغلفة قراءة/إعداد خفيفة فوق وحدات lib/ — فتُعامل
# كأوامر قراءة فقط هنا (تحذير فقط عند غياب أداة، بلا استرداد
# متزامن وبلا تشغيل خادم).
_NEW_COMMANDS = ("approval", "team", "routines", "check-back", "usage",
                 "models", "round-pack", "handoffs", "keys", "sentinel",
                 "control", "inspect", "read-log", "search-log",
                 "send-work", "wait-job", "interrupt-job", "switch-model",
                 "wait", "events", "brief", "workers", "export",
                 "features", "triage", "recipe", "webhook", "setup",
                 "router")
_READONLY_COMMANDS = ("version",) + _NEW_COMMANDS


def _ensure_environment(read_only=False):
    """أصلح البيئة بنفسك قبل حلّ الأدوات (best-effort، بلا فشل).

    يضيف مجلدي أدوات الـhome إلى PATH أولًا (شل التنفيذ لا يشملهما
    أصلًا)، فإن بقيت أداة متوقعة غائبة أو غاب ملف الخدمة، يشغّل
    setup-env.sh مرة واحدة بمهلة 300 ثانية. وأخيرًا يتأكد أن خادم
    OmniRoute شغال على loopback لأن أمر `chat` يحتاجه (عيب 2026-11-21).
    أي فشل يُسجَّل تحذيرًا فقط ولا يوقف التشغيل. حارس البيئة
    STUDIO_ENV_RESTORED يمنع إعادة تشغيل سكربت الاستعادة في
    الاستدعاءات المتداخلة؛ أما فحص الخادم فرخيص فيُعاد كل مرة.

    إصلاح بطء بدء التشغيل 2026-11-26 (عيب: `version` استغرق
    323 ثانية): غياب ملف الخدمة وحده كان يطلق الاستعادة المتزامنة
    بمهلة 300 ثانية حتى مع وجود كل الأدوات — فصار يُطلقها في
    الخلفية (Popen) بلا حظر، لأن خطوة 0 من setup-env.sh تعيد
    الملف من نسخة الـhome في ثوانٍ. أما أمر قراءة فقط
    (`read_only=True`، مثل `version`) فلا يطلق أي استرداد إطلاقًا
    ولا فحص أدوات الحماية ولا خادم OmniRoute — تحذير على stderr
    فقط. والأداة الغائبة فعلًا في أمر إنتاجي ما زالت تطلق
    الاسترداد المتزامن كما هو (مهلة 300 ثانية معلنة في التحذير).
    """
    import shutil
    home = os.path.expanduser("~")
    for d in (os.path.join(home, ".local", "bin"),
              os.path.join(home, ".npm-global", "bin")):
        if os.path.isdir(d) and d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    if os.environ.get("STUDIO_ENV_RESTORED") != "1":
        missing = [t for t in _EXPECTED_TOOLS if shutil.which(t) is None]
        # مكتبتا بايثون النظاميتان (PyYAML/Pillow) — حزمتا apt قد تُمسحان
        # مع الريستارت ولا يغطيهما `command -v`؛ فحص الاستيراد يطلق
        # الاستعادة نفسها (setup-env.sh يعيد تثبيتهما في الخطوة 8).
        # إصلاح 2026-11-22 (حل مشكلة التثبيت بعد إعادة التشغيل).
        import importlib.util as _ilu
        py_missing = [m for m in ("yaml", "PIL")
                      if _ilu.find_spec(m) is None]
        if py_missing:
            missing = missing + ["python:%s" % m for m in py_missing]
        unit_missing = not os.path.isfile(_UNIT_FILE)
        if missing or unit_missing:
            script = _SETUP_ENV_SCRIPT
            if not os.path.isfile(script):
                # إلى stderr لا stdout — فمخرجات JSON للأوامر
                # (مثل avatar-job --template وcheck --json) تبقى
                # قابلة للقراءة الآلية في بيئة متدهورة.
                print("تحذير: أدوات غائبة (%s) ولا يوجد سكربت استعادة %s"
                      % (", ".join(missing) or "ملف الخدمة", script),
                      file=sys.stderr)
            else:
                reasons = []
                if missing:
                    reasons.append("أدوات غائبة (%s)" % ", ".join(missing))
                if unit_missing:
                    reasons.append("ملف الخدمة غائب")
                reason_text = " و".join(reasons)
                if read_only:
                    # أمر قراءة فقط: تحذير فقط، بلا أي استرداد
                    # (لا متزامن ولا خلفي) وبلا فحص حماية/خادم.
                    print("تحذير: %s — أمر قراءة فقط، لا استرداد"
                          % reason_text, file=sys.stderr)
                elif missing:
                    print("تحذير: %s — تشغيل سكربت الاستعادة… "
                          "(قد يستغرق حتى 300 ثانية)"
                          % reason_text, file=sys.stderr)
                    if not _script_safe_to_run(script):
                        print("تحذير: سكربت الاستعادة غير آمن للتشغيل "
                              "التلقائي (مالك/صلاحيات) — يُتخطى: %s"
                              % script, file=sys.stderr)
                    else:
                        _log_auto_script(script, reason_text)
                        env = dict(os.environ)
                        env["STUDIO_ENV_RESTORED"] = "1"
                        try:
                            subprocess.run(["/bin/bash", script], env=env,
                                           timeout=300,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL,
                                           check=False)
                        except (OSError,
                                subprocess.TimeoutExpired) as e:
                            print("تحذير: فشلت استعادة البيئة تلقائيًا "
                                  "(%s) — أكمل بدونها" % e, file=sys.stderr)
                else:
                    # غياب ملف الخدمة وحده: الاستعادة في الخلفية
                    # بلا حظر — خطوة 0 من السكربت تعيد الملف
                    # من نسخة الـhome في ثوانٍ (نفس نمط
                    # _ensure_protection_tools).
                    print("تحذير: %s — تشغيل سكربت الاستعادة في الخلفية…"
                          % reason_text, file=sys.stderr)
                    if not _script_safe_to_run(script):
                        print("تحذير: سكربت الاستعادة غير آمن للتشغيل "
                              "التلقائي (مالك/صلاحيات) — يُتخطى: %s"
                              % script, file=sys.stderr)
                    else:
                        _log_auto_script(script, reason_text)
                        env = dict(os.environ)
                        env["STUDIO_ENV_RESTORED"] = "1"
                        try:
                            subprocess.Popen(
                                ["/bin/bash", script], env=env,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL,
                                start_new_session=True,
                                close_fds=True)
                        except OSError:
                            pass
    if read_only:
        return
    _ensure_protection_tools()
    _ensure_omniroute_server()


_OMNIROUTE_URL = "http://127.0.0.1:20128"


def _omniroute_server_up(timeout=2):
    """هل خادم OmniRoute يرد على /api/health؟ (أي حالة دون 500 تعني شغالًا)."""
    try:
        with urllib.request.urlopen(_OMNIROUTE_URL + "/api/health",
                                    timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _ensure_omniroute_server():
    """تأكد أن خادم OmniRoute شغال على loopback قبل أي استدعاء ذكاء.

    عيب وُجد في اختبار النظام 2026-11-21: أمر `omniroute chat` ليس
    مستقلًا — هو عميل HTTP للخادم على localhost:20128؛ وإن كان الخادم
    متوقفًا يفشل بصمت (exit 1 بلا أي رسالة خطأ، لأن ApiError يحمل
    exitCode فيُنهي العملية دون طباعة)، فيظن studio أن النماذج
    المجانية معطلة بينما المشكلة أن الخادم متوقف فقط. تحذير فحص
    التحديثات على stderr ضجيج غير قاتل ويُحذف من المخرجات أصلًا.
    خادم OmniRoute شغال على 127.0.0.1 فقط (HOSTNAME) فلا
    ينكشف على الشبكة، ويبقى شغالًا — أمر chat يحتاجه في كل تشغيل.
    تنبيه (اختبار اختراق 2026-11-21): الخادم يقرأ `HOSTNAME`
    لا `OMNIROUTE_SERVER_HOST` (server.js: `HOSTNAME || '0.0.0.0'`)،
    فالمتغير القديم وحده كان يترك الخادم على كل الواجهات.
    best-effort: أي فشل تحذير فقط ولا يوقف التشغيل.
    """
    import shutil
    if _omniroute_server_up():
        return
    if shutil.which("omniroute") is None:
        return
    env = dict(os.environ)
    env["HOSTNAME"] = "127.0.0.1"
    env["OMNIROUTE_SERVER_HOST"] = "127.0.0.1"
    # إصلاح 2026-11-21 (اختبار اختراق): REQUIRE_API_KEY=true إلزامي —
    # افتراضي حزمة omniroute هو false، وبدونه تقبل /v1/chat/completions
    # طلبات بلا مفتاح. القيمة في ~/.omniroute/.env أيضًا.
    env["REQUIRE_API_KEY"] = "true"
    try:
        subprocess.run(["omniroute", "serve", "--no-open", "--daemon",
                        "--port", "20128"], env=env, timeout=120,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    except (OSError, subprocess.TimeoutExpired):
        print("تحذير: تعذّر تشغيل خادم OmniRoute",
              file=sys.stderr)
        return
    for _ in range(30):
        time.sleep(2)
        if _omniroute_server_up():
            print("خادم OmniRoute شغال على 127.0.0.1:20128",
                  file=sys.stderr)
            return
    print("تحذير: خادم OmniRoute لم يرد بعد تشغيله — قد يفشل توليد السيناريو",
          file=sys.stderr)


def _ensure_protection_tools():
    """أصلح أدوات الحماية وقاعدة ClamAV في الخلفية إن غابت (best-effort).

    إصلاح دائم 2026-11-21: أدوات الحماية الست وقاعدة ClamAV تُمسح مع كل
    ريستارت VM، ولم يكن أي مسار تلقائي يعيدها (setup-env.sh لا يشملها،
    وخطافا الشل يعيدان ملف الخدمة فقط). هذه الدالة تفحصها في كل تشغيل،
    وإن غاب شيء أطلقت حارس البيئة ensure-env.sh --apt-only منفصلًا في
    الخلفية (مع قفل flock يمنع التكرار) وأكملت التشغيل فورًا — أدوات
    الحماية ليست في مسار النشر الحرج، فلا معنى لحظر النشر دقائق في
    انتظار apt. أي فشل صامت ولا يوقف التشغيل أبدًا.
    """
    import glob
    import shutil
    missing = [t for t in _PROTECTION_TOOLS if shutil.which(t) is None]
    db_missing = (not glob.glob(os.path.join(_CLAMAV_DB_DIR, "*.cvd"))
                  and not glob.glob(os.path.join(_CLAMAV_DB_DIR, "*.cld")))
    if not missing and not db_missing:
        return
    script = _ENSURE_ENV_SCRIPT
    if not os.path.isfile(script):
        return
    if not _script_safe_to_run(script):
        # إلى stderr لا stdout — فمخرجات JSON للأوامر
        # (مثل avatar-job --template وcheck --json) تبقى
        # قابلة للقراءة الآلية في بيئة متدهورة (نفس إصلاح
        # _ensure_environment في v0.1.38).
        print("تحذير: سكربت حارس البيئة غير آمن للتشغيل التلقائي "
              "(مالك/صلاحيات) — يُتخطى: %s" % script,
              file=sys.stderr)
        return
    _log_auto_script(script, "أدوات حماية غائبة")
    try:
        subprocess.Popen(
            ["/bin/bash", script, "--apt-only"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, start_new_session=True,
            close_fds=True)
        print("تحذير: أدوات حماية غائبة (%s)%s — إطلاق إصلاحها في الخلفية"
              % (", ".join(missing) or "لا شيء",
                 " وقاعدة ClamAV غائبة" if db_missing else ""),
              file=sys.stderr)
    except OSError:
        pass


def shutil_which(cmd):
    import shutil
    return shutil.which(cmd) is not None


# ---------------------------------------------------------------- script
SCRIPT_PROMPT = (
    "اكتب عنوان هوك صادم من 8 كلمات بالعامية المصرية لفيديو قصة قصيرة "
    "بعبرة عن: {story}. ثم سطرًا واحدًا كابشن تشويقي لا يكشف النهاية. "
    "أرجع العنوان في السطر الأول والكابشن في السطر الثاني فقط."
)

STORY_TEXTS = {
    "anza": ("عنزة صغيرة ادّعى شيخ أنها معجزة إلهية في القاهرة سنة 1184، "
             "والناس بتركع لها وتجيب لها فستق ولوز وذهب"),
}

FALLBACK_TITLES = {
    # بديل موثق عند فشل OmniRoute: هوك من سيناريو OpenMontage الجاهز.
    # خاص بقصة العنزة فقط؛ أي قصة أخرى لها بديل عام من وصفها.
    "anza": ("عنزة صغيرة بقت أشهر مخلوق في القاهرة!",
             "سنة 1184… عنزة صغيرة بقت أشهر مخلوق في "
             "القاهرة، والناس كانت بتركع لها!"),
}


def _fallback_script(story):
    """هوك/كابشن بديل عند فشل OmniRoute — خاص بالقصة لا عامًا."""
    if story in FALLBACK_TITLES:
        return FALLBACK_TITLES[story]
    desc = STORY_TEXTS.get(story, story)
    return ("قصة حقيقية بعبرة عن: %s" % desc,
            "قصة قصيرة حقيقية عن %s — والنهاية أغرب مما تتخيل." % desc)


def _llm_chat(cfg, prompt, max_tokens=200, temperature=0.7, system=None):
    """استدعاء LLM عبر سلسلة المزودين مع تسجيل الحالة.

    system: موجّه نظام صريح (يُمرَّر كما هو إلى omniroute_client.chat؛
    وبلاه يحمّل chat الموجّه العربي الافتراضي كما كان — فكل الاستدعاءات
    القديمة بلا system تعمل حرفيًا كما اليوم).

    يبني السلسلة من قسم omniroute في config (الموديل، البديل،
    Gemini) ويسجّل كل محاولة مزود في
    runs/llm-provider-state.json (نجاح/فشل + تهدئة الحصة).
    يرجع (النص، المسار، الموديل) كما يرجع omniroute_client.chat.
    """
    cfg_o = cfg.get("omniroute", {}) if isinstance(cfg, dict) else {}
    providers = omniroute_client.providers_from_config(cfg_o)
    runs_dir = None
    try:
        runs_dir = expand(cfg["paths"]["runs_dir"])
    except Exception:
        runs_dir = None
    state = (llm_state.load_state(runs_dir) if runs_dir
             else llm_state.default_state())

    def on_attempt(provider, ok, kind):
        llm_state.record_attempt(state, provider, ok, kind)
        if runs_dir:
            try:
                llm_state.save_state(state, runs_dir)
            except OSError:
                pass

    return omniroute_client.chat(
        prompt, cfg_o.get("model"), cfg_o.get("fallback_model"),
        cfg_o.get("base_url", "http://localhost:20128"),
        max_tokens=max_tokens, temperature=temperature,
        system=system,
        retries=int(cfg_o.get("retries", 1)),
        retry_delay=int(cfg_o.get("retry_delay_seconds", 5)),
        providers=providers, state=state, on_attempt=on_attempt)


def cmd_script(cfg, story, allow_fallback, run_dir=None, lang="ar"):
    cfg_o = cfg["omniroute"]
    # الموجّه حسب اللغة (الموجة الأولى — W4): العربي افتراضيًا حرفيًا
    # كما كان؛ و--lang en يمرّر الموجّه الإنجليزي الأصلي.
    _system = omniroute_client.load_system_prompt(lang)
    prompt = SCRIPT_PROMPT.format(
        story=STORY_TEXTS.get(story, story))
    t0 = time.time()
    try:
        text, via, model = _llm_chat(cfg, prompt,
                                     max_tokens=200, temperature=0.7,
                                     system=_system)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        result = {"source": "omniroute", "via": via, "model": model,
                  "title": lines[0] if lines else "",
                  "caption": lines[1] if len(lines) > 1 else "",
                  "raw": text,
                  "seconds": round(time.time() - t0, 1)}
        print("العنوان (عبر %s/%s): %s" % (via, model, result["title"]))
    except omniroute_client.OmniRouteError as e:
        print("فشل استدعاء OmniRoute: %s" % e)
        if not allow_fallback:
            return None, {"source": "omniroute", "status": "failed",
                          "error": str(e),
                          "seconds": round(time.time() - t0, 1)}
        # بديل موثق: هوك من سيناريو OpenMontage الجاهز (خاص بالقصة)
        fb_title, fb_caption = _fallback_script(story)
        result = {"source": "fallback:openmontage-script",
                  "title": fb_title,
                  "caption": fb_caption,
                  "error": str(e),
                  "seconds": round(time.time() - t0, 1)}
        print("استُخدم البديل من سيناريو OpenMontage الجاهز: %s"
              % result["title"])
    _meta_llm = {}

    def _chat(prompt):
        text, _via, _model = _llm_chat(cfg, prompt,
                                       max_tokens=200, temperature=0.7,
                                       system=_system)
        _meta_llm["via"] = _via
        _meta_llm["model"] = _model
        return text
    meta = script_meta_lib.generate_publish_meta(
        {"title": result["title"],
         "text": STORY_TEXTS.get(story, story)}, chat_fn=_chat)
    result["publish_meta"] = meta
    result["publish_meta_llm_via"] = _meta_llm.get("via")
    result["publish_meta_llm_model"] = _meta_llm.get("model")
    print("وصف النشر: %s" % meta["description"])
    print("الهاشتاغات: %s" % " ".join(meta["hashtags"]))
    if run_dir:
        with open(os.path.join(run_dir, "script-ai.json"), "w",
                  encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result, result


# --------------------------------------------------------------- produce
def cmd_produce(cfg, project, run_dir):
    root = expand(cfg["openmontage"]["root"])
    proj_path = openmontage_stage.find_project(root, project)
    manifest = openmontage_stage.stage(
        proj_path, run_dir, cfg["video"]["image_clip_seconds"])
    print("جُهزت %d صورة، سرد %.1f ثانية، %d عبارة كتابة"
          % (len(manifest["images"]), manifest["narration_duration"],
             len(manifest["phrases"])))
    return manifest


# ------------------------------------------- مقروئية الكابشن (v0.1.55)
def _format_ass_time(seconds):
    """نسّق ثوانيًا كوقت ASS (H:MM:SS.cc) لسطر Dialogue مولَّد محليًا."""
    total_cs = int(round(float(seconds) * 100))
    hours, rem = divmod(total_cs, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return "%d:%02d:%02d.%02d" % (hours, minutes, secs, cs)


def _phrases_ass_text(phrases):
    """حوّل عبارات {start,end,text} إلى نص ASS صالح للتحليل.

    العبارات هي نفسها الممرَّرة إلى الكابشنات وقت التجميع،
    فالقياس على النص المولَّد فعلًا لا على ملف قديم.
    """
    lines = [
        "[Script Info]",
        "Title: captions",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text",
    ]
    for phrase in phrases or []:
        try:
            start = float(phrase.get("start"))
            end = float(phrase.get("end"))
        except (TypeError, ValueError, AttributeError):
            continue
        text = str(phrase.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s"
                     % (_format_ass_time(start),
                        _format_ass_time(end), text))
    return "\n".join(lines) + "\n"


def _readability_summary(report, formatted, ass_path, source):
    """لخّص تقرير المقروئية في قاموس JSON صالح للسجل والمانيفست."""
    def _short(phrase):
        return {"text": phrase["text"], "start": phrase["start"],
                "end": phrase["end"], "cps": round(phrase["cps"], 1)}
    return {"ass_path": ass_path, "source": source,
            "total": report["total"],
            "flashing": [_short(p) for p in report["flashing"]],
            "borderline": [_short(p) for p in report["borderline"]],
            "max_cps": round(report["max_cps"], 1),
            "median_cps": round(report["median_cps"], 1),
            "report": formatted}


def _print_readability(summary):
    """اطبع تقرير المقروئية (تحذير + تقرير فقط — لا أثر في النتيجة)."""
    print("مقروئية الكابشن:")
    for line in summary["report"].splitlines():
        print("  " + line)


def _check_phrases_readability(phrases):
    """حلّل عبارات الكابشن بمقياس المقروئية (تحذير فقط).

    استيراد كسول للوحدة؛ وأي عطل (غياب الوحدة، عبارات تالفة)
    يطبع تحذيرًا ويعيد None — لا يفشل التجميع أبدًا ولا يلمس
    أي ملف (الفحص قراءة فقط على نص مبني في الذاكرة).
    """
    try:
        from lib import caption_readability as readability_lib
    except ImportError:
        print("تحذير: وحدة فحص مقروئية الكابشن غير متاحة — "
              "تخطّى الفحص")
        return None
    try:
        report = readability_lib.analyze_ass_text(
            _phrases_ass_text(phrases))
    except Exception as e:
        print("تحذير: تعذّر فحص مقروئية الكابشن (%s)" % e)
        return None
    return _readability_summary(
        report, readability_lib.format_report(report), None, "phrases")


# -------------------------------------------------------------- assemble
def cmd_assemble(cfg, run_dir, title, out_path, watermark_on=True,
                 cards_dir=None, grade=None, sfx_events=(),
                 overlays=(), assets_dir=None, no_title=False):
    """تجميع وتصدير، ثم (افتراضيًا) شعار الصفحة أعلى اليمين، ثم
    بطاقات الاقتباس الختامية إن أُعطي مجلدها. البطاقات تحمل الشعار
    أصلًا، فتُلحق بعد الشعار. المدة الكلية المستهدفة 40-60 ثانية:
    المحتوى 31-51 ثانية + 9 ثوانٍ بطاقات. الأصول الاختيارية
    (sfx_events/overlays/assets_dir) تُطبَّق بعد الإنهاء
    عبر lib/assets.py؛ وبلا أي منها لا يُستدعى شيء.
    no_title=True (جولة v0.1.62): لا يُحرق عنوان الهوك في Concat
    (title=None) ولا يدّعي البيان الجانبي عنوانًا محروقًا، فيبقى
    hook-title لاحقًا ممكنًا بلا رفض من حارس التضاعف.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise concat_mcp.ConcatError("ملف البيان غير موجود — شغّل "
                                     "produce أولًا: %s" % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    concat_assets_dir = os.path.join(run_dir, "assets")
    concat_bin = expand(cfg["concat"]["bin"])
    if not os.path.isfile(concat_bin):
        raise concat_mcp.ConcatError("ثنائي Concat غير موجود: %s"
                                     % concat_bin)
    projects_root = expand(cfg["concat"]["projects_dir"])
    project_name = "studio-" + os.path.basename(run_dir.rstrip("/"))
    log_path = os.path.join(run_dir, "concat-mcp.jsonl")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    out = concat_mcp.assemble(
        concat_bin, projects_root, project_name, concat_assets_dir,
        manifest, None if no_title else title, out_path, cfg["video"],
        log_path)
    print("صُدّر الفيديو: %s (%.0f ثانية تصدير)"
          % (out, time.time() - t0))
    if grade:
        out = _apply_grade(out, grade)
    out = _finish_video(out, watermark_on, cards_dir)
    if sfx_events or overlays:
        # أصول اختيارية (مؤثرات/طبقات) في المكان نفسه —
        # الاستيراد كسول لأن lib/assets.py وحدة اختيارية قد لا
        # تكون موجودة بعد؛ وبلا أعلام لا يُستدعى apply_assets
        # إطلاقًا فيبقى سلوك اليوم نفسه.
        from lib import assets as assets_lib
        out = assets_lib.apply_assets(
            out, out, sfx=tuple(sfx_events or ()),
            overlays=tuple(overlays or ()), assets_dir=assets_dir)
    _write_assemble_manifest(cfg, run_dir, None if no_title else title,
                             out, "concat", no_title=no_title)
    return out, round(time.time() - t0, 1)


def _write_assemble_manifest(cfg, run_dir, title, out_path,
                               backend, source="studio", no_title=False):
    """اكتب بيان مصدر الفيديو بعد التجميع (جولة v0.1.37).

    يقرأ بيان الإنتاج (run_dir/manifest.json: الهوك والعبارات
    والنص الكامل) وسيناريو الذكاء (script-ai.json: العنوان).
    لا يفشل التجميع أبدًا — أي عطل يُطبع تحذيرًا فقط.
    no_title=True (جولة v0.1.62): لم يُحرق أي عنوان، فلا يُكتب
    عنوان في البيان — وإلا رفض حارس hook-title (lib/hook_title.py)
    حرق الهوك لاحقًا ظنًا أن العنوان محروق أصلًا.
    """
    try:
        produce = {}
        produce_path = os.path.join(run_dir, "manifest.json")
        if os.path.isfile(produce_path):
            with open(produce_path, encoding="utf-8") as f:
                produce = json.load(f)
        script = {}
        script_path = os.path.join(run_dir, "script-ai.json")
        if os.path.isfile(script_path):
            with open(script_path, encoding="utf-8") as f:
                script = json.load(f)
        hook = produce.get("hook") or script.get("title") or title or ""
        scenes = []
        for i, phrase in enumerate(produce.get("phrases") or [], 1):
            start = phrase.get("start") or 0
            end = phrase.get("end") or 0
            scenes.append({"scene": i, "start": start, "end": end,
                           "duration": round(end - start, 2),
                           "text": phrase.get("text", "")})
        narration = {}
        if produce.get("narration"):
            narration = {
                "voice": (cfg.get("narration") or {}).get("voice", "piper"),
                "atempo": (cfg.get("narration") or {}).get("atempo", 1.0),
                "duration_seconds": produce.get("narration_duration")}
        # مقروئية الكابشن (جولة v0.1.55): عبارات الإنتاج هي نفسها
        # الممرَّرة إلى الكابشنات وقت التجميع — تحذير + تقرير فقط،
        # لا يفشل التجميع أبدًا؛ وتُسجَّل النتيجة في بيان المصدر.
        readability = _check_phrases_readability(
            produce.get("phrases") or [])
        if readability is not None:
            _print_readability(readability)
        extra = {"backend": backend,
                 "project": produce.get("project"),
                 "script_source": script.get("source")}
        if readability is not None:
            extra["caption_readability"] = readability
        # عنوان البيان هو العنوان المحروق الذي يقرأه حارس
        # hook-title — فبلا حرق (no_title) يبقى فارغًا حتى لو
        # حمل السيناريو عنوانًا؛ وحقل hook وحده لا يفعّل الحارس.
        man_title = "" if no_title else (script.get("title")
                                         or title or "")
        man = manifest_lib.build_manifest(
            out_path, title=man_title,
            hook=hook, story=produce.get("full_text", ""),
            source=source, scenes=scenes,
            phrases=produce.get("phrases") or [],
            narration=narration,
            extra=extra)
        path = manifest_lib.write_manifest(out_path, man)
        print("بيان المصدر: %s" % path)
        return path
    except Exception as e:
        print("تحذير: تعذرت كتابة بيان المصدر (%s) — الفيديو سليم" % e)
        return None


def _finish_video(out_path, watermark_on=True, cards_dir=None):
    """خطوة الإنهاء المشتركة لكل الخلفيات: شعار ثم بطاقات ختامية."""
    out = out_path
    if watermark_on:
        t0 = time.time()
        watermark.apply_watermark(out, out)
        print("أُضيف شعار الصفحة أعلى اليمين (%.0f ثانية)"
              % (time.time() - t0))
    if cards_dir:
        cards = watermark.find_cards(cards_dir)
        t0 = time.time()
        tmp = out + ".cards-tmp.mp4"
        watermark.append_quote_cards(out, cards, tmp)
        os.replace(tmp, out)
        print("أُلحقت %d بطاقات اقتباس ختامية (%.0f ثانية)"
              % (len(cards), time.time() - t0))
    # إصلاح تلقائي لفجوات الصمت (الجولة 6 بند 3): إن فشل فحص
    # الصمت فقط، امزج ضجيجًا ورديًا خافتًا وأعد الفحص؛ أي فشل
    # آخر (مدة/مقاس/شعار) يُترك كما هو. الفشل هنا لا يفشل
    # التجميع — يُطبع تحذير ويُترك الفيديو الأصلي.
    try:
        result = check_lib.run_checks(out)
        silence = next(c for c in result["checks"]
                       if c["name"] == "الصمت عند الفواصل")
        if not silence["ok"]:
            fixed = fix_audio_lib.fix_silence_gaps(
                out, min_seconds=4.0 if result["long"] else 1.0)
            print(fix_audio_lib.format_report(fixed))
            out = fixed["output"]
    except Exception as e:
        print("تعذر الإصلاح التلقائي للصمت (%s) — يُترك الفيديو "
              "كما هو" % e)
    return out


def cmd_assemble_headless(cfg, run_dir, title, out_path,
                          watermark_on=True, cards_dir=None, grade=None):
    """تجميع عبر نواة headless-editor (خلفية بديلة لـConcat).

    يبني مشروع JSON من البيان ويستدعي `editor.py render`؛ يحفظ
    المشروع في run_dir/headless-project.json. Concat يبقى الافتراضي.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise headless_stage.HeadlessError(
            "ملف البيان غير موجود — شغّل produce أولًا: %s"
            % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    editor_path = expand(cfg["headless"]["editor"])
    project_path = os.path.join(run_dir, "headless-project.json")
    project = headless_stage.build_project(manifest, title, assets_dir,
                                           cfg["video"])
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    result = headless_stage.render_project(editor_path, project_path,
                                           out_path)
    print("صُدّر الفيديو عبر headless-editor: %s (%.0f ثانية ريندر، "
          "%.1f ميجا)" % (result["output"], result["seconds"],
                          result["size_bytes"] / (1024 * 1024)))
    out = _apply_grade(result["output"], grade) if grade else result["output"]
    out = _finish_video(out, watermark_on, cards_dir)
    _write_assemble_manifest(cfg, run_dir, title, out, "headless")
    return out, result["seconds"]


def cmd_assemble_mlt(cfg, run_dir, title, out_path,
                     watermark_on=True, cards_dir=None, grade=None):
    """تجميع عبر MLT/melt (خلفية بديلة لـConcat — تايم لاين XML).

    يبني ملف .mlt من البيان ويستدعي `melt`؛ يحفظ المشروع في
    run_dir/mlt-project.mlt (يُفتح في Kdenlive/Shotcut لاحقًا).
    Concat يبقى الافتراضي.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise mlt_stage.MltError(
            "ملف البيان غير موجود — شغّل produce أولًا: %s"
            % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    # قص الصور لتملأ الإطار (بلا أشرطة سوداء) — نسخ بمقاس الإطار
    # في run_dir/mlt-images بجانب ملف .mlt.
    fill_dir = os.path.join(run_dir, "mlt-images")
    mlt_stage.prepare_fill_images(
        manifest, assets_dir, fill_dir,
        int(cfg["video"]["width"]), int(cfg["video"]["height"]))
    mlt_path = os.path.join(run_dir, "mlt-project.mlt")
    xml_text = mlt_stage.build_mlt(manifest, title, assets_dir,
                                   cfg["video"], images_dir=fill_dir)
    with open(mlt_path, "w", encoding="utf-8") as f:
        f.write(xml_text)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    result = mlt_stage.render_mlt(mlt_path, out_path)
    print("صُدّر الفيديو عبر MLT/melt: %s (%.0f ثانية ريندر، %.1f ميجا)"
          % (result["output"], result["seconds"],
             result["size_bytes"] / (1024 * 1024)))
    if grade:
        out = _apply_grade(result["output"], grade)
    else:
        out = result["output"]
    out = _finish_video(out, watermark_on, cards_dir)
    _write_assemble_manifest(cfg, run_dir, title, out, "mlt")
    return out, result["seconds"]


def _apply_grade(out_path, grade):
    """طبّق preset لونيًا بعد الريندر وقبل الشعار (الشعار لا يُدرَّج).

    يُستدعى من كل خلفيات التجميع عند تمرير --grade؛ بلا grade
    يُعاد المسار كما هو.
    """
    result = lut_grade_lib.apply_lut(out_path, grade)
    print(lut_grade_lib.format_report(result))
    return result["output"]


def cmd_assemble_openreel(cfg, run_dir, title, out_path,
                          watermark_on=True, cards_dir=None, grade=None):
    """تجميع عبر الوضع التلقائي لـOpenReel (خلفية بديلة ثالثة).

    يبني مشروع openreel-auto v1 JSON من البيان ويستدعي
    `render.py`؛ يحفظ المشروع في run_dir/openreel-project.json.
    Concat يبقى الافتراضي — وهذه الخلفية أبطأ (~3× الزمن
    الحقيقي بلا GPU) لكنها تقبل مشاريع openreel-edit من المحرر.
    """
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise openreel_lib.OpenReelError(
            "ملف البيان غير موجود — شغّل produce أولًا: %s"
            % manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    render_path = expand(cfg["openreel"]["render"])
    project_path = os.path.join(run_dir, "openreel-project.json")
    project = openreel_lib.build_project(manifest, title, assets_dir,
                                         cfg["video"])
    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    result = openreel_lib.render_project(render_path, project_path,
                                         out_path)
    print("صُدّر الفيديو عبر OpenReel: %s (%.0f ثانية ريندر، %.1f ميجا)"
          % (result["output"], result["seconds"],
             result["size_bytes"] / (1024 * 1024)))
    out = _apply_grade(result["output"], grade) if grade else result["output"]
    out = _finish_video(out, watermark_on, cards_dir)
    _write_assemble_manifest(cfg, run_dir, title, out, "openreel")
    return out, result["seconds"]


# ------------------------------------------------------------ clean-audio
def cmd_clean_audio(cfg, input_path, output_path, threshold, margin, force):
    """قص صمت الصوت الخام عبر Auto-Editor (خطوة اختيارية).

    للصوت الخام قبل التجميع فقط — أبدًا على السرد النهائي
    (وقفاته مقصودة دراميًا). يطبع تحذيرًا بذلك في كل تشغيل.
    """
    print("تحذير: هذه الخطوة للصوت الخام فقط — لا تستخدمها على السرد "
          "النهائي (وقفاته مقصودة دراميًا والكتابة مبنية عليها).")
    try:
        import subprocess as _sp
        before = _sp.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", input_path],
            capture_output=True, text=True, timeout=30)
        dur_before = float(before.stdout.strip())
    except Exception:
        dur_before = None
    result = autoedit.clean_audio(
        input_path, output_path, threshold=threshold, margin=margin,
        force=force,
        studio_dir=os.path.dirname(os.path.abspath(__file__)))
    try:
        import subprocess as _sp
        after = _sp.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1", output_path],
            capture_output=True, text=True, timeout=30)
        dur_after = float(after.stdout.strip())
    except Exception:
        dur_after = None
    if dur_before is not None and dur_after is not None:
        print("نُظّف الصوت: %.2f ث ← %.2f ث (%.1f ثانية عمل)"
              % (dur_before, dur_after, result["seconds"]))
    else:
        print("نُظّف الصوت: %s (%.1f ثانية عمل)"
              % (result["output"], result["seconds"]))
    return result


# ------------------------------------------------------------ fx
def cmd_fx(cfg, image, output, duration, text, audio, zoom_to, fontsize):
    """تركيبة MoviePy اختيارية: Ken Burns + نص عربي متحرك + صوت.

    يعمل فقط من بيئة MoviePy (والا فشل برسالة واضحة).
    """
    result = moviepy_fx.render_fx(
        image, output, duration, text=text, audio_path=audio,
        zoom_to=zoom_to, fontsize=fontsize)
    print("رُكّبت التركيبة: %s (%.1f ثانية عمل، %.1f ميجا)"
          % (result["output"], result["seconds"],
             result["size_bytes"] / 1024 / 1024))
    return result


# ------------------------------------------------------------ karaoke-ass
def cmd_karaoke_ass(cfg, audio, ass_path, model, max_chars, lang="ar"):
    """كابشنات كاريوكي (كلمة-بكلمة) من faster-whisper — منطق Capite
    مُعاد تنفيذه (انظر lib/capite_captions.py). خيار تجريبي فقط؛
    راجع النص قبل النشر (small يخطئ في ~22% من الكلمات).
    مع lang="en" (الموجة الأولى — W5): النسخ إنجليزي والملف
    يُبنى بالمسار اللاتيني LTR (words_to_latin_ass) بدل مسار
    الكاريوكي العربي — والموضع أسفل الصورة فقط في المسارين."""
    lang = i18n_lib.normalize_lang(lang)
    if lang == "en":
        words, text = whisper_captions.transcribe_words(
            audio, model=model, language="en")
        if not words:
            raise capite_captions.CapiteError(
                "لم يسمع whisper أي كلام في: %s" % audio)
        ass_text, groups = latin_captions.words_to_latin_ass(words)
        out_dir = os.path.dirname(os.path.abspath(ass_path))
        os.makedirs(out_dir, exist_ok=True)
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_text)
        n_words = sum(len(ln) for g in groups for ln in g["lines"])
        print("كُتبت %d كلمة لاتينية (LTR) في %d مجموعة في %s"
              % (n_words, len(groups), ass_path))
        print("النص المسموع: %s" % text)
        print("راجع النص قبل النشر — حتى موديل small يخطئ في ~22% "
              "من كلمات سرد Piper (WHISPER-TEST.md).")
        return groups
    groups, text = capite_captions.karaoke_ass(
        audio, ass_path, model=model, max_chars=max_chars)
    n_words = sum(len(ln) for g in groups for ln in g["lines"])
    print("كُتبت %d كلمة في %d مجموعة في %s"
          % (n_words, len(groups), ass_path))
    print("النص المسموع: %s" % text)
    print("راجع النص قبل النشر — حتى موديل small يخطئ في ~22% من "
          "كلمات سرد Piper (WHISPER-TEST.md).")
    return groups


# ------------------------------------------------------------ trim
def cmd_trim(cfg, input_path, output_path, start, end, duration, exact):
    """قص مقطع بلا إعادة ترميز (ما يعادل LosslessCut تحت الغطاء).

    البداية/النهاية تلتصق بحدود الإطارات (±~0.2 ث)؛ --exact
    يعيد الترميز لقطع دقيق بالإطار.
    """
    result = trim.trim_lossless(input_path, output_path, start=start,
                                end=end, duration=duration, exact=exact)
    got = result["out_duration"]
    print("قُصّ المقطع: %s (المطلوب %.2f ث، الناتج %.2f ث، %.1f ثانية "
          "عمل)%s"
          % (result["output"], result["duration"],
             got if got is not None else -1, result["seconds"],
             " — إعادة ترميز دقيقة" if exact else " — بلا إعادة ترميز"))
    if not exact:
        print("ملحوظة: القص بلا إعادة ترميز يلتصق بحدود الإطارات "
              "(±~0.2 ث)؛ استخدم --exact لقطع دقيق بالإطار.")
    return result


# ------------------------------------------------------------ thumbnail
def cmd_thumbnail(cfg, video_path, hook, out_path, at_seconds=None,
                  width=thumbnail.WIDTH, height=thumbnail.HEIGHT,
                  fontsize=thumbnail.FONTSIZE,
                  margin_v=thumbnail.MARGIN_V, max_chars=20):
    out, at, lines = thumbnail.make_thumbnail(
        video_path, hook, out_path, at_seconds, width=width, height=height,
        fontsize=fontsize, margin_v=margin_v, max_chars=max_chars)
    w, h = thumbnail.probe_image(out)
    print("صورة مصغرة: %s (%dx%d، لقطة عند %.1f ثانية)" % (out, w, h, at))
    print("نص الهوك: %s" % " / ".join(lines))
    return out


# ------------------------------------------------------------------- run
def _request_chat_fn(cfg):
    """chat_fn لتدفق request: نص فقط فوق _llm_chat (جولة v0.1.43)."""
    def chat_fn(prompt):
        text, _via, _model = _llm_chat(cfg, prompt,
                                       max_tokens=800, temperature=0.7)
        return text
    return chat_fn


def _request_run_fn(cfg):
    """run_fn لتدفق request: غلاف فوق cmd_run (جولة v0.1.43).

    بلا مشروع OpenMontage جاهز يرفع NoProjectError فيتحول الطلب
    إلى «queued» (القصة محفوظة في الطابور) بدل فشل كاذب — بناء
    مشروع من نص حر لا يوجد في الشجرة بعد (بند لاحق موثَّق).
    """
    def run_fn(cfg, story_text, title, project, out_path,
               allow_fallback, queue_number):
        project = project or (KNOWN_PROJECTS.get(queue_number)
                              or (None, None))[1]
        if not project:
            raise request_flow.NoProjectError(queue_number, title)
        slug = request_flow.extract_title(story_text)
        rc = cmd_run(cfg, slug, project, out_path, allow_fallback)
        if rc != 0:
            raise request_flow.RequestFlowError(
                "فشل خط الإنتاج (cmd_run رجع %d)" % rc)
        return out_path
    return run_fn


def cmd_run(cfg, story, project, out_path, allow_fallback, dry_run=False,
            backend="concat", watermark_on=True, cards_dir=None,
            grade=None, lang="ar", resume=None, voice=None):
    runs_dir = expand(cfg["paths"]["runs_dir"])
    if backend not in ("concat", "headless", "mlt", "openreel"):
        print(i18n_lib.t("run_unknown_backend", lang, backend))
        return 1
    # صوت الراوي (الموجة الأولى — W3): --voice قد يكون اسم محرك أو
    # اسم موديل Piper رجاليًا؛ والاسم غير المعروف أو غير الذكوري
    # يُرفض بخطأ واضح قبل أي خطوة. السرد نفسه من أصول مشروع
    # OpenMontage الجاهز، فالصوت هنا يُتحقق منه ويُسجَّل في سجل
    # التشغيل (ولا يُعاد تركيب سرد المشروع الجاهز في هذا الأمر).
    try:
        _run_engine, _run_model = _resolve_voice_arg(voice)
    except ValueError as e:
        print(str(e))
        return 2
    voice_engine = _run_engine or _default_voice(cfg)
    if dry_run:
        # وضع تجريبي: يطبع ما سيفعله التشغيل دون استدعاء أي طبقة.
        root = expand(cfg["openmontage"]["root"])
        proj = os.path.join(root, "projects", project)
        print(i18n_lib.t("run_dry_header", lang))
        print("اللغة: %s — صوت السرد: %s%s"
              % (lang, voice_engine,
                 " (%s)" % _run_model if _run_model else ""))
        print(i18n_lib.t("run_dry_scenario", lang, story,
                         cfg["omniroute"]["model"],
                         cfg["omniroute"].get("fallback_model"),
                         cfg["omniroute"].get("retries", 1)))
        print(i18n_lib.t("run_dry_fallback_line", lang,
                         i18n_lib.t("run_dry_fallback_allowed", lang)
                         if allow_fallback
                         else i18n_lib.t("run_dry_fallback_denied", lang)))
        print(i18n_lib.t("run_dry_produce", lang, proj,
                         i18n_lib.t("run_dry_exists", lang)
                         if os.path.isdir(proj)
                         else i18n_lib.t("run_dry_missing", lang)))
        print(i18n_lib.t("run_dry_assemble", lang, backend, out_path,
                         int(cfg["video"]["width"]),
                         int(cfg["video"]["height"])))
        print(i18n_lib.t("run_dry_logo", lang,
                         i18n_lib.t("run_dry_logo_yes", lang)
                         if watermark_on
                         else i18n_lib.t("run_dry_logo_no", lang)))
        print(i18n_lib.t("run_dry_cards", lang,
                         cards_dir
                         or i18n_lib.t("run_dry_cards_no", lang)))
        if grade:
            print(i18n_lib.t("run_dry_grade", lang, grade,
                             lut_grade_lib.PRESETS[grade]))
        if backend == "concat":
            print(i18n_lib.t("run_dry_concat_bin", lang,
                             expand(cfg["concat"]["bin"]),
                             i18n_lib.t("run_dry_exists", lang)
                             if os.path.isfile(expand(cfg["concat"]["bin"]))
                             else i18n_lib.t("run_dry_missing", lang)))
        elif backend == "headless":
            print(i18n_lib.t("run_dry_headless", lang,
                             expand(cfg["headless"]["editor"]),
                             i18n_lib.t("run_dry_exists", lang)
                             if os.path.isfile(
                                 expand(cfg["headless"]["editor"]))
                             else i18n_lib.t("run_dry_missing", lang)))
        elif backend == "mlt":
            print(i18n_lib.t("run_dry_melt", lang,
                             i18n_lib.t("run_dry_exists", lang)
                             if shutil_which("melt")
                             else i18n_lib.t("run_dry_missing", lang)))
        if backend == "openreel":
            print(i18n_lib.t("run_dry_openreel", lang,
                             expand(cfg["openreel"]["render"]),
                             i18n_lib.t("run_dry_exists", lang)
                             if os.path.isfile(
                                 expand(cfg["openreel"]["render"]))
                             else i18n_lib.t("run_dry_missing", lang)))
        print(i18n_lib.t("run_dry_rundir", lang, runs_dir))
        return 0
    # تعليم التشغيلات المنقطعة من جولات سابقة (جولة v0.1.41 —
    # بند 6): أي تشغيل ما زال running مع boot_id مختلف أو
    # عملية ميتة يُعلَّم crashed فيُستأنف لاحقًا.
    run_record.detect_crashed(runs_dir)
    _resume_plan = None
    if resume:
        # استئناف تشغيل منقطع: لا سجل جديد ولا مجلد جديد؛
        # الخطوات المكتملة تُتخطى فقط، والمدخلات الأصلية
        # تُستعاد من نقطة التفتيش عند غياب أعلام CLI.
        try:
            _record_path, _resume_plan = run_resume.prepare_resume(
                runs_dir, resume)
        except run_resume.ResumeError as e:
            print("تعذّر الاستئناف: %s" % e)
            return 1
        _ra = _resume_plan["resume_args"]
        story = story or _ra["story"]
        project = project or _ra["project"]
        backend = _ra["backend"] or backend
        out_path = out_path or _ra["out_path"]
        if _ra["watermark"] is not None:
            watermark_on = _ra["watermark"]
        cards_dir = cards_dir or _ra["cards_dir"]
        grade = grade or _ra["grade"]
        lang = _ra["lang"] or lang
        if _ra["allow_fallback"] is not None:
            allow_fallback = _ra["allow_fallback"]
        run_id = _resume_plan["run_id"]
        run_dir = _resume_plan["run_dir"]
        log = {"run": run_id, "story": story, "project": project,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {},
               "cost_usd": 0.0, "resumed": True,
               "resume_count": _resume_plan["resume_count"] + 1}
        print(i18n_lib.t("run_started", lang, run_id))
        print("استئناف من الخطوة: %s" % _resume_plan["next_step"])
    else:
        run_id, run_dir = new_run(runs_dir, story)
        log = {"run": run_id, "story": story, "project": project,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {},
               "cost_usd": 0.0}
        print(i18n_lib.t("run_started", lang, run_id))
        # سجل تشغيل (جولة v0.1.37): الإعدادات المحلولة قبل التنفيذ.
        _settings = run_record.resolve_settings(
            cfg, {"backend": backend, "grade": grade,
                  "watermark": watermark_on, "story": story,
                  "project": project})
        run_record.print_settings(_settings)
        _record_path, _ = run_record.begin_record(
            runs_dir, "run", _settings, run_id=run_id)
    log["voice"] = voice_engine
    log["voice_model"] = _run_model
    # سجل تشغيل بنيوي (جولة الأنماط W5b): ملف JSON واحد
    # runs/run-log-<معرّف>.json بمعرّف ارتباط وتوقيت المراحل
    # ورموز الأخطاء؛ لا يغيّر أي مخرج أو رمز خروج.
    _run_log = run_log_lib.RunLog("run", out_dir=runs_dir)
    try:
        # مدخلات نقاط التفتيش (جولة v0.1.41 — بند 6): تُحفظ
        # مع كل خطوة مكتملة ليستعيدها الاستئناف لاحقًا.
        _cp_inputs = {"story": story, "project": project,
                      "backend": backend, "out_path": out_path,
                      "watermark": watermark_on, "grade": grade,
                      "cards_dir": cards_dir, "lang": lang,
                      "allow_fallback": allow_fallback,
                      "voice": voice_engine, "voice_model": _run_model,
                      "run_dir": run_dir}
        # 1) السيناريو عبر OmniRoute (مع بديل موثق عند الفشل)
        with _run_log.stage("script"):
            if (_resume_plan is not None
                    and run_resume.should_skip("script", _resume_plan)):
                _script_result = run_resume.load_script_result(run_dir)
                title = _script_result["title"]
                log["steps"]["script"] = {"status": "skipped",
                                          "resumed": True}
                print("تخطَّت خطوة السيناريو (مكتملة من قبل)")
            else:
                # ذاكرة مراحل (جولة الأنماط W5a): مدخلات مطابقة
                # حرفيًا تعيد السيناريو المخزّن بلا استدعاء LLM؛
                # وأي فشل في الذاكرة يرجع للمسار العادي بصمت.
                _script_inputs = {
                    "story": story,
                    "lang": lang,
                    "model": cfg["omniroute"].get("model"),
                    "fallback_model": cfg["omniroute"].get(
                        "fallback_model"),
                    "allow_fallback": allow_fallback,
                    "prompt": SCRIPT_PROMPT.format(
                        story=STORY_TEXTS.get(story, story))}
                _cached_path = None
                try:
                    _cached_path = stage_cache_lib.StageCache().lookup(
                        "script", _script_inputs)
                except Exception:
                    _cached_path = None
                if _cached_path:
                    try:
                        with open(_cached_path, encoding="utf-8") as _sf:
                            result = json.load(_sf)
                        if (not isinstance(result, dict)
                                or not result.get("title")):
                            raise ValueError("سيناريو مخزّن غير صالح")
                        step = {"source": "stage-cache",
                                "status": "cached"}
                        with open(os.path.join(
                                run_dir, "script-ai.json"),
                                "w", encoding="utf-8") as _sf:
                            json.dump(result, _sf, ensure_ascii=False,
                                      indent=2)
                        print("استُخدم السيناريو المخزّن (ذاكرة المراحل)")
                    except Exception:
                        _cached_path = None
                if not _cached_path:
                    result, step = cmd_script(
                        cfg, story, allow_fallback, run_dir, lang=lang)
                    # يُخزَّن السيناريو الحقيقي فقط (لا البديل):
                    # بديل OpenMontage قد يخفي فشل LLM لاحقًا.
                    if (result is not None
                            and result.get("source") == "omniroute"):
                        try:
                            stage_cache_lib.StageCache().store(
                                "script", _script_inputs,
                                os.path.join(run_dir, "script-ai.json"))
                        except Exception:
                            pass
                log["steps"]["script"] = step
                if result is None:
                    raise RuntimeError("توقف خط الإنتاج: فشل توليد "
                                       "السيناريو وبلا بديل مسموح")
                title = result["title"]
                run_record.save_checkpoint(
                    _record_path, "script", inputs=_cp_inputs,
                    outputs={"title": title,
                             "script_file": "script-ai.json"})
        # 2) الإنتاج: تجهيز أصول OpenMontage
        t0 = time.time()
        with _run_log.stage("produce"):
            if (_resume_plan is not None
                    and run_resume.should_skip("produce", _resume_plan)):
                with open(os.path.join(run_dir, "manifest.json"),
                          encoding="utf-8") as _mf:
                    manifest = json.load(_mf)
                log["steps"]["produce"] = {"status": "skipped",
                                           "resumed": True,
                                           "images": len(manifest["images"]),
                                           "phrases": len(manifest["phrases"])}
                print("تخطَّت خطوة الإنتاج (مكتملة من قبل)")
            else:
                manifest = cmd_produce(cfg, project, run_dir)
                log["steps"]["produce"] = {"status": "ok",
                                           "seconds": round(time.time() - t0, 1),
                                           "images": len(manifest["images"]),
                                           "phrases": len(manifest["phrases"])}
                run_record.save_checkpoint(
                    _record_path, "produce", inputs=_cp_inputs,
                    outputs={"manifest_file": "manifest.json",
                             "images": len(manifest["images"]),
                             "phrases": len(manifest["phrases"])})
        # 3) التجميع والتصدير (Concat افتراضيًا، أو headless-editor أو MLT
        #    أو OpenReel) ثم شعار الصفحة وبطاقات الاقتباس الختامية
        #    (داخل assemble).
        t0 = time.time()
        with _run_log.stage("assemble"):
            if backend == "headless":
                out, secs = cmd_assemble_headless(
                    cfg, run_dir, title, out_path, watermark_on, cards_dir,
                    grade)
            elif backend == "mlt":
                out, secs = cmd_assemble_mlt(
                    cfg, run_dir, title, out_path, watermark_on, cards_dir,
                    grade)
            elif backend == "openreel":
                out, secs = cmd_assemble_openreel(
                    cfg, run_dir, title, out_path, watermark_on, cards_dir,
                    grade)
            else:
                out, secs = cmd_assemble(cfg, run_dir, title, out_path,
                                         watermark_on, cards_dir, grade)
            log["steps"]["assemble"] = {"status": "ok", "seconds": secs,
                                        "backend": backend, "output": out}
        # تسجيل الفيديو في ذاكرة المراحل (جولة الأنماط W5a):
        # تسجيل بلا نسخ وبلا إصابة تخطٍّ للتجميع في هذه الجولة؛
        # وأي فشل هنا لا يمسّ الفيديو المنتج.
        try:
            stage_cache_lib.StageCache().record(
                "video",
                {"title": title,
                 "manifest_hash": stage_cache_lib.hash_file(
                     os.path.join(run_dir, "manifest.json")),
                 "backend": backend, "grade": grade,
                 "watermark": watermark_on},
                out)
        except Exception:
            pass
        log["status"] = "done"
        print(i18n_lib.t("run_done", lang, out))
        run_record.finish_record(_record_path, "done", outputs=[out])
    except Exception as e:
        log["status"] = "failed"
        log["error"] = str(e)
        run_record.finish_record(_record_path, "failed", error=e)
        # المرحلة الفاشلة سجّلت الاستثناء نفسه أصلًا (عبر
        # stage()) — لا يُسجَّل مرة ثانية؛ والتسجيل هنا فقط
        # لخطأ وقع خارج أي مرحلة.
        if not _run_log.errors:
            _run_log.record_error(e, context="run")
        _run_log.finish("failed")
        _print_translated("فشل خط الإنتاج", e, "run", lang)
        write_log(run_dir, log)
        return 1
    _run_log.finish("ok", output={"video": out})
    write_log(run_dir, log)
    return 0


# ------------------------------------------------------------------ quick
_QUICK_PROMPT_AR = (
    "اكتب قصة قصيرة بعنوان «{title}» بصيغة الاستوديو: هوك صادم من "
    "جملة واحدة يخفي النهاية، ثم القصة في 3–4 جمل قصيرة (الجسم كله "
    "≤ 250 حرفًا — الفيديو الكامل 40–60 ثانية فقط)، قرار أخلاقي "
    "واحد ثم انقلاب أو عوض، ثم عبرة من سطر واحد تُستنتج من الأحداث "
    "لا تُلَقَّن، ثم سؤال ختامي محيّر. أرجعها بهذا الشكل بالضبط:\n"
    "هوك: <جملة واحدة>\n"
    "القصة: <نص القصة>\n"
    "العبرة: <سطر واحد>\n"
    "سؤال: <سؤال ختامي>")
_QUICK_PROMPT_EN = (
    "Write a short story titled \"{title}\" in the studio format: a "
    "shocking one-sentence hook that hides the ending, then the story "
    "in 3-4 short sentences (the story body between 450 and 600 "
    "characters — the whole video is only 40-60 seconds), one moral "
    "decision, "
    "then a twist or a reward, then a one-line moral drawn from the "
    "events, then a puzzling closing question. Return it in exactly "
    "this shape:\n"
    "HOOK: <one sentence>\n"
    "STORY: <the story text>\n"
    "MORAL: <one line>\n"
    "QUESTION: <closing question>")
_QUICK_LABELS = {
    "hook": ("هوك", "hook"),
    "body": ("القصة", "story"),
    "moral": ("العبرة", "moral"),
    "question": ("سؤال", "question"),
}
_QUICK_DEFAULT_QUESTION = {
    "ar": "لو كنت مكانه، كنت هتعمل إيه؟",
    "en": "What would you do if you were in their place?",
}


def _parse_quick_story(text, lang="ar"):
    """قسّم نص قصة مولّدة إلى {hook, body, moral, question}.

    يقبل الصيغة الموسومة (هوك:/القصة:/العبرة:/سؤال: أو
    HOOK:/STORY:/MORAL:/QUESTION:)؛ وبلاها يشتق الأجزاء من الجمل:
    الأولى هوك، والأخيرة سؤال إن انتهت بعلامة استفهام، وما قبلها
    عبرة، والوسط جسم القصة. يرفع ValueError عند نص بلا جمل صالحة."""
    import re
    lang = i18n_lib.normalize_lang(lang)
    text = (text or "").strip()
    if not text:
        raise ValueError("نص القصة المولّدة فارغ")
    parts = {}
    current = None
    rest_lines = []
    for line in text.splitlines():
        m = re.match(r"^\s*([^:：]{1,20})\s*[:：]\s*(.*)$", line.strip())
        label = None
        if m:
            head = m.group(1).strip().lower()
            for key, names in _QUICK_LABELS.items():
                if head in [n.lower() for n in names]:
                    label = key
                    break
        if label:
            current = label
            parts[current] = m.group(2).strip()
        elif current:
            parts[current] = (parts[current] + " " + line.strip()).strip()
        else:
            rest_lines.append(line.strip())
    if parts.get("hook") or parts.get("moral") or parts.get("question"):
        body = parts.get("body") or " ".join(
            l for l in rest_lines if l)
        hook = parts.get("hook") or ""
        moral = parts.get("moral") or ""
        question = parts.get("question") or ""
        if not hook or not body or not moral:
            raise ValueError("القصة المولّدة ناقصة الأجزاء (هوك/جسم/عبرة)")
        if not question:
            question = _QUICK_DEFAULT_QUESTION[lang]
        return {"hook": hook.strip(), "body": body.strip(),
                "moral": moral.strip(), "question": question.strip()}
    sentences = [s.strip() for s in
                 long_narration.split_sentences(text) if s.strip()]
    if len(sentences) < 3:
        raise ValueError("القصة المولّدة أقصر من أن تُقسَّم (هوك/جسم/عبرة)")
    hook = sentences[0]
    if sentences[-1].rstrip().endswith(("?", "؟")):
        question = sentences[-1]
        moral = sentences[-2]
        body = " ".join(sentences[1:-2])
    else:
        question = _QUICK_DEFAULT_QUESTION[lang]
        moral = sentences[-1]
        body = " ".join(sentences[1:-1])
    if not body:
        raise ValueError("القصة المولّدة بلا جسم بعد الهوك والعبرة")
    return {"hook": hook, "body": body, "moral": moral,
            "question": question}


def _quick_template_story(title, lang="ar"):
    """قصة مدمجة من القوالب (رجوع بلا LLM): قالب honesty_charity
    ببطل هو العنوان نفسه وموقف عام يختبر الأمانة — هوك جملة واحدة
    + عبرة + سؤال ختامي من القالب نفسه."""
    lang = i18n_lib.normalize_lang(lang)
    situation = ("faced a moment that tested his honesty"
                 if lang == "en"
                 else "واجه موقفًا يختبر أمانته")
    outline = story_templates_lib.build_scene_outline(
        "honesty_charity", title, hero=title, situation=situation,
        clips=6, lang=lang)
    scenes = outline["scenes"]
    story = {"hook": scenes[0]["prompt"],
             "body": " ".join(s["prompt"] for s in scenes[1:-1]),
             "moral": scenes[-1]["prompt"],
             "question": outline["closing_question"],
             "source": "template:honesty_charity"}
    return story


def _quick_llm_story(cfg, title, lang="ar"):
    """ولّد قصة quick عبر LLM بالموجّه حسب اللغة (W4). يرفع
    OmniRouteError عند فشل كل المزودين، وValueError عند نص ناقص."""
    lang = i18n_lib.normalize_lang(lang)
    prompt = (_QUICK_PROMPT_EN if lang == "en" else _QUICK_PROMPT_AR
              ).format(title=title)
    system = omniroute_client.load_system_prompt(lang)
    text, _via, _model = _llm_chat(cfg, prompt, max_tokens=800,
                                   temperature=0.7, system=system)
    story = _parse_quick_story(text, lang)
    story["source"] = "omniroute"
    return story


_QUICK_CHAPTER_MAX_SECONDS = 40.0


def _fit_quick_chapter(story, chapter_text, chapter_info, narr_dir,
                       voice_engine, model_path, lang):
    """قصّر فصل quick لميزانية 40 ثانية (الفيديو الكامل 40–60 ثانية).

    المقدمة (الهوك) ~13ث والخاتمة (السؤال) ~7ث ثابتتان تقريبًا،
    فيبقى للفصل (جسم + عبرة) 40ث. إن تجاوزت مدته المقاسة الحد،
    تُحذف جمل الجسم الأخيرة واحدة تلو الأخرى ويُعاد تركيب الفصل
    (العبرة والهوك والسؤال بلا مساس أبدًا) حتى يدخل في الميزانية
    أو يبقى جملة واحدة. يرجع (chapter_text, chapter_info) —
    وقد يكونان الأصلين بلا تغيير.
    """
    if chapter_info["duration"] <= _QUICK_CHAPTER_MAX_SECONDS:
        return chapter_text, chapter_info
    sentences = [s for s in long_narration.split_sentences(story["body"])
                 if s.strip()]
    trimmed = list(sentences)
    info = chapter_info
    text = chapter_text
    while (len(trimmed) > 1
           and info["duration"] > _QUICK_CHAPTER_MAX_SECONDS):
        trimmed = trimmed[:-1]
        text = (" ".join(trimmed) + " " + story["moral"]).strip()
        info = long_narration.synthesize_long(
            text, os.path.join(narr_dir, "chapter.wav"),
            voice=voice_engine, model=model_path, lang=lang)
    if info["duration"] > _QUICK_CHAPTER_MAX_SECONDS:
        print("تحذير: فصل quick ما زال %.1f ثانية بعد التقليص "
              "(الميزانية %.0f) — الفيديو الكامل قد يتجاوز 60 ثانية"
              % (info["duration"], _QUICK_CHAPTER_MAX_SECONDS))
    else:
        print("قُصّر فصل quick من %.1f إلى %.1f ثانية ليبقى الفيديو "
              "الكامل ضمن 40–60 ثانية"
              % (chapter_info["duration"], info["duration"]))
    return text, info


def cmd_quick(cfg, title, lang="ar", voice=None, out_path=None,
              dry_run=False, allow_fallback=False, publish=False):
    """أمر واحد `quick`: عنوان ← فيديو قصة قصيرة كامل بلا أسئلة.

    LLM بالموجّه حسب اللغة (أو قالب مدمج مع --allow-fallback عند
    غياب LLM — نفس دلالة allow_fallback في cmd_run)؛ سرد Piper
    (رجل، باللغة المطلوبة) + صور ثابتة مولّدة محليًا بحركة Ken Burns
    خفيفة عبر build_fast_draft (بلا انتظار GPU) + تجميع + شعار
    الصفحة؛ والكتابة أسفل الصورة فقط (مسار build_project نفسه)؛
    وبلا موسيقى أبدًا؛ وبلا نشر تلقائي — النشر فقط مع --publish
    الصريح. مع lang="en" يُكتب أيضًا ملف ASS لاتيني جانبي.
    يرجع 0 عند النجاح، و1 عند فشل الإنتاج، و2 عند وسائط غير صالحة.
    """
    lang = i18n_lib.normalize_lang(lang)
    title = (title or "").strip()
    if not title:
        print("عنوان القصة مطلوب: qisas quick \"عنوان القصة\"")
        return 2
    try:
        engine, model_path = _resolve_voice_arg(voice)
    except ValueError as e:
        print(str(e))
        return 2
    voice_engine = engine or _default_voice(cfg)
    runs_dir = expand(cfg["paths"]["runs_dir"])
    videos_dir = expand(cfg["paths"]["videos_dir"])
    out = expand(out_path) if out_path else os.path.join(
        videos_dir, "quick-%s.mp4" % time.strftime("%Y%m%d-%H%M%S"))
    if dry_run:
        print("== خطة quick (وضع تجريبي — لن يُنتج شيء) ==")
        print("العنوان: %s" % title)
        print("اللغة: %s" % lang)
        print("الصوت: %s%s" % (voice_engine,
                               " (%s)" % model_path if model_path else ""))
        print("الحركة: kenburns (صور ثابتة بحركة Ken Burns خفيفة — "
              "بلا انتظار GPU)")
        print("المخرج: %s" % out)
        print("السيناريو: LLM بالموجّه (%s)%s"
              % (lang,
                 " مع رجوع لقالب مدمج عند الفشل"
                 if allow_fallback else " — بلا رجوع عند الفشل"))
        print("النشر: %s" % ("مطلوب بعد الإنتاج (--publish)"
                             if publish
                             else "لا — لاحق بأمر publish الصريح"))
        if lang == "en":
            print(EN_VOICE_LICENSE_NOTE)
        return 0
    run_id, run_dir = new_run(runs_dir, "quick")
    log = {"run": run_id, "cmd": "quick", "title": title, "lang": lang,
           "voice": voice_engine, "voice_model": model_path,
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {}}
    try:
        try:
            story = _quick_llm_story(cfg, title, lang)
        except (omniroute_client.OmniRouteError, ValueError) as e:
            print("فشل توليد القصة عبر LLM: %s" % e)
            if not allow_fallback:
                raise RuntimeError(
                    "توقف quick: فشل توليد القصة وبلا بديل مسموح "
                    "(استخدم --allow-fallback لقالب مدمج)")
            story = _quick_template_story(title, lang)
            print("استُخدمت القصة المدمجة من القوالب: %s"
                  % story["hook"])
        log["steps"]["story"] = {"status": "ok",
                                 "source": story["source"],
                                 "hook": story["hook"]}
        print("الهوك: %s" % story["hook"])
        width = int(cfg["video"]["width"])
        height = int(cfg["video"]["height"])
        images = []
        for i, hue in enumerate(("gold", "earth", "green")):
            img_path = os.path.join(run_dir, "scene-%d.jpg" % (i + 1))
            demo.make_scene_image(img_path, width, height,
                                  hue=hue, seed=7 + i)
            images.append(img_path)
        narr_dir = os.path.join(run_dir, "narration")
        os.makedirs(narr_dir, exist_ok=True)
        intro_info = long_narration.synthesize_long(
            story["hook"], os.path.join(narr_dir, "intro.wav"),
            voice=voice_engine, model=model_path, lang=lang)
        chapter_text = (story["body"] + " " + story["moral"]).strip()
        chapter_info = long_narration.synthesize_long(
            chapter_text, os.path.join(narr_dir, "chapter.wav"),
            voice=voice_engine, model=model_path, lang=lang)
        chapter_text, chapter_info = _fit_quick_chapter(
            story, chapter_text, chapter_info, narr_dir,
            voice_engine, model_path, lang)
        chapter = long_video.chapter_from_text(
            title, chapter_text, chapter_info, images,
            moral=story["moral"])
        outro_info = long_narration.synthesize_long(
            story["question"], os.path.join(narr_dir, "outro.wav"),
            voice=voice_engine, model=model_path, lang=lang)
        spec = {"title": title, "hook": story["hook"],
                "intro": {"text": story["hook"],
                          "narration": intro_info["output"],
                          "duration": intro_info["duration"]},
                "outro": {"text": story["question"],
                          "narration": outro_info["output"],
                          "duration": outro_info["duration"]},
                "chapters": [chapter],
                "width": width, "height": height,
                "fps": int(cfg["video"]["fps"])}
        result = long_video.build_fast_draft(
            spec, out, voice=voice_engine, work_dir=run_dir)
        video = _finish_video(result["output"], True, None)
        log["steps"]["video"] = {"status": "ok", "output": video,
                                 "duration": result["duration"]}
        print("اكتمل quick: %s (%.1f ثانية)"
              % (video, result["duration"]))
        ass_path = None
        if lang == "en":
            try:
                with open(result["report"]["project_json"],
                          encoding="utf-8") as f:
                    project = json.load(f)
            except (OSError, ValueError) as e:
                print("تحذير: تعذّرت قراءة مشروع quick للكابشن (%s) — "
                      "الفيديو سليم" % e)
                project = None
            if project is not None:
                ass_path = _write_latin_ass_from_project(
                    project,
                    os.path.splitext(video)[0] + "-captions-en.ass")
                if ass_path:
                    log["captions_ass"] = ass_path
                    print("كابشن لاتيني (LTR): %s" % ass_path)
        story_record = dict(story)
        story_record.update({"lang": lang, "voice": voice_engine,
                             "output": video, "duration": result["duration"],
                             "captions_ass": ass_path})
        with open(os.path.join(run_dir, "quick-story.json"), "w",
                  encoding="utf-8") as f:
            json.dump(story_record, f, ensure_ascii=False, indent=2)
        log["status"] = "done"
        log["output"] = video
        log["duration"] = result["duration"]
        if publish:
            caption = "%s\n\n%s\n\n%s" % (story["hook"], story["moral"],
                                         story["question"])
            rc = cmd_publish(cfg, video, title, caption, lang=lang)
            log["publish_rc"] = rc
            write_log(run_dir, log)
            return rc
        print("النشر: لم يُنشر — انشر لاحقًا بأمر publish الصريح")
        write_log(run_dir, log)
        return 0
    except Exception as e:
        log["status"] = "failed"
        log["error"] = str(e)
        _print_translated("فشل quick", e, "quick", lang)
        write_log(run_dir, log)
        return 1


# ---------------------------------------------------------------- doctor
def cmd_check(cfg, video, long_mode=False, as_json=False,
              captions_dir=None, avatar_image=None,
              aspect_policy="native"):
    """فحص جودة فيديو قبل النشر (تقرير عربي PASS/FAIL).

    يرجع 0 إن نجحت كل الفحوصات، و1 عند أي فشل (أو تعذر القراءة).
    مع --captions يُدقَّق أيضًا تشكيل الكابشنات العربية في
    ملفات ASS بالمجلد (حروف متصلة، RTL، بلا U+FFFD).
    مع --avatar-image تُقارن نسبة أبعاد الفيديو بنسبة صورة
    الأفاتار (تحذير فقط — لا أثر في كود الخروج).
    """
    try:
        result = check_lib.run_checks(expand(video), long_mode=long_mode)
    except check_lib.CheckError as e:
        if as_json:
            print(json.dumps({"ok": False, "error": str(e)},
                             ensure_ascii=False))
        else:
            _print_translated("تعذر فحص الفيديو", e, "check")
        return 1
    if avatar_image:
        try:
            aspect = check_lib.check_avatar_aspect(
                expand(video), expand(avatar_image),
                policy=aspect_policy)
        except check_lib.CheckError as e:
            aspect = {"level": "warn", "detail": str(e)}
        result["avatar_aspect"] = aspect
        if aspect["level"] == "warn" and not as_json:
            print("تحذير — نسبة أبعاد الأفاتار: %s"
                  % aspect["detail"])
    # بيان المصدر (جولة v0.1.37): legacy تحذير فقط، لا فشل أبدًا؛
    # فيديو جديد بلا بيان (أو بيان مشوَّه) فشل.
    manifest_status, manifest_issues = manifest_lib.verify_manifest(
        expand(video))
    if not as_json:
        if manifest_status == "ok":
            print("بيان المصدر: سليم (البصمة مطابقة)")
        elif manifest_status in ("legacy", "mismatch"):
            print("تحذير — بيان المصدر: %s" % manifest_issues[0])
        else:
            print("بيان المصدر: %s" % "; ".join(manifest_issues))
    manifest_ok = manifest_status in ("ok", "legacy", "mismatch")
    # تأكيدات التغطية/الحدود (جولة v0.1.37 — مقترح tinker رقم 3):
    # تُشغَّل فقط عند وجود بيان فيه مشاهد موقَّتة، وتُلحق
    # بالتقرير قبل طباعته.
    manifest_data = (manifest_lib.load_manifest(expand(video))
                     if manifest_status in ("ok", "mismatch") else None)
    if manifest_data:
        try:
            extra = coverage_lib.extra_checks(expand(video),
                                              manifest_data)
            result["checks"].extend(extra)
            result["passed"] = all(c["ok"] for c in result["checks"])
        except Exception as e:
            if not as_json:
                print("تحذير: تعذرت تأكيدات التغطية (%s)" % e)
    # عيّنة سلوكية (جولة v0.1.37 — مقترح tinker رقم 6): 3 لقطات
    # + معاينة 3 ثوانٍ في runs/samples/<اسم الفيديو>/ — للمراجعة
    # البصرية السريعة بلا فتح الفيديو كاملًا. لا تؤثر في النتيجة.
    # في وضع --json تُتخطى كاملةً ليبقى المخرج JSON خالصًا.
    if not as_json:
        try:
            _samples_dir = os.path.join(
                expand(cfg["paths"]["runs_dir"]), "samples",
                os.path.splitext(os.path.basename(expand(video)))[0])
            _sample = check_lib.sample_video(expand(video), _samples_dir)
            print("عيّنة سلوكية: %s" % _samples_dir)
            for _frame in _sample["frames"]:
                print("  لقطة: %s" % _frame)
            print("  معاينة 3ث: %s" % _sample["preview"])
        except Exception as e:
            print("تحذير: تعذرت العيّنة السلوكية (%s)" % e)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(check_lib.format_report(result))
    if captions_dir:
        try:
            ass_result = ass_shaping_lib.audit_ass_dir(captions_dir)
        except FileNotFoundError as e:
            if as_json:
                print(json.dumps({"ok": False, "error": str(e)},
                                 ensure_ascii=False))
            else:
                print("تعذر تدقيق الكابشنات: %s" % e)
            return 1
        if as_json:
            print(json.dumps(ass_result, ensure_ascii=False, indent=2))
        else:
            print(ass_shaping_lib.format_report(ass_result))
        return 0 if (result["passed"] and ass_result["ok"]
                     and manifest_ok) else 1
    return 0 if (result["passed"] and manifest_ok) else 1


def cmd_avatar_job(cfg, args):
    """أمر تحقق نحيف لوظيفة أفاتار (جولة v0.1.38 §1+5).

    --validate job.json [--profile NAME]: تحقق + طباعة أعلام
    الملف؛ خروج 0 «وظيفة الأفاتار سليمة» أو 1 + خطأ عربي.
    --template [--scene-type S]: اطبع وظيفة مثال JSON.
    --list-profiles: الملفات الثلاثة + أعلامها.
    """
    if args.list_profiles:
        for name in avatar_profiles_lib.list_profiles():
            profile = avatar_profiles_lib.get_profile(name)
            flags = avatar_profiles_lib.profile_flags(name)
            print("%s (%s، %d GPU): %s"
                  % (name, profile.get("resolution", "?"),
                     profile.get("gpus", 0), " ".join(flags)))
        return 0
    if args.template:
        print(json.dumps(
            avatar_job_lib.job_template(
                scene_type=args.scene_type or "narration"),
            ensure_ascii=False, indent=2))
        return 0
    if args.validate:
        try:
            job = avatar_job_lib.load_job(expand(args.validate))
        except avatar_job_lib.AvatarJobError as e:
            print("وظيفة الأفاتار غير سليمة: %s" % e)
            return 1
        profile_name = (args.profile
                        or job["settings"].get("profile")
                        or "t4x2-int8")
        try:
            flags = avatar_profiles_lib.profile_flags(profile_name)
        except avatar_profiles_lib.AvatarProfilesError as e:
            print("وظيفة الأفاتار غير سليمة: %s" % e)
            return 1
        print("وظيفة الأفاتار سليمة")
        print("الملف: %s" % profile_name)
        print("الأعلام: %s" % " ".join(flags))
        return 0
    print("لازم أحد: --validate أو --template أو --list-profiles")
    return 2


def cmd_manifest(cfg, video, title=None, hook=None, story=None):
    """ولّد بيان مصدر لفيديو موجود (جولة v0.1.37).

    مصدر يدوي — لفيديوهات قديمة أو منقولة بلا بيان (مثل عائشة
    ج1 والنجار). البيان المولَّد هنا يوثق ما هو معروف فقط؛
    الحقول غير المعروفة تبقى فارغة بصراحة.
    """
    video = expand(video)
    if not os.path.isfile(video):
        print("ملف الفيديو غير موجود: %s" % video)
        return 1
    try:
        man = manifest_lib.build_manifest(
            video,
            title=title or os.path.splitext(os.path.basename(video))[0],
            hook=hook or "", story=story or "", source="manual")
    except Exception as e:
        print("تعذرت كتابة البيان: %s" % e)
        return 1
    path = manifest_lib.write_manifest(video, man)
    print("بيان المصدر: %s" % path)
    return 0


def cmd_fix_audio(cfg, video, scene_audio=None, out_path=None,
                  denoise=False, loudnorm=False):
    """إصلاح فجوات الصمت في فيديو (ضجيج وردي + صوت المشاهد).

    مع --denoise يزيل ضجيج الخلفية بعده (afftdn)، ومع --loudnorm
    يطبّع الجهارة إلى -16 LUFS بعدهما (loudnorm) — كل مرور
    بملف ناتج خاص به. يرجع 0 إن نجح كل شيء أو كان الفيديو
    سليمًا أصلًا، و1 عند أي فشل.
    """
    try:
        result = fix_audio_lib.fix_silence_gaps(
            expand(video), scene_audio_paths=scene_audio,
            out_path=expand(out_path) if out_path else None)
    except fix_audio_lib.FixAudioError as e:
        print("فشل إصلاح الصوت: %s" % e)
        return 1
    print(fix_audio_lib.format_report(result))
    out = result["output"]
    if denoise:
        try:
            result = fix_audio_lib.denoise_audio(out)
        except fix_audio_lib.FixAudioError as e:
            print("فشل إزالة الضجيج: %s" % e)
            return 1
        print(fix_audio_lib.format_audio_pass_report(result))
        out = result["output"]
    if loudnorm:
        try:
            result = fix_audio_lib.normalize_loudness(out)
        except fix_audio_lib.FixAudioError as e:
            print("فشل تطبيع الجهارة: %s" % e)
            return 1
        print(fix_audio_lib.format_audio_pass_report(result))
        out = result["output"]
    return 0


def cmd_grade(cfg, video, preset, out_path=None, list_presets=False):
    """تدرج لوني على فيديو بـpreset جاهز (lut3d).

    مع --list-presets يطبع الـpresets المتاحة فقط. يرجع 0 عند
    النجاح و1 عند أي فشل.
    """
    if list_presets:
        for p in lut_grade_lib.list_presets():
            print("%s — %s" % (p["name"], p["description"]))
        return 0
    try:
        result = lut_grade_lib.apply_lut(
            expand(video), preset,
            expand(out_path) if out_path else None)
    except lut_grade_lib.LutError as e:
        print("فشل التدرج اللوني: %s" % e)
        return 1
    print(lut_grade_lib.format_report(result))
    return 0


def cmd_srt_ass(cfg, srt_path, ass_path, font_size=52):
    """حوّل ملف SRT إلى ASS بنمط subs/ (نفس الخط والمحاذاة).

    يرجع 0 عند النجاح و1 عند ملف مفقود أو بلا عبارات صالحة.
    """
    try:
        phrases, skipped = whisper_captions.srt_to_ass(
            expand(srt_path), expand(ass_path), font_size=font_size)
    except whisper_captions.WhisperError as e:
        print("فشل تحويل SRT: %s" % e)
        return 1
    print("كُتب %d عبارة في %s" % (len(phrases), expand(ass_path)))
    if skipped:
        print("تُخطّيت %d كتلة (فارغة أو زمن تالف)" % skipped)
    return 0


def cmd_init(cfg, args):
    """معالج الإعداد التفاعلي — يكتب config.yaml.

    بلا أعلام: يسأل المستخدم بالعربية. مع أي علم: يعمل بلا
    تفاعل بالقيم الممررة + الافتراضيات للباقي.
    """
    config_path = expand(args.config) if args.config else os.path.join(
        STUDIO_DIR, "config.yaml")
    flags = {}
    for key, attr in (("page_id", "page_id"),
                      ("channel_id", "channel_id"),
                      ("voice", "voice"),
                      ("morning", "morning"),
                      ("evening", "evening"),
                      ("queue_file", "queue_file"),
                      ("page_name", "page_name"),
                      ("logo_file", "logo_file"),
                      ("payment_number", "payment_number")):
        value = getattr(args, attr, None)
        if value is not None:
            flags[key] = value
    if not flags:
        flags = None
    return init_wizard.run_wizard(cfg, config_path, flags=flags,
                                  force=args.force,
                                  check_only=args.check_only)


def cmd_llm_status(cfg, lang="ar"):
    """حالة مزودي الذكاء: السلسلة المهيأة + التهدئة + عدادات
    اليوم (قراءة فقط — بلا أي استدعاء حي)."""
    cfg_o = cfg.get("omniroute", {}) if isinstance(cfg, dict) else {}
    providers = omniroute_client.providers_from_config(cfg_o)
    runs_dir = expand(cfg["paths"]["runs_dir"])
    state = llm_state.load_state(runs_dir)
    print(i18n_lib.t("llm_chain", lang))
    for i, p in enumerate(providers, 1):
        print("  %d) %s (%s)" % (i, p["model"], p["kind"]))
    for line in llm_state.status_lines(
            state, [p["model"] for p in providers]):
        print(line)
    # توفر Ollama الحي (جولة v0.1.39 — ساق أخيرة محلية): فحص
    # خفيف بلا توليد؛ ولا يرفع أبدًا.
    _ollama_legs = [p for p in providers if p.get("kind") == "ollama"]
    if _ollama_legs:
        _ol = _ollama_legs[0]
        _st = omniroute_client.ollama_status(
            _ol.get("base_url"), _ol.get("model"))
        if _st.get("available"):
            print(i18n_lib.t("llm_ollama_ok", lang, _st.get("model")))
        else:
            print(i18n_lib.t("llm_ollama_down", lang,
                             (_st.get("detail")
                              or i18n_lib.t("llm_ollama_down_default",
                                            lang))))
    return 0


def cmd_debug_config(profile=None, cli_overrides=None):
    """اعرض الإعداد الفعّال ومصدر كل قيمة (قراءة فقط).

    بروفايل غير موجود أو إعداد تالف ← رسالة عربية وخروج 2
    (بلا رجوع صامت لافتراضي يخفي المشكلة).
    """
    try:
        resolved = profiles_lib.resolve(
            profile, studio_root=STUDIO_DIR,
            cli_overrides=cli_overrides or [])
    except profiles_lib.ProfileError as e:
        print(str(e))
        return 2
    print(profiles_lib.format_diagnosis(resolved))
    return 0


def cmd_doctor(cfg, fix=False, accounts_flag=False, llm_flag=False,
               lang="ar", as_json=False):
    """فحص بيئة studio (تقرير PASS/FAIL صادق).

    --fix يصلح ما يمكن (config.yaml من المثال + إنشاء مجلدي
    الفيديو والتشغيل) ثم يعيد الفحص.
    --accounts يضيف قسمًا منفصلًا بعدّاده الخاص لفحوصات الحسابات
    (فيسبوك/يوتيوب/Veo/TikTok/Instagram — قراءة فقط).
    --llm يضيف قسمًا منفصلًا لفحوصات سلسلة LLM (بوابة
    OmniRoute + مساعد Gemini — قراءة فقط).
    --json (ع20) يرجع وثيقة واحدة
    {"ok", "problems", "warnings", "checks": [{id, status, message,
    fix}]} (الأساسية + فحص الترخيص + فحوص المضيف) وخروج 7 عند
    أي FAIL؛ ومع --fix تُضاف fixed/unfixed. أقسام --accounts
    و--llm لا تدخل وثيقة JSON.

    (الجولة v0.1.41: سطرا الغلاف هنا مترجمان؛ وجسم تقرير
    lib/doctor.py يبقى عربيًا — خارج الحزمة.)
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if as_json:
        from lib import cli_output as _cli_output
        out = _cli_output.Output(json_mode=True)
        checks = doctor.run_checks(cfg)
        fixed_names = []
        unfixed_names = []
        if fix:
            fixed = doctor.apply_fixes(checks, cfg, studio_dir=here)
            checks = fixed["checks"]
            fixed_names = fixed["fixed"]
            unfixed_names = fixed["unfixed"]
        checks = checks + [license_lib.doctor_check()]
        checks = checks + doctor.run_host_checks(cfg)
        report = doctor.to_json_report(checks)
        if fix:
            report["fixed"] = fixed_names
            report["unfixed"] = unfixed_names
        out.result(report)
        return 0 if report["ok"] else doctor.DOCTOR_FAIL_EXIT
    if fix:
        initial = doctor.run_checks(cfg)
        fixed = doctor.apply_fixes(initial, cfg, studio_dir=here)
        if fixed["fixed"]:
            print("أُصلح: %s" % "، ".join(fixed["fixed"]))
        if fixed["unfixed"]:
            print("تعذّر إصلاح: %s" % "، ".join(fixed["unfixed"]))
        checks = fixed["checks"]
    else:
        checks = doctor.run_checks(cfg)
    # فحص الترخيص (جولة v0.1.43): حالة التجربة/الرخصة — يرفع
    # عدّاد doctor الكلي إلى 28 (27 في run_checks + هذا الفحص).
    checks = checks + [license_lib.doctor_check()]
    text, errors, warnings = doctor.format_report(checks)
    print(text)
    if accounts_flag:
        from lib import accounts as accounts_lib
        acc = accounts_lib.run_account_checks(cfg)
        acc_text, acc_errors, acc_warnings = doctor.format_report(acc)
        print(i18n_lib.t("doctor_accounts_section", lang, len(acc)))
        print(acc_text)
        errors += acc_errors
        warnings += acc_warnings
    if llm_flag:
        llm_checks = doctor.run_llm_checks(cfg)
        llm_text, llm_errors, llm_warnings = doctor.format_report(
            llm_checks)
        print(i18n_lib.t("doctor_llm_section", lang, len(llm_checks)))
        print(llm_text)
        errors += llm_errors
        warnings += llm_warnings
    return 0 if errors == 0 else 1


def cmd_protect(cfg):
    """فحص حماية المشروع — تقرير عربي واحد: سلامة الملفات +
    صلاحياتها + مسح الأسرار + آخر نسخة احتياطية.
    قراءة فقط — لا يحذف ولا يحجر ولا يعدّل أي ملف.
    الخروج 1 عند أي خطأ أساسي، و0 مع التحذيرات أو الفحوصات
    غير المتاحة (تُطبع كـ [غير متاح])."""
    results = protect_lib.run_all()
    text, errors, _warnings = protect_lib.format_report(results)
    print(text)
    return 0 if errors == 0 else 1


# ------------------------------------------------------------------- demo
def cmd_demo(cfg, out_path=None, backend="headless"):
    """نفّذ القصة التجريبية المدمجة (مسار مجاني فقط)."""
    if out_path is None:
        out_path = os.path.join(
            expand(cfg["paths"]["videos_dir"]),
            "demo-%s.mp4" % time.strftime("%Y%m%d-%H%M%S"))
    # سجل تشغيل (جولة v0.1.37).
    _demo_settings = run_record.resolve_settings(
        cfg, {"backend": backend, "story": "demo"})
    run_record.print_settings(_demo_settings)
    _demo_record, _ = run_record.begin_record(
        expand(cfg["paths"]["runs_dir"]), "demo", _demo_settings)
    try:
        result = demo.run_demo(cfg, expand(out_path), backend=backend)
    except Exception as e:
        run_record.finish_record(_demo_record, "failed", error=e)
        raise
    run_record.finish_record(_demo_record, "done",
                             outputs=[result["output"]])
    # بيان مصدر (جولة v0.1.37).
    try:
        _demo_scenes = [
            {"scene": i + 1, "text": s}
            for i, s in enumerate(demo.load_demo()["scenes"])]
        _man = manifest_lib.build_manifest(
            result["output"], title=result["title"], hook=result["hook"],
            story="\n\n".join(demo.load_demo()["scenes"]),
            moral=result["moral"], source="demo",
            scenes=_demo_scenes,
            narration={"voice": (cfg.get("narration") or {}).get(
                "voice", "piper")},
            extra={"backend": backend})
        _mp = manifest_lib.write_manifest(result["output"], _man)
        print("بيان المصدر: %s" % _mp)
    except Exception as e:
        print("تحذير: تعذرت كتابة بيان المصدر (%s) — الفيديو سليم" % e)
    print("فيديو التجربة: %s (%.1f ثانية، %d مشاهد، %.1f ميجا، "
          "%.0f ثانية ريندر)"
          % (result["output"], result["duration"],
             len(demo.load_demo()["scenes"]),
             result["size_bytes"] / (1024 * 1024), result["seconds"]))
    print("العنوان: %s" % result["title"])
    print("الهوك: %s" % result["hook"])
    print("العبرة: %s" % result["moral"])
    return result


# ---------------------------------------------------------------- publish
YT_DEFAULT_TAGS = ["قصص وعبر", "قصص واقعية", "قصص مؤثرة", "حكايات"]


def cmd_publish(cfg, video, title, caption, thumbnail=None,
                platforms=("facebook", "youtube"), page_id=None,
                schedule=None, privacy=None, tags=None, dry_run=False,
                skip_check=False, skip_caption_check=False,
                allow_missing_manifest=False, generate_meta=False,
                part=1, parts=1, lang="ar", ai_voice=False):
    """انشر فيديوًا واحدًا على فيسبوك و/أو يوتيوب.

    يرجع 0 فقط إن نُشر على كل المنصات المطلوبة فعلًا؛ وإن نُشر بعضها
    فقط (أو كُتبت حزمة يوتيوب اليدوية بدل الرفع) يرجع 1 مع شرح
    ما بقي. --dry-run يطبع الحمولة الدقيقة دون نشر أي شيء.
    فحص امتثال الكابشن مسبق افتراضيًا (يرفض أي بوابة متابعة/
    تعليق)؛ و--skip-caption-check للتجاوز الصريح فقط.

    (الجولة v0.1.41: سطور البوابات ونتائج المنصات هنا مترجمة؛
    ونصوص المكتبات — بيان المصدر وcaption_check وcheck
    وsocial_lib — تبقى عربية.)
    """
    video = expand(video)
    if not os.path.isfile(video):
        print(i18n_lib.t("publish_video_missing", lang, video))
        return 1
    # بوابة بيان المصدر (جولة v0.1.37): فيديو جديد بلا بيان لا يُنشر
    # إلا بتجاوز صريح؛ legacy تحذير فقط؛ عدم تطابق البصمة تحذير
    # (الفيديو تغيّر بعد البيان — غالبًا إضافة شعار).
    manifest_status, manifest_issues = manifest_lib.verify_manifest(video)
    if manifest_status == "missing" and not dry_run \
            and not allow_missing_manifest:
        print(i18n_lib.t("publish_manifest_reject", lang,
                         manifest_issues[0]))
        print(i18n_lib.t("publish_manifest_hint", lang, video))
        print(i18n_lib.t("publish_manifest_allow", lang))
        return 1
    if manifest_status in ("legacy", "mismatch", "invalid"):
        print(i18n_lib.t("publish_manifest_warn", lang,
                         "; ".join(manifest_issues)))
    elif manifest_status == "missing":
        print(i18n_lib.t("publish_manifest_warn", lang,
                         manifest_issues[0])
              + (" (في النشر الحقيقي يُرفض الفيديو الجديد بلا بيان)"
                 if lang == "ar"
                 else " (in a real publish, a new video without a "
                      "manifest is refused)"))
    if schedule and int(schedule) <= int(time.time()):
        print(i18n_lib.t("publish_schedule_past", lang))
        return 1
    # سطر الإفصاح (جولة v0.1.43): صوت Supertonic في بيان الفيديو
    # يفرض «صوت مولّد بالذكاء الاصطناعي» في الكابشن والوصف —
    # يُكتشف من البيان تلقائيًا، أو بعلَم --ai-voice الصريح.
    if not ai_voice:
        _man = manifest_lib.load_manifest(video)
        if _man and ((_man.get("narration") or {}).get("voice")
                     == "supertonic-M1"):
            ai_voice = True
    page_id = page_id or cfg.get("publish", {}).get("page_id") or ""
    privacy = privacy or cfg.get("publish", {}).get("youtube_privacy") \
        or "public"
    # توليد بيانات النشر (جولة v0.1.39 — --generate-meta): العنوان
    # والوصف والوسوم من نص القصة عبر سلسلة LLM مع بديل محلي
    # بلا شبكة عند الفشل؛ والقيم الصريحة (--caption/--tags)
    # تغلب المولّدة. يُبنى قبل الكابشن والوصف أدناه.
    if generate_meta:
        def _meta_chat(prompt):
            text, _via, _model = _llm_chat(
                cfg, prompt, max_tokens=300, temperature=0.7)
            return text
        _meta = publish_meta_lib.generate_publish_meta(
            {"title": title, "text": caption or title},
            part=part, parts=parts, chat_fn=_meta_chat)
        _pub = publish_meta_lib.format_for_publish(_meta)
        title = _pub["title"] or title
        if not caption:
            caption = _pub["caption"]
        if tags is None and _pub["tags"]:
            tags = [t.strip() for t in _pub["tags"].split(",")
                    if t.strip()]
        print(i18n_lib.t("publish_meta_generated", lang,
                         _meta.get("source"), title))
    tags = tags if tags is not None else list(YT_DEFAULT_TAGS)
    fb_caption = yt_desc = yt_title = None
    try:
        if "facebook" in platforms:
            fb_caption = publish.build_caption(title, caption,
                                               ai_voice=ai_voice)
        if "youtube" in platforms:
            yt_desc = publish.build_youtube_description(
                title, caption, ai_voice=ai_voice)
            yt_title = publish.build_youtube_title(title)
    except publish.PublishError as e:
        print(i18n_lib.t("publish_meta_error", lang, e))
        return 1
    thumb = expand(thumbnail) if thumbnail else None
    if thumb and not os.path.isfile(thumb):
        print(i18n_lib.t("publish_thumb_missing", lang, thumb))
        return 1
    # فحص امتثال الكابشن مسبق افتراضيًا: أي جملة تجعل الجزء التالي
    # مشروطًا بالمتابعة أو التعليق ترفض النشر كله قبل أي فحص فيديو
    # أو طباعة حمولة. --skip-caption-check للتجاوز الصريح فقط.
    # الكابشن النهائي يُعرض دائمًا قبل النشر (تجريبي وحقيقي).
    from lib import caption_check
    if "facebook" in platforms and not skip_caption_check:
        cap_result = caption_check.check_caption(fb_caption)
        print(i18n_lib.t("publish_caption_final", lang, len(fb_caption)))
        print("   " + fb_caption.replace("\n", "\n   "))
        if not cap_result["ok"]:
            print(i18n_lib.t("publish_caption_rejected", lang))
            for issue in cap_result["issues"]:
                print("  - «%s» (%s)"
                      % (issue["sentence"], issue["reason"]))
            if cap_result["fixed"]:
                print(i18n_lib.t("publish_caption_suggested", lang))
                print("   " + cap_result["fixed"].replace("\n", "\n   "))
            else:
                print(i18n_lib.t("publish_caption_hook_blocked", lang))
            print(i18n_lib.t("publish_caption_retry", lang))
            return 1
    elif "facebook" in platforms:
        print(i18n_lib.t("publish_caption_final_skipped", lang,
                         len(fb_caption)))
        print("   " + fb_caption.replace("\n", "\n   "))
    # فحص جودة مسبق افتراضي قبل أي نشر (أو معاينة): فيديو فاشل
    # لا يُنشر ولا تُطبع حمولته. --skip-check للتجاوز الصريح فقط.
    if not skip_check:
        try:
            result = check_lib.run_checks(video)
        except check_lib.CheckError as e:
            _print_translated("تعذر فحص الجودة قبل النشر", e, "check",
                              lang)
            print(i18n_lib.t("publish_check_fix_hint", lang))
            return 1
        print(check_lib.format_report(result))
        if not result["passed"]:
            print(i18n_lib.t("publish_check_failed", lang))
            return 1
    if dry_run:
        print(i18n_lib.t("publish_dry_header", lang))
        if "facebook" in platforms:
            try:
                argv = publish.facebook_argv(page_id, video, fb_caption,
                                             schedule)
            except publish.PublishError as e:
                print(i18n_lib.t("publish_fb_build_fail", lang, e))
                return 1
            import shlex
            print(i18n_lib.t("publish_fb_reel", lang, page_id or "?"))
            print("   " + " ".join(shlex.quote(a) for a in argv))
            if schedule:
                print(i18n_lib.t("publish_scheduled_at", lang,
                                 publish.format_schedule(schedule)))
            print(i18n_lib.t("publish_caption_chars", lang,
                             len(fb_caption)))
            print("   " + fb_caption.replace("\n", "\n   "))
        if "youtube" in platforms:
            payload = publish.youtube_payload(
                yt_title, yt_desc, tags, privacy, schedule,
                thumbnail=thumb)
            print(i18n_lib.t("publish_yt_payload", lang))
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        if "tiktok" in platforms:
            try:
                res = social_lib.dry_run_summary(
                    "tiktok", video, title, caption, thumbnail=thumb)
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_tiktok_build_fail", lang, e))
                return 1
            print(i18n_lib.t("publish_tiktok_header", lang))
            print("   " + res["summary"])
            print(json.dumps(res["payload"], ensure_ascii=False, indent=2))
            print(i18n_lib.t("publish_tiktok_unverified", lang))
        if "instagram" in platforms:
            ig_user_id = (cfg.get("publish") or {}).get(
                "instagram_user_id")
            try:
                res = social_lib.dry_run_summary(
                    "instagram", video, title, caption,
                    ig_user_id=ig_user_id, thumbnail=thumb)
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_ig_build_fail", lang, e))
                return 1
            print(i18n_lib.t("publish_ig_header", lang))
            print("   " + res["summary"])
            print(json.dumps(res["payload"], ensure_ascii=False, indent=2))
            print(i18n_lib.t("publish_ig_unverified", lang))
        return 0
    ok = True
    if "facebook" in platforms:
        try:
            res = publish.post_facebook(page_id, video, fb_caption,
                                        schedule)
            print(i18n_lib.t("publish_fb_done", lang,
                             i18n_lib.t("publish_fb_scheduled", lang)
                             if res["state"] == "scheduled"
                             else i18n_lib.t("publish_fb_published", lang),
                             res["post_id"]))
            if schedule:
                print(i18n_lib.t("publish_scheduled_at", lang,
                                 publish.format_schedule(schedule)))
        except publish.PublishError as e:
            print(i18n_lib.t("publish_fb_failed", lang, e))
            ok = False
    if "youtube" in platforms:
        token = expand(cfg.get("publish", {}).get("youtube_token") or
                       "~/workspace/studio/youtube-token.json")
        if os.path.isfile(token):
            try:
                res = publish.upload_youtube(
                    video, yt_title, yt_desc, tags, privacy, schedule,
                    thumbnail=thumb, token=token)
                print(i18n_lib.t("publish_yt_done", lang, res["url"]))
                if schedule:
                    print(i18n_lib.t("publish_scheduled_at", lang,
                                     publish.format_schedule(schedule)))
            except publish.PublishError as e:
                print(i18n_lib.t("publish_yt_failed", lang, e))
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-youtube"
                % time.strftime("%Y%m%d-%H%M%S"))
            bundle = publish.write_youtube_bundle(
                bundle_dir, video, yt_title, yt_desc, tags, privacy,
                schedule, thumbnail=thumb)
            print(i18n_lib.t("publish_yt_no_creds", lang))
            print(i18n_lib.t("publish_bundle_ready", lang, bundle))
            print(i18n_lib.t("publish_yt_auth_hint", lang))
            ok = False
    if "tiktok" in platforms:
        token = social_lib.load_token("tiktok")
        if token:
            try:
                res = social_lib.upload_tiktok(video, title, caption,
                                               token)
                print(social_lib.format_result(
                    social_lib.normalize_result("tiktok", res)))
                print(i18n_lib.t("publish_check_verify_fb", lang))
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_tiktok_failed", lang, e))
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-tiktok" % time.strftime("%Y%m%d-%H%M%S"))
            try:
                payload = social_lib.tiktok_init_payload(
                    video, title, caption)
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_tiktok_build_fail", lang, e))
                return 1
            bundle = social_lib.write_social_bundle(
                bundle_dir, "tiktok", video, title, caption, payload)
            print(i18n_lib.t("publish_tiktok_no_token", lang))
            print(i18n_lib.t("publish_bundle_ready", lang, bundle))
            print(social_lib.setup_steps("tiktok"))
            ok = False
    if "instagram" in platforms:
        ig_user_id = (cfg.get("publish") or {}).get("instagram_user_id")
        token = social_lib.load_token("instagram")
        if token and ig_user_id:
            try:
                res = social_lib.upload_instagram(
                    video, title, caption, ig_user_id, token)
                print(social_lib.format_result(
                    social_lib.normalize_result("instagram", res)))
                print(i18n_lib.t("publish_check_verify_ig", lang))
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_ig_failed", lang, e))
                ok = False
        else:
            bundle_dir = os.path.join(
                expand(cfg["paths"]["videos_dir"]),
                "publish-%s-instagram" % time.strftime("%Y%m%d-%H%M%S"))
            try:
                payload = social_lib.instagram_reel_payload(
                    video, title, caption, ig_user_id)
            except social_lib.SocialPublishError as e:
                print(i18n_lib.t("publish_ig_build_fail", lang, e))
                return 1
            bundle = social_lib.write_social_bundle(
                bundle_dir, "instagram", video, title, caption, payload,
                ig_user_id=ig_user_id)
            print(i18n_lib.t("publish_ig_no_token", lang))
            print(i18n_lib.t("publish_bundle_ready", lang, bundle))
            print(social_lib.setup_steps("instagram"))
            ok = False
    return 0 if ok else 1


def cmd_publish_preflight(cfg, video, title, caption, tags=None,
                          ai_voice=False):
    """`publish --preflight`: فحص مسار يوتيوب فقط — صلاحية
    التوكن ثم إنشاء جلسة رفع قابلة للاستئناف، بلا إرسال أي
    بايت من الفيديو وبلا نشر أي شيء. يرجع 0 إن كان المسار
    يعمل من الـVM، و1 مع رسالة عربية (يدوي من YouTube Studio)
    عند فشل SSL أو التوكن. ai_voice يلحق سطر الإفصاح بالوصف
    (ترخيص Supertonic)؛ ويُكتشف من بيان الفيديو تلقائيًا."""
    video = expand(video)
    if not os.path.isfile(video):
        print("ملف الفيديو غير موجود: %s" % video)
        return 1
    if not ai_voice:
        _man = manifest_lib.load_manifest(video)
        if _man and ((_man.get("narration") or {}).get("voice")
                     == "supertonic-M1"):
            ai_voice = True
    token = expand(cfg.get("publish", {}).get("youtube_token") or
                   "~/workspace/studio/youtube-token.json")
    try:
        yt_title = publish.build_youtube_title(title)
        yt_desc = publish.build_youtube_description(title, caption,
                                                    ai_voice=ai_voice)
    except publish.PublishError as e:
        print("خطأ في بيانات النشر: %s" % e)
        return 1
    tag_list = ([t.strip() for t in tags.split(",") if t.strip()]
                if isinstance(tags, str) else (tags or []))
    try:
        result = publish.youtube_preflight(
            token, yt_title, yt_desc, tag_list,
            os.path.getsize(video))
    except publish.PublishError as e:
        # رسالة الرافع نفسه تبدأ بـ«فحص ما قبل النشر…» أصلًا
        # (فشل SSL/توكن) — تُطبع كما هي بلا بادئة مكررة.
        msg = str(e)
        if "فحص ما قبل النشر" in msg:
            print(msg)
        else:
            print("فحص ما قبل النشر على يوتيوب: فشل — %s" % msg)
        return 1
    print(result.get("report")
          or "فحص ما قبل النشر على يوتيوب: المسار يعمل من الـVM.")
    return 0


def cmd_youtube_auth(cfg, client_secrets=None, token=None):
    """تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح)."""
    venv_python = publish.youtube_venv_python()
    if not venv_python:
        print("بيئة YouTube غير موجودة (.venv-youtube) — شغّل setup.sh أولًا")
        return 1
    secrets = expand(client_secrets or
                     cfg.get("publish", {}).get("youtube_client_secrets")
                     or "~/workspace/studio/client_secrets.json")
    token = expand(token or cfg.get("publish", {}).get("youtube_token")
                   or "~/workspace/studio/youtube-token.json")
    if not os.path.isfile(secrets):
        print("ملف client_secrets غير موجود: %s" % secrets)
        print("أنشئ مشروعًا في Google Cloud Console وفعّل YouTube "
              "Data API v3، ثم حمّل client_secrets.json (انظر README).")
        return 1
    uploader = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "lib", "youtube_upload.py")
    print("سيُفتح المتصفح لتسجيل الدخول بحساب يوتيوب…")
    try:
        proc = subprocess.run(
            [venv_python, "-I", uploader, "auth",
             "--client-secrets", secrets, "--token", token],
            timeout=300)
    except subprocess.TimeoutExpired:
        print("انتهت مهلة تبادل OAuth (300 ثانية) — أعد المحاولة "
              "والمتصفح مفتوح")
        return 1
    return proc.returncode


def cmd_youtube_reauth(cfg, client_secrets=None, token=None):
    """إعادة الموافقة على يوتيوب — نفس تبادل OAuth في
    `youtube-auth`، بأمر موجَّه يطبع الرابط والخطوات.

    لا ينشر التطبيق Production ولا يغيّر مشروع Google Cloud —
    يعيد الموافقة فقط على نفس التطبيق في وضع الاختبار (7 أيام).
    """
    print("إعادة الموافقة على يوتيوب:")
    print("1. سيُفتح المتصفح لتسجيل الدخول بحساب يوتيوب.")
    print("2. وافق على نطاق الرفع (youtube.upload).")
    print("3. التوكن الجديد صالح 7 أيام (وضع الاختبار) — أعد "
          "الموافقة قبل انتهائها بيومين.")
    print("ملاحظة: نشر التطبيق Production خيار منفصل — انظر README "
          "(قسم «توكن يوتيوب: وضع الاختبار») قبل أن تقرره.")
    return cmd_youtube_auth(cfg, client_secrets=client_secrets,
                            token=token)


# ---------------------------------------------------------- long-narration
def _default_voice(cfg):
    """صوت السرد الافتراضي: من الإعداد (narration.voice — يضبطه
    معالج `init`)، وإلا piper (الراوي الرجل). قيمة غير معروفة
    في الإعداد تُعامل كـ piper. (جولة v0.1.43: supertonic-M1
    صوت ثانٍ اختياري مسموح في الإعداد — الافتراضي يبقى piper
    دائمًا.)"""
    voice = (cfg.get("narration") or {}).get("voice") or "piper"
    return voice if voice in ("piper", "gtts", "supertonic-M1") \
        else "piper"


def _resolve_voice_arg(voice, lang="ar"):
    """حسم --voice (الموجة الأولى — W3): اسم محرك (piper/gtts/
    supertonic-M1) أو اسم موديل Piper من سجل i18n (الاسم الكامل
    مثل en_US-ryan-medium أو الاسم القصير مثل ryan/kareem، مع
    لاحقة .onnx اختيارية). يرجع (engine, model_path_or_None):
    موديل صريح يعني محرك piper ومسار الموديل؛ وبلا --voice يرجع
    (None, None) فيستخدم المستدعي الافتراضي من الإعداد.
    يرفع ValueError برسالة عربية واضحة عند اسم غير معروف أو
    صوت غير ذكوري — الراوي رجل دائمًا (فـen_US-lessac-medium
    الأنثوي مرفوض كاسم غير معروف لأنه خارج سجل الأصوات الرجالية)."""
    if voice is None:
        return None, None
    name = str(voice).strip()
    if name.endswith(".onnx"):
        name = name[:-5]
    if name in ("piper", "gtts", "supertonic-M1"):
        return name, None
    for key, entry in i18n_lib.PIPER_VOICES.items():
        if name in (entry["model"], entry.get("voice_dir")):
            if entry.get("gender") != "male":
                raise ValueError(
                    "الصوت %s ليس صوت راوٍ رجالي — الراوي رجل دائمًا"
                    % voice)
            return "piper", i18n_lib.voice_model_path(key)
    known = sorted(e["model"] for e in i18n_lib.PIPER_VOICES.values()
                   if e.get("gender") == "male")
    raise ValueError(
        "صوت غير معروف: %s (المسموح: piper أو gtts أو supertonic-M1 "
        "أو موديل Piper رجالي: %s)" % (voice, ", ".join(known)))


def _write_latin_ass_from_project(project, ass_path):
    """اجمع كلمات مسارات مشروع headless (بتوقيتاتها المطلقة) واكتب
    ملف ASS لاتينيًا (LTR، أسفل الصورة فقط) عبر words_to_latin_ass.
    يرجع مسار الملف أو None عند غياب الكلمات أو فشل التوليد
    (fail-open: يُطبع تحذير ولا يفشل الفيديو)."""
    words = []
    for track in (project or {}).get("tracks", []) or []:
        for w in track.get("words") or []:
            try:
                words.append({"w": w["w"],
                              "start": float(w["start"]),
                              "end": float(w["end"])})
            except (KeyError, TypeError, ValueError):
                continue
    if not words:
        return None
    try:
        ass_text, _groups = latin_captions.words_to_latin_ass(words)
    except latin_captions.LatinCaptionError as e:
        print("تحذير: تعذّر توليد الكابشن اللاتيني (%s) — الفيديو سليم"
              % e)
        return None
    try:
        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_text)
    except OSError as e:
        print("تحذير: تعذّرت كتابة الكابشن اللاتيني (%s) — الفيديو سليم"
              % e)
        return None
    return ass_path


def cmd_long_narration(cfg, text, text_file, out_path, gap, atempo,
                       voice="piper", lang="ar"):
    """سرد طويل مقسّم إلى WAV واحد (Piper رجل افتراضيًا؛ أو gTTS).
    lang: لغة السرد (الموجة الأولى — W3) — تُمرَّر إلى synthesize_long
    فيُحسم موديل Piper منها عند غياب model صريح؛ وvoice قد يكون اسم
    موديل Piper رجاليًا (يُحسم عبر _resolve_voice_arg ويغلب lang)."""
    lang = i18n_lib.normalize_lang(lang)
    engine, model_path = _resolve_voice_arg(voice)
    voice = engine or "piper"
    if text_file:
        # إصلاح اختبار اختراق 2026-11-21: ملف نص قادم من ملف فصول
        # JSON كان يقرأ أي ملف على القرص — احصره في مساحة العمل.
        from lib.paths import resolve_inside_workspace
        text_file = resolve_inside_workspace(text_file, "ملف نص السرد")
        with open(text_file, encoding="utf-8") as f:
            text = f.read()
    result = long_narration.synthesize_long(
        text, expand(out_path), gap=gap, atempo=atempo, voice=voice,
        model=model_path, lang=lang)
    print("سرد طويل (%s): %s (%.1f ثانية، %d جملة)"
          % (voice, result["output"], result["duration"],
             len(result["chunks"])))
    return result


# -------------------------------------------------------------- long-video
PAGE_URL = "https://www.facebook.com/1048148471706586"
DEFAULT_LONG_OUTRO = "اشترك في القناة عشان قصة الجمعة الجاية توصلك"


def _long_video_known_projects():
    """خريطة slug القصة → اسم مشروع OpenMontage (من KNOWN_PROJECTS)."""
    return {slug: project for _, (slug, project) in KNOWN_PROJECTS.items()}


def _stage_project_chapter(cfg, project_name, work_dir, title=None,
                           moral=""):
    """جهّز مشروع OpenMontage وابنِ منه فصلًا (بيان + أصول)."""
    root = expand(cfg["openmontage"]["root"])
    proj_path = openmontage_stage.find_project(root, project_name)
    chapter_dir = os.path.join(work_dir, "staged", project_name)
    os.makedirs(chapter_dir, exist_ok=True)
    manifest = openmontage_stage.stage(
        proj_path, chapter_dir, cfg["video"]["image_clip_seconds"])
    assets_dir = os.path.join(chapter_dir, "assets")
    return long_video.chapter_from_manifest(manifest, assets_dir,
                                            title=title, moral=moral)


def _run_chapter(cfg, run_id, title=None, moral=""):
    """ابنِ فصلًا من مجلد تشغيل سابق (manifest.json + assets/)."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    run_dir = run_dir_for(runs_dir, run_id)
    manifest_path = os.path.join(run_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise long_video.LongVideoError(
            "لا يوجد بيان في التشغيل: %s" % run_dir)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assets_dir = os.path.join(run_dir, "assets")
    return long_video.chapter_from_manifest(manifest, assets_dir,
                                            title=title, moral=moral)


def _validate_chapters_spec(spec):
    """تحقق من بنية ملف الفصول (L5): كائن، و«chapters» قائمة،
    وكل مدخل كائن فيه «type» من الأنواع المعروفة، والحقول
    المطلوبة لكل نوع موجودة نصًا غير فارغ. يرفع LongVideoError."""
    chapters = spec.get("chapters", [])
    if not isinstance(chapters, list):
        raise long_video.LongVideoError(
            "حقل «chapters» في ملف الفصول يجب أن يكون قائمة")
    required = {"story": "story", "project": "project", "run": "run",
                "chapter-dir": "path", "text": "text"}
    for i, entry in enumerate(chapters):
        if not isinstance(entry, dict):
            raise long_video.LongVideoError(
                "الفصل %d في ملف الفصول ليس كائنًا" % (i + 1))
        kind = entry.get("type")
        if kind not in required:
            raise long_video.LongVideoError(
                "الفصل %d نوعه غير معروف: %s (المسموح: "
                "story/project/run/chapter-dir/text)"
                % (i + 1, kind))
        field = required[kind]
        value = entry.get(field)
        if kind == "text":
            value = value or entry.get("text_file")
        if not isinstance(value, str) or not value.strip():
            raise long_video.LongVideoError(
                "الفصل %d من نوع %s ينقصه الحقل «%s»"
                % (i + 1, kind, field))
        for key in ("title", "moral"):
            if key in entry and not isinstance(entry[key], str):
                raise long_video.LongVideoError(
                    "الفصل %d حقل «%s» يجب أن يكون نصًا" % (i + 1, key))
        if "motion_clips" in entry:
            mc = entry["motion_clips"]
            if not isinstance(mc, list) or not mc or any(
                    not isinstance(x, str) or not x.strip() for x in mc):
                raise long_video.LongVideoError(
                    "الفصل %d حقل «motion_clips» يجب أن يكون قائمة نصوص "
                    "غير فارغة" % (i + 1))
    for key in ("title", "hook", "intro", "outro", "music"):
        if key in spec and not isinstance(spec[key], str):
            raise long_video.LongVideoError(
                "حقل «%s» في ملف الفصول يجب أن يكون نصًا" % key)
    if "motion" in spec:
        if spec["motion"] not in ("clips", "still", "kenburns",
                                  "youtube-long"):
            raise long_video.LongVideoError(
                "حقل «motion» في ملف الفصول غير معروف: %s (المسموح: "
                "clips/still/kenburns/youtube-long)" % spec["motion"])
    for key in ("motion_manifest", "motion_dir"):
        if key in spec and not isinstance(spec[key], str):
            raise long_video.LongVideoError(
                "حقل «%s» في ملف الفصول يجب أن يكون نصًا" % key)


def _attach_motion_clips(ch, entry):
    """انسخ motion_clips من مدخل الفصل إلى قاموس الفصل المُرجَع."""
    if isinstance(entry, dict) and entry.get("motion_clips"):
        ch["motion_clips"] = list(entry["motion_clips"])
    return ch


def _resolve_long_chapter(cfg, entry, work_dir, atempo, index, voice="piper",
                          lang="ar", model=None):
    """حوّل مدخل فصل واحد (من ملف الفصول أو CLI) إلى قاموس فصل.
    lang/model: لغة السرد وموديل Piper الصريح (الموجة الأولى — W3)
    للفصول النصية — تُمرَّران إلى synthesize_long كما هما."""
    if not isinstance(entry, dict):
        raise long_video.LongVideoError("مدخل فصل ليس كائنًا: %r" % (entry,))
    kind = entry.get("type")
    title = entry.get("title")
    moral = entry.get("moral") or ""
    if kind == "story":
        slug = entry.get("story")
        if not isinstance(slug, str) or not slug.strip():
            raise long_video.LongVideoError(
                "فصل story بلا حقل «story»")
        known = _long_video_known_projects()
        if slug in known:
            project = known[slug]
        else:
            # جرّب مشروعًا بنفس اسم القصة قبل الفشل
            root = expand(cfg["openmontage"]["root"])
            try:
                openmontage_stage.find_project(root, slug)
            except (openmontage_stage.StageError, ValueError) as e:
                raise long_video.LongVideoError(
                    "لا يوجد مشروع OpenMontage جاهز لقصة %s (%s) — "
                    "جهّز مشروعها أولًا أو استخدم --chapter-dir"
                    % (slug, e))
            project = slug
        return _attach_motion_clips(
            _stage_project_chapter(cfg, project, work_dir,
                                   title=title, moral=moral), entry)
    if kind == "project":
        proj = entry.get("project")
        if not isinstance(proj, str) or not proj.strip():
            raise long_video.LongVideoError(
                "فصل project بلا حقل «project»")
        return _attach_motion_clips(
            _stage_project_chapter(cfg, proj, work_dir,
                                   title=title, moral=moral), entry)
    if kind == "run":
        run = entry.get("run")
        if not isinstance(run, str) or not run.strip():
            raise long_video.LongVideoError("فصل run بلا حقل «run»")
        return _attach_motion_clips(
            _run_chapter(cfg, run, title=title, moral=moral), entry)
    if kind == "chapter-dir":
        # إصلاح اختبار اختراق 2026-11-21: مجلد فصل خارج مساحة العمل
        # كان يُقرأ وتُكتب فيه ملفات عمل (.long-video) — احصره.
        from lib.paths import resolve_inside_workspace
        if not isinstance(entry.get("path"), str) \
                or not entry.get("path", "").strip():
            raise long_video.LongVideoError(
                "فصل chapter-dir بلا حقل «path»")
        try:
            chapter_path = resolve_inside_workspace(entry["path"],
                                                    "مجلد الفصل")
        except ValueError as e:
            raise long_video.LongVideoError(str(e))
        return _attach_motion_clips(long_video.load_chapter_dir(
            chapter_path,
            work_dir=os.path.join(work_dir, "chapters", "ch%d" % index),
            atempo=atempo, title=title, moral=moral or None), entry)
    if kind == "text":
        from lib.paths import resolve_inside_workspace
        text = entry.get("text")
        if not isinstance(text, (str, type(None))):
            raise long_video.LongVideoError(
                "الفصل النصي حقل «text» يجب أن يكون نصًا")
        if entry.get("text_file"):
            if not isinstance(entry.get("text_file"), str):
                raise long_video.LongVideoError(
                    "الفصل النصي حقل «text_file» يجب أن يكون نصًا")
            try:
                text_path = resolve_inside_workspace(entry["text_file"],
                                                     "ملف نص الفصل")
            except ValueError as e:
                raise long_video.LongVideoError(str(e))
            try:
                with open(text_path, encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                raise long_video.LongVideoError(
                    "تعذّرت قراءة ملف نص الفصل: %s" % e)
        if not text or not text.strip():
            raise long_video.LongVideoError(
                "الفصل النصي بلا نص: %s" % (title or "?"))
        raw_images = entry.get("images", [])
        if not isinstance(raw_images, list) or any(
                not isinstance(p, str) for p in raw_images):
            raise long_video.LongVideoError(
                "الفصل النصي حقل «images» يجب أن يكون قائمة نصوص")
        try:
            images = [resolve_inside_workspace(p, "صورة الفصل")
                      for p in raw_images]
            if entry.get("cover"):
                images = [resolve_inside_workspace(entry["cover"],
                                                   "غلاف الفصل")] + images
        except ValueError as e:
            raise long_video.LongVideoError(str(e))
        if not images:
            raise long_video.LongVideoError(
                "الفصل النصي بلا صور (cover أو images): %s" % title)
        wav = os.path.join(work_dir, "narration",
                           "text-chapter-%d.wav" % index)
        os.makedirs(os.path.dirname(wav), exist_ok=True)
        info = long_narration.synthesize_long(text, wav, atempo=atempo,
                                              voice=voice, lang=lang,
                                              model=model)
        return _attach_motion_clips(
            long_video.chapter_from_text(title, text, info, images,
                                         moral=moral), entry)
    raise long_video.LongVideoError(
        "نوع فصل غير معروف: %s (المسموح: story/project/run/"
        "chapter-dir/text)" % kind)


def _loop_music_to_cover(music, total, run_dir):
    """كرّر ملف موسيقى أقصر من الفيديو حتى يغطي مدته.

    نواة headless ترفض مقطعًا صوتيًا أقصر من مدته المطلوبة،
    فالموسيقى القصيرة تُكرَّر (loop) إلى ملف عمل. يرجع المسار المستخدم.
    """
    dur = long_narration.probe_duration(music)
    if dur >= total:
        return music
    looped = os.path.join(run_dir, "music-loop.wav")
    try:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1",
                        "-i", music, "-t", str(total), looped],
                       capture_output=True, text=True, timeout=300,
                       check=True)
    except subprocess.CalledProcessError as e:
        raise long_video.LongVideoError(
            "فشل تكرار الموسيقى الخلفية: %s" % (e.stderr or "")[-300:])
    print("الموسيقى الخلفية أقصر من الفيديو (%.1f ث < %.1f ث) — كُرّرت"
          % (dur, total))
    return looped


def _cli_flag_present(flag):
    """هل مُرّر علم CLI صريح (بصيغتي --flag X و--flag=X)؟

    يميّز تمرير --motion صريحًا عن قيمته الافتراضية في argparse،
    حتى يتجاوز العلم مفاتيح ملف الفصول فقط عند تمريره فعلًا.
    """
    return any(a == flag or a.startswith(flag + "=")
               for a in sys.argv[1:])


def cmd_long_video(cfg, args, lang="ar"):
    """فيديو طويل أفقي 1280×720 من عدة فصول (8–12 دقيقة).
    lang: لغة السرد والكابشن (الموجة الأولى) — من --lang الصريح
    في الأمر أو لغة CLI العامة؛ و--voice قد يكون اسم موديل Piper
    رجاليًا (يُحسم عبر _resolve_voice_arg)."""
    lang = i18n_lib.normalize_lang(
        getattr(args, "cmd_lang", None) or lang)
    try:
        _lv_engine, _lv_model = _resolve_voice_arg(
            getattr(args, "voice", None))
    except ValueError as e:
        print(str(e))
        return 2
    runs_dir = expand(cfg["paths"]["runs_dir"])
    run_id, run_dir = new_run(runs_dir, "long-video")
    log = {"run": run_id, "cmd": "long-video",
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": {},
           "lang": lang}
    # صوت السرد: --voice الصريح أولًا، وإلا الافتراضي من الإعداد.
    voice = _lv_engine or _default_voice(cfg)
    model_path = _lv_model
    print("تشغيل الفيديو الطويل: %s" % run_id)
    # سجل تشغيل (جولة v0.1.37).
    _lv_settings = run_record.resolve_settings(
        cfg, {"backend": "long-video", "story": "long-video"})
    _lv_settings["voice"] = voice
    run_record.print_settings(_lv_settings)
    _lv_record, _ = run_record.begin_record(
        runs_dir, "long-video", _lv_settings, run_id=run_id)
    try:
        spec = {}
        if args.chapters_file:
            # إصلاح اختبار اختراق 2026-11-22 (L5): ملف فصول
            # مشوَّه كان يتعطل برسائل خام (JSONDecodeError/KeyError/
            # AttributeError) — يُتحقق من البنية كلها هنا ويرفع
            # LongVideoError برسالة عربية قبل أي معالجة.
            try:
                with open(expand(args.chapters_file),
                          encoding="utf-8") as f:
                    spec = json.load(f)
            except (ValueError, OSError) as e:
                raise long_video.LongVideoError(
                    "ملف الفصول غير صالح (%s): %s"
                    % (args.chapters_file, e))
            if not isinstance(spec, dict):
                raise long_video.LongVideoError(
                    "ملف الفصول يجب أن يكون كائن JSON")
            _validate_chapters_spec(spec)
        # --auto-week: قصص الأسبوع من ملف الطابور بدل التجميع اليدوي.
        if getattr(args, "auto_week", False):
            if (args.story or args.project or args.run_id
                    or args.chapter_dir or args.chapter_text
                    or args.chapters_file):
                raise long_video.LongVideoError(
                    "لا يُجمع --auto-week مع مصادر فصول يدوية "
                    "(--story/--project/--run/--chapter-dir/"
                    "--chapter-text/--chapters-file)")
            since = None
            if getattr(args, "since", None):
                try:
                    since = datetime.date.fromisoformat(args.since)
                except ValueError:
                    raise long_video.LongVideoError(
                        "--since بصيغة YYYY-MM-DD (وصل: %s)" % args.since)
            queue_path = expand(getattr(args, "queue_file", None)
                                or cfg["paths"]["queue_file"])
            try:
                usable, skipped = autoweek.pick_week_stories(
                    queue_path, cfg, KNOWN_PROJECTS, since=since)
            except autoweek.AutoWeekError as e:
                raise long_video.LongVideoError(str(e))
            print("قصص الأسبوع (%d):" % len(usable))
            for u in usable:
                print("  - %s (%s)" % (u["title"],
                      u["date"].strftime("%Y-%m-%d")))
            for s in skipped:
                print("  تُتخطى: %s — %s" % (s["title"], s["reason"]))
            spec = {"chapters": [
                {"type": u["type"],
                 ("story" if u["type"] == "story" else
                  "project" if u["type"] == "project" else "path"):
                     u["source"], "title": u["title"]}
                for u in usable]}
            if not args.title:
                args.title = "قصص الأسبوع | القصة الكاملة"
            if not args.hook:
                args.hook = "قصص الأسبوع كاملة — اسمعهم ورا بعض"
        title = args.title or spec.get("title")
        if not title:
            raise long_video.LongVideoError("عنوان الفيديو الطويل مطلوب")
        hook = args.hook or spec.get("hook") or title
        intro_text = args.intro or spec.get("intro") or hook
        outro_text = args.outro or spec.get("outro") or DEFAULT_LONG_OUTRO
        music = None
        if args.music:
            music = expand(args.music)
        elif spec.get("music"):
            music = expand(spec["music"])
        else:
            # الموسيقى المدمجة افتراضيًا (شوبان — ملكية عامة)؛
            # long_video.default_music في الإعداد يتجاوزها، و"none"
            # تلغيها.
            cfg_music = (cfg.get("long_video") or {}).get("default_music")
            if cfg_music == "none":
                music = None
            elif cfg_music:
                music = expand(cfg_music)
            elif os.path.isfile(DEFAULT_MUSIC):
                music = DEFAULT_MUSIC
                print("الموسيقى الخلفية الافتراضية: %s" % music)
        if music:
            # إصلاح اختبار اختراق 2026-11-21: ملف موسيقى من ملف
            # فصول JSON كان يُقرأ من أي مسار — احصره في مساحة العمل.
            from lib.paths import resolve_inside_workspace
            try:
                music = resolve_inside_workspace(music, "ملف الموسيقى")
            except ValueError as e:
                raise long_video.LongVideoError(str(e))
        entries = list(spec.get("chapters", []))
        for slug in args.story:
            entries.append({"type": "story", "story": slug})
        for proj in args.project:
            entries.append({"type": "project", "project": proj})
        for run in args.run_id:
            entries.append({"type": "run", "run": run})
        for d in args.chapter_dir:
            entries.append({"type": "chapter-dir", "path": d})
        if len(args.text_file) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --text-file (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.text_file), len(args.chapter_text)))
        if args.cover and len(args.cover) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --cover (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.cover), len(args.chapter_text)))
        if args.moral and len(args.moral) != len(args.chapter_text):
            raise long_video.LongVideoError(
                "عدد --moral (%d) يجب أن يساوي عدد --chapter-text (%d)"
                % (len(args.moral), len(args.chapter_text)))
        for i, (ct, tf) in enumerate(zip(args.chapter_text,
                                         args.text_file)):
            entry = {"type": "text", "title": ct, "text_file": tf}
            if args.cover:
                entry["cover"] = args.cover[i]
            if args.moral:
                entry["moral"] = args.moral[i]
            entries.append(entry)
        if not entries:
            raise long_video.LongVideoError(
                "لا توجد فصول — مرّر --story أو --project أو --run أو "
                "--chapter-dir أو --chapter-text أو --chapters-file")
        # 1) الفصول
        chapters = []
        for i, entry in enumerate(entries):
            t0 = time.time()
            ch = _resolve_long_chapter(cfg, entry, run_dir, args.atempo, i,
                                       voice=voice, lang=lang,
                                       model=model_path)
            chapters.append(ch)
            print("فصل %d: %s (%.1f ثانية، %d عبارة)"
                  % (i + 1, ch["title"], ch["duration"],
                     len(ch.get("phrases", []))))
            log["steps"]["chapter-%d" % (i + 1)] = {
                "status": "ok", "seconds": round(time.time() - t0, 1),
                "title": ch["title"], "duration": ch["duration"]}
        # 1أ) تحسين الحركة (--improve-motion، الموجة الأولى — W1):
        # بدّل صور الفصول بمقاطع مولّدة من المانيفست مع إعادة
        # استخدام الإطارات المجمّدة عبر StageCache — بلا توليد GPU
        # هنا (التوليد خارج هذه الدالة). المانيفست من
        # --motion-manifest (أو ملف الفصول)، والمجلد من --motion-dir
        # (أو مجلد المانيفست عند غيابه).
        improved_motion = None
        if getattr(args, "improve_motion", False):
            _im_manifest = getattr(args, "motion_manifest", None) \
                or spec.get("motion_manifest")
            if not _im_manifest:
                raise long_video.LongVideoError(
                    "--improve-motion يحتاج --motion-manifest (مسار "
                    "مانيفست الحركة)")
            _im_dir = getattr(args, "motion_dir", None) \
                or spec.get("motion_dir")
            _im_dir = expand(_im_dir) if _im_dir else os.path.dirname(
                os.path.abspath(expand(_im_manifest)))
            _im_clip = (long_video.YOUTUBE_LONG_IMAGE_SECONDS
                        if (getattr(args, "motion", None) == "youtube-long"
                            or spec.get("motion") == "youtube-long")
                        else None)
            improved_motion = long_video.improve_motion(
                {"title": title, "hook": hook, "chapters": chapters},
                expand(_im_manifest), _im_dir,
                cache=stage_cache_lib.StageCache(), work_dir=run_dir,
                clip_seconds=_im_clip)
            chapters = improved_motion["spec"]["chapters"]
            motion = "clips"
            print("حُسّنت الحركة: أُعيد استخدام %d مقطعًا، ووُلّد %d "
                  "إطارًا مجمّدًا"
                  % (len(improved_motion.get("reused") or []),
                     len(improved_motion.get("generated") or [])))
        # 1ب) مقاطع الحركة (v0.1.44): أعلام CLI تتجاوز مفاتيح ملف
        # الفصول (motion/motion_manifest/motion_dir) عند تمريرها.
        if improved_motion is not None:
            motion = "clips"
        elif _cli_flag_present("--motion"):
            motion = getattr(args, "motion", None) \
                or long_video.FAST_MOTION_DEFAULT
        elif isinstance(spec.get("motion"), str):
            motion = spec["motion"]
        else:
            motion = getattr(args, "motion", None) \
                or long_video.FAST_MOTION_DEFAULT
        motion_manifest = getattr(args, "motion_manifest", None) \
            or spec.get("motion_manifest")
        motion_dir = getattr(args, "motion_dir", None) \
            or spec.get("motion_dir")
        motion_log = {"mode": motion, "warnings": [], "chapters": []}
        if improved_motion is not None:
            motion_log["warnings"].extend(
                improved_motion.get("warnings") or [])
            motion_log["chapters"].extend(
                list((improved_motion.get("report") or {}).get("chapters")
                     or []))
        elif motion in ("clips", "youtube-long"):
            if motion_manifest:
                manifest_path = expand(motion_manifest)
                try:
                    manifest = motion_clips.load_motion_manifest(
                        manifest_path)
                except motion_clips.MotionError as e:
                    raise long_video.LongVideoError(str(e))
                if motion_dir:
                    motion_dir = expand(motion_dir)
                else:
                    motion_dir = os.path.dirname(
                        os.path.abspath(manifest_path))
                freeze_dir = os.path.join(run_dir, "motion-freezes")
                # إيقاع الصور الاحتياطية يتبع الوضع (youtube-long: 2.5ث،
                # clips: 5ث) — يُمرَّر للمحلِّل ليقسّم باقي مدة الفصل
                # والرجوع بلا مقاطع إلى صور متناوبة بدل صورة واحدة
                # متجمدة (إصلاح فجوة 2026-11-24).
                clip_seconds = (
                    long_video.YOUTUBE_LONG_IMAGE_SECONDS
                    if motion == "youtube-long"
                    else motion_clips.IMAGE_CLIP_SECONDS)
                for i, ch in enumerate(chapters):
                    resolved = motion_clips.resolve_chapter_motion(
                        ch, manifest, motion_dir, i + 1,
                        clip_seconds=clip_seconds)
                    ch_warnings = list(resolved["warnings"])
                    segments = []
                    for j, seg in enumerate(resolved["segments"]):
                        if seg["kind"] == "freeze":
                            out_jpg = os.path.join(
                                freeze_dir,
                                "ch%d-%d.jpg" % (i + 1, j))
                            try:
                                motion_clips.extract_last_frame(
                                    seg["src"], out_jpg)
                                segments.append({
                                    "kind": "image", "src": out_jpg,
                                    "duration": seg["duration"]})
                            except motion_clips.MotionError as e:
                                ch_warnings.append(
                                    "تعذّر تجميد آخر إطار للمقطع في "
                                    "الفصل %s (%s) — صورة ثابتة بدلًا منه"
                                    % (ch["title"], e))
                                segments.append({
                                    "kind": "image",
                                    "src": ch["images"][0],
                                    "duration": seg["duration"]})
                        else:
                            segments.append(seg)
                    ch["motion_segments"] = segments
                    ch["motion_report"] = {"mode": resolved["mode"],
                                           "warnings": ch_warnings}
                    motion_log["chapters"].append(
                        {"title": ch["title"], "mode": resolved["mode"],
                         "warnings": ch_warnings})
                    motion_log["warnings"].extend(ch_warnings)
            else:
                msg = ("وضع %s بلا --motion-manifest — كل الفصول "
                       "صور ثابتة بلا Ken Burns" % motion)
                motion_log["warnings"].append(msg)
                for ch in chapters:
                    motion_log["chapters"].append(
                        {"title": ch["title"], "mode": "still",
                         "warnings": [msg]})
        elif motion == "kenburns":
            print("وضع الحركة kenburns: السلوك القديم (Ken Burns) — "
                  "اختياري صريح")
        for w in motion_log["warnings"]:
            print("تحذير حركة: %s" % w)
        log["motion"] = motion_log
        # 2) سرد المقدمة والخاتمة (Piper مقسّم افتراضيًا؛ أو gTTS)
        narr_dir = os.path.join(run_dir, "narration")
        os.makedirs(narr_dir, exist_ok=True)
        intro_info = long_narration.synthesize_long(
            intro_text, os.path.join(narr_dir, "intro.wav"),
            atempo=args.atempo, voice=voice, lang=lang,
            model=model_path)
        outro_info = long_narration.synthesize_long(
            outro_text, os.path.join(narr_dir, "outro.wav"),
            atempo=args.atempo, voice=voice, lang=lang,
            model=model_path)
        # 3) بناء مشروع headless وريندره أفقيًا
        project, meta = long_video.build_project({
            "title": title, "hook": hook,
            "intro": {"text": intro_text,
                      "narration": intro_info["output"],
                      "duration": intro_info["duration"]},
            "outro": {"text": outro_text,
                      "narration": outro_info["output"],
                      "duration": outro_info["duration"]},
            "chapters": chapters, "music": music,
            "motion": motion,
            "width": 1280, "height": 720,
            "fps": int(cfg["video"]["fps"])})
        if music:
            music = _loop_music_to_cover(
                music, meta["total_duration"], run_dir)
            for track in project["tracks"]:
                if track.get("role") == "background":
                    track["src"] = music
        project_path = os.path.join(run_dir, "long-project.json")
        with open(project_path, "w", encoding="utf-8") as f:
            json.dump(project, f, ensure_ascii=False, indent=2)
        out_path = expand(args.out)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)),
                    exist_ok=True)
        # كابشن لاتيني (الموجة الأولى — W5): مع lang="en" يُكتب ملف
        # ASS جانبي من كلمات مسارات المشروع (LTR، أسفل الصورة فقط).
        if lang == "en":
            _ass_path = os.path.splitext(out_path)[0] + "-captions-en.ass"
            _written = _write_latin_ass_from_project(project, _ass_path)
            if _written:
                log["captions_ass"] = _written
                print("كابشن لاتيني (LTR): %s" % _written)
        t0 = time.time()
        editor_path = expand(cfg["headless"]["editor"])
        result = headless_stage.render_project(editor_path, project_path,
                                               out_path, timeout=1800)
        print("صُدّر الفيديو الطويل عبر headless-editor: %s "
              "(%.0f ثانية ريندر، %.1f ميجا)"
              % (result["output"], result["seconds"],
                 result["size_bytes"] / (1024 * 1024)))
        # 4) الشعار فقط (بلا بطاقات اقتباس أبدًا في الفيديو الطويل)
        out = _finish_video(result["output"], not args.no_watermark, None)
        # 4أ) مقروئية الكابشن (جولة v0.1.55): عبارات الفصول
        # بإزاحتها الفعلية (content_start) هي الكابشنات
        # المريندرة — تحذير + تقرير فقط، لا يفشل الفيديو أبدًا؛
        # وتُسجَّل النتيجة في سجل التشغيل وبيان المصدر. أي عطل
        # هنا (بما فيه شكل meta غير متوقع) يُطبع تحذيرًا فقط.
        _lv_readability = None
        try:
            _lv_phrases = []
            for _i, _ch in enumerate(chapters):
                _cs = meta["chapters"][_i].get("content_start") or 0.0
                for _p in _ch.get("phrases") or []:
                    try:
                        _s = _cs + float(_p.get("start") or 0)
                        _e = _cs + float(_p.get("end") or 0)
                    except (TypeError, ValueError):
                        continue
                    _lv_phrases.append({"start": _s, "end": _e,
                                        "text": _p.get("text") or ""})
            _lv_readability = _check_phrases_readability(_lv_phrases)
        except Exception as e:
            print("تحذير: تعذّر فحص مقروئية الكابشن (%s) — "
                  "الفيديو سليم" % e)
            _lv_readability = None
        if _lv_readability is not None:
            log["caption_readability"] = _lv_readability
            _print_readability(_lv_readability)
        # 5) طوابع الفصول ووصف يوتيوب
        base, _ = os.path.splitext(out_path)
        ts_path = base + "-timestamps.txt"
        desc_path = base + "-description.txt"
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(long_video.format_timestamps(meta))
        with open(desc_path, "w", encoding="utf-8") as f:
            f.write(long_video.build_description(meta, hook, outro_text,
                                                 PAGE_URL))
        total = meta["total_duration"]
        if total < long_video.TARGET_MIN_SECONDS or \
                total > long_video.TARGET_MAX_SECONDS:
            print("تنبيه: مدة الفيديو %.1f ثانية خارج الهدف 8–12 دقيقة"
                  % total)
        log["status"] = "done"
        log["output"] = out
        log["duration"] = total
        log["timestamps"] = ts_path
        log["description"] = desc_path
        print("اكتمل الفيديو الطويل: %s (%.1f ثانية، %d فصول)"
              % (out, total, len(chapters)))
        print("طوابع الفصول: %s" % ts_path)
        print("وصف يوتيوب: %s" % desc_path)
        run_record.finish_record(_lv_record, "done",
                                 outputs=[out, ts_path, desc_path])
        # بيان مصدر (جولة v0.1.37).
        try:
            _lv_scenes = [
                {"scene": i + 1, "title": ch.get("title", ""),
                 "text": ch.get("text", "")[:200]}
                for i, ch in enumerate(chapters)]
            _lv_extra = {"chapters": len(chapters),
                         "motion": motion,
                         "timestamps": ts_path,
                         "description": desc_path}
            if _lv_readability is not None:
                _lv_extra["caption_readability"] = _lv_readability
            _man = manifest_lib.build_manifest(
                out, title=title, hook=hook, moral="",
                source="long-video", scenes=_lv_scenes,
                narration={"voice": voice},
                extra=_lv_extra)
            _mp = manifest_lib.write_manifest(out, _man)
            print("بيان المصدر: %s" % _mp)
        except Exception as e:
            print("تحذير: تعذرت كتابة بيان المصدر (%s) — الفيديو سليم" % e)
    except Exception as e:
        log["status"] = "failed"
        log["error"] = str(e)
        run_record.finish_record(_lv_record, "failed", error=e)
        print("فشل الفيديو الطويل: %s" % e)
        write_log(run_dir, log)
        return 1
    write_log(run_dir, log)
    return 0


# ------------------------------------------------------------- run-queue
def parse_queue(path):
    """يقرأ قصص «في الانتظار» من ملف الطابور بالترتيب.

    يجمع الأسطر المرقّمة `N. **العنوان**` الواقعة تحت قسم «في
    الانتظار» أو قسم «دفعة ثانية» فقط — فالقسم «المنشور» فيه ترقيم
    أيضًا لكنه ليس انتظارًا. يرجع قائمة قواميس
    {"number": int, "title": str, "note": str}.
    """
    import re
    stories = []
    waiting = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                heading = line.strip()
                waiting = ("في الانتظار" in heading
                           or "دفعة ثانية" in heading)
                continue
            if not waiting:
                continue
            m = re.match(r"\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(?:—\s*(.*))?$",
                         line.strip())
            if m:
                stories.append({"number": int(m.group(1)),
                                "title": m.group(2).strip(),
                                "note": (m.group(3) or "").strip()})
    return stories


def check_story_ready(cfg, story):
    """هل للقصة مشروع OpenMontage جاهز؟ يرجع
    (جاهزة؟، slug القصة، اسم المشروع، سبب التخطي)."""
    known = KNOWN_PROJECTS.get(story["number"])
    if known is None:
        # محاولة أخيرة: عنوان «العنزة» بأي رقم (لو أُعيد ترقيم الطابور)
        if "العنزة" in story["title"]:
            known = ("anza", "anza-part1")
        else:
            return (False, None, None,
                    "يحتاج تجهيز مشروع — لا يوجد مشروع OpenMontage "
                    "مطابق لهذه القصة بعد")
    slug, project = known
    proj_path = os.path.join(expand(cfg["openmontage"]["projects_dir"]),
                             project)
    if not os.path.isdir(proj_path):
        return (False, slug, project,
                "يحتاج تجهيز مشروع — مجلد المشروع غير موجود: %s"
                % proj_path)
    return (True, slug, project, "")


def cmd_run_queue(cfg, limit=None, continue_on_error=False, dry_run=False,
                  allow_fallback=False):
    """دفعة جماعية من ملف الطابور: القصص الجاهزة تُشغَّل بالتتابع
    عبر cmd_run نفسه؛ بلا مشروع تُتخطى مع تسجيل السبب. النتائج في
    runs/queue-<تاريخ>.json، وتُلحَق خلاصة بتاريخ اليوم في ملف
    الطابور (للتشغيل الحقيقي فقط)."""
    queue_path = expand(cfg["paths"]["queue_file"])
    if not os.path.isfile(queue_path):
        print("ملف الطابور غير موجود: %s" % queue_path)
        return 1
    try:
        stories = parse_queue(queue_path)
    except OSError as e:
        print("تعذر قراءة ملف الطابور: %s" % e)
        return 1
    if limit is not None:
        stories = stories[:limit]
    if not stories:
        print("لا توجد قصص في الانتظار في ملف الطابور")
        return 0
    print("قصص في الانتظار (أول %d):" % len(stories))
    plan = []
    for s in stories:
        ready, slug, project, reason = check_story_ready(cfg, s)
        plan.append({"number": s["number"], "title": s["title"],
                     "ready": ready, "story": slug, "project": project,
                     "reason": reason})
        print("  %d. %s — %s" % (s["number"], s["title"],
              "جاهزة (مشروع %s)" % project if ready
              else "تُتخطى: %s" % reason))
    if dry_run:
        print("وضع تجريبي — لم يُشغَّل شيء ولم يُكتب أي ملف")
        return 0
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    date = time.strftime("%Y%m%d")
    out_path = os.path.join(runs_dir, "queue-%s.json" % date)
    n = 2
    while os.path.exists(out_path):
        out_path = os.path.join(runs_dir, "queue-%s-%d.json" % (date, n))
        n += 1
    results = {"date": time.strftime("%Y-%m-%d %H:%M:%S"),
               "limit": limit, "stories": []}
    overall = 0
    for item in plan:
        entry = {"number": item["number"], "title": item["title"],
                 "ready": item["ready"], "project": item["project"]}
        if not item["ready"]:
            entry["status"] = "skipped"
            entry["reason"] = item["reason"]
            results["stories"].append(entry)
            continue
        out_video = os.path.join(expand(cfg["paths"]["videos_dir"]),
                                 "%s-queue.mp4" % item["story"])
        t0 = time.time()
        rc = cmd_run(cfg, item["story"], item["project"], out_video,
                     allow_fallback)
        entry["status"] = "done" if rc == 0 else "failed"
        entry["seconds"] = round(time.time() - t0, 1)
        entry["output"] = out_video if rc == 0 else None
        results["stories"].append(entry)
        if rc != 0:
            overall = 1
            print("فشلت قصة %d (%s)" % (item["number"], item["title"]))
            if not continue_on_error:
                print("توقفت الدفعة — استخدم --continue-on-error "
                      "للمتابعة بعد الفشل")
                break
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("سُجّلت نتائج الدفعة في: %s" % out_path)
    # خلاصة بتاريخ اليوم تُلحق بملف الطابور (سجل زمني مثل باقي أقسامه)
    try:
        with open(queue_path, "a", encoding="utf-8") as f:
            f.write("\n## تحديث run-queue — %s\n\n" % results["date"])
            for e in results["stories"]:
                f.write("- %d. %s — %s%s\n" % (
                    e["number"], e["title"], e["status"],
                    (" (%s)" % e.get("reason", "")) if e["status"]
                    == "skipped" else ""))
    except OSError as e:
        print("تحذير: تعذر إلحاق الخلاصة بملف الطابور: %s" % e)
    return overall


# ------------------------------------------------------------- queue add
def cmd_queue_add(cfg, title, text_file, parts=1, note=None,
                  queue_file=None):
    """أضف قصة إلى ملف الطابور بسطر واحد (يرفض المكرر).

    يرجع 0 عند النجاح، و1 عند أي رفض (عنوان مكرر/نص فارغ/...).
    """
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    try:
        with open(expand(text_file), encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print("تعذر قراءة ملف نص القصة: %s" % e)
        return 1
    stories_dir = os.path.join(STUDIO_DIR, "queue")
    # توصيل فهرس القصص الدلالي (جولة v0.1.48): يُمرَّر صراحةً —
    # بلا qdrant-client أو Ollama يرجع get_default_index() ‏None
    # فلا فحص (fail-open)؛ وشبه مكرر فوق العتبة يرفضه add_story
    # بـQueueError قبل أي كتابة.
    from lib import story_index as story_index_lib
    _index = story_index_lib.get_default_index()
    try:
        result = queue_lib.add_story(queue_path, title, text, parts=parts,
                                     note=note, stories_dir=stories_dir,
                                     story_index=_index)
    except queue_lib.QueueError as e:
        print("رفضت الإضافة: %s" % e)
        return 1
    except OSError as e:
        print("فشل الكتابة في ملف الطابور: %s" % e)
        return 1
    finally:
        if _index is not None:
            _index.close()
    print("أُضيفت القصة رقم %d إلى الطابور: %s"
          % (result["number"], result["title"]))
    if result["text_file"]:
        print("نص القصة محفوظ في: %s" % result["text_file"])
    if result.get("index_note"):
        print(result["index_note"])
    return 0


def cmd_queue_validate(cfg, queue_file=None):
    """حقّق بنية ملف الطابور (جولة v0.1.37 — مقترح tinker رقم 8).

    قراءة فقط — لا يعدّل الطابور أبدًا. يرجع 0 إن سليم، و1
    مع طباعة المشكلات إن وجدت.
    """
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    ok, issues = queue_check.validate_queue_file(queue_path)
    if ok:
        print("الطابور سليم: %s" % queue_path)
        return 0
    print("مشكلات في بنية الطابور (%d):" % len(issues))
    for issue in issues:
        print("  - %s" % issue)
    return 1


def cmd_queue_import(cfg, text_file, title, queue_file=None, start=None):
    """استورد قصة طويلة من ملف نصي إلى الطابور — مقسَّمة لأجزاء
    ~40–60 ثانية سردًا، كل جزء بموعد مقترح (9:00/19:00 بالتناوب).

    يرجع 0 عند النجاح، و1 عند أي رفض (ملف مفقود/نص فارغ/عنوان
    مكرر)، و2 عند تاريخ بداية غير صالح.
    """
    from lib import queue_import as queue_import_lib
    from lib.paths import resolve_inside_workspace
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    try:
        text_path = resolve_inside_workspace(text_file, "ملف نص القصة")
    except ValueError as e:
        print("ملف قصة غير صالح: %s" % e)
        return 1
    start_date = None
    if start:
        try:
            start_date = datetime.date.fromisoformat(start)
        except ValueError:
            print("تاريخ بداية غير صالح (YYYY-MM-DD): %s" % start)
            return 2
    stories_dir = os.path.join(STUDIO_DIR, "queue")
    try:
        result = queue_import_lib.import_story(
            queue_path, text_path, title, stories_dir=stories_dir,
            start_date=start_date)
    except (ValueError, queue_lib.QueueError) as e:
        print("فشل الاستيراد: %s" % e)
        return 1
    except OSError as e:
        print("فشل الكتابة في ملف الطابور: %s" % e)
        return 1
    print("استُوردت «%s» — %d أجزاء:" % (result["title"],
                                          len(result["parts"])))
    for part in result["parts"]:
        print("  الجزء %d — الطابور #%d — ~%s ثانية — مقترح %s"
              % (part["part"], part["number"], part["seconds"],
                 part["suggested_time"]))
    return 0


# ------------------------------------------------------------------ analyze
def cmd_analyze(cfg, page_id=None, channel_id=None, dna=False,
                video=None, hook=None, subs_dir=None, story_text=None,
                slug=None, reference=None, story=None,
                audio_profile=None):
    """حلّل آخر فيديو منشور بأرقام حقيقية (فيسبوك + يوتيوب).

    يطبع المنصتين جنبًا إلى جنب + 2–3 اقتراحات تحسين مشتقة من
    الأرقام، ويحفظ JSON في runs/analyze-<وقت>.json. أي مصدر لا
    يصل يُطبع «غير معروف» — بلا أرقام مخترعة أبدًا. يرجع 1 فقط
    إن تعذر المصدران معًا.

    مع --dna: تحليل DNA الفيروسي لفيديو واحد (--video) — درجة
    الهوك 0–10 + الإيقاع + الصمت + كثافة الكلمات + حكم مربوط
    بأرقام المنصتين لنفس الفيديو (بمطابقة العنوان).
    """
    if dna:
        return cmd_analyze_dna(cfg, video=video, hook=hook,
                               subs_dir=subs_dir, story_text=story_text,
                               page_id=page_id, channel_id=channel_id,
                               slug=slug, reference=reference,
                               new_story_path=story,
                               audio_profile=audio_profile)
    if audio_profile:
        print("تنبيه: --audio-profile يعمل مع --dna فقط ويُتجاهل")
    page_id = page_id or (cfg.get("publish") or {}).get("page_id")
    channel_id = (channel_id
                  or (cfg.get("publish") or {}).get("youtube_channel_id"))
    _raw_sink = {}
    fb = None
    fb_note = None
    fb_bin = publish.find_facebook_bin()
    if not fb_bin:
        fb_note = "facebook-cli غير متاح"
    elif not page_id:
        fb_note = "معرّف الصفحة غير مضبوط (publish.page_id)"
    else:
        fb, fb_note = analyze.fb_last_video(
            fb_bin, page_id, raw_sink=_raw_sink)
    yt, yt_note = analyze.yt_latest_video(channel_id, raw_sink=_raw_sink)
    # لقطة خام قبل حساب أي ملخص (جولة v0.1.37 — البند 11):
    # الاستجابتان الخام حرفيًا + بصمة + طابع زمني.
    _runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(_runs_dir, exist_ok=True)
    _snapshot_path = insights.save_snapshot(
        _runs_dir, _raw_sink.get("facebook"), _raw_sink.get("youtube"))
    print("== آخر فيديو منشور — تحليل الأداء ==")
    print("-- فيسبوك --")
    if fb:
        print("المنشور: %s" % (fb["caption"][:80] or fb["object_id"]))
        print("نُشر: %s" % (fb["published_time"] or "غير معروف"))
        print("المشاهدات: %s — التفاعلات: %s — الإعجابات: %s — "
              "التعليقات: %s — المشاركات: %s"
              % (analyze.format_value(fb["views"]),
                 analyze.format_value(fb["engagements"]),
                 analyze.format_value(fb["reactions"]),
                 analyze.format_value(fb["comments"]),
                 analyze.format_value(fb["shares"])))
        if fb_note:
            print("ملاحظة: %s" % fb_note)
    else:
        print("غير معروف — %s" % (fb_note or "تعذرت القراءة"))
    print("-- يوتيوب --")
    if yt:
        print("الفيديو: %s" % (yt["title"] or yt["video_id"]))
        print("رُفع: %s — المدة: %s ثانية"
              % (yt["upload_date"] or "غير معروف",
                 yt["duration"] if yt["duration"] is not None
                 else "غير معروف"))
        print("المشاهدات: %s — الإعجابات: %s — التعليقات: %s"
              % (analyze.format_value(yt["views"]),
                 analyze.format_value(yt["likes"]),
                 analyze.format_value(yt["comments"])))
    else:
        print("غير معروف — %s" % (yt_note or "تعذرت القراءة"))
    print("-- ما يُحسَّن في الفيديو التالي --")
    # توصيل فهرس الفيديوهات (جولة v0.1.48): يُمرَّر صراحةً إلى
    # suggest() مرة واحدة ويُعاد استخدام نتيجته في الطباعة
    # وملف JSON؛ وبلا qdrant-client أو Ollama يرجع None
    # فيُحذف سطر «أقرب فيديو سابق» بصمت (fail-open).
    from lib import story_index as story_index_lib
    _index = story_index_lib.get_default_index()
    try:
        _suggestions = analyze.suggest(fb, yt, index=_index)
    finally:
        if _index is not None:
            _index.close()
    for i, tip in enumerate(_suggestions, 1):
        print("%d. %s" % (i, tip))
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    out_path = os.path.join(
        runs_dir, "analyze-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "snapshot_file": _snapshot_path,
                   "facebook": fb, "facebook_note": fb_note,
                   "youtube": yt, "youtube_note": yt_note,
                   "suggestions": _suggestions},
                  f, ensure_ascii=False, indent=2)
    print("حُفظ التحليل في: %s" % out_path)
    print("حُفظت اللقطة الخام في: %s" % _snapshot_path)
    return 0 if (fb is not None or yt is not None) else 1


# ------------------------------------------------------------ analyze-ref
def cmd_analyze_ref(cfg, url, model="small"):
    """تحليل فيديو مرجعي وحفظ JSON في runs/ref-<id>.json.

    تحليل خاص فقط (انظر تنبيه ref_analyzer.COPYRIGHT_NOTICE) —
    بلا إعادة نشر أو توزيع، والصوت المنزّل يُحذف بعد التحليل.
    """
    try:
        result = ref_analyzer.analyze_reference(url, model=model)
    except ref_analyzer.RefError as e:
        print("فشل تحليل الفيديو المرجعي: %s" % e)
        return 1
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    vid = result["video"].get("id") or "unknown"
    out_path = os.path.join(runs_dir, "ref-%s.json" % vid)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    v = result["video"]
    print("الفيديو: %s" % v.get("title"))
    print("المدة: %s ثانية — المشاهدات: %s — الناشر: %s"
          % (v.get("duration_seconds"), v.get("view_count"),
             v.get("uploader")))
    a = result.get("analysis")
    if a:
        print("الهوك (أول 10 ثوانٍ): %s" % a["hook_first_10s"])
        print("سرعة السرد: %s كلمة/دقيقة (%d كلمة)"
              % (a["words_per_minute"], a["word_count"]))
        print("الختام (آخر 10 ثوانٍ): %s%s"
              % (a["ending_last_10s"],
                 " — فيه سؤال" if a["ending_has_question"] else ""))
    print("حُفظ التحليل في: %s" % out_path)
    return 0


# ------------------------------------------------------- analyze --dna
def cmd_analyze_snapshot(cfg):
    """أعد قياس DNA لفيديوهات مجموعة التقييم وقارن بالأساس
    (جولة v0.1.37 — مقترح tinker رقم 5).

    يعيد قياس كل فيديو له ملف محلي (الهوك من المجموعة نفسها،
    والـslug يُشتق من اسم الملف) ويحفظ اللقطة الخام في
    runs/eval-snapshot-<وقت>.json. يرجع 1 إن تغيّر أي مقياس
    عن الأساس (انحدار)، و0 إن طابق الكل.
    """
    from lib import eval_set as eval_set_lib
    try:
        data = eval_set_lib.load_eval_set()
    except (OSError, ValueError) as e:
        print("تعذرت قراءة مجموعة التقييم: %s" % e)
        return 1
    videos = eval_set_lib.eval_videos(data)
    subs_dir = expand("~/workspace/videos/subs")
    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    results = []
    any_change = False
    for entry in videos:
        video_file = entry.get("video_file")
        if not video_file:
            print("- %s: بلا ملف فيديو — يُتخطى (%s)"
                  % (entry["id"],
                     entry.get("video_file_note", "لا ملف على القرص")))
            results.append({"id": entry["id"], "skipped": True,
                            "reason": "no video file"})
            continue
        path = expand(video_file)
        if not os.path.isfile(path):
            print("- %s: ملف الفيديو غير موجود — يُتخطى: %s"
                  % (entry["id"], path))
            results.append({"id": entry["id"], "skipped": True,
                            "reason": "missing file"})
            continue
        try:
            report = dna_lib.analyze_dna(
                path, title=entry.get("title"),
                hook=entry.get("hook"), subs_dir=subs_dir)
        except (dna_lib.DnaError, check_lib.CheckError) as e:
            print("- %s: فشل القياس: %s" % (entry["id"], e))
            results.append({"id": entry["id"], "skipped": True,
                            "reason": str(e)})
            continue
        measured = {
            "hook_score": (report["hook"] or {}).get("total"),
            "duration_seconds": report["duration"],
            "shot_count": report["pacing"]["shot_count"],
            "avg_shot_seconds": report["pacing"]["avg_shot_seconds"],
            "wpm": report["word_density"]["wpm"],
            "silence_ok": report["silence"]["ok"],
        }
        diffs = eval_set_lib.compare_measurement(entry, measured)
        changed = [d for d in diffs if d["changed"]]
        if changed:
            any_change = True
        print("- %s: %s" % (
            entry["id"],
            "مطابق للأساس" if not changed else "تغيّر عن الأساس!"))
        for d in changed:
            print("    %s: %s ← %s" % (d["metric"], d["baseline"],
                                       d["measured"]))
        results.append({"id": entry["id"], "measured": measured,
                        "diffs": diffs})
    out_path = os.path.join(
        runs_dir, "eval-snapshot-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"seed": data.get("seed"),
                   "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "results": results}, f, ensure_ascii=False, indent=2)
    print("حُفظت اللقطة في: %s" % out_path)
    return 1 if any_change else 0


def cmd_ab_eval_set(cfg, variants=3, cost_per_video=0):
    """اختبر هوكات بديلة لكل فيديو في مجموعة التقييم وقارن
    بالأساس (جولة v0.1.37 — مقترح tinker رقم 5).

    لكل فيديو: يقترح N هوكًا عبر LLM ويسجّل درجته DNA، ويقول
    إن كان أي بديل يتفوق على درجة أساس المجموعة. لا ينشر
    شيئًا؛ السجل في runs/ab-eval-<وقت>.json.
    """
    from lib import eval_set as eval_set_lib
    try:
        data = eval_set_lib.load_eval_set()
    except (OSError, ValueError) as e:
        print("تعذرت قراءة مجموعة التقييم: %s" % e)
        return 1
    videos = eval_set_lib.eval_videos(data)
    cfg_o = cfg["omniroute"]
    _eval_llm = {}

    def chat_fn(prompt):
        text, _via, _model = _llm_chat(
            cfg, prompt, max_tokens=400, temperature=0.8)
        _eval_llm["via"] = _via
        _eval_llm["model"] = _model
        return text

    runs_dir = expand(cfg["paths"]["runs_dir"])
    os.makedirs(runs_dir, exist_ok=True)
    results = []
    for entry in videos:
        baseline = entry.get("hook_score")
        print("== %s — الأساس: %s/%s =="
              % (entry["title"], baseline, entry.get("hook_max", 9)))
        if baseline is None:
            print("  بلا درجة أساس — يُتخطى")
            results.append({"id": entry["id"], "skipped": True})
            continue
        suggested, src = ab_lib.suggest_hooks_n(
            entry["title"], chat_fn, n=variants)
        print("  الهوكات المقترحة (%s)" % src)
        scored = []
        for h in suggested:
            res = dna_lib.score_hook(h)
            scored.append({"hook": h, "score": res["total"],
                           "verdict": res["verdict"]})
        scored.sort(key=lambda v: v["score"], reverse=True)
        for v in scored:
            print("  - %s — DNA ‏%s/9 (%s)"
                  % (v["hook"], v["score"], v["verdict"]))
        best = scored[0] if scored else None
        beats = bool(best) and best["score"] > baseline
        print("  %s" % ("أفضل بديل يتفوق على الأساس ✓"
                        if beats
                        else "لا بديل يتفوق على الأساس — الأساس باقٍ"))
        results.append({"id": entry["id"], "baseline": baseline,
                        "best": best, "beats_baseline": beats,
                        "variants": scored})
    out_path = os.path.join(
        runs_dir, "ab-eval-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"seed": data.get("seed"),
                   "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "llm_model": _eval_llm.get("model"),
                   "llm_via": _eval_llm.get("via"),
                   "results": results}, f, ensure_ascii=False, indent=2)
    print("سُجّل في: %s" % out_path)
    if _eval_llm.get("model"):
        print("النموذج المستخدم: %s (عبر %s)"
              % (_eval_llm["model"], _eval_llm.get("via")))
    return 0


def cmd_analyze_dna(cfg, video=None, hook=None, subs_dir=None,
                    story_text=None, page_id=None, channel_id=None,
                    slug=None, reference=None, new_story_path=None,
                    audio_profile=None):
    """تحليل DNA الفيروسي لفيديو واحد (الجولة 7)."""
    if not video:
        print("تحليل DNA يحتاج --video <ملف mp4>")
        return 2
    page_id = page_id or (cfg.get("publish") or {}).get("page_id")
    channel_id = (channel_id
                  or (cfg.get("publish") or {}).get("youtube_channel_id"))
    title = os.path.splitext(os.path.basename(expand(video)))[0]
    story = None
    if story_text:
        try:
            with open(expand(story_text), encoding="utf-8") as f:
                story = f.read()
        except OSError as e:
            print("تعذرت قراءة ملف نص القصة: %s" % e)
            return 1
    # أرقام المنصتين لنفس الفيديو (بمطابقة العنوان/الهوك) — أي
    # مصدر لا يصل يُطبع «غير معروف» في التقرير.
    fb = yt = None
    needle = (hook or "").strip() or title
    fb_bin = publish.find_facebook_bin()
    if page_id and fb_bin:
        entries, _note = ab_lib.fetch_fb_posts(fb_bin, page_id)
        match = ab_lib.match_variant(entries, needle, "caption")
        if match is not None:
            fb = match
    if channel_id:
        yt_entries, _note = ab_lib.fetch_yt_uploads(channel_id)
        match = ab_lib.match_variant(yt_entries, needle, "title")
        if match is not None:
            yt = match
    try:
        report = dna_lib.analyze_dna(
            expand(video), title=title, hook=hook or None,
            subs_dir=subs_dir, story_text=story, fb=fb, yt=yt,
            slug=slug)
    except dna_lib.DnaError as e:
        print("فشل تحليل DNA: %s" % e)
        return 1
    except check_lib.CheckError as e:
        print("فشل تحليل DNA: %s" % e)
        return 1
    if audio_profile:
        # ملف أداء الصوت (جولة v0.1.38 §2): يُلحق بالتقرير؛
        # وفشله لا يُفشل DNA أبدًا — تحذير ويُكمل.
        try:
            report["audio_profile"] = audio_profile_lib.build_profile(
                expand(audio_profile))
        except Exception as e:
            print("تحذير: تعذر بناء ملف أداء الصوت (%s)" % e)
    print(dna_lib.format_report(report))
    if reference:
        new_story = None
        if new_story_path:
            try:
                with open(expand(new_story_path),
                          encoding="utf-8") as f:
                    new_story = f.read()
            except OSError as e:
                print("تعذرت قراءة ملف نص القصة الجديدة: %s" % e)
                return 1
        try:
            ref_report = dna_lib.analyze_dna(
                expand(reference), title=None, hook=None,
                subs_dir=subs_dir, story_text=story_text, slug=slug)
        except dna_lib.DnaError as e:
            print("فشل تحليل DNA للمرجع: %s" % e)
            return 1
        except check_lib.CheckError as e:
            print("فشل تحليل DNA للمرجع: %s" % e)
            return 1
        print(dna_lib.build_rebuild_proposal(ref_report, new_story))
    runs_dir = expand(cfg["paths"]["runs_dir"])
    out_path = dna_lib.save_report(report, runs_dir)
    print("حُفظ تقرير DNA في: %s" % out_path)
    return 0


# ------------------------------------------------------------------ ideas
def cmd_ideas(cfg, count=5, theme=None, add=None, queue_file=None):
    """ولّد أفكار قصص بأسلوب الصفحة (النموذج أولًا، والبنك
    المحلي بديلًا)، مع منع تكرار أي عنوان في الطابور.
    --add N يضيف الفكرة رقم N إلى الطابور عبر queue add."""
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    cfg_o = cfg["omniroute"]
    _ideas_llm = {}

    def chat_fn(prompt):
        text, _via, _model = _llm_chat(
            cfg, prompt, max_tokens=800, temperature=0.8)
        _ideas_llm["via"] = _via
        _ideas_llm["model"] = _model
        return text

    ideas_list, notes = ideas.generate_ideas(
        queue_path, count=count, theme=theme, chat_fn=chat_fn)
    print(ideas.format_ideas(ideas_list))
    if _ideas_llm.get("model"):
        print("النموذج المستخدم: %s (عبر %s)"
              % (_ideas_llm["model"], _ideas_llm.get("via")))
    for note in notes:
        print("ملاحظة: %s" % note)
    if not ideas_list:
        print("لم تُولَّد أي فكرة — جرّب موضوعًا آخر")
        return 1
    if add is not None:
        if add < 1 or add > len(ideas_list):
            print("رقم الفكرة غير صالح: %d (المتاح 1–%d)"
                  % (add, len(ideas_list)))
            return 2
        idea = ideas_list[add - 1]
        stories_dir = os.path.join(STUDIO_DIR, "queue")
        try:
            result = ideas.add_idea(queue_path, idea, stories_dir)
        except queue_lib.QueueError as e:
            print("رفضت الإضافة: %s" % e)
            return 1
        print("أُضيفت الفكرة رقم %d إلى الطابور: %s"
              % (result["number"], result["title"]))
        print("مسودة النص في: %s" % result["text_file"])
    return 0


# ------------------------------------------------------------------ daily
def cmd_schedule_watch(cfg, post_id, story_slug, slot="morning",
                       moral="", question="", next_part_time=None,
                       execute=False):
    """`schedule --watch`: راقب منشورًا مجدولًا وعلّق أول تعليق
    عند نشره. dry-run افتراضيًا؛ والتنفيذ فقط مع --execute."""
    story = {"moral": moral, "question": question,
             "next_part_time": next_part_time or ""}
    if not execute:
        # الوضع التجريبي لا يحتاج facebook-cli إطلاقًا: خطة
        # ونص التعليق فقط، بلا قراءة وبلا تعليق.
        res = schedule_watch_lib.watch_slot(
            post_id, story, None, None, execute=False, slot=slot)
        print("-- خطة مراقبة (وضع تجريبي — لم يُقرأ المنشور ولم يُعلَّق) --")
        print("المنشور: %s — الموعد: %s" % (res["post_id"], res["slot"]))
        print(res["would_post"])
        return 0
    fb = publish.find_facebook_bin()
    if not fb:
        print("facebook-cli غير متاح في PATH — أكمل الربط أولًا")
        return 1

    def read_fn(pid):
        proc = subprocess.run(
            [fb, "post", "read", "--post-id", str(pid)],
            capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise publish.PublishError(
                "فشل قراءة حالة المنشور %s (رمز الخروج %d): %s"
                % (pid, proc.returncode,
                   (proc.stderr or proc.stdout or "")[-300:]))
        try:
            data = json.loads(proc.stdout or "")
        except ValueError:
            raise publish.PublishError(
                "مخرجات facebook-cli ليست JSON صالحًا")
        return data  # schedule_watch يستخرج مفتاح "state" منه

    def comment_fn(pid, text):
        proc = publish._run(
            [fb, "post", "comments", "add", "--post-id", str(pid),
             "--text", text],
            "نشر أول تعليق على فيسبوك")
        if proc.returncode != 0:
            raise publish.PublishError(
                "فشل نشر التعليق (رمز الخروج %d): %s"
                % (proc.returncode,
                   (proc.stderr or proc.stdout or "")[-300:]))
        try:
            return json.loads((proc.stdout or "").strip())
        except ValueError:
            return {"comment_id": "غير معروفة"}

    res = schedule_watch_lib.watch_slot(post_id, story, read_fn,
                                        comment_fn, execute=True,
                                        slot=slot,
                                        runs_dir=expand(
                                            cfg["paths"]["runs_dir"]))
    # runs_dir: دلالات المهام المجدولة (v0.1.41 بند 3) — تسجيل
    # الـoccurrence قبل البدء؛ ريستارت بعد البدء يُتخطى لا يُكرر.
    if res.get("ok"):
        print("نُشر أول تعليق على المنشور %s (comment_id: %s)"
              % (res["post_id"], res.get("comment_id", "غير معروفة")))
        return 0
    print(res.get("error") or res.get("message") or "فشل غير معروف")
    return 1


def _print_first_scene_sample(cfg, project):
    """اطبع عيّنة المشهد الأول في dry-run (جولة v0.1.37).

    تجميلية — لا تفشل الخطة أبدًا: مشروع غير جاهز أو خطأ
    قراءة يُطبع سطرًا واحدًا فقط.
    """
    if not project:
        return
    try:
        sample = first_scene.first_scene_sample(cfg, project)
    except Exception as e:  # noqa: BLE001 — العيّنة لا تفشل الخطة
        print("تعذّرت عيّنة المشهد الأول: %s" % e)
        return
    if sample is None:
        print("عيّنة المشهد الأول: المشروع غير جاهز للقراءة")
        return
    print(first_scene.format_sample(sample))
    print("")


def cmd_daily(cfg, slot="morning", execute=False, video=None,
              moral="", question="", queue_file=None,
              auto_approve=False, backend="concat", grade=None):
    """أمر اليوم الواحد: خطة (dry-run افتراضيًا) أو تنفيذ
    كامل مع --execute (إنتاج + فحص + مصغرة + نشر + نص
    أول تعليق). الجولة 7: مسار Veo يحفظ خطة المشاهد ويطلب
    الموافقة على الإنفاق تفاعليًا — إلا مع --auto-approve
    أو في تشغيل غير تفاعلي (كرون)."""
    if queue_file:
        cfg = copy.deepcopy(cfg)
        cfg["paths"]["queue_file"] = queue_file
    # بوابة بنية الطابور (جولة v0.1.37): طابور معطوب = لا تخطيط
    # ولا إنتاج — أصلح الطابور أولًا بـ `queue validate`.
    _ok, _issues = queue_check.validate_queue_file(
        expand(cfg["paths"]["queue_file"]))
    if not _ok:
        print("بنية الطابور معطوبة — أصلحها أولًا "
              "(python3 studio.py queue validate):")
        for _issue in _issues:
            print("  - %s" % _issue)
        return 1
    try:
        plan = daily.plan_daily(
            cfg, slot, video=video, moral=moral, question=question,
            ready_fn=lambda s: check_story_ready(cfg, s))
    except daily.DailyError as e:
        print("تعذر التخطيط لليوم: %s" % e)
        return 1
    except publish.PublishError as e:
        print("خطأ في بيانات النشر: %s" % e)
        return 1
    if not execute:
        print(daily.format_plan(plan))
        _print_first_scene_sample(cfg, plan.get("project"))
        print("== وضع تجريبي — لم يُنفَّذ شيء "
              "(أضف --execute للتنفيذ) ==")
        return 0

    def produce_fn(c, slug, project, out_path):
        return cmd_run(c, slug, project, out_path, False,
                       backend=backend, grade=grade)

    def check_fn(v):
        return check_lib.run_checks(v)

    def thumbnail_fn(v, hook, out):
        path, _sec, _lines = thumbnail.make_thumbnail(v, hook, out)
        return path

    def publish_fn(c, v, t, cap, thumb):
        return cmd_publish(c, v, t, cap, thumbnail=thumb,
                           skip_check=True)

    try:
        rc, _result = daily.execute_daily(
            cfg, plan, produce_fn, check_fn, thumbnail_fn, publish_fn,
            expand(cfg["paths"]["runs_dir"]), auto_approve=auto_approve,
            record_spend_fn=_record_veo_spend)
    except check_lib.CheckError as e:
        print("تعذر فحص الجودة: %s" % e)
        return 1
    return rc


# ------------------------------------------------------------------ batch
def cmd_batch(cfg, count=1, source="openmontage", execute=False,
              continue_on_error=False, queue_file=None, from_json=None,
              no_spend=False, no_cache=False):
    """دفعة جماعية (الجولة 7): القصص التالية من الطابور في
    تشغيل واحد — إنتاج + فحص + مصغرة + سجل. افتراضيًا وضع
    تجريبي (يطبع الخطة بلا تنفيذ)؛ والتنفيذ فقط مع --execute.
    --from-json يبني الخطة من ملف JSON بدل الطابور (ويتخطى
    بوابة بنية الطابور)؛ و--no-spend يحاكي الدفعة كاملة بلا
    أي إنفاق (ويرفض مع --execute)؛ و--no-cache يعطّل إعادة
    استخدام منتجات الريندر."""
    if no_spend and execute:
        print("لا يجتمع --no-spend مع --execute — اختر أحدهما")
        return 2
    if queue_file:
        cfg = copy.deepcopy(cfg)
        cfg["paths"]["queue_file"] = queue_file
    if from_json:
        try:
            plan = batch_lib.plan_batch_from_json(
                cfg, json_path=expand(from_json), source=source,
                ready_fn=lambda s: check_story_ready(cfg, s))
        except batch_lib.BatchError as e:
            print("تعذرت خطة الدفعة من JSON: %s" % e)
            return 1
    else:
        # بوابة بنية الطابور (جولة v0.1.37) — انظر cmd_daily.
        _ok, _issues = queue_check.validate_queue_file(
            expand(cfg["paths"]["queue_file"]))
        if not _ok:
            print("بنية الطابور معطوبة — أصلحها أولًا "
                  "(python3 studio.py queue validate):")
            for _issue in _issues:
                print("  - %s" % _issue)
            return 1
        try:
            plan = batch_lib.plan_batch(
                cfg, count, source=source,
                ready_fn=lambda s: check_story_ready(cfg, s))
        except batch_lib.BatchError as e:
            print("تعذرت خطة الدفعة: %s" % e)
            return 1
    if no_spend:
        report = batch_lib.validate_batch(
            cfg, plan, runs_dir=expand(cfg["paths"]["runs_dir"]))
        print(batch_lib.format_no_spend_report(report))
        return 0 if report.get("ok") else 1
    if not execute:
        print(batch_lib.format_plan(plan))
        _first_ready = next(
            (s for s in plan.get("stories") or []
             if s.get("ready") and s.get("project")), None)
        if _first_ready is not None:
            _print_first_scene_sample(cfg, _first_ready["project"])
        print("== وضع تجريبي — لم يُنفَّذ شيء "
              "(أضف --execute للتنفيذ) ==")
        return 0

    def produce_fn(c, slug, project, out_path):
        return cmd_run(c, slug, project, out_path, False)

    def check_fn(v):
        return check_lib.run_checks(v)

    def thumbnail_fn(v, hook, out):
        path, _sec, _lines = thumbnail.make_thumbnail(v, hook, out)
        return path

    try:
        rc, _result = batch_lib.execute_batch(
            cfg, plan, produce_fn, check_fn, thumbnail_fn,
            expand(cfg["paths"]["runs_dir"]),
            continue_on_error=continue_on_error,
            record_spend_fn=_record_veo_spend,
            use_cache=not no_cache)
    except check_lib.CheckError as e:
        print("تعذر فحص الجودة: %s" % e)
        return 1
    return rc


# ------------------------------------------------------------- scene-plan
def cmd_scene_plan(cfg, story=None, clips=6, queue_file=None,
                   template=None, template_hero=None,
                   template_situation=None, template_moral=None,
                   lang="ar", template_lang=None):
    """خطة مشاهد Veo مكتوبة لقصة من الطابور (الجولة 7) — تُطبع
    وتُحفظ قبل أي إنفاق، مع فحص السقف. story: رقم القصة في
    الطابور أو جزء من عنوانها. --template يبني الموجهات من
    قالب قصة جاهز (هوك/تصعيد/انقلاب/عبرة) عند غياب نص الطابور.
    template_lang: لغة القالب ar/en (افتراضيًا لغة CLI) —
    تُمرَّر عبر set_template_lang لأن lib/scene_plan.py
    يستدعي build_scene_outline بلا وسيط لغة (يُعاد الضبط
    كما كان بعد البناء)."""
    if story is None:
        print(i18n_lib.t("sceneplan_need_story", lang))
        return 2
    _templates = [t[0] for t in story_templates_lib.list_templates()]
    if template is not None and template not in _templates:
        print(i18n_lib.t("sceneplan_unknown_template", lang, template,
                         ", ".join(_templates)))
        return 2
    eff_template_lang = None
    if template is not None:
        raw = template_lang if template_lang is not None else lang
        try:
            eff_template_lang = story_templates_lib.set_template_lang(raw)
        except ValueError:
            print(i18n_lib.t("sceneplan_template_lang_invalid", lang,
                             raw))
            return 2
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    if not os.path.isfile(queue_path):
        print(i18n_lib.t("sceneplan_queue_missing", lang, queue_path))
        return 1
    try:
        stories = parse_queue(queue_path)
    except OSError as e:
        print(i18n_lib.t("sceneplan_queue_unreadable", lang, e))
        return 1
    target = None
    if str(story).strip().isdigit():
        for s in stories:
            if s["number"] == int(str(story).strip()):
                target = s
                break
    else:
        needle = str(story).strip()
        for s in stories:
            if needle in s["title"]:
                target = s
                break
    if target is None:
        print(i18n_lib.t("sceneplan_no_match", lang, story))
        return 1
    try:
        plan = scene_plan_lib.build_scene_plan(
            cfg, target, clips=clips, template=template,
            template_hero=template_hero,
            template_situation=template_situation,
            template_moral=template_moral)
    except scene_plan_lib.CapError as e:
        print(i18n_lib.t("sceneplan_cap_rejected", lang, e))
        return 1
    except ValueError as e:
        print(i18n_lib.t("sceneplan_invalid", lang, e))
        return 2
    finally:
        if eff_template_lang is not None:
            story_templates_lib.set_template_lang("ar")
    print(scene_plan_lib.format_plan(plan))
    out_path = scene_plan_lib.save_plan(
        plan, expand(cfg["paths"]["runs_dir"]))
    print(i18n_lib.t("sceneplan_saved", lang, out_path))
    return 0


# ------------------------------------------- tiktok-auth / instagram-auth
def cmd_social_auth(cfg, platform, token=None):
    """خطوات ربط TikTok/Instagram يدويًا + حفظ التوكن (600).

    بلا --token: يطبع الخطوات فقط. مع --token: يحفظه ولا يعرضه.
    """
    if token:
        try:
            path = social_lib.save_token(platform, token)
        except social_lib.SocialPublishError as e:
            print("فشل حفظ التوكن: %s" % e)
            return 1
        print("حُفظ توكن %s في: %s (صلاحية 600 — لم يُعرض)"
              % (platform, path))
        print("أعد النشر الآن: python3 studio.py publish --video "
              "<ملف> --title \"...\" --platforms %s" % platform)
        return 0
    print(social_lib.setup_steps(platform))
    return 0


# ------------------------------------------- tiktok-bundle / tiktok-status
def cmd_tiktok_bundle(cfg, video, title, caption="", moral="",
                      next_part=False,
                      next_part_time="بكرة 7 مساءً", ai_voice=False,
                      out_dir=None, dry_run=False):
    """ابنِ حزمة رفع TikTok لمهمة متصفح — بلا نشر وبلا شبكة.

    مع --dry-run: يبني الكابشن والخطوات ويطبعهما بلا أي كتابة
    ملفات وبلا فحص الفيديو. بلا --dry-run: يكتب الحزمة
    (metadata.json + caption.txt + steps.txt) في مجلد الحزمة
    ويرجع 0؛ وعند TikTokPublishError يطبع خطأً عربيًا ويرجع 1.
    """
    if dry_run:
        try:
            text = tiktok_lib.build_tiktok_caption(
                title, caption or "", moral=moral, next_part=next_part,
                next_part_time=next_part_time, ai_voice=ai_voice)
        except tiktok_lib.TikTokPublishError as e:
            print("فشل بناء كابشن TikTok: %s" % e)
            return 1
        print("== كابشن TikTok (تجريبي — بلا كتابة ملفات) ==")
        print(text)
        print("عدد حروف الكابشن: %d / %d"
              % (len(text), tiktok_lib.TIKTOK_CAPTION_LIMIT))
        print("== خطوات الرفع (تجريبي — ستُكتب في steps.txt) ==")
        steps_fn = getattr(tiktok_lib, "_browser_task_steps", None)
        if steps_fn is not None:
            print(steps_fn(os.path.abspath(expand(video))))
        else:
            print("1) افتح %s مسجَّلًا باسم @%s."
                  % (tiktok_lib.TIKTOK_UPLOAD_URL,
                     tiktok_lib.TIKTOK_USERNAME_DEFAULT))
            print("2) ارفع الملف: %s"
                  % os.path.abspath(expand(video)))
            print("3) الصق الكابشن أعلاه حرفيًا — بلا إضافة ولا حذف.")
            print("4) الرؤية: عامة (Public)، ثم انشر الفيديو.")
        return 0
    bundle_dir = out_dir or os.path.join(
        expand(cfg["paths"]["videos_dir"]),
        "tiktok-bundle-%s" % time.strftime("%Y%m%d-%H%M%S"))
    try:
        result = tiktok_lib.write_tiktok_bundle(
            bundle_dir, expand(video), title, caption or "",
            moral=moral, next_part=next_part,
            next_part_time=next_part_time, ai_voice=ai_voice)
    except tiktok_lib.TikTokPublishError as e:
        print("فشل بناء حزمة TikTok: %s" % e)
        return 1
    print("حزمة رفع TikTok جاهزة في: %s" % result["bundle_dir"])
    print("عدد حروف الكابشن: %d / %d"
          % (len(result["caption"]), tiktok_lib.TIKTOK_CAPTION_LIMIT))
    print("البيانات: %s" % result["metadata_path"])
    print("الخطوات: %s" % result["steps_path"])
    info = result.get("video_info") or {}
    print("فحص الفيديو: %s (%d بايت)"
          % (info.get("video") or expand(video),
             info.get("size") or 0))
    duration = info.get("duration")
    print("المدة: %s"
          % ("%.1f ثانية" % duration if duration is not None
             else "غير معروفة (تُفحص عند الرفع)"))
    width, height = info.get("width"), info.get("height")
    print("الأبعاد: %s"
          % ("%d×%d" % (width, height) if width and height
             else "غير معروفة (تُفحص عند الرفع)"))
    print("الصوت: %s"
          % ("موجود" if info.get("has_audio") else
             "غير معروف (تُفحص عند الرفع)"
             if info.get("has_audio") is None else "مفقود"))
    print("الرفع عبر مهمة متصفح (بلا نشر من هنا) — الخطوات في steps.txt")
    return 0


def cmd_tiktok_status(cfg):
    """اطبع حالة إعداد TikTok كأسطر عربية (قراءة فقط، بلا شبكة)."""
    st = tiktok_lib.tiktok_status(cfg, studio_dir=STUDIO_DIR)
    print(st["detail"])
    print("الحساب: @%s" % st["username"])
    print("الرابط: %s" % st["profile_url"])
    print("طريقة الرفع: مهمة متصفح (بلا توكن API)")
    print("ربط API: %s" % ("موجود ملف توكن (المسار غير مربوط بعد)"
                            if st["api_linked"] else "غير مربوط"))
    return 0


# ------------------------------------------- tiktok-long (النسخة الطويلة)
def cmd_tiktok_long(cfg, video_a, video_b, title, caption="",
                    moral="", kind="full", out_dir=None,
                    max_seconds=None, dry_run=False, part_tags=None):
    """ادمج فيديوهين قصيرين في النسخة الطويلة اليومية لـ TikTok
    (65–110 ثانية) + حزمة رفع لمهمة متصفح — بلا نشر وبلا شبكة.

    مع --dry-run: يفحص المدخلين ويطبع مجموع المدتين بلا أي دمج
    وبلا كتابة ملفات. بلا --dry-run: يكتب الحزمة (الفيديو المدمج
    + metadata.json + caption.txt + steps.txt + long.json) في
    مجلد الحزمة ويرجع 0؛ وعند TikTokLongError/TikTokPublishError
    يطبع خطأً عربيًا ويرجع 1.
    """
    max_seconds = (tiktok_long_lib.LONG_MAX_SECONDS
                   if max_seconds is None else max_seconds)
    if dry_run:
        try:
            info_a = tiktok_long_lib.probe_short(expand(video_a))
            info_b = tiktok_long_lib.probe_short(expand(video_b))
        except tiktok_long_lib.TikTokLongError as e:
            print("فشل فحص النسخة الطويلة: %s" % e)
            return 1
        total = info_a["duration"] + info_b["duration"]
        print("المدخل الأول: %.1f ثانية (%s)"
              % (info_a["duration"], info_a["video"]))
        print("المدخل الثاني: %.1f ثانية (%s)"
              % (info_b["duration"], info_b["video"]))
        print("مجموع المدتين: %.1f ثانية (النطاق %.0f–%.0f)"
              % (total, tiktok_long_lib.LONG_MIN_SECONDS, max_seconds))
        if total < tiktok_long_lib.LONG_MIN_SECONDS or \
                total > max_seconds:
            print("المجموع خارج نطاق النسخة الطويلة — اختر زوجًا آخر")
            return 1
        print("الزوج صالح للنسخة الطويلة — بلا دمج في هذا الوضع")
        return 0
    bundle_dir = out_dir or os.path.join(
        expand(cfg["paths"]["videos_dir"]),
        "tiktok-long-%s" % time.strftime("%Y%m%d-%H%M%S"))
    try:
        result = tiktok_long_lib.write_long_bundle(
            bundle_dir, expand(video_a), expand(video_b),
            title, caption or "", moral=moral, kind=kind,
            part_tags=part_tags, max_seconds=max_seconds)
    except (tiktok_long_lib.TikTokLongError,
            tiktok_lib.TikTokPublishError) as e:
        print("فشل بناء النسخة الطويلة: %s" % e)
        return 1
    info = result["video_info"]
    print("النسخة الطويلة جاهزة في: %s" % result["bundle_dir"])
    print("الفيديو المدمج: %s (%.1f ثانية، %d×%d، %d بايت)"
          % (info["video"], info["duration"],
             info["width"], info["height"], info["size"]))
    print("النوع: %s — العنوان: %s"
          % (kind, tiktok_long_lib.long_title(title, kind)))
    print("عدد حروف الكابشن: %d / %d"
          % (len(result["caption"]), tiktok_lib.TIKTOK_CAPTION_LIMIT))
    print("البيانات: %s" % result["metadata_path"])
    print("تفاصيل الدمج: %s" % result["long_path"])
    print("الخطوات: %s" % result["steps_path"])
    print("الرفع عبر مهمة متصفح (بلا نشر من هنا) — الخطوات في steps.txt")
    return 0


# ---------------------------------------------------------------------- ab
def _cmd_ab_variants(cfg, video, hook_a, hook_b, title, out_dir,
                     cost_per_video, variants, engine="fast",
                     balance_units=None, ledger_entries=None):
    """اختبار A/B بعدة نسخ (≥3): اقتراح N هوكًا + نسخ مرتبة
    بدرجة DNA + الفائز (الأعلى درجة)."""
    runs_dir = expand(out_dir or cfg["paths"]["runs_dir"])
    cfg_o = cfg["omniroute"]
    _ab_llm = {}

    def chat_fn(prompt):
        text, _via, _model = _llm_chat(
            cfg, prompt, max_tokens=400, temperature=0.8)
        _ab_llm["via"] = _via
        _ab_llm["model"] = _model
        return text

    hooks = [h for h in (hook_a, hook_b) if h]
    if len(hooks) < variants:
        suggested, src = ab_lib.suggest_hooks_n(
            title or os.path.basename(video), chat_fn, n=variants)
        for h in suggested:
            if h not in hooks:
                hooks.append(h)
            if len(hooks) >= variants:
                break
        print("الهوكات المقترحة (%s)" % src)
    try:
        record = ab_lib.create_ab_variants(
            expand(video), hooks[:variants], runs_dir, title=title,
            cost_per_video=cost_per_video,
            llm_model=_ab_llm.get("model"), engine=engine,
            balance_units=balance_units,
            ledger_entries=ledger_entries)
    except (ValueError, thumbnail.ThumbnailError) as e:
        print("فشل اختبار A/B: %s" % e)
        return 1
    print("== نسخ اختبار A/B (مرتبة بدرجة DNA) ==")
    for i, v in enumerate(record["variants"], 1):
        mark = " ★ الفائز" if v["hook"] == record["best"] else ""
        print("%d) %s — DNA ‏%s/%s (%s)%s"
              % (i, v["hook"], v["dna_score"], v["dna_max"],
                 v["dna_verdict"], mark))
        print("   المصغرة: %s" % v["thumb"])
        if v.get("cost_estimate"):
            print("   التكلفة: %s"
                  % ab_lib.format_variant_cost(v["cost_estimate"]))
    cost = record.get("cost_estimate_units") or {}
    if cost:
        print("تقدير التكلفة (وحدات Veo): لكل نسخة %s — المجموع %s"
              % (cost_per_video, cost.get("total")))
    print("الفائز (أعلى درجة DNA): %s" % record["best"])
    print("سُجّل في: %s" % record["record_path"])
    print(ab_lib.AB_NOTE)
    print("انشر كل نسخة بعنوانها (هوكها) ثم قارن بـ:")
    print("  python3 studio.py ab-results --ab-file %s"
          % record["record_path"])
    return 0


def cmd_ab(cfg, video, hook_a=None, hook_b=None, title=None,
           out_dir=None, cost_per_video=0, variants=3, engine="fast",
           balance_units=None, ledger_entries=None):
    """اختبار A/B: هوكان ومصغرتان لفيديو واحد + سجل الزوج.

    cost_per_video: تقدير وحدات Veo لإنتاج كل بديل من جديد
    (الافتراضي 0 — نفس الفيديو، هوك+مصغرة فقط؛ وتوليد جديد
    كامل = 120 وحدة).
    variants: عدد نسخ الهوك (افتراضي 3؛ 2 = السلوك السابق
    بهوكين فقط عبر create_ab).
    engine: محرك Veo للتقدير (fast ‏20 وحدة/مقطع أو lite ‏10؛
    بعد تقاعد Fast في 5 ديسمبر مرّر lite).
    """
    if isinstance(variants, bool) or not isinstance(variants, int) \
            or variants < 2:
        print("عدد النسخ يجب أن يكون عددًا صحيحًا ≥ 2")
        return 2
    if variants != 2:
        return _cmd_ab_variants(cfg, video, hook_a, hook_b, title,
                                out_dir, cost_per_video, variants,
                                engine=engine,
                                balance_units=balance_units,
                                ledger_entries=ledger_entries)
    runs_dir = expand(out_dir or cfg["paths"]["runs_dir"])
    _ab2_llm = {}
    if not hook_a or not hook_b:
        cfg_o = cfg["omniroute"]

        def chat_fn(prompt):
            text, _via, _model = _llm_chat(
                cfg, prompt, max_tokens=200, temperature=0.8)
            _ab2_llm["via"] = _via
            _ab2_llm["model"] = _model
            return text

        # توصيل فهرس الفيديوهات (جولة v0.1.48): يُمرَّر صراحةً؛
        # وبلا qdrant-client أو Ollama يُحذف «أقرب فيديو سابق»
        # بصمت (fail-open).
        from lib import story_index as story_index_lib
        _index = story_index_lib.get_default_index()
        try:
            _hooks = ab_lib.suggest_hooks(
                title or os.path.basename(video), chat_fn, index=_index)
        finally:
            if _index is not None:
                _index.close()
        sug_a, sug_b, src = _hooks
        hook_a = hook_a or sug_a
        hook_b = hook_b or sug_b
        print("الهوكان المقترحان (%s)" % src)
        _nv = getattr(_hooks, "nearest_video", None)
        if _nv:
            print("أقرب فيديو سابق: «%s» (%s — تشابه %.2f)"
                  % (_nv.get("hook") or _nv.get("title") or "؟",
                     _nv.get("title") or "بلا عنوان",
                     _nv.get("similarity") or 0.0))
    try:
        record = ab_lib.create_ab(expand(video), hook_a, hook_b,
                                  runs_dir, title=title,
                                  cost_per_video=cost_per_video,
                                  llm_model=_ab2_llm.get("model"),
                                  engine=engine,
                                  balance_units=balance_units,
                                  ledger_entries=ledger_entries)
    except (ValueError, thumbnail.ThumbnailError) as e:
        print("فشل اختبار A/B: %s" % e)
        return 1
    print("نسخة أ — الهوك: %s" % record["hook_a"])
    print("  المصغرة: %s" % record["thumb_a"])
    print("نسخة ب — الهوك: %s" % record["hook_b"])
    print("  المصغرة: %s" % record["thumb_b"])
    cost = record.get("cost_estimate_units") or {}
    if cost:
        print("تقدير التكلفة (وحدات Veo): أ %s — ب %s — المجموع %s"
              % (cost.get("variant_a"), cost.get("variant_b"),
                 cost.get("total")))
    _ests = record.get("cost_estimates") or {}
    for _label, _key in (("أ", "variant_a"), ("ب", "variant_b")):
        _est = _ests.get(_key)
        if _est:
            print("  تكلفة النسخة %s: %s"
                  % (_label, ab_lib.format_variant_cost(_est)))
    print("سُجّل الزوج في: %s" % record["record_path"])
    print(ab_lib.AB_NOTE)
    print("انشر كل نسخة بعنوانها (هوكها) ثم قارن بـ:")
    print("  python3 studio.py ab-results --ab-file %s"
          % record["record_path"])
    return 0


def cmd_ab_results(cfg, ab_file=None):
    """قارن مشاهدات نسختي اختبار A/B (فيسبوك + يوتيوب)."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    if ab_file:
        path = expand(ab_file)
    else:
        candidates = sorted(
            Path(runs_dir).glob("ab-*/ab-*.json"))
        path = str(candidates[-1]) if candidates else None
    if not path or not os.path.isfile(path):
        print("لا يوجد سجل اختبار A/B — أنشئ واحدًا أولًا "
              "بـ studio.py ab")
        return 1
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    record["record_path"] = path
    page_id = (cfg.get("publish") or {}).get("page_id")
    channel_id = (cfg.get("publish") or {}).get("youtube_channel_id")
    fb_bin = publish.find_facebook_bin()
    if not page_id:
        fb_entries, fb_note = [], "معرّف الصفحة غير مضبوط"
    elif not fb_bin:
        fb_entries, fb_note = [], "facebook-cli غير متاح"
    else:
        fb_entries, fb_note = ab_lib.fetch_fb_posts(fb_bin, page_id)
    yt_entries, yt_note = ab_lib.fetch_yt_uploads(channel_id)
    if fb_note:
        print("فيسبوك: %s" % fb_note)
    if yt_note:
        print("يوتيوب: %s" % yt_note)
    comparison = ab_lib.compare_ab(record, fb_entries, yt_entries)
    print(ab_lib.format_comparison(record, comparison))
    return 0


# ------------------------------------------------------- update + backup
def cmd_update(cfg, dry_run=False,
               repo="aalhdydy550-ui/qisas-studio", branch="main"):
    """جلب آخر إصدار من GitHub وتطبيق الملفات المتغيرة فقط،
    مع نسخة احتياطية أولًا؛ والملفات المحمية لا تُمسّ أبدًا."""
    try:
        tree = update_backup.fetch_tree(repo, branch)
    except update_backup.UpdateError as e:
        print("فشل جلب الشجرة البعيدة: %s" % e)
        return 1
    changes = update_backup.plan_update(STUDIO_DIR, tree)
    if not changes:
        print("المشروع محدَّث بالفعل — لا ملفات متغيرة")
        return 0
    print("ملفات ستتغير (%d):" % len(changes))
    for change in changes:
        print("  %s %s" % ("+" if change["action"] == "add" else "~",
                           change["path"]))
    if dry_run:
        print("وضع تجريبي — لم يُكتب شيء")
        return 0

    def fetch_fn(path):
        return update_backup.fetch_file_raw(repo, branch, path)

    def backup_fn(paths):
        zip_path, _inc, _miss = update_backup.make_backup(
            STUDIO_DIR, cfg)
        print("نسخة احتياطية قبل التحديث: %s" % zip_path)
        # إصلاح اختبار اختراق 2026-11-22 (M5): نسخة ثانية من
        # الملفات المتغيرة نفسها (ومنها الكود) للتراجع منها
        # بأمر `restore --file <zip>`.
        pre_path, pre_inc = update_backup.make_pre_update_backup(
            STUDIO_DIR, paths)
        if pre_path:
            print("نسخة الملفات المتغيرة قبل التحديث: %s (%d ملفًا)"
                  % (pre_path, len(pre_inc)))

    try:
        # إصلاح اختبار اختراق 2026-11-22 (H1): تُمرَّر بصمات
        # الشجرة فيُتحقق من كل محتوى منزَّل قبل أي كتابة.
        written = update_backup.apply_update(
            STUDIO_DIR, changes, fetch_fn, backup_fn, tree=tree)
    except update_backup.UpdateError as e:
        print("فشل التحديث: %s" % e)
        return 1
    print("طُبّق %d ملفًا" % len(written))
    print("أعد تشغيل الاختبارات: "
          "python3 -m unittest discover -s tests")
    return 0


def cmd_restore(cfg, backup_file):
    """استعد ملفات من نسخة «قبل التحديث» (zip).

    التراجع الصريح من تحديث فاسد (إصلاح اختبار اختراق
    2026-11-22، M5): `studio.py restore --file
    backups/pre-update-....zip`. ملف النسخة يجب أن يكون داخل
    مجلد المشروع، والملفات المحمية لا تُستعاد أبدًا.
    """
    try:
        from lib.paths import resolve_inside
        path = resolve_inside(STUDIO_DIR, expand(backup_file),
                              "ملف النسخة الاحتياطية")
    except ValueError as e:
        print("ملف نسخة غير صالح: %s" % e)
        return 1
    try:
        restored = update_backup.restore_backup(path, STUDIO_DIR)
    except update_backup.UpdateError as e:
        print("فشلت الاستعادة: %s" % e)
        return 1
    print("استُعيد %d ملفًا من %s" % (len(restored), path))
    for name in restored:
        print("  %s" % name)
    print("أعد تشغيل الاختبارات: "
          "python3 -m unittest discover -s tests")
    return 0


def cmd_restore_backup(cfg, backup_file, dry_run=False, yes=False):
    """استرجع الإعداد والطابور وطلبات العملاء من نسخة `backup` (zip).

    أمان إلزامي: (1) كل مدخل يُفحص قبل أي كتابة — لا أسرار أبدًا
    (توكن يوتيوب/client_secrets/.env/مفاتيح تُرفض وتُلغي العملية
    كلها)؛ (2) نسخة احتياطية من الحالة الحالية تُؤخذ أولًا
    تلقائيًا، وإن تعذّرت أُلغيت الاستعادة؛ (3) تأكيد صريح قبل
    الكتابة فوق الملفات ما لم يُمرَّر --yes. --dry-run يعرض
    الخطة فقط بلا كتابة وبلا نسخة أمان.
    """
    try:
        from lib.paths import resolve_inside
        path = resolve_inside(STUDIO_DIR, expand(backup_file),
                              "ملف النسخة الاحتياطية")
    except ValueError as e:
        print("ملف نسخة غير صالح: %s" % e)
        return 1
    try:
        plan = update_backup.plan_user_restore(path, STUDIO_DIR)
    except update_backup.UpdateError as e:
        print("فشلت الاستعادة: %s" % e)
        return 1
    print("ستُستعاد %d ملفًا من %s:" % (len(plan["restorable"]), path))
    for name in plan["restorable"]:
        print("  %s" % name)
    if plan["skipped"]:
        print("تُتخطى (%d): %s" % (len(plan["skipped"]),
                                    ", ".join(plan["skipped"])))
    if dry_run:
        print("وضع تجريبي — لم يُكتب شيء، ولم تُؤخذ نسخة احتياطية")
        return 0
    if not yes:
        answer = input("ستُكتب فوق الملفات الحالية. اكتب «نعم» "
                       "للتأكيد: ").strip().lower()
        if answer not in ("نعم", "yes", "y"):
            print("أُلغيت الاستعادة — لم يتغير شيء")
            return 1
    try:
        safety, _inc, _miss = update_backup.make_backup(STUDIO_DIR, cfg)
    except update_backup.UpdateError as e:
        print("تعذّرت نسخة الأمان من الحالة الحالية — أُلغيت "
              "الاستعادة: %s" % e)
        return 1
    print("نسخة أمان من الحالة الحالية: %s" % safety)
    try:
        restored = update_backup.apply_user_restore(
            path, STUDIO_DIR, plan)
    except (update_backup.UpdateError, OSError) as e:
        print("فشلت الاستعادة أثناء الكتابة: %s" % e)
        print("الحالة السابقة محفوظة في: %s" % safety)
        return 1
    print("استُعيد %d ملفًا:" % len(restored))
    for name in restored:
        print("  %s" % name)
    print("نسخة الأمان: %s" % safety)
    return 0


def cmd_backup(cfg, out_dir=None, keep=None):
    """نسخة احتياطية zip: الإعداد + الطابور + طلبات العملاء +
    سجلات التشغيل."""
    try:
        zip_path, included, missing = update_backup.make_backup(
            STUDIO_DIR, cfg,
            out_dir=expand(out_dir) if out_dir else None,
            keep=(keep if keep is not None
                  else update_backup.BACKUP_KEEP))
    except update_backup.UpdateError as e:
        print("فشل النسخ الاحتياطي: %s" % e)
        return 1
    print("نسخة احتياطية: %s (%d ملفًا)"
          % (zip_path, len(included)))
    for name in included:
        print("  %s" % name)
    if missing:
        print("مفقود (لم يُضمَّن): %s" % ", ".join(missing))
    return 0


# ----------------------------------------------------------------- balance
def _record_veo_spend(units):
    """سجّل إنفاق Veo فعليًا: اخصم من config.yaml واختم الوقت
    (الجولة 8). تحذير فقط عند التعذر — لا يُفشل التشغيل.
    يرجع الرصيد الجديد أو None."""
    config_path = os.path.join(STUDIO_DIR, "config.yaml")
    try:
        new_balance = balance_lib.record_veo_spend(config_path, units)
    except (ValueError, OSError) as e:
        print("تحذير: تعذر تسجيل إنفاق Veo (%d وحدة): %s"
              % (units, e))
        return None
    if new_balance is None:
        print("تحذير: لا رصيد مسجَّل في config.yaml — لم يُخصم "
              "إنفاق Veo (%d وحدة)؛ حدّث الرصيد بـ "
              "`balance --set N`." % units)
    else:
        print("سُجّل إنفاق Veo: %d وحدة — الرصيد المسجَّل الآن "
              "%d وحدة." % (units, new_balance))
    return new_balance


def _save_veo_balance(balance_units, stamp):
    """احفظ رصيد Veo + وقت تحديثه في config.yaml بتعديل نصي.

    تعديل نصي (لا إعادة كتابة YAML) حتى تبقى تعليقات الملف.
    يرجع True عند النجاح.
    """
    import re
    config_path = os.path.join(STUDIO_DIR, "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        text = f.read()
    bal_line = "  balance_units: %d" % balance_units
    stamp_line = "  updated_at: %s" % stamp
    m = re.search(r"(?m)^veo:\n((?:  .*\n)*)", text)
    if not m or not m.group(1):
        if m:
            text = text[:m.end()] + bal_line + "\n" + stamp_line + "\n" \
                + text[m.end():]
        else:
            text = text.rstrip("\n") + "\n\nveo:\n" + bal_line + \
                "\n" + stamp_line + "\n"
    else:
        section = m.group(1)
        section = re.sub(r"(?m)^  balance_units:.*$",
                         bal_line, section)
        if "balance_units:" not in section:
            section = bal_line + "\n" + section
        section = re.sub(r"(?m)^  updated_at:.*$",
                         stamp_line, section)
        if "updated_at:" not in section:
            section += stamp_line + "\n"
        text = text[:m.start(1)] + section + text[m.end(1):]
    tmp = config_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, config_path)
    return True


def cmd_balance(cfg, balance=None, renew=None, cost_min=None,
                cost_max=None, record=None, video=None, clips=None,
                history_flag=False, cap=None, config_path=None,
                set_balance=None):
    """توقع رصيد Veo بالأيام — من الرصيد المسجَّل في الإعداد
    (ليس حيًا من API).

    --record N --video NAME يسجّل إنفاقًا فعليًا بعد توليد في
    Flow في runs/cost-ledger.jsonl؛ و--history يعرض السجل.
    --cap N يضبط سقف الإنفاق لكل توليد Veo (فيديو واحد) في
    config.yaml؛ و--cap 0 يلغي السقف.
    --set N (الجولة 8) يضبط الرصيد المسجَّل مع ختم وقت التحديث
    بتوقيت القاهرة الآن.
    """
    if cap is not None:
        if isinstance(cap, bool) or not isinstance(cap, int) \
                or cap < 0:
            print("سقف غير صالح: %s (المسموح: عدد صحيح ≥ 0 — و0 "
                  "يلغي السقف)" % (cap,))
            return 2
        path = config_path or os.path.join(STUDIO_DIR, "config.yaml")
        try:
            if cap == 0:
                balance_lib.remove_veo_key("cap_units", path)
                print("أُلغي سقف الإنفاق (بلا سقف الآن).")
            else:
                balance_lib.save_veo_value("cap_units", cap, path)
                print("حُفظ سقف الإنفاق (%d وحدة لكل توليد Veo) في "
                      "config.yaml." % cap)
        except (ValueError, OSError) as e:
            print("فشل حفظ السقف: %s" % e)
            return 1
        veo = dict(cfg.get("veo") or {})
        if cap == 0:
            veo.pop("cap_units", None)
        else:
            veo["cap_units"] = cap
        cfg = dict(cfg)
        cfg["veo"] = veo
    if record is not None:
        from lib import cost_ledger
        try:
            entry = cost_ledger.record(STUDIO_DIR, record, video,
                                       clips=clips)
        except ValueError as e:
            print("سجل التكاليف: %s" % e)
            return 2
        print("سُجّل إنفاق %d وحدة — %s (%s)"
              % (entry["units"], entry["video"], entry["date"]))
        return 0
    if history_flag:
        from lib import cost_ledger
        print(cost_ledger.format_history(
            cost_ledger.history(STUDIO_DIR)))
        return 0
    veo = cfg.get("veo") or {}
    bal = (balance if balance is not None
           else veo.get("balance_units", balance_lib.DEFAULT_BALANCE))
    ren = renew or veo.get("renews", balance_lib.DEFAULT_RENEWS)
    cmin = (cost_min if cost_min is not None
            else veo.get("daily_cost_min", balance_lib.DEFAULT_COST_MIN))
    cmax = (cost_max if cost_max is not None
            else veo.get("daily_cost_max", balance_lib.DEFAULT_COST_MAX))
    if balance is not None:
        # الجولة 6: احفظ الرصيد الجديد + وقت تحديثه في config.yaml.
        stamp = balance_lib.now_iso()
        _save_veo_balance(balance, stamp)
        veo = dict(veo)
        veo["balance_units"] = balance
        veo["updated_at"] = stamp
        print("حُفظ الرصيد الجديد (%d وحدة) في config.yaml مع وقت "
              "التحديث." % balance)
    if set_balance is not None:
        # الجولة 8: ضبط الرصيد المسجَّل + ختم وقت القاهرة الآن.
        if isinstance(set_balance, bool) \
                or not isinstance(set_balance, int) or set_balance < 0:
            print("رصيد غير صالح: %s (المسموح: عدد صحيح ≥ 0)"
                  % (set_balance,))
            return 2
        path = config_path or os.path.join(STUDIO_DIR, "config.yaml")
        try:
            stamp = balance_lib.now_iso_cairo()
            balance_lib.save_veo_value("balance_units", set_balance,
                                       path)
            balance_lib.save_veo_value("updated_at", stamp, path)
        except (ValueError, OSError) as e:
            print("فشل حفظ الرصيد: %s" % e)
            return 1
        veo = dict(veo)
        veo["balance_units"] = set_balance
        veo["updated_at"] = stamp
        bal = set_balance
        print("حُفظ الرصيد الجديد (%d وحدة) في config.yaml مع وقت "
              "التحديث بتوقيت القاهرة (%s)."
              % (set_balance, stamp))
    try:
        result = balance_lib.forecast(bal, ren, cmin, cmax,
                                      updated_at=veo.get("updated_at"),
                                      cap_units=veo.get("cap_units"))
    except (ValueError, TypeError) as e:
        print("قيم غير صالحة: %s" % e)
        return 2
    print(balance_lib.format_forecast(result))
    return 0


def cmd_preview(cfg, video, caption=None, first_comment=None,
                out_dir=None, title=None):
    """صفحة معاينة HTML لفيديو قبل النشر (إطارات + صوت + فحص
    جودة + كابشن + أول تعليق). يرجع 0 عند النجاح."""
    from lib import preview as preview_lib
    try:
        out, result = preview_lib.build_preview(
            video, caption=caption, first_comment=first_comment,
            out_dir=expand(out_dir) if out_dir else None, title=title)
    except check_lib.CheckError as e:
        print("تعذرت المعاينة: %s" % e)
        return 1
    print("صفحة المعاينة: %s" % out)
    print(check_lib.format_report(result))
    return 0


# ---------------------------------------------------------------- jobs
def cmd_jobs_list(cfg, status=None, story=None, date=None, kind=None,
                  limit=20):
    """اعرض سجل المهام الدائم (runs/jobs.jsonl) — الأحدث أولًا."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    jobs = job_registry_lib.list_jobs(
        runs_dir, status=status, story=story, date=date, kind=kind,
        limit=limit)
    print(job_registry_lib.format_jobs(jobs))
    return 0


def cmd_jobs_show(cfg, job_id):
    """اعرض مهمة واحدة من سجل المهام بمعرّفها."""
    runs_dir = expand(cfg["paths"]["runs_dir"])
    job = job_registry_lib.get_job(runs_dir, job_id)
    if not job:
        print("لا توجد مهمة بهذا المعرف: %s" % job_id)
        return 1
    print(job_registry_lib.format_jobs([job]))
    return 0


# --------------------------------------------------------------- reframe
def cmd_reframe(cfg, video, out, focus_x=0.5, safety_margin=0):
    """أعد تأطير مقطع أفقي إلى عمودي 720×1280 (قصّ لا تمديد)."""
    try:
        result = avatar_aspect_lib.reframe_video(
            expand(video), expand(out), focus_x=focus_x,
            safety_margin=safety_margin)
    except avatar_aspect_lib.ReframeError as e:
        print("فشل إعادة التأطير: %s" % e)
        return 1
    print("أُعيد التأطير: %s" % result["output"])
    print("  المصدر: %sx%s → الخرج: %sx%s (قصّ x=%s w=%s)%s"
          % (result["source_width"], result["source_height"],
             result["out_width"], result["out_height"],
             result["crop"]["x"], result["crop"]["width"],
             " — بلا إعادة ترميز" if not result["reframed"] else ""))
    return 0


# ------------------------------------------------------------ shorts-cut
def cmd_shorts_cut(cfg, video, out_dir=None, count=3, phrases=None,
                   min_len=None, max_len=None):
    """قطّع فيديو طويل إلى شورتات عمودية 40–60 ثانية.

    --phrases ملف ASS اختياري (عبارات الفيديو الطويل) لتحسين
    اختيار النوافذ؛ والكابشنات المولّدة لكل شورت ملفات ASS
    منفصلة أسفل الشاشة فقط — حرقها داخل الفيديو خطوة لاحقة
    قبل النشر (فلتر subtitles).
    """
    video = expand(video)
    if not os.path.isfile(video):
        print("ملف الفيديو غير موجود: %s" % video)
        return 1
    if out_dir:
        out = expand(out_dir)
    else:
        out = os.path.join(
            expand(cfg["paths"]["videos_dir"]),
            "shorts-%s" % time.strftime("%Y%m%d-%H%M%S"))
    phrases_list = None
    if phrases:
        try:
            phrases_list = long_video.parse_ass(expand(phrases))
        except (OSError, long_video.LongVideoError) as e:
            print("تعذرت قراءة ملف العبارات: %s" % e)
            return 1
    kwargs = {}
    if min_len is not None:
        kwargs["min_len"] = min_len
    if max_len is not None:
        kwargs["max_len"] = max_len
    results = shorts_cut_lib.cut_shorts(
        video, out, count=count, phrases=phrases_list, **kwargs)
    print(shorts_cut_lib.format_report(results, video))
    return 0 if results else 1


# ------------------------------------------- queue publish (جولة v0.1.39)
def _queue_entries_with_publish(cfg, queue_file=None):
    """اقرأ عناصر الانتظار مع حالات نشرها (لأوامر queue)."""
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    with open(queue_path, encoding="utf-8") as f:
        text = f.read()
    return queue_lib.entries_with_publish(text, queue_path)


def cmd_queue_publish_status(cfg, number, platform, status,
                             queue_file=None):
    """حدّث حالة نشر قصة في الطابور لمنصة واحدة."""
    if platform not in queue_lib.PUBLISH_PLATFORMS:
        print("منصة غير معروفة: %s (المسموح: %s)"
              % (platform, ", ".join(queue_lib.PUBLISH_PLATFORMS)))
        return 2
    if status not in queue_lib.PUBLISH_STATUSES:
        print("حالة غير معروفة: %s (المسموح: %s)"
              % (status, ", ".join(queue_lib.PUBLISH_STATUSES)))
        return 2
    queue_path = expand(queue_file or cfg["paths"]["queue_file"])
    if not os.path.isfile(queue_path):
        print("ملف الطابور غير موجود: %s" % queue_path)
        return 1
    try:
        queue_lib.set_platform_status(queue_path, number, platform,
                                      status)
    except queue_lib.QueueError as e:
        print("تعذر تحديث حالة النشر: %s" % e)
        return 1
    print("حُدثت حالة النشر: القصة %d — %s: %s"
          % (number, platform, status))
    return 0


def cmd_queue_publish_summary(cfg, queue_file=None):
    """ملخص حالات النشر لكل منصة في الطابور."""
    try:
        entries = _queue_entries_with_publish(cfg, queue_file)
    except OSError as e:
        print("تعذر قراءة ملف الطابور: %s" % e)
        return 1
    summary = queue_lib.publish_summary(entries)
    print("حالات النشر (%d قصة في الانتظار):" % summary["entries"])
    for platform in queue_lib.PUBLISH_PLATFORMS:
        counts = summary[platform]
        print("  %s: معلق %d — منشور %d — فاشل %d — متخطى %d"
              % (platform, counts["pending"], counts["published"],
                 counts["failed"], counts["skipped"]))
    return 0


def cmd_queue_pending(cfg, platform, queue_file=None):
    """اعرض القصص المعلقة النشر على منصة واحدة."""
    if platform not in queue_lib.PUBLISH_PLATFORMS:
        print("منصة غير معروفة: %s (المسموح: %s)"
              % (platform, ", ".join(queue_lib.PUBLISH_PLATFORMS)))
        return 2
    try:
        entries = _queue_entries_with_publish(cfg, queue_file)
    except OSError as e:
        print("تعذر قراءة ملف الطابور: %s" % e)
        return 1
    pending = queue_lib.pending_for_platform(entries, platform)
    if not pending:
        print("لا قصص معلقة على %s" % platform)
        return 0
    print("قصص معلقة على %s (%d):" % (platform, len(pending)))
    for entry in pending:
        print("  %d. %s" % (entry["number"], entry["title"]))
    return 0


def cmd_logs(cfg, today=True, limit=20):
    """آخر التشغيلات من runs/ ونتائجها بالعربي (اليوم افتراضيًا)."""
    from lib import runlog as runlog_lib
    runs_dir = expand(cfg["paths"]["runs_dir"])
    entries = runlog_lib.collect_runs(runs_dir, today_only=today,
                                      limit=limit)
    print(runlog_lib.format_runs(entries))
    return 0


def cmd_expand_motion_prompts(cfg, prompts_path, out_path,
                              expand_fn=None):
    """وسّع موجّهات حركة قصيرة من ملف JSON إلى موجّهات مفصلة.

    المدخلات: قائمة [{"id"?, "prompt"}]؛ والناتج قائمة
    [{"id", "prompt", "expanded_prompt", "expanded", "reason"}]
    تُكتب JSON في out_path مع ملخص عربي (كم وُسّع/كم رُجع
    للأصل + الأسباب). fail-open على مستوى العنصر: أي موجّه
    فشل توسيعه يُحفظ بأصله في الناتج ولا يُحذف أبدًا.
    expand_fn حقن اختباري؛ وبلاه تُستورد
    lib.prompt_expand.expand_motion_prompts (عقد جولة
    v0.1.54 — W1). خروج 2 على مدخلات فاسدة (ملف مفقود /
    JSON فاسد / عنصر بلا prompt)؛ و1 على فشل كتابة الناتج.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تحويل نصي صريح بلا إنتاج.
    in_path = expand(prompts_path)
    try:
        with open(in_path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print("ملف الموجّهات غير موجود: %s" % in_path)
        return 2
    except (ValueError, OSError) as e:
        print("تعذّرت قراءة ملف الموجّهات %s: %s" % (in_path, e))
        return 2
    if not isinstance(raw, list):
        print("ملف الموجّهات يجب أن يكون قائمة JSON من العناصر "
              "(وصل نوع غير قائمة): %s" % in_path)
        return 2
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            print("عنصر الموجّه رقم %d ليس كائن JSON — كل عنصر "
                  "يجب أن يكون {\"id\"?, \"prompt\"}" % (index + 1))
            return 2
        prompt = item.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            print("عنصر الموجّه رقم %d بلا prompt صالح "
                  "(id=%s) — كل عنصر يحتاج prompt نصًا غير فارغ"
                  % (index + 1, item.get("id")))
            return 2
    if expand_fn is None:
        try:
            from lib import prompt_expand
            expand_fn = prompt_expand.expand_motion_prompts
        except ImportError:
            print("تحذير: وحدة التوسيع lib.prompt_expand غير متاحة — "
                  "رُجعت كل الموجّهات لأصلها")
            expand_fn = None
    results = None
    if expand_fn is not None:
        try:
            results = expand_fn(raw)
        except Exception:
            print("تحذير: فشل التوسيع كاملًا — رُجعت كل الموجّهات "
                  "لأصلها")
            results = None
    if not isinstance(results, list):
        results = []
    out_items = []
    for index, item in enumerate(raw):
        prompt = item["prompt"]
        result = results[index] if index < len(results) else None
        expanded_prompt = None
        expanded = False
        reason = None
        if isinstance(result, dict):
            reason = result.get("reason")
            if result.get("expanded") is True:
                candidate = result.get("expanded_prompt")
                if isinstance(candidate, str) and candidate.strip():
                    expanded_prompt = candidate
                    expanded = True
                else:
                    reason = reason or "expanded-prompt-missing"
            elif result.get("expanded") is False:
                reason = reason or "not-expanded"
        if not expanded:
            expanded_prompt = prompt
            reason = reason or "expansion-failed"
        out_items.append({
            "id": item.get("id"),
            "prompt": prompt,
            "expanded_prompt": expanded_prompt,
            "expanded": expanded,
            "reason": reason,
        })
    out_file = expand(out_path)
    parent = os.path.dirname(os.path.abspath(out_file))
    try:
        os.makedirs(parent, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(out_items, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print("تعذّرت كتابة الناتج في %s: %s" % (out_file, e))
        return 1
    total = len(out_items)
    done = sum(1 for row in out_items if row["expanded"])
    fell = total - done
    print("وُسّع %d من %d موجّهات؛ ورُجع %d للأصل."
          % (done, total, fell))
    if fell:
        reasons = {}
        for row in out_items:
            if not row["expanded"]:
                reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
        for reason, count in sorted(reasons.items()):
            print("الأسباب: %s (%d)" % (reason, count))
        for row in out_items:
            if not row["expanded"]:
                print("رُجع للأصل: %s — %s"
                      % (row["id"] if row["id"] is not None else "?",
                         row["reason"]))
    print("كُتب الناتج في: %s" % out_file)
    return 0


def _read_growth_text_file(path, what):
    """اقرأ ملفًا نصيًا لأوامر النمو؛ None مع رسالة عربية عند الفشل."""
    try:
        with open(expand(path), encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        print("تعذّرت قراءة %s %s: %s" % (what, expand(path), e))
        return None


def _print_json(payload):
    """اطبع حمولة JSON خالصة (سطر واحد) — بلا أي نص قبلها."""
    print(json.dumps(payload, ensure_ascii=False))


def cmd_seo_check(cfg, title, description, tags, story_file=None,
                  as_json=False):
    """افحص عنوانًا ووصفًا ووسومًا قبل النشر (فحص SEO فقط).

    خروج 1 إن كان التقرير ok=False (فحص قبل النشر)، و0 إن
    كان ok=True، و2 على مدخل فاسد (ملف قصة مفقود/عنوان
    فارغ/وسوم غير صالحة). --json يطبع JSON خالصًا بلا أي
    سطر نصي قبله (درس v0.1.56).
    """
    del cfg  # الإعداد غير مستخدم: الأمر فحص نصي صريح بلا إنتاج.
    story_text = None
    if story_file:
        story_text = _read_growth_text_file(story_file, "ملف القصة")
        if story_text is None:
            return 2
    try:
        report = seo_check_lib.check_seo(title, description, tags,
                                         story_text=story_text)
    except (ValueError, TypeError) as e:
        print("مدخل فحص SEO غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(seo_check_lib.to_json_dict(report))
    else:
        print(seo_check_lib.format_report(report))
    return 0 if report["ok"] else 1


def cmd_title_lint(cfg, title=None, thumb=None, titles_file=None,
                   as_json=False):
    """دقّق عنوانًا ومصغرة كوحدة واحدة (أو رتّب عناوين من ملف).

    استشاري (تقرير/ترتيب): خروج 0 عند النجاح مهما كانت
    المشكلات، و2 على مدخل فاسد فقط (لا عنوان ولا ملف، أو
    ملف مفقود/فارغ، أو عنوان فارغ).
    """
    del cfg  # الإعداد غير مستخدم: الأمر فحص نصي صريح بلا إنتاج.
    if titles_file is not None and title is not None:
        print("مرّر --title أو --titles-file (أحدهما فقط)")
        return 2
    if titles_file is not None:
        text = _read_growth_text_file(titles_file, "ملف العناوين")
        if text is None:
            return 2
        titles = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not titles:
            print("ملف العناوين فارغ — اكتب عنوانًا في كل سطر")
            return 2
        try:
            reports = title_lint_lib.rank_titles(titles, thumb)
        except (ValueError, TypeError) as e:
            print("مدخل تدقيق العناوين غير صالح: %s" % e)
            return 2
        if as_json:
            _print_json(reports)
        else:
            for i, report in enumerate(reports):
                if i:
                    print()
                print("العنوان %d (الأفضل أولًا):" % (i + 1))
                print(title_lint_lib.format_report(report))
        return 0
    if title is None:
        print("مرّر --title أو --titles-file")
        return 2
    try:
        report = title_lint_lib.lint_title(title, thumb)
    except (ValueError, TypeError) as e:
        print("مدخل تدقيق العنوان غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(report)
    else:
        print(title_lint_lib.format_report(report))
    return 0


def cmd_hook_score(cfg, hook=None, hook_file=None, story_file=None,
                   as_json=False):
    """قيّم هوكًا (أو هوكات من ملف) ورتّبها — أفضل اثنين مميزان.

    استشاري: خروج 0 عند النجاح مهما كانت الدرجات، و2 على
    مدخل فاسد فقط (لا هوك ولا ملف، أو ملف مفقود/فارغ، أو
    هوك فارغ).
    """
    del cfg  # الإعداد غير مستخدم: الأمر تقييم نصي صريح بلا إنتاج.
    if hook is not None and hook_file is not None:
        print("مرّر --hook أو --hook-file (أحدهما فقط)")
        return 2
    if hook_file is not None:
        text = _read_growth_text_file(hook_file, "ملف الهوكات")
        if text is None:
            return 2
        hooks = [ln.strip() for ln in text.splitlines() if ln.strip()]
    elif hook is not None:
        hooks = [hook]
    else:
        print("مرّر --hook أو --hook-file — لا هوك ولا ملف")
        return 2
    if not hooks:
        print("لا هوكات — ملف الهوكات فارغ أو الهوك فارغ")
        return 2
    story_text = None
    if story_file:
        story_text = _read_growth_text_file(story_file, "ملف القصة")
        if story_text is None:
            return 2
    try:
        panels = hook_panel_lib.score_hooks(hooks,
                                            story_text=story_text)
    except Exception as e:
        print("مدخل تقييم الهوك غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(panels)
    else:
        print(hook_panel_lib.format_panel(panels))
    return 0


def cmd_viral_rank(cfg, videos_file, top=5, as_json=False):
    """رتّب فيديوهات بمضاعف كل قناة على وسيطها الخاص.

    استشاري: خروج 0 عند النجاح، و2 على ملف مفقود/JSON
    فاسد/قائمة غير صالحة.
    """
    del cfg  # الإعداد غير مستخدم: الأمر ترتيب نصي صريح بلا إنتاج.
    path = expand(videos_file)
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        print("ملف الفيديوهات غير موجود: %s" % path)
        return 2
    except (ValueError, OSError) as e:
        print("تعذّرت قراءة ملف الفيديوهات %s: %s" % (path, e))
        return 2
    try:
        result = viral_rank_lib.rank_outliers(raw, top_n=top)
    except (ValueError, TypeError) as e:
        print("مدخل ترتيب الشواذ غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(result)
    else:
        print(viral_rank_lib.format_report(result))
    return 0


def cmd_retention_read(cfg, csv_file, duration=None, transcript_file=None,
                       as_json=False):
    """اقرأ تصدير احتفاظ Studio (CSV) وشخّص أكبر تسرب.

    استشاري: خروج 0 عند النجاح، و2 على ملف مفقود/CSV فاسد/
    مدة غير صالحة.
    """
    del cfg  # الإعداد غير مستخدم: الأمر قراءة نصية صريحة بلا إنتاج.
    transcript_text = None
    if transcript_file:
        transcript_text = _read_growth_text_file(
            transcript_file, "ملف النص المكتوب")
        if transcript_text is None:
            return 2
    try:
        result = retention_read_lib.read_retention(
            expand(csv_file), duration=duration,
            transcript_text=transcript_text)
    except (ValueError, TypeError) as e:
        print("مدخل قراءة الاحتفاظ غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(result)
    else:
        print(retention_read_lib.format_report(result))
    return 0


def cmd_channel_audit(cfg, titles_file, hooks_file=None,
                      thumb_texts_file=None, dates_file=None,
                      retention_csv=None, duration=None, title=None,
                      description=None, tags=None, as_json=False):
    """دقّق القناة وينتهِ في إصلاح واحد (قائمة yt-audit).

    استشاري: خروج 0 عند النجاح مهما كان الإصلاح، و2 على مدخل
    فاسد فقط (ملف عناوين مفقود/فارغ، تواريخ غير صالحة، CSV
    فاسد، بيانات نشر ناقصة).
    """
    del cfg  # الإعداد غير مستخدم: الأمر تقرير صريح بلا إنتاج.
    text = _read_growth_text_file(titles_file, "ملف العناوين")
    if text is None:
        return 2
    titles = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not titles:
        print("ملف العناوين فارغ — اكتب عنوانًا في كل سطر")
        return 2
    hooks = None
    if hooks_file:
        htext = _read_growth_text_file(hooks_file, "ملف الهوكات")
        if htext is None:
            return 2
        hooks = [ln.strip() for ln in htext.splitlines() if ln.strip()]
    thumb_texts = None
    if thumb_texts_file:
        ttext = _read_growth_text_file(thumb_texts_file,
                                       "ملف نصوص المصغرات")
        if ttext is None:
            return 2
        # سطر لكل عنوان؛ سطر فارغ يعني بلا نص مصغرة لذلك العنوان.
        thumb_texts = [ln.strip() or None for ln in ttext.splitlines()]
    dates = None
    if dates_file:
        dtext = _read_growth_text_file(dates_file, "ملف تواريخ الرفع")
        if dtext is None:
            return 2
        dates = [ln.strip() for ln in dtext.splitlines() if ln.strip()]
    latest_meta = None
    if title is not None or description is not None or tags is not None:
        if title is None or description is None or tags is None:
            print("بيانات النشر الأخيرة تحتاج --title و--description "
                  "و--tags معًا")
            return 2
        latest_meta = {"title": title, "description": description,
                       "tags": tags}
    try:
        result = channel_audit_lib.audit_channel(
            titles, hooks=hooks, thumb_texts=thumb_texts,
            upload_dates=dates,
            retention_csv=expand(retention_csv) if retention_csv else None,
            retention_duration=duration, latest_meta=latest_meta)
    except (ValueError, TypeError) as e:
        print("مدخل تدقيق القناة غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(channel_audit_lib.to_json_dict(result))
    else:
        print(channel_audit_lib.format_report(result))
    return 0


# ------------------------------------------- trend-scout (جولة v0.1.58)
def cmd_trend_scout(cfg, videos_file, top_n=5, as_json=False):
    """كشّاف ترندات أسبوعي: رتّب فيديوهات عامة واقترح إدخالات طابور.

    استشاري: خروج 0 عند النجاح، و2 على مدخل فاسد (ملف مفقود
    أو JSON فاسد أو فيديو بلا قناة/عنوان). --json يطبع JSON
    خالصًا بلا أي سطر نصي قبله (درس v0.1.56 — و`to_json`
    هنا يرجع سلسلة جاهزة فتُطبع كما هي بلا ترميز مزدوج).
    الاقتراحات لا تكتب في الطابور أبدًا — المشغّل ينسخها
    بنفسه.
    """
    del cfg  # الإعداد غير مستخدم: الأمر بحث نصي صريح بلا إنتاج.
    text = _read_growth_text_file(videos_file, "ملف الفيديوهات")
    if text is None:
        return 2
    try:
        result = trend_scout_lib.scout_trends(text, top_n=top_n)
    except (ValueError, TypeError) as e:
        print("مدخل كشّاف الترند غير صالح: %s" % e)
        return 2
    if as_json:
        print(trend_scout_lib.to_json(result), end="")
    else:
        print(trend_scout_lib.format_report(result))
    return 0


# ------------------------------------------- scene-shorts (جولة v0.1.58)
def cmd_scene_shorts(cfg, video, scenes_file, out_dir=None, phrases=None,
                     full_hook="", as_json=False):
    """قصّ فيديو طويل إلى أجزاء مشهدية عمودية 40–60 ثانية.

    مشاهد كاملة فقط؛ والجزء غير المكتمل يُسجَّل في التقرير
    ولا يُحذف بصمت. خروج 0 إن قُصّ جزء مكتمل واحد على الأقل،
    و1 إن لم يُقصّ أي جزء مكتمل، و2 على مدخل فاسد (فيديو
    مفقود أو ملف مشاهد/عبارات فاسد). --json يطبع JSON خالصًا.
    """
    video = expand(video)
    scenes_text = _read_growth_text_file(scenes_file, "ملف المشاهد")
    if scenes_text is None:
        return 2
    try:
        scenes = json.loads(scenes_text)
    except ValueError as e:
        print("ملف المشاهد JSON فاسد: %s" % e)
        return 2
    phrases_list = None
    if phrases:
        try:
            phrases_list = long_video.parse_ass(expand(phrases))
        except (OSError, long_video.LongVideoError) as e:
            print("تعذّرت قراءة ملف العبارات: %s" % e)
            return 2
    if out_dir:
        out = expand(out_dir)
    else:
        out = os.path.join(
            expand(cfg["paths"]["videos_dir"]),
            "scene-shorts-%s" % time.strftime("%Y%m%d-%H%M%S"))
    try:
        info = check_lib.probe(video)
        results = scene_shorts_lib.cut_scene_shorts(
            video, scenes, out, phrases=phrases_list)
    except scene_shorts_lib.SceneShortsError as e:
        print("تعذّر تقطيع المشاهد: %s" % e)
        return 2
    except (check_lib.CheckError, OSError, ValueError, KeyError,
            TypeError) as e:
        print("مدخل تقطيع المشاهد غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json({"source": video, "duration": info["duration"],
                     "parts": results})
    else:
        print(scene_shorts_lib.format_comparison_report(
            results, video, info["duration"], full_hook=full_hook))
    return 0 if any(r.get("output") for r in results) else 1


# ------------------------------------------- tiktok-check (جولة v0.1.58)
def cmd_tiktok_check(cfg, title, caption, hook=None, moral="",
                     story_file=None, queue_file=None, needed=7,
                     trend_keywords=None, as_json=False):
    """افحص شورتًا قبل نشره على TikTok (فحص فقط).

    تغليف رقيق فوق `lib.tiktok_check.cmd_tiktok_check` بنفس
    رموز الخروج: 1 إن كان التقرير غير سليم (فحص قبل النشر)،
    و0 إن كان سليمًا، و2 على مدخل فاسد. --json خالص.
    """
    keywords = None
    if trend_keywords:
        if isinstance(trend_keywords, str):
            keywords = [k.strip() for k in trend_keywords.split(",")
                        if k.strip()]
        else:
            keywords = list(trend_keywords)
    return tiktok_check_lib.cmd_tiktok_check(
        cfg, title, caption, hook=hook, moral=moral,
        story_file=story_file, queue_file=queue_file, needed=needed,
        trend_keywords=keywords, as_json=as_json)


# ------------------------------------------- script-check (جولة v0.1.58)
def cmd_script_check(cfg, script_file, as_json=False, timed_phrases=None,
                     narration_audio=None, narration_wpm=None,
                     narration_duration=None):
    """بوابة سكريبت نصية قبل الإنتاج (مرحلة السكريبت).

    تغليف فوق `lib.script_check.cmd_script_check`: خروج 0
    سليم، و1 تقرير غير سليم، و2 مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر فحص نصي صريح بلا إنتاج.
    args = argparse.Namespace(
        script=script_file, json=as_json, timed_phrases=timed_phrases,
        narration_audio=narration_audio, narration_wpm=narration_wpm,
        narration_duration=narration_duration)
    return script_check_lib.cmd_script_check(args)


# ------------------------------------------- topic-brief (جولة v0.1.58)
def cmd_topic_brief(cfg, theme=None, input_file=None, candidates_file=None,
                    queue_file=None, as_json=False):
    """موجز بحث لموضوع قبل الكتابة (مرحلة البحث).

    إما ملف JSON واحد (--input) بصيغة {theme, candidates,
    existing_titles}، أو --theme مع --candidates-file (قائمة
    JSON بصيغة مرشحي trend-scout) و--queue-file (نص الطابور —
    قراءة فقط لعناوينه الحالية). خروج 0 عند النجاح، و2 على
    مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر بحث نصي صريح بلا إنتاج.
    candidates = []
    existing = []
    if input_file is not None:
        text = _read_growth_text_file(input_file, "ملف مدخل الموجز")
        if text is None:
            return 2
        try:
            payload = json.loads(text)
        except ValueError as e:
            print("ملف مدخل الموجز JSON فاسد: %s" % e)
            return 2
        if not isinstance(payload, dict):
            print("ملف مدخل الموجز يجب أن يحوي قاموسًا واحدًا")
            return 2
        theme = payload.get("theme")
        candidates = payload.get("candidates", [])
        existing = payload.get("existing_titles", [])
    else:
        if candidates_file:
            ctext = _read_growth_text_file(candidates_file,
                                           "ملف المرشحين")
            if ctext is None:
                return 2
            try:
                candidates = json.loads(ctext)
            except ValueError as e:
                print("ملف المرشحين JSON فاسد: %s" % e)
                return 2
        if queue_file:
            qtext = _read_growth_text_file(queue_file, "ملف الطابور")
            if qtext is None:
                return 2
            try:
                existing = topic_brief_lib.titles_from_queue_text(qtext)
            except topic_brief_lib.BriefError as e:
                print("تعذّرت قراءة عناوين الطابور: %s" % e)
                return 2
    try:
        brief = topic_brief_lib.build_brief(theme, candidates, existing)
    except (topic_brief_lib.BriefError, ValueError, TypeError) as e:
        print("مدخل موجز البحث غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(brief)
    else:
        print(brief["brief_text"])
    return 0


# ------------------------------------------- hook-title (جولة v0.1.58)
def cmd_hook_title(cfg, video, title, out=None, as_json=False, force=False):
    """عنوان هوك كبير مكتوب أول 3 ثوانٍ — على شورت جاهز.

    --json يعرض مواصفة العنوان فقط (بلا حرق) بأبعاد الفيديو
    إن زُوّد، وإلا 720×1280. بلا --json يحرق العنوان في
    الفيديو (إعادة ترميز على نمط shorts_cut). خروج 0 عند
    النجاح، و1 عند فشل الحرق، و2 على مدخل فاسد (فيديو مفقود
    أو عنوان فارغ). العنوان في النطاق الأوسط فقط — أبدًا في
    الثلث العلوي أو منطقة الكابشنات (قرار 10:09 — التغيير
    الوحيد في ثوابت الصيغة بهذه الجولة).
    """
    del cfg  # الإعداد غير مستخدم: الأمر خطوة مستقلة على فيديو جاهز.
    if not title or not title.strip():
        print("نص الهوك فارغ — عنوان الهوك من نص السكريبت نفسه، "
              "بلا اختراع نص")
        return 2
    if as_json:
        width, height = 720, 1280
        if video:
            video = expand(video)
            if not os.path.isfile(video):
                print("ملف الفيديو غير موجود: %s" % video)
                return 2
            try:
                info = check_lib.probe(video)
                width, height = info["width"], info["height"]
            except check_lib.CheckError as e:
                print("تعذّر فحص الفيديو: %s" % e)
                return 2
        try:
            spec = hook_title_lib.hook_title_spec(title, width, height)
        except hook_title_lib.HookTitleError as e:
            print("مواصفة عنوان الهوك غير صالحة: %s" % e)
            return 2
        _print_json(spec)
        return 0
    if not video:
        print("مرّر --video (فيديو الشورت الجاهز)")
        return 2
    video = expand(video)
    if not os.path.isfile(video):
        print("ملف الفيديو غير موجود: %s" % video)
        return 2
    if out:
        out_path = expand(out)
    else:
        base, ext = os.path.splitext(os.path.abspath(video))
        out_path = base + "-hook-title" + (ext or ".mp4")
    try:
        hook_title_lib.apply_hook_title(video, title, out_path,
                                        force=force)
    except hook_title_lib.HookTitleError as e:
        print("تعذّر حرق عنوان الهوك: %s" % e)
        return 1
    print("حُرق عنوان الهوك «%s» في أول 3 ثوانٍ: %s"
          % (title.strip(), out_path))
    return 0


# ------------------------------------------- SRE (جولة v0.1.60)
def _load_json_file(path, what):
    """اقرأ ملف JSON وأعد محتواه؛ None مع رسالة عربية عند الفشل."""
    text = _read_growth_text_file(path, what)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError as e:
        print("%s JSON فاسد: %s" % (what, e))
        return None


def _write_mapping_json(mapping, path, what):
    """اكتب mapping في ملف JSON؛ True عند النجاح."""
    try:
        with open(expand(path), "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as e:
        print("تعذّرت كتابة %s %s: %s" % (what, expand(path), e))
        return False
    return True


def cmd_reliability_report(cfg, runs_file, window_days=30, as_json=False):
    """تقرير موثوقية من سجلات تشغيل (قراءة/تشخيص فقط).

    تغليف رقيق فوق `lib.reliability_report.build_reliability_report`:
    خروج 0 عند النجاح، و2 على مدخل فاسد (ملف غائب أو JSON تالف
    أو ليس قائمة أو نافذة غير صالحة). --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تقرير من ملف صريح.
    if not isinstance(window_days, int) or isinstance(window_days, bool) \
            or window_days <= 0:
        print("نافذة التقرير --window-days يجب أن تكون عددًا صحيحًا موجبًا")
        return 2
    runs = _load_json_file(runs_file, "ملف سجلات التشغيل")
    if runs is None:
        return 2
    if not isinstance(runs, list):
        print("ملف سجلات التشغيل يجب أن يحوي قائمة سجلات")
        return 2
    try:
        report = reliability_report_lib.build_reliability_report(
            runs, window_days=window_days)
    except (ValueError, TypeError) as e:
        print("مدخل تقرير الموثوقية غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(report)
        return 0
    print("تقرير الموثوقية (%s يومًا): %d تشغيلًا، %d فاشلًا "
          "(معدل فشل %.1f%%)"
          % (window_days, report["total_runs"], report["failed"],
             report["failure_rate"] * 100))
    for kind, stats in sorted(report["by_kind"].items()):
        if stats["total"]:
            print("  %s: %d تشغيلًا، معدل فشل %.1f%%"
                  % (kind, stats["total"],
                     stats["failure_rate"] * 100))
    return 0


def cmd_failure_classify(cfg, text=None, file=None, as_json=False):
    """صنّف نص فشل إلى بيئة/كود/خارجي/غير معروف (قراءة فقط).

    تغليف رقيق فوق `lib.failure_classify.classify_failure`:
    واحد من --text أو --file إلزامي (وإلا خروج 2)، وخروج 0
    عند النجاح، و2 على مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تصنيف نص صريح.
    if bool(text) == bool(file):
        print("مرّر --text أو --file (أحدهما فقط)")
        return 2
    if file is not None:
        text = _read_growth_text_file(file, "ملف نص الفشل")
        if text is None:
            return 2
    result = failure_classify_lib.classify_failure(text)
    if as_json:
        _print_json(result)
        return 0
    print("تصنيف الفشل: %s (ثقة %s)"
          % (result["class"], result["confidence"]))
    if result["signals"]:
        print("  الإشارات: %s" % ", ".join(result["signals"]))
    print("  الخطوة التالية: %s" % result["suggestion"])
    return 0


def cmd_incident_probe(cfg, context_file, mask=False, mapping_out=None,
                       as_json=False):
    """حقّق في حادثة من سياق JSON جاهز (قراءة فقط).

    تغليف رقيق فوق `lib.incident_probe.probe_incident`: خروج 0
    عند النجاح، و2 على مدخل فاسد (ملف غائب أو JSON تالف أو ليس
    قاموسًا). مع --mask تُخفى الاقتباسات ونص الفشل في المخرجات
    عبر `lib.id_mask`، والـmapping يُكتب في --mapping-out فقط
    إن طُلب — ولا يُطبع أبدًا في stdout. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تحقيق من ملف صريح.
    context = _load_json_file(context_file, "ملف سياق الحادثة")
    if context is None:
        return 2
    if not isinstance(context, dict):
        print("ملف سياق الحادثة يجب أن يحوي قاموسًا واحدًا")
        return 2
    try:
        report = incident_probe_lib.probe_incident(context)
    except (ValueError, TypeError) as e:
        print("مدخل تحقيق الحادثة غير صالح: %s" % e)
        return 2
    if mask:
        report, mapping = id_mask_lib.mask_record(report)
        if mapping_out is not None:
            if not _write_mapping_json(mapping, mapping_out,
                                       "ملف الـmapping"):
                return 2
    if as_json:
        _print_json(report)
        return 0
    cause = report["likely_root_cause"]
    print("تحقيق الحادثة: %s" % report["title"])
    print("  السبب الجذري المحتمل: %s — %s (ثقة %s)"
          % (cause["class"], cause["summary"], cause["confidence"]))
    for hyp in report["hypotheses"]:
        print("  فرضية %s: %s"
              % (hyp["hypothesis"], hyp["status"]))
    for step in report["next_steps"]:
        print("  - %s" % step)
    return 0


def cmd_id_mask(cfg, text=None, file=None, mapping_out=None,
                redact=False, unmask=False, mapping_file=None,
                as_json=False):
    """أخفِ معرّفات في نص أو أعد إظهارها (قراءة فقط على المدخل).

    افتراضيًا يطبع {"masked": ...}؛ ومع --redact يطبع
    {"redacted": ...} بلا mapping (حجب نهائي للأسرار)؛ ومع
    --unmask --mapping P يطبع {"unmasked": ...}. الـmapping
    يُكتب في --mapping-out فقط إن طُلب — ولا يُطبع أبدًا في
    stdout. خروج 0 عند النجاح، و2 على مدخل فاسد (لا نص ولا
    ملف، أو كلاهما، أو mapping غائب/فاسد، أو --unmask بلا
    --mapping). --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تحويل نص صريح.
    if unmask:
        if mapping_file is None:
            print("--unmask يحتاج --mapping (ملف الـmapping)")
            return 2
        mapping = _load_json_file(mapping_file, "ملف الـmapping")
        if mapping is None:
            return 2
        if not isinstance(mapping, dict):
            print("ملف الـmapping يجب أن يحوي قاموسًا واحدًا")
            return 2
    if bool(text) == bool(file):
        print("مرّر --text أو --file (أحدهما فقط)")
        return 2
    if file is not None:
        text = _read_growth_text_file(file, "ملف النص")
        if text is None:
            return 2
    if unmask:
        result = id_mask_lib.unmask_text(text, mapping)
        if as_json:
            _print_json({"unmasked": result})
        else:
            print(result)
        return 0
    if redact:
        result = id_mask_lib.redact_secrets(text)
        if as_json:
            _print_json({"redacted": result})
        else:
            print(result)
        return 0
    masked, mapping = id_mask_lib.mask_text(text)
    if mapping_out is not None:
        if not _write_mapping_json(mapping, mapping_out, "ملف الـmapping"):
            return 2
    if as_json:
        _print_json({"masked": masked})
    else:
        print(masked)
    return 0


def cmd_runbook_check(cfg, runbook=None, runbook_file=None, root=".",
                      as_json=False):
    """افحص دفتر تشغيل (قراءة فقط — بلا أي إصلاح).

    تغليف رقيق فوق `lib.runbook_check`: --runbook اسم دفتر
    مدمج (env-restore أو publish-failure) أو --runbook-file
    مسار ملف (أحدهما فقط). خروج 0 إن نجح الكل أو تُخطي فقط،
    و1 إن فشلت أي خطوة، و2 على مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر فحص دفتر صريح.
    if bool(runbook) == bool(runbook_file):
        print("مرّر --runbook أو --runbook-file (أحدهما فقط)")
        return 2
    if runbook is not None:
        if not runbook.replace("-", "").replace("_", "").isalnum():
            print("اسم الدفتر غير صالح: %s" % runbook)
            return 2
        studio_dir = os.path.dirname(os.path.abspath(__file__))
        runbooks_dir = os.path.join(studio_dir, "lib", "runbooks")
        # ملفات الدفاتر المدمجة بشرطة سفلية (env_restore.json)
        # بينما معرّفاتها بشرطة عادية (env-restore) — جرّب الاسمين.
        runbook_file = None
        for candidate in (runbook + ".json",
                          runbook.replace("-", "_") + ".json"):
            path = os.path.join(runbooks_dir, candidate)
            if os.path.isfile(path):
                runbook_file = path
                break
        if runbook_file is None:
            print("الدفتر المدمج غير موجود: %s" % runbook)
            return 2
    try:
        data = runbook_check_lib.load_runbook(expand(runbook_file))
    except runbook_check_lib.RunbookError as e:
        print("تعذّر تحميل الدفتر: %s" % e)
        return 2
    try:
        result = runbook_check_lib.check_runbook(data, root=root or ".")
    except runbook_check_lib.RunbookError as e:
        print("الدفتر غير صالح: %s" % e)
        return 2
    if as_json:
        _print_json(result)
    else:
        summary = result["summary"]
        print("فحص الدفتر «%s»: %d ناجحة، %d فاشلة، %d متخطاة"
              % (result["title"], summary["passed"], summary["failed"],
                 summary["skipped"]))
        for step in result["steps"]:
            print("  [%s] %s — %s"
                  % (step["status"], step["title"], step["detail"]))
    return 0 if result["summary"]["ok"] else 1


def cmd_failure_drill(cfg, drill=None, all_drills=False, workdir=None,
                      keep=False, as_json=False):
    """درّب على عطل اصطناعي وتحقّق من أن الكشف يعمل (قراءة فقط
    خارج مجلد عمل مؤقت — لا يمسّ أي ملف حقيقي).

    تغليف رقيق فوق `lib.failure_drill`: افتراضيًا --all، أو
    --drill ID لعطل واحد. خروج 0 إن نجح الكل في الكشف، و1 إن
    فشل أي drill في الكشف، و2 على drill مجهول أو مدخل فاسد.
    --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تدريب اصطناعي صريح.
    if drill is not None and all_drills:
        print("مرّر --drill أو --all (أحدهما فقط)")
        return 2
    if workdir is not None:
        workdir = expand(workdir)
        try:
            os.makedirs(workdir, exist_ok=True)
        except OSError as e:
            print("تعذّر إنشاء مجلد العمل: %s" % e)
            return 2
    try:
        if drill is not None:
            result = failure_drill_lib.run_drill(drill, workdir=workdir,
                                                 keep=keep)
            ok = result["status"] == "pass"
        else:
            result = failure_drill_lib.run_all_drills(workdir=workdir,
                                                      keep=keep)
            ok = result["summary"]["ok"]
    except failure_drill_lib.DrillError as e:
        print("تعذّر التدريب: %s" % e)
        return 2
    if as_json:
        _print_json(result)
    else:
        if drill is not None:
            print("تدريب «%s»: %s — %s"
                  % (result["title"], result["status"],
                     result["detail"]))
        else:
            summary = result["summary"]
            print("تدريبات الأعطال: %d ناجحة من %d"
                  % (summary["passed"], summary["total"]))
            for item in result["drills"]:
                print("  [%s] %s — %s"
                      % (item["status"], item["title"], item["detail"]))
    return 0 if ok else 1


# ------------------------------------------- keyword-analyze (جولة v0.1.61)
def cmd_keyword_analyze(cfg, keyword=None, metrics_json=None,
                        keywords_json=None, as_json=False):
    """حلّل كلمة مفتاحية (أو دفعية) وقدّر صعوبة استهدافها.

    تغليف رقيق فوق `lib.keyword_analyze`: كلمة واحدة
    (--keyword مع --metrics-json اختياري)، أو دفعية
    (--keywords-json). خروج 0 عند النجاح، و2 على مدخل فاسد
    (ملف مفقود/JSON فاسد/كلمة فارغة). --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تحليل بيانات صريحة.
    if keywords_json is not None:
        if keyword is not None or metrics_json is not None:
            print("مرّر --keywords-json أو --keyword (أحدهما فقط)")
            return 2
        text = _read_growth_text_file(keywords_json, "ملف الكلمات")
        if text is None:
            return 2
        try:
            result = keyword_analyze_lib.analyze_keywords(text)
        except (ValueError, TypeError) as e:
            print("مدخل محلّل الكلمات غير صالح: %s" % e)
            return 2
    else:
        if not keyword:
            print("مرّر --keyword أو --keywords-json")
            return 2
        metrics = None
        if metrics_json is not None:
            payload = _load_json_file(metrics_json, "ملف مقاييس الكلمة")
            if payload is None:
                return 2
            if not isinstance(payload, dict):
                print("ملف مقاييس الكلمة يجب أن يحوي قاموسًا واحدًا")
                return 2
            inner = payload.get("metrics")
            metrics = inner if isinstance(inner, dict) else payload
        try:
            result = keyword_analyze_lib.analyze_keyword(keyword, metrics)
        except (ValueError, TypeError) as e:
            print("مدخل محلّل الكلمات غير صالح: %s" % e)
            return 2
    if as_json:
        print(keyword_analyze_lib.to_json(result), end="")
    else:
        print(keyword_analyze_lib.format_report(result))
    return 0


# ------------------------------------------- content-optimize (جولة v0.1.61)
def cmd_content_optimize(cfg, title, keyword, body_file, description="",
                         phrases_json=None, as_json=False):
    """قيّم محتوى ضد كلمة مفتاحية (درجة 0–100، النطاق الصحي 55–75).

    تغليف رقيق فوق `lib.content_optimizer`: العنوان والكلمة
    ونص ملف (--body-file) ووصف اختياري وعبارات موصى بها
    اختيارية (--phrases-json). خروج 0 عند النجاح، و2 على مدخل
    فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تقييم نص صريح.
    body = _read_growth_text_file(body_file, "ملف نص المحتوى")
    if body is None:
        return 2
    phrases = None
    if phrases_json is not None:
        phrases = _load_json_file(phrases_json, "ملف العبارات الموصى بها")
        if phrases is None:
            return 2
        if not isinstance(phrases, list):
            print("ملف العبارات الموصى بها يجب أن يحوي قائمة")
            return 2
    try:
        result = content_optimizer_lib.optimize_content(
            title, description, body, keyword,
            recommended_phrases=phrases)
    except (ValueError, TypeError) as e:
        print("مدخل محسِّن المحتوى غير صالح: %s" % e)
        return 2
    if as_json:
        print(content_optimizer_lib.to_json(result), end="")
    else:
        print(content_optimizer_lib.format_report(result))
    return 0


# ------------------------------------------- keyword-generate (جولة v0.1.61)
def cmd_keyword_generate(cfg, seed, corpus_json=None, limit=20,
                         as_json=False):
    """ولّد كلمات مفتاحية ذات صلة من بذرة (بلا أحجام مخترعة).

    تغليف رقيق فوق `lib.keyword_generate`: البذرة إلزامية،
    وcorpus اختياري (--corpus-json)، و--limit (1–100،
    الافتراضي 20). خروج 0 عند النجاح، و2 على مدخل فاسد.
    --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر توليد من بذرة صريحة.
    corpus = None
    if corpus_json is not None:
        text = _read_growth_text_file(corpus_json, "ملف corpus الكلمات")
        if text is None:
            return 2
        corpus = text
    try:
        result = keyword_generate_lib.generate_keywords(
            seed, corpus=corpus, limit=limit)
    except (ValueError, TypeError) as e:
        print("مدخل مولّد الكلمات غير صالح: %s" % e)
        return 2
    if as_json:
        print(keyword_generate_lib.to_json(result), end="")
    else:
        print(keyword_generate_lib.format_report(result))
    return 0


# ------------------------------------------- micro-niche (جولة v0.1.61)
def cmd_micro_niche(cfg, niches_json, library_json=None, as_json=False):
    """ابحث عن تخصصات دقيقة قليلة المنافسة (فرصة/مزدحم/بلا طلب).

    تغليف رقيق فوق `lib.micro_niche`: ملف تخصصات
    (--niches-json) ومكتبة قصصنا اختيارية (--library-json
    أو مضمّنة في الملف نفسه). خروج 0 عند النجاح، و2 على
    مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر بحث في بيانات صريحة.
    text = _read_growth_text_file(niches_json, "ملف التخصصات")
    if text is None:
        return 2
    library = None
    if library_json is not None:
        library = _load_json_file(library_json, "ملف مكتبة القصص")
        if library is None:
            return 2
        if not isinstance(library, list):
            print("ملف مكتبة القصص يجب أن يحوي قائمة")
            return 2
    try:
        result = micro_niche_lib.find_micro_niches(text, library=library)
    except (ValueError, TypeError) as e:
        print("مدخل باحث التخصصات غير صالح: %s" % e)
        return 2
    if as_json:
        print(micro_niche_lib.to_json(result), end="")
    else:
        print(micro_niche_lib.format_report(result))
    return 0


# ------------------------------------------- page-analyze (جولة v0.1.61)
def cmd_page_analyze(cfg, page_json, as_json=False):
    """حلّل صفحة/فيديو (عنوان + وصف + وسوم) واقترح تحسينات.

    تغليف رقيق فوق `lib.page_analyze`: ملف صفحة واحد
    (--page-json). خروج 0 عند النجاح، و2 على مدخل فاسد.
    --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر تحليل صفحة صريحة.
    text = _read_growth_text_file(page_json, "ملف الصفحة")
    if text is None:
        return 2
    try:
        result = page_analyze_lib.analyze_page(text)
    except (ValueError, TypeError) as e:
        print("مدخل محلّل الصفحة غير صالح: %s" % e)
        return 2
    if as_json:
        print(page_analyze_lib.to_json(result), end="")
    else:
        print(page_analyze_lib.format_report(result))
    return 0


# ------------------------------------------- fresh-keywords (جولة v0.1.61)
def cmd_fresh_keywords(cfg, trends_json, days=7, today=None, as_json=False):
    """رتّب كلمات رائجة اليوم من بيانات ترند (بلا أرقام مخترعة).

    تغليف رقيق فوق `lib.fresh_keywords`: ملف ترندات
    (--trends-json) ونافذة حداثة (--days، الافتراضي 7)
    وتاريخ مرجعي اختياري (--today بصيغة YYYY-MM-DD).
    خروج 0 عند النجاح، و2 على مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر ترتيب بيانات صريحة.
    text = _read_growth_text_file(trends_json, "ملف الترندات")
    if text is None:
        return 2
    try:
        result = fresh_keywords_lib.fresh_keywords(
            text, days=days, today=today)
    except (ValueError, TypeError) as e:
        print("مدخل الكلمات الطازجة غير صالح: %s" % e)
        return 2
    if as_json:
        print(fresh_keywords_lib.to_json(result), end="")
    else:
        print(fresh_keywords_lib.format_report(result))
    return 0


# ------------------------------------------- topical-authority (جولة v0.1.61)
def cmd_topical_authority(cfg, library_json, topics_json=None,
                          as_json=False):
    """قس سلطة مكتبة القصص الموضوعية وحدّد فجوات التغطية.

    تغليف رقيق فوق `lib.topical_authority`: ملف مكتبة
    (--library-json) وخريطة مواضيع اختيارية (--topics-json).
    خروج 0 عند النجاح، و2 على مدخل فاسد. --json خالص.
    """
    del cfg  # الإعداد غير مستخدم: الأمر قياس مكتبة صريحة.
    text = _read_growth_text_file(library_json, "ملف مكتبة القصص")
    if text is None:
        return 2
    topic_map = None
    if topics_json is not None:
        topic_map = _load_json_file(topics_json, "ملف خريطة المواضيع")
        if topic_map is None:
            return 2
        if not isinstance(topic_map, dict):
            print("ملف خريطة المواضيع يجب أن يحوي قاموسًا واحدًا")
            return 2
    try:
        result = topical_authority_lib.topical_authority(
            text, topic_map=topic_map)
    except (ValueError, TypeError) as e:
        print("مدخل السلطة الموضوعية غير صالح: %s" % e)
        return 2
    if as_json:
        print(topical_authority_lib.to_json(result), end="")
    else:
        print(topical_authority_lib.format_report(result))
    return 0


# الأوامر التجارية (جولة v0.1.43): كل ما ينتج/ينشر/يبيع — تُغلق
# بعد انتهاء فترة التجربة (30 يومًا من أول تشغيل) بلا ترخيص
# مدفوع. الأوامر غير المذكورة هنا (قراءة/تشخيص/صيانة/إعداد)
# معفاة ولا تبدأ ساعة التجربة. `run --demo` معفى أيضًا (طريق
# التقييم للمستخدم الجديد) — يُفحص في main() لا هنا.
# الأوامر المُبوَّبة بالنجمة (جولة v0.1.48): الثمانية فقط —
# run/produce/assemble/publish/batch/daily/long-video/client-run.
# تُتخطى البوابة مع --dry-run؛ وتسري بغض النظر عن --noncommercial
# (ليست بوابة تجارية). doctor/license/--help بلا بوابة بطبيعتها.
STAR_GATED_COMMANDS = frozenset((
    "run", "produce", "assemble", "publish", "batch", "daily",
    "long-video", "client-run", "quick",
))


COMMERCIAL_COMMANDS = frozenset((
    "run", "produce", "assemble", "long-video", "long-narration",
    "daily", "batch", "run-queue", "publish", "schedule",
    "client-run", "process-queue", "orders", "script", "thumbnail",
    "quote-cards", "scene-plan", "ideas", "fix-audio", "grade",
    "trim", "fx", "karaoke-ass", "srt-ass", "whisper-ass",
    "manifest", "avatar-job", "ab", "ab-results", "shorts-cut",
    "reframe", "preview", "request", "quick",
))

# ------------------------------------------- أوامر الموجة ب (جولة v0.1.63)
# أغلفة رقيقة فوق وحدات الموجة أ — بلا منطق جديد هنا؛ المنطق في
# lib/. كل أمر يرجع رمز خروج من ع1 ويطبع عبر lib/cli_output.py
# عند --json (وثيقة JSON واحدة على stdout)، وسطورًا بشرية عربية
# بلا --json. الاستيرادات كسولة داخل الدوال حيث أمكن.
#
# انحرافات موثقة عن الخطة (لا دالة لها في وحدات الموجة أ):
# - حالة الفريق: لا تحميل/حفظ لها في lib/team_file.py، فيحفظها
#   الأمر في runs/team-state.json (0600، كتابة ذرية).
# - حدود الاستخدام: لا دالة حفظ في lib/usage_caps.py، فيكتب الأمر
#   ~/.qisas-studio/usage-caps.json بنفسه (0600، كتابة ذرية).
# - wait/wait-job: لا دالة انتظار في الوحدات، فالاستطلاع حلقة
#   صغيرة هنا فوق get_job (بلا منطق قرار جديد).
# - control: بلا معالج موصَّل، فيرجع run_control ملخص الفعل
#   والهدف بعد التحقق منهما (لا ينفّذ فعلًا حقيقيًا).
# - switch-model: لا حفظ للنموذج المختار في الوحدات، فالأمر
#   يتحقق من المحرك وصحته فقط (بلا تغيير إعداد دائم).


def _new_output(args):
    """Output عقد CLI الموحّد من رايتي الجذر --json/--quiet."""
    from lib import cli_output as _cli_output
    return _cli_output.Output(
        json_mode=bool(getattr(args, "json", False)),
        quiet=bool(getattr(args, "quiet", False)))


def _runs_dir_of(cfg):
    """مجلد التشغيل runs/ من الإعداد."""
    return expand(cfg["paths"]["runs_dir"])


def _team_state_path(cfg):
    """مسار ملف حالة الفريق المحفوظة (runs/team-state.json)."""
    return os.path.join(_runs_dir_of(cfg), "team-state.json")


def _load_team_state(cfg):
    """اقرأ حالة الفريق المحفوظة؛ غيابها = حالة فارغة."""
    from lib import team_file as _team_file
    path = _team_state_path(cfg)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return _team_file.empty_state()
    if not isinstance(data, dict):
        return _team_file.empty_state()
    data.setdefault("teams", {})
    data.setdefault("bots", {})
    return data


def _save_team_state(cfg, state):
    """احفظ حالة الفريق ذريًا بصلاحية 0600."""
    path = _team_state_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _usage_caps_path():
    """مسار ملف حدود الاستخدام (~/.qisas-studio/usage-caps.json)."""
    return os.path.join(os.path.expanduser("~"), ".qisas-studio",
                        "usage-caps.json")


def _save_usage_caps(updates):
    """احفظ تحديثات حدود الاستخدام ذريًا بصلاحية 0600.

    قيمة 0 أو None تمسح الحد (بلا حد)؛ والباقي يُكتب كما هو.
    يرجع محتوى الملف بعد الحفظ.
    """
    path = _usage_caps_path()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}
    for key, value in updates.items():
        if value is None or value == 0:
            raw.pop(key, None)
        else:
            raw[key] = value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return raw


def _parse_feature_value(text):
    """فسّر قيمة مفتاح مزايا نصية: true/false/عدد/نص."""
    low = text.strip().lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    return text


def _parse_recipe_step(text):
    """فسّر خطوة وصفة بصيغة «الاسم: الأمر...» إلى قاموس."""
    import shlex
    if ":" not in text:
        raise ValueError(
            "صيغة الخطوة: «الاسم: الأمر...» (وصل: %s)" % text)
    name, command = text.split(":", 1)
    parts = shlex.split(command.strip())
    if not name.strip() or not parts:
        raise ValueError(
            "الخطوة تحتاج اسمًا وأمرًا غير فارغين (وصل: %s)" % text)
    return {"name": name.strip(), "command": parts}


_JOB_TERMINAL = ("done", "failed", "skipped", "reused", "cancelled")

# حالات المهمة (done/failed/...) ← حالات الانتظار
# (completed/idle/...) التي يفهمها wait_outcome_for_state.
_JOB_STATE_TO_WAIT_STATE = {
    "done": "completed",
    "failed": "failed",
    "skipped": "idle",
    "reused": "idle",
    "cancelled": "failed",
}


def _wait_outcome(status):
    """حوّل حالة مهمة منتهية إلى نتيجة انتظار (بند 19)."""
    from lib import job_registry as _job_registry
    wait_state = _JOB_STATE_TO_WAIT_STATE.get(status)
    if wait_state is None:
        return "timed-out"
    return _job_registry.wait_outcome_for_state(wait_state)


def _poll_job(cfg, job_id, timeout, poll_interval):
    """استطلع مهمة حتى تنتهي أو تنتهي المهلة.

    يرجع (المهمة أو None، انتهت؟). مهمة منتهية أصلًا ترجع فورًا.
    """
    from lib import job_registry as _job_registry
    runs_dir = _runs_dir_of(cfg)
    deadline = time.monotonic() + max(0.0, float(timeout))
    job = _job_registry.get_job(runs_dir, job_id)
    while job is not None and job.get("status") not in _JOB_TERMINAL:
        if time.monotonic() >= deadline:
            return job, False
        time.sleep(max(0.0, float(poll_interval)))
        job = _job_registry.get_job(runs_dir, job_id)
    return job, job is not None


def cmd_approval(args, out):
    """approval show|set — مستويات الموافقة الخمسة (ع3).

    show يطبع المستوى والوضع والمنح؛ وset يضبط --level أو
    --mode أو --custom (ACTION=DECISION). خروج 2 على مدخل باطل.
    """
    from lib import approval as _approval
    if args.approval_cmd == "show":
        state = _approval.show()
        return _approval_show_result(state, out)
    gate = _approval.ApprovalGate()
    changed = []
    try:
        if getattr(args, "level", None):
            gate.set_level(args.level)
            changed.append("level=%s" % args.level)
        if getattr(args, "mode", None):
            gate.set_mode(args.mode)
            changed.append("mode=%s" % args.mode)
        for item in getattr(args, "custom", None) or []:
            if "=" not in item:
                return out.error(
                    "صيغة custom غير صالحة: %s (الصيغة ACTION=DECISION)"
                    % item,
                    hint="مثال: --custom publish=ask",
                    code=2)
            action, decision = item.split("=", 1)
            gate.set_custom_action(action.strip(), decision.strip())
            changed.append("custom %s=%s"
                           % (action.strip(), decision.strip()))
    except _approval.ApprovalError as e:
        return out.error(str(e), code=2)
    if not changed:
        return out.error("حدد ما يُضبط: --level أو --mode أو --custom",
                         hint="مثال: approval set --level auto",
                         code=2)
    state = _approval.show()
    state = dict(state)
    state["changed"] = changed
    out.result(state, human_lines=[
        "مستوى الموافقة: %s" % state["level"],
        "الوضع: %s" % state["mode"],
        "ما تغيّر: %s" % "، ".join(changed),
    ])
    return 0


def _approval_show_result(state, out):
    """نتيجة موحدة لأمر approval show."""
    out.result({"level": state["level"], "mode": state["mode"],
                "custom": state["custom"], "grants": state["grants"]},
               human_lines=[
                   "مستوى الموافقة: %s" % state["level"],
                   "الوضع: %s" % state["mode"],
                   "منح دائمة/جلسة: %d" % len(state["grants"]),
               ])
    return 0


def cmd_team(cfg, args, out):
    """team apply|export|check — ملف الفريق الإعلاني (ع17).

    apply يطبع الخطة ثم يطبّقها (--dry-run للخطة فقط، و--prune
    للحذف في فرق prune: true)؛ وcheck خروج 6 إن كان شيء
    سيتغيّر؛ وexport يطبع الحالة المحفوظة. إعادة التطبيق بلا
    تغييرات تطبع `No changes.`.
    """
    from lib import team_file as _team_file
    if args.team_cmd == "export":
        state = _load_team_state(cfg)
        data = _team_file.export_state(state)
        lines = ["الفرق: %d — البوتات: %d"
                 % (len(data["teams"]), len(data["bots"]))]
        for team in data["teams"]:
            lines.append("فريق: %s" % team.get("name"))
        for bot in data["bots"]:
            lines.append("بوت: %s (فريق %s)"
                         % (bot.get("name"), bot.get("team")))
        out.result(data, human_lines=lines)
        return 0
    try:
        data = _team_file.load_team_file(expand(args.file))
    except FileNotFoundError:
        return out.error("ملف الفريق غير موجود: %s" % args.file,
                         code=7)
    except OSError as e:
        return out.error("تعذر قراءة ملف الفريق: %s" % e, code=1)
    except _team_file.TeamFileError as e:
        return out.error(str(e), code=getattr(e, "exit_code", 2) or 2)
    state = _load_team_state(cfg)
    if args.team_cmd == "check":
        try:
            changed = _team_file.check(data, state)
        except _team_file.TeamFileError as e:
            return out.error(str(e), code=getattr(e, "exit_code", 2) or 2)
        out.result({"changed": bool(changed)},
                   human_lines=["سيتغيّر شيء عند التطبيق"
                                if changed else "No changes."])
        return 6 if changed else 0
    try:
        result = _team_file.apply(data, state, dry_run=args.dry_run,
                                  prune=args.prune)
    except _team_file.TeamFileError as e:
        return out.error(str(e), code=getattr(e, "exit_code", 2) or 2)
    except _team_file.TeamApplyError as e:
        if getattr(e, "state", None) is not None:
            _save_team_state(cfg, e.state)
        return out.error(str(e),
                         hint="أُنجز جزء من التطبيق — أعد التطبيق "
                              "ليكمل من حيث توقف",
                         code=1)
    if not args.dry_run:
        _save_team_state(cfg, result["state"])
    applied = result.get("applied") or []
    lines = [result.get("message") or ""]
    for action in applied:
        if isinstance(action, dict):
            lines.append("- %s" % (action.get("detail")
                                   or action.get("name") or "؟"))
    out.result({"changed": bool(result.get("changed")),
                "message": result.get("message"),
                "applied": applied},
               human_lines=lines)
    return 0


def cmd_routines(cfg, args, out):
    """routines ledger|missed — سجل وقوعات الروتينات (ع4).

    ledger يعرض سطور السجل (بفلترة اختيارية)؛ وmissed يلخّص
    الوقوعات الفائتة وعددها المنهار.
    """
    from lib import schedule_watch as _schedule_watch
    runs_dir = _runs_dir_of(cfg)
    if args.routines_cmd == "ledger":
        entries = _schedule_watch.read_ledger(
            runs_dir, routine=args.routine, state=args.state,
            limit=args.limit)
        lines = ["%s — %s — %s — %s (×%s)"
                 % (e.get("ts", "")[:19], e.get("routine"),
                    e.get("state"), e.get("reason"),
                    e.get("count") or 1)
                 for e in entries] or ["لا وقوعات مسجلة بعد"]
        out.result({"entries": entries, "count": len(entries)},
                   human_lines=lines)
        return 0
    entries = _schedule_watch.read_ledger(
        runs_dir, routine=args.routine, state="missed",
        limit=args.limit)
    collapsed = sum(int(e.get("count") or 1) for e in entries)
    lines = ["الوقوعات الفائتة: %d صفًا (%d وقوعًا منهارًا)"
             % (len(entries), collapsed)]
    for e in entries:
        lines.append("%s — %s — %s (×%s)"
                     % (e.get("ts", "")[:19], e.get("routine"),
                        e.get("reason"), e.get("count") or 1))
    out.result({"entries": entries, "count": len(entries),
                "collapsed": collapsed},
               human_lines=lines)
    return 0


def cmd_check_back(cfg, args, out):
    """check-back add|list|cancel — متابعة مؤجلة لمرة واحدة.

    add يقبل --due بصيغة ISO أو --in-minutes؛ وlist يفلتر
    بالتشغيل/العامل/الحالة؛ وcancel يلغي معلَّقًا (7 إن غاب).
    """
    from lib import check_back as _check_back
    runs_dir = _runs_dir_of(cfg)
    if args.check_back_cmd == "list":
        try:
            records = _check_back.list_check_backs(
                runs_dir, run_id=args.run_id, worker=args.worker,
                status=args.status)
        except _check_back.CheckBackError as e:
            return out.error(str(e), code=2)
        pending = _check_back.count_pending(
            runs_dir, run_id=args.run_id, worker=args.worker)
        lines = ["%s — %s — %s — يستحق %s"
                 % (r.get("id"), r.get("run_id"), r.get("status"),
                    str(r.get("due") or "")[:19])
                 for r in records] or ["لا check-backs مسجلة"]
        out.result({"check_backs": records, "count": len(records),
                    "pending": pending},
                   human_lines=lines)
        return 0
    if args.check_back_cmd == "cancel":
        record = _check_back.cancel_check_back(runs_dir, args.id)
        if record is None:
            return out.error("لا يوجد check-back بهذا المعرف: %s"
                             % args.id,
                             code=7)
        out.result({"check_back": record},
                   human_lines=["أُلغي check-back %s (الحالة: %s)"
                                % (record.get("id"),
                                   record.get("status"))])
        return 0
    due = args.due
    if due is None and args.in_minutes is not None:
        from datetime import datetime as _datetime
        from datetime import timedelta as _timedelta
        try:
            from zoneinfo import ZoneInfo as _ZoneInfo
            _cairo = _ZoneInfo("Africa/Cairo")
        except Exception:
            _cairo = None
        now = _datetime.now(_cairo) if _cairo else _datetime.now()
        due = now + _timedelta(minutes=args.in_minutes)
    if due is None:
        return out.error("حدد الموعد: --due بصيغة ISO أو --in-minutes",
                         hint="مثال: --in-minutes 5",
                         code=2)
    try:
        record = _check_back.add_check_back(
            runs_dir, args.run_id, args.worker, due, note=args.note)
    except _check_back.CheckBackError as e:
        return out.error(str(e), code=2)
    out.result({"check_back": record},
               human_lines=["أُضيف check-back %s — يستحق %s"
                            % (record.get("id"),
                               str(record.get("due") or "")[:19])])
    return 0


def cmd_usage_caps(cfg, args, out):
    """usage caps show|set — حدود الاستخدام (ع9).

    show يعرض الحدود والمجاميع الجارية؛ وset يكتب حدًا واحدًا
    أو أكثر (0 يمسح الحد). متغيرات البيئة QISAS_USAGE_CAP_*
    تفوز على الملف عند العرض.
    """
    from lib import usage_caps as _usage_caps
    if args.caps_cmd == "show":
        caps = _usage_caps.load_caps(studio_root=STUDIO_DIR)
        usage = _usage_caps.current_totals(studio_root=STUDIO_DIR)
        lines = _usage_caps.format_caps(caps, usage).split("\n")
        out.result({"caps": caps, "usage": usage},
                   human_lines=lines)
        return 0
    updates = {}
    for key, attr in (("dailyUsd", "daily_usd"),
                      ("monthlyUsd", "monthly_usd"),
                      ("dailyTokens", "daily_tokens"),
                      ("monthlyTokens", "monthly_tokens")):
        value = getattr(args, attr, None)
        if value is not None:
            updates[key] = value
    if getattr(args, "stops", None):
        updates["stops"] = args.stops
    if not updates:
        return out.error("حدد حدًا واحدًا على الأقل لضبطه",
                         hint="مثال: usage caps set --daily-usd 5",
                         code=2)
    _save_usage_caps(updates)
    caps = _usage_caps.load_caps(studio_root=STUDIO_DIR)
    lines = _usage_caps.format_caps(caps).split("\n")
    out.result({"caps": caps, "saved": updates},
               human_lines=lines)
    return 0


def cmd_models(args, out):
    """models list|health — سجل محركات النماذج (بند 9).

    list يعرض المحركات المسجلة؛ وhealth يعرض صحة كل محرك
    (محرك مجهول يتدهور إلى «غير متاح» ولا يرمي أبدًا).
    """
    from lib import model_driver as _model_driver
    _model_driver.register_builtin_drivers()
    if args.models_cmd == "list":
        names = _model_driver.list_drivers()
        health = _model_driver.driver_health_all()
        lines = ["المحركات: %d" % len(names)]
        for name in names:
            info = health.get(name) or {}
            lines.append("- %s: %s"
                         % (name, "متاح" if info.get("available")
                            else "غير متاح (%s)"
                            % (info.get("reason") or "؟")))
        out.result({"drivers": names, "health": health},
                   human_lines=lines)
        return 0
    health = _model_driver.driver_health_all()
    lines = []
    for name in sorted(health):
        info = health[name]
        lines.append("- %s: %s"
                     % (name, "متاح" if info.get("available")
                        else "غير متاح (%s)"
                        % (info.get("reason") or "؟")))
    out.result({"health": health}, human_lines=lines or ["لا محركات"])
    return 0


def cmd_round_pack(cfg, args, out):
    """round-pack export|import|review — حزم الجولات (ع15).

    export يبني ملف .md واحدًا (أسراره منظفة ومعدودة)؛ وimport
    يستورد بعد المراجعة (بلا استبدال إلا بـ--force)؛ وreview
    يتحقق بلا كتابة (خروج 8 عند رفض الحزمة).
    """
    from lib import round_pack as _round_pack
    if args.pack_cmd == "export":
        try:
            summary = _round_pack.export_pack(
                expand(args.dir), args.files or [],
                name=args.name, version=args.version or VERSION,
                changes=args.change or [], tests=args.test or [],
                out_path=expand(args.out))
        except _round_pack.PackError as e:
            return out.error(str(e), code=2)
        out.result(summary, human_lines=[
            "صُدّرت الحزمة: %s" % summary["path"],
            "الملفات: %d — الحجم: %d بايت — أسرار نُظّفت: %d"
            % (summary["files"], summary["total_bytes"],
               summary["secrets_scrubbed"]),
        ])
        return 0
    if args.pack_cmd == "import":
        try:
            summary = _round_pack.import_pack(
                expand(args.pack), expand(args.dest),
                allow_overwrite=args.force)
        except _round_pack.PackError as e:
            return out.error(str(e), code=2)
        out.result(summary, human_lines=[
            "استُوردت الحزمة «%s» (%s) إلى %s"
            % (summary.get("pack"), summary.get("version"),
               expand(args.dest)),
            "الملفات: %s" % ", ".join(summary.get("files") or []),
        ])
        return 0
    review = _round_pack.review_pack(expand(args.pack))
    lines = list(review.get("summary_lines") or [])
    for warning in review.get("warnings") or []:
        lines.append("تحذير: %s" % warning)
    for error in review.get("errors") or []:
        lines.append("خطأ: %s" % error)
    out.result(review, human_lines=lines)
    return 0 if review.get("ok") else 8


def cmd_handoffs(cfg, args, out):
    """handoffs list — تسليمات المنسّق وحالاتها (ع4)."""
    from lib import job_registry as _job_registry
    try:
        records = _job_registry.list_deliveries(
            _runs_dir_of(cfg), state=args.state, limit=args.limit)
    except _job_registry.JobRegistryError as e:
        return out.error(str(e), code=2)
    text = _job_registry.format_deliveries(records)
    out.result({"deliveries": records, "count": len(records)},
               human_lines=text.split("\n"))
    return 0


def cmd_keys(args, out):
    """keys set|test|rotate|list — الأسرار كتابة فقط (ع12).

    المفتاح عبر --token-file فقط — أبدًا --token على سطر
    الأوامر (يُرفض برمز 2). set/test يجريان استدعاء اختبار
    واحدًا؛ والمرفوض لا يُحفظ. list يعرض الأسماء والوجود
    فقط — أبدًا القيم.
    """
    from lib import secret_guard as _secret_guard
    if args.keys_cmd == "list":
        try:
            entries = _secret_guard.list_keys()
        except _secret_guard.KeyStoreError as e:
            return out.error(str(e), code=1)
        lines = ["المفاتيح المحفوظة: %d" % len(entries)]
        for entry in entries:
            lines.append("- %s (%s): موجود"
                         % (entry.get("name"),
                            entry.get("provider") or "custom"))
        out.result({"keys": entries, "count": len(entries)},
                   human_lines=lines)
        return 0
    if getattr(args, "token", None) is not None:
        return out.error(
            "لا تمرّر المفتاح في سطر الأوامر أبدًا — ضعه في ملف "
            "ومرّر مساره عبر --token-file",
            hint="مثال: keys set --name gemini "
                 "--token-file /tmp/token.txt",
            code=2)
    if args.keys_cmd == "test":
        try:
            value = _secret_guard.read_token_file(
                expand(args.token_file))
        except _secret_guard.KeyStoreError as e:
            return out.error(str(e), code=2)
        ok, message = _secret_guard.test_key(args.provider, value)
        out.result({"provider": args.provider, "ok": bool(ok),
                    "message": message},
                   human_lines=[message])
        return 0 if ok else 1
    try:
        value = _secret_guard.read_token_file(expand(args.token_file))
    except _secret_guard.KeyStoreError as e:
        return out.error(str(e), code=2)
    try:
        if args.keys_cmd == "set":
            entry = _secret_guard.set_key(
                args.name, value, provider=args.provider)
        else:
            entry = _secret_guard.rotate_key(args.name, value)
    except _secret_guard.KeyTestError as e:
        return out.error(str(e),
                         hint="المفتاح الذي يرفضه المزوّد لا يُحفظ",
                         code=1)
    except _secret_guard.KeyStoreError as e:
        return out.error(str(e), code=7)
    except ValueError as e:
        return out.error(str(e), code=2)
    verb = "حُفظ المفتاح" if args.keys_cmd == "set" else "دُوّر المفتاح"
    out.result({"key": entry},
               human_lines=["%s «%s» (%s)"
                            % (verb, entry.get("name"),
                               entry.get("provider"))])
    return 0


def cmd_sentinel(cfg, args, out):
    """sentinel — فاحص صحة يقرأ فقط ويجمّع الأعطال (ع14).

    يقرأ runs/jobs.jsonl وسجلات التشغيل قراءة فقط، ويكتب
    القضايا خارج مجلد البيانات. --out داخل البيانات أو git
    مرفوض. خروج 0 دائمًا عند نجاح الفحص.
    """
    from lib import sentinel as _sentinel
    data_dir = expand(args.data_dir) if args.data_dir else STUDIO_DIR
    out_dir = expand(args.out) if args.out else None
    try:
        code, summary = _sentinel.run_sentinel(
            data_dir, out_dir=out_dir,
            json_mode=bool(getattr(args, "json", False)), once=True)
    except _sentinel.SentinelError as e:
        return out.error(str(e), code=2)
    scanned = summary.get("scanned") or {}
    out.result(summary, human_lines=[
        "الفحص: %s" % ("تغيّرت المصادر" if summary.get("changed")
                       else "لا تغيير في المصادر"),
        "قضايا جديدة: %s — الإجمالي: %s"
        % (summary.get("new_issues"), summary.get("total_issues")),
        "فُحص: %s مهمة، %s سطر سجل"
        % (scanned.get("jobs"), scanned.get("log_lines")),
        "مجلد القضايا: %s" % summary.get("out_dir"),
    ])
    return code


def cmd_control(cfg, args, out):
    """control <verb> — سطح تحكم محدود (بند 17).

    أفعال القراءة تعمل بلا هدف؛ وأفعال التعديل ترفض الهدف
    الصامت (خروج 2)؛ وفعل مجهول مرفوض (خروج 2). بلا معالج
    موصَّل يرجع الفعل ملخص الفعل والهدف بعد التحقق منهما.
    """
    from lib import control_fixture as _control_fixture
    target = None
    if getattr(args, "target", None):
        target = _control_fixture.ControlTarget(
            data_dir=_runs_dir_of(cfg), label=args.target)
    try:
        result = _control_fixture.run_control(args.verb, target=target)
    except _control_fixture.ControlError as e:
        return out.error(str(e), code=2)
    if not isinstance(result, dict):
        result = {"result": result}
    lines = ["الفعل: %s" % result.get("verb", args.verb)]
    if result.get("target"):
        lines.append("الهدف: %s" % result["target"])
    out.result(result, human_lines=lines)
    return 0


def cmd_inspect(cfg, args, out):
    """inspect jobs|runs — قراءات محدودة (بند 19).

    jobs يسرد مهام سجل التشغيل؛ وruns يسرد مجلدات التشغيل
    في runs/.
    """
    from lib import job_registry as _job_registry
    runs_dir = _runs_dir_of(cfg)
    if args.inspect_cmd == "jobs":
        try:
            jobs = _job_registry.list_jobs(
                runs_dir, status=args.status, limit=args.limit)
        except _job_registry.JobRegistryError as e:
            return out.error(str(e), code=2)
        text = _job_registry.format_jobs(jobs)
        out.result({"jobs": jobs, "count": len(jobs)},
                   human_lines=text.split("\n"))
        return 0
    names = []
    try:
        for name in sorted(os.listdir(runs_dir)):
            if os.path.isdir(os.path.join(runs_dir, name)):
                names.append(name)
    except OSError:
        names = []
    lines = ["مجلدات التشغيل في runs/: %d" % len(names)]
    lines.extend("- %s" % name for name in names)
    out.result({"runs": names, "count": len(names)},
               human_lines=lines)
    return 0


def cmd_read_log(cfg, args, out):
    """read-log — اقرأ آخر N مدخلًا من سجل (بند 19).

    الحد الأقصى 200 مدخل. ملف غائب خروج 7.
    """
    from lib import log_reader as _log_reader
    path = (expand(args.file) if args.file
            else os.path.join(_runs_dir_of(cfg), "studio.log"))
    try:
        entries = _log_reader.read_log(path, limit=args.limit)
    except _log_reader.LogReaderError as e:
        message = str(e)
        code = 7 if ("غير موجود" in message or "لا يوجد" in message) \
            else 1
        return out.error(message, code=code)
    lines = [json.dumps(e, ensure_ascii=False) for e in entries]
    out.result({"path": path, "entries": entries,
                "count": len(entries)},
               human_lines=lines or ["السجل فارغ"])
    return 0


def cmd_search_log(cfg, args, out):
    """search-log — ابحث في سجل (أول 100 مطابقة، بند 19)."""
    from lib import log_reader as _log_reader
    path = (expand(args.file) if args.file
            else os.path.join(_runs_dir_of(cfg), "studio.log"))
    try:
        matches = _log_reader.search_log(path, args.query,
                                         limit=args.limit)
    except _log_reader.LogReaderError as e:
        message = str(e)
        code = 7 if ("غير موجود" in message or "لا يوجد" in message) \
            else 1
        return out.error(message, code=code)
    lines = [json.dumps(e, ensure_ascii=False) for e in matches]
    out.result({"path": path, "query": args.query, "matches": matches,
                "count": len(matches)},
               human_lines=lines or ["لا مطابقات"])
    return 0


def cmd_send_work(cfg, args, out):
    """send-work — سجّل تسليمًا جديدًا بحالة source (ع4/ع11).

    المصدر تسمية ع11 إلزامية؛ والافتراضي مصدر سطر الأوامر.
    """
    from lib import job_registry as _job_registry
    source = args.source or _job_registry.format_source(
        "cli", "send-work", "direct")
    try:
        record = _job_registry.register_delivery(
            _runs_dir_of(cfg), source, kind=args.kind,
            title=args.title)
    except _job_registry.JobRegistryError as e:
        return out.error(str(e), code=2)
    out.result({"delivery": record},
               human_lines=["سُجّل التسليم %s بحالة %s"
                            % (record.get("id"), record.get("state"))])
    return 0


def cmd_wait_job(cfg, args, out):
    """wait-job — انتظر مهمة حتى تنتهي (بند 19).

    النتيجة settled عند انتهاء المهمة، وtimed-out عند انتهاء
    المهلة. خروج 0 عند done، و1 عند فشل/مهلة.
    """
    from lib import job_registry as _job_registry
    job, settled = _poll_job(cfg, args.job_id, args.timeout, args.poll)
    if job is None:
        return out.error("لا توجد مهمة بهذا المعرف: %s" % args.job_id,
                         code=7)
    status = job.get("status")
    if settled:
        outcome = _wait_outcome(status)
    else:
        outcome = "timed-out"
    out.result({"job_id": args.job_id, "status": status,
                "outcome": outcome, "settled": bool(settled)},
               human_lines=["المهمة %s: %s (الانتظار: %s)"
                            % (args.job_id, status, outcome)])
    return 0 if status == "done" else 1


def cmd_interrupt_job(cfg, args, out):
    """interrupt-job — قاطع مهمة وشجرتها المفوَّضة (بند 19).

    مهمة غائبة خروج 7؛ ومهمة منتهية أصلًا ترجع بلا تغيير.
    """
    from lib import job_registry as _job_registry
    runs_dir = _runs_dir_of(cfg)
    if _job_registry.get_job(runs_dir, args.job_id) is None:
        return out.error("لا توجد مهمة بهذا المعرف: %s" % args.job_id,
                         code=7)
    changed = _job_registry.interrupt_job(runs_dir, args.job_id)
    out.result({"job_id": args.job_id, "changed": len(changed),
                "jobs": changed},
               human_lines=["قُوطعت المهمة %s — تغيّر %d سجلًا"
                            % (args.job_id, len(changed))])
    return 0


def cmd_switch_model(args, out):
    """switch-model — تحقق من محرك نموذج قبل التبديل (بند 9).

    محرك مجهول خروج 7؛ ومحرك معروف غير متاح يُبلَّغ بلا فشل.
    (لا حفظ دائم للنموذج المختار — لا دالة له في الموجة أ.)
    """
    from lib import model_driver as _model_driver
    _model_driver.register_builtin_drivers()
    driver = _model_driver.get_driver(args.model)
    health = driver.health()
    if (not health.get("available")
            and health.get("reason") == "unknown_driver"):
        return out.error("محرك غير معروف: %s" % args.model,
                         hint="اعرض المحركات بـ: models list",
                         code=7)
    out.result({"model": args.model,
                "available": bool(health.get("available")),
                "health": health},
               human_lines=["النموذج: %s — %s"
                            % (args.model,
                               "متاح" if health.get("available")
                               else "غير متاح (%s)"
                               % (health.get("reason") or "؟"))])
    return 0


def cmd_wait(cfg, args, out):
    """wait — انتظر مهمة مع أحداثها (بند 19).

    كـ wait-job لكنه يعيد أيضًا أحداث المهمة وعلامة
    الاستئناف (resumed). خروج 0 عند settled، و1 عند غيره.
    """
    from lib import log_reader as _log_reader
    runs_dir = _runs_dir_of(cfg)
    job, settled = _poll_job(cfg, args.job_id, args.timeout, args.poll)
    if job is None:
        return out.error("لا توجد مهمة بهذا المعرف: %s" % args.job_id,
                         code=7)
    events = _log_reader.read_job_events(runs_dir, args.job_id,
                                         limit=args.limit)
    resumed = _log_reader.events_resumed(events)
    if settled:
        outcome = _wait_outcome(job.get("status"))
    elif _log_reader.events_settled(events):
        settled = True
        outcome = "settled"
    else:
        outcome = "timed-out"
    out.result({"job_id": args.job_id, "status": job.get("status"),
                "outcome": outcome, "settled": bool(settled),
                "resumed": resumed, "events": events},
               human_lines=["المهمة %s: %s (الانتظار: %s)"
                            % (args.job_id, job.get("status"), outcome)])
    return 0 if outcome == "settled" else 1


def cmd_events(cfg, args, out):
    """events — اقرأ أحداث مهمة (بند 19).

    آخر N حدثًا (افتراضي 200) + علامة الاستئناف من أول حدث.
    مهمة بلا أحداث ترجع قائمة فارغة — بلا خطأ.
    """
    from lib import log_reader as _log_reader
    runs_dir = _runs_dir_of(cfg)
    events = _log_reader.read_job_events(runs_dir, args.job_id,
                                         limit=args.limit)
    resumed = _log_reader.events_resumed(events)
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    out.result({"job_id": args.job_id, "events": events,
                "count": len(events), "resumed": resumed},
               human_lines=lines or ["لا أحداث لهذه المهمة"])
    return 0


def cmd_brief(cfg, args, out):
    """brief show|dismiss — الموجز اليومي (ع16).

    show يعرض حالة الموجز (لا يُنشر موجز فارغ أبدًا)؛ وdismiss
    يرفض صفًا — للمالك فقط (خروج 5 عند ملكية غيره، و7 عند
    صف غائب).
    """
    from lib import daily_brief as _daily_brief
    runs_dir = _runs_dir_of(cfg)
    if args.brief_cmd == "show":
        state = _daily_brief.load_state(runs_dir)
        brief = _daily_brief.build_brief()
        text = _daily_brief.render_brief(brief)
        lines = text.split("\n")
        lines.append("")
        lines.append("ملف الموجز: %s"
                     % (state.get("brief_file") or "لم يُسلَّم بعد"))
        lines.append("المنطقة الزمنية: %s"
                     % (state.get("timezone") or "Africa/Cairo"))
        out.result({"empty": bool(_daily_brief.is_empty(brief)),
                    "timezone": state.get("timezone"),
                    "brief_file": state.get("brief_file"),
                    "important_rows": state.get("important_rows") or [],
                    "delivered": state.get("delivered") or {}},
                   human_lines=lines)
        return 0
    state = _daily_brief.load_state(runs_dir)
    rows = [{"id": row_id, "title": row_id, "body": ""}
            for row_id in state.get("important_rows") or []]
    brief = _daily_brief.build_brief(needs_you=rows)
    try:
        brief = _daily_brief.dismiss_row(
            brief, args.row_id, owner=args.owner,
            thread_owner=args.thread_owner)
    except _daily_brief.BriefError as e:
        message = str(e)
        if "للمالك فقط" in message:
            code = 5
        elif "لا يوجد صف" in message:
            code = 7
        else:
            code = 1
        return out.error(message, code=code)
    state["last_dismissals"] = list(brief.get("dismissed") or [])
    _daily_brief.save_state(runs_dir, state)
    out.result({"row_id": args.row_id,
                "dismissed": brief.get("dismissed") or []},
               human_lines=["رُفض الصف %s" % args.row_id])
    return 0


def cmd_workers(cfg, args, out):
    """workers pause|resume|stop — إيقاف العمال (بند 28).

    pause مجمّد قابل للاستئناف؛ وstop نهائي لا يُستأنف بعده
    (خروج 1). --all يطبّق على كل عامل مسجل.
    """
    from lib import job_registry as _job_registry
    runs_dir = _runs_dir_of(cfg)
    actions = {"pause": _job_registry.pause_worker,
               "resume": _job_registry.resume_worker,
               "stop": _job_registry.stop_worker}
    func = actions[args.workers_cmd]
    if args.all:
        workers = sorted(_job_registry.list_workers(runs_dir))
    elif args.worker:
        workers = [args.worker]
    else:
        return out.error("حدد عاملًا بـ --worker أو كل العمال بـ --all",
                         hint="مثال: workers pause --worker doctor",
                         code=2)
    if not workers:
        out.result({"workers": []},
                   human_lines=["لا عمال مسجلون"])
        return 0
    results = []
    try:
        for worker in workers:
            results.append(func(runs_dir, worker))
    except _job_registry.JobRegistryError as e:
        return out.error(str(e), code=1)
    lines = ["%s: %s" % (r.get("worker"), r.get("state"))
             for r in results]
    out.result({"workers": results}, human_lines=lines)
    return 0


def cmd_export_job(cfg, args, out):
    """export --job ID --out DIR — حزمة تشخيصية (بند 32).

    manifest.json + job.json + نصوص (≤2000 رسالة لكلٍّ)،
    أسرار منزوعة. مجلد غير فارغ مرفوض إلا بـ--force.
    مهمة غائبة خروج 7.
    """
    from lib import diagnostic_export as _diagnostic_export
    from lib import job_registry as _job_registry
    runs_dir = _runs_dir_of(cfg)
    job = _job_registry.get_job(runs_dir, args.job)
    if job is None:
        return out.error("لا توجد مهمة بهذا المعرف: %s" % args.job,
                         code=7)
    try:
        manifest = _diagnostic_export.export_job(
            job, expand(args.out), force=args.force)
    except _diagnostic_export.ExportError as e:
        return out.error(str(e), code=1)
    out.result(manifest, human_lines=[
        "صُدّرت حزمة المهمة %s إلى %s"
        % (args.job, expand(args.out)),
        "الملفات: %s — البايتات: %s"
        % (manifest.get("total_files"), manifest.get("total_bytes")),
    ])
    return 0


def cmd_features(args, out):
    """features list|set — مفاتيح المزايا (ع7).

    list يعرض المفاتيح المعروفة بقيمها الفعالة (الغائب مميز
    عن false)؛ وset يدمج مفتاحًا واحدًا (true/false/عدد/نص).
    """
    from lib import features as _features
    if args.features_cmd == "list":
        values = _features.list_features()
        lines = ["مفاتيح المزايا: %d" % len(values)]
        for name in sorted(values):
            lines.append("- %s: %s" % (name, values[name]))
        out.result({"features": values}, human_lines=lines)
        return 0
    try:
        effective = _features.set(args.name,
                                  _parse_feature_value(args.value))
    except _features.FeatureError as e:
        return out.error(str(e), code=2)
    out.result({"name": args.name, "value": effective},
               human_lines=["المفتاح %s = %s" % (args.name, effective)])
    return 0


def cmd_triage(cfg, args, out):
    """triage inbox — فرز تعليقات/رسائل الصفحة (بند 23).

    يقرأ العناصر من ملف JSON (--file: قائمة {id, text}) أو
    نص واحد (--text). عنصر يفشل فرزُه يُؤجَّل للفحص التالي
    (status=deferred) — بلا فشل للأمر كله.
    """
    from lib import inbox_triage as _inbox_triage
    items = []
    if args.file:
        try:
            with open(expand(args.file), encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return out.error("ملف العناصر غير موجود: %s" % args.file,
                             code=7)
        except (OSError, ValueError) as e:
            return out.error("تعذر قراءة ملف العناصر: %s" % e, code=2)
        if not isinstance(raw, list):
            return out.error("ملف العناصر يجب أن يحوي قائمة",
                             code=2)
        items = raw
    elif args.text:
        items = [{"id": "cli-1", "text": args.text}]
    else:
        return out.error("مرّر عناصر الفرز: --file أو --text",
                         hint="مثال: triage inbox --text «مرحبًا»",
                         code=2)
    for item in items:
        if (not isinstance(item, dict)
                or not isinstance(item.get("text"), str)):
            return out.error("كل عنصر يحتاج {id, text} نصًا",
                             code=2)
    try:
        results = _inbox_triage.triage(items)
    except Exception as e:
        return out.error("فشل الفرز: %s" % e, code=1)
    deferred = sum(1 for r in results
                   if r.get("status") == "deferred")
    lines = ["فُرز %d عنصرًا — مؤجل: %d" % (len(results), deferred)]
    for r in results:
        lines.append("- %s: %s" % (r.get("id"),
                                   r.get("status") or "؟"))
    out.result({"items": results, "count": len(results),
                "deferred": deferred},
               human_lines=lines)
    return 0


def cmd_recipe(cfg, args, out):
    """recipe save|run|list — وصفات خطوات متكررة (بند 30).

    save يقبل --step مكررًا بصيغة «الاسم: الأمر...»؛ وrun
    ينفّذ الخطوات بالترتيب بلا نموذج (--dry-run يسرد فقط)؛
    وlist يسرد الوصفات المحفوظة.
    """
    from lib import recipes as _recipes
    recipes_dir = (expand(args.dir) if getattr(args, "dir", None)
                   else os.path.join(STUDIO_DIR, "recipes"))
    if args.recipe_cmd == "list":
        found = _recipes.list_recipes(recipes_dir)
        lines = ["الوصفات: %d" % len(found)]
        for recipe in found:
            lines.append("- %s (%d خطوات)"
                         % (recipe.get("name"), recipe.get("steps")))
        out.result({"recipes": found, "count": len(found)},
                   human_lines=lines)
        return 0
    if args.recipe_cmd == "save":
        try:
            steps = [_parse_recipe_step(s) for s in args.step or []]
        except ValueError as e:
            return out.error(str(e), code=2)
        if not steps:
            return out.error("الوصفة تحتاج خطوة واحدة على الأقل "
                             "(--step «الاسم: الأمر...»)",
                             code=2)
        try:
            path = _recipes.save_recipe(
                recipes_dir, args.name, args.description or "",
                steps, overwrite=args.force)
        except _recipes.RecipeError as e:
            return out.error(str(e), code=2)
        out.result({"recipe": args.name, "path": path, "steps": steps},
                   human_lines=["حُفظت الوصفة «%s» في %s"
                                % (args.name, path)])
        return 0
    try:
        report = _recipes.run_recipe(recipes_dir, args.name,
                                     dry_run=args.dry_run)
    except _recipes.RecipeError as e:
        return out.error(str(e), code=7)
    lines = ["الوصفة «%s»: %s" % (report.get("recipe"),
                                   "نجحت" if report.get("ok")
                                   else "فشلت")]
    for step in report.get("steps") or []:
        lines.append("- %s: %s" % (step.get("name"),
                                   step.get("returncode")))
    out.result(report, human_lines=lines)
    return 0 if report.get("ok") else 1


def cmd_webhook(cfg, args, out):
    """webhook serve|token — مستقبل webhooks (ع18).

    serve يرفض البدء ما لم تكن راية webhookReceiver=True
    (خروج 5 + كيف تُفعَّل)؛ وtoken يصدر رمزًا يُعرض مرة
    واحدة فقط (يُحفظ تجزئته لا نصه).
    """
    from lib import webhook_receiver as _webhook
    if args.webhook_cmd == "token":
        path = (expand(args.path) if getattr(args, "path", None)
                else os.path.join(os.path.expanduser("~"),
                                  ".qisas-studio",
                                  "webhook-token.json"))
        token = _webhook.issue_token(path)
        # الرمز يُعرض مرة واحدة حرفيًا — يُطبع مباشرة بلا
        # تنقيح (تنقيح المخرجات قد يقنّعه فيفسد نسخه).
        if bool(getattr(args, "json", False)):
            print(json.dumps(
                {"ok": True, "token": token, "token_path": path,
                 "note": "يُعرض مرة واحدة — احفظه الآن"},
                ensure_ascii=False))
        else:
            print("رمز webhook (يُعرض مرة واحدة — احفظه الآن):")
            print(token)
            print("ملف التجزئة: %s" % path)
        return 0
    if not _webhook.is_enabled():
        return out.error(_webhook.enable_hint(),
                         hint="studio.py features set "
                              "webhookReceiver true",
                         code=5)
    try:
        receiver = _webhook.serve(host=args.host, port=args.port)
    except _webhook.WebhookError as e:
        return out.error(str(e), code=1)
    except OSError as e:
        import errno as _errno
        code = 6 if e.errno == _errno.EADDRINUSE else 1
        return out.error("تعذر تشغيل مستقبل webhooks: %s" % e,
                         code=code)
    if bool(getattr(args, "json", False)):
        out.result({"listening": True, "host": args.host,
                    "port": args.port})
    else:
        print("مستقبل webhooks يعمل على %s:%d — أوقف بـ Ctrl-C"
              % (args.host, args.port))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        receiver.stop()
        return 130


def cmd_setup(args, out):
    """setup — إعداد أول تشغيل (بند 26).

    يسجّل تاريخ أول تشغيل مرة واحدة؛ وإعادة التشغيل ترجع
    التقرير نفسه بلا أي كتابة.
    """
    from lib import license as _license
    report = _license.first_run_setup()
    lines = _license.first_run_lines(report)
    out.result(report, human_lines=lines)
    return 0


def cmd_router_test(args, out):
    """router test — اختبار توجيه نموذج واحد (بند 5).

    استدعاء اختبار واحد بلا مصنّف (decider) فيرجع الافتراضي
    بسبب no_choice — ولا يرمي أبدًا ولا يتصل بالشبكة.
    """
    from lib import router as _router
    result = _router.route(args.task, args.role or [], "",
                           args.request or "", args.default)
    out.result(result, human_lines=[
        "النموذج: %s — الجهد: %s — المصدر: %s — %s"
        % (result.get("model"), result.get("effort"),
           result.get("source"), result.get("attribution")),
        "السبب: %s" % (result.get("reason") or "—"),
    ])
    return 0


def main():
    # ثنائية اللغة (الجولة v0.1.41): وصف المساعدة يتبع LANG
    # من البيئة (العربي افتراضيًا)؛ و--lang العام يغلبها.
    _help_lang = i18n_lib.detect_lang(env=os.environ)
    _desc = ("Unified production line for story videos" if _help_lang == "en"
             else "خط إنتاج موحد لفيديوهات القصص")
    _epilog = ("For Arabic help: python3 studio.py help-ar"
               if _help_lang == "en"
               else "للمساعدة بالعربية: python3 studio.py help-ar")
    ap = argparse.ArgumentParser(prog="studio",
                                 description=_desc,
                                 epilog=_epilog)
    # الجولة 8: --version يطبع الإصدار + حالة البعيد من سجل
    # المزامنة المحلي (بلا شبكة)؛ ونصه يُبنى قبل التحليل لأن
    # argparse يطبعه ويخرج فورًا.
    ap.add_argument("--version", action="version",
                    version="studio %s\n%s"
                    % (VERSION, remote_status_line()))
    # الجولة v0.1.41: --lang على مستوى التطبيق (قبل الأمر) —
    # ar (الافتراضي دائمًا) أو en؛ وبلاه تُقرأ LANG/LANGUAGE
    # ثم مفتاح lang في config.yaml.
    ap.add_argument("--lang", choices=["ar", "en"], default=None,
                    help="CLI language: ar (Arabic, default) or en "
                         "(English) — اللغة: ar (العربية، الافتراضي) "
                         "أو en (الإنجليزية)")
    # الجولة v0.1.43: --noncommercial على مستوى التطبيق (قبل الأمر) —
    # إقرار بأن هذا التشغيل استخدام شخصي غير تجاري، فيُعفى من بوابة
    # الترخيص التجاري (فترة التجربة 30 يومًا). بلا العلَم يُفترض
    # الاستخدام تجاريًا وتطبَّق البوابة على الأوامر الإنتاجية.
    ap.add_argument("--noncommercial", action="store_true",
                    help="هذا التشغيل استخدام شخصي غير تجاري — يُعفى "
                         "من بوابة الترخيص التجاري (PolyForm "
                         "Noncommercial: الشخصي مجاني دائمًا)")
    # الجولة v0.1.63 (ع2): رايتا الجذر --json و--quiet — تمرران
    # إلى Output في كل الأوامر الجديدة (وثيقة JSON واحدة على
    # stdout عند --json، وإسقاط التقدّم عند --quiet).
    ap.add_argument("--json", action="store_true",
                    help="اطبع نتيجة الأمر JSON واحدًا على stdout "
                         "(بدل السطور البشرية العربية)")
    ap.add_argument("--quiet", action="store_true",
                    help="أسقط سطور التقدّم على stderr")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="فحص حالة الطبقات الثلاث")
    sub.add_parser("version",
                   help="اطبع إصدار studio وحالة البعيد (بلا شبكة)")
    sub.add_parser("license",
                   help="حالة الترخيص وفترة التجربة (قراءة فقط)")
    sub.add_parser("help-ar", help="مساعدة عربية — كل أمر ووظيفته ومثال عليه")
    p = sub.add_parser("doctor", help="فحص بيئة studio (PASS/FAIL صادق)")
    p.add_argument("--fix", action="store_true",
                   help="أنشئ config.yaml من المثال إن غاب")
    p.add_argument("--accounts", action="store_true",
                   help="أضف فحوصات الحسابات: فيسبوك/يوتيوب/Veo/"
                        "TikTok/Instagram (قراءة فقط)")
    p.add_argument("--llm", action="store_true",
                   help="أضف فحوصات سلسلة LLM: بوابة OmniRoute + "
                        "مساعد Gemini (قراءة فقط)")
    # الجولة v0.1.63 (ع20): --json يرجع تقرير ع20 ورمز خروج 7
    # عند أي FAIL. الافتراضي SUPPRESS حتى لا يمحو قيمة راية
    # الجذر --json حين تُمرَّر قبل الأمر.
    p.add_argument("--json", action="store_true",
                   default=argparse.SUPPRESS,
                   help="اطبع التقرير JSON: {ok, problems, warnings, "
                        "checks:[{id, status, message, fix}]}")
    sub.add_parser("llm-status",
                   help="حالة مزودي الذكاء: السلسلة + التهدئة + "
                        "عدادات اليوم (قراءة فقط)")
    p = sub.add_parser("debug-config",
                       help="الإعداد الفعّال ومصدر كل قيمة (قراءة فقط)")
    p.add_argument("--profile", default=None,
                   help="اسم البروفايل: render أو publish أو review")
    p.add_argument("--set", action="append", default=[],
                   metavar="KEY=VALUE",
                   help="تجاوز من سطر الأوامر (مثال: --set effort=high)")
    sub.add_parser("protect",
                   help="فحص حماية المشروع: سلامة + صلاحيات + أسرار + "
                        "نسخة احتياطية (قراءة فقط)")
    p = sub.add_parser("check", help="فحص جودة فيديو قبل النشر (PASS/FAIL)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--long", action="store_true",
                   help="فيديو طويل أفقي 1280×720 (8–12 دقيقة)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON بدل النص العربي")
    p.add_argument("--captions", metavar="DIR",
                   help="مجلد ملفات ASS للكابشنات — دقّق تشكيلها "
                        "العربي مع فحص الفيديو")
    p.add_argument("--avatar-image", metavar="FILE",
                   help="صورة مرجع الأفاتار — قارن نسبة أبعادها "
                        "بنسبة الفيديو (تحذير فقط)")
    p.add_argument("--aspect-policy",
                   choices=["native", "crop", "pad", "rotate"],
                   default="native",
                   help="سياسة نسبة الأبعاد مع --avatar-image "
                        "(الافتراضي: native)")
    p = sub.add_parser("manifest",
                       help="ولّد بيان مصدر لفيديو موجود (مصدر يدوي)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--title", help="عنوان الفيديو (افتراضي: اسم الملف)")
    p.add_argument("--hook", default="", help="هوك الفيديو")
    p.add_argument("--story", default="", help="نص القصة")
    p = sub.add_parser("avatar-job",
                       help="تحقق من وظيفة أفاتار ناطق (JSON) أو اطبع "
                            "مثالًا أو اعرض ملفات العتاد")
    p.add_argument("--validate", metavar="FILE",
                   help="ملف وظيفة JSON للتحقق منه")
    p.add_argument("--profile",
                   help="ملف عتاد للأعلام (افتراضي: من الوظيفة)")
    p.add_argument("--template", action="store_true",
                   help="اطبع وظيفة مثال JSON")
    p.add_argument("--scene-type",
                   choices=["narration", "dialogue", "singing"],
                   default="narration",
                   help="نوع مشهد المثال (مع --template)")
    p.add_argument("--list-profiles", action="store_true",
                   help="اعرض ملفات العتاد الثلاثة + أعلامها")
    p = sub.add_parser("fix-audio",
                       help="إصلاح فجوات الصمت في فيديو (ضجيج وردي + "
                            "صوت المشاهد الأصلي)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--scene-audio", action="append", default=[],
                   help="ملف صوت مشهد أصلي (يُكرَّر، تُدمج بالترتيب)")
    p.add_argument("--out", help="ملف الفيديو الناتج (الافتراضي: "
                                 "<الاسم>-fixed.mp4 بجانب الأصلي)")
    p.add_argument("--denoise", action="store_true",
                   help="أزل ضجيج الخلفية بعد الإصلاح (فلتر afftdn)")
    p.add_argument("--loudnorm", action="store_true",
                   help="طبّع الجهارة إلى -16 LUFS بعد الإصلاح (loudnorm)")
    p = sub.add_parser("grade",
                       help="تدرج لوني على فيديو بـpreset جاهز (lut3d)")
    p.add_argument("--video", help="ملف الفيديو mp4 "
                                    "(مطلوب إلا مع --list-presets)")
    p.add_argument("--preset",
                   choices=sorted(lut_grade_lib.PRESETS),
                   help="الـpreset: warm (دافئ ذهبي — هوية الصفحة) أو "
                        "vivid أو cinematic أو soft")
    p.add_argument("--out", help="ملف الفيديو الناتج (الافتراضي: "
                                "<الاسم>-<preset>.mp4 بجانب الأصلي)")
    p.add_argument("--list-presets", action="store_true",
                   help="اطبع الـpresets المتاحة فقط")
    p = sub.add_parser("srt-ass",
                       help="حوّل ملف SRT إلى ASS بنمط subs/ (نفس الخط "
                            "والمحاذاة)")
    p.add_argument("--srt", required=True, help="ملف SRT المصدر")
    p.add_argument("--out", required=True, help="ملف ASS الناتج")
    p.add_argument("--font-size", type=int, default=52,
                   help="حجم الخط في ASS (الافتراضي: 52)")
    p = sub.add_parser("init", help="معالج إعداد تفاعلي — يكتب config.yaml")
    p.add_argument("--page-id", help="معرّف صفحة فيسبوك")
    p.add_argument("--channel-id", help="معرّف قناة يوتيوب")
    p.add_argument("--voice", choices=["piper", "gtts", "supertonic-M1"],
                   help="صوت الراوي: piper (الرجل، الافتراضي) أو gtts أو "
                        "supertonic-M1 (صوت ثانٍ اختياري)")
    p.add_argument("--morning", help="موعد النشر الصباحي HH:MM")
    p.add_argument("--evening", help="موعد النشر المسائي HH:MM")
    p.add_argument("--queue-file", help="ملف طابور القصص")
    p.add_argument("--config",
                   help="مسار config.yaml (الافتراضي: مجلد studio)")
    p.add_argument("--force", action="store_true",
                   help="اكتب فوق config.yaml موجود بلا سؤال")
    p.add_argument("--page-name", help="اسم الصفحة (يُحفظ في identity.page_name)")
    p.add_argument("--logo-file", help="ملف الشعار PNG (يُنسخ إلى assets/qisas-logo-badge.png)")
    p.add_argument("--payment-number", help="رقم الدفع فودافون كاش (11 رقمًا يبدأ بـ 01)")
    p.add_argument("--check-only", action="store_true",
                   help="تحقق من الربط فقط بلا كتابة أي ملف")
    p = sub.add_parser("publish", help="نشر فيديو على فيسبوك ويوتيوب")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--title", required=True, help="عنوان الفيديو")
    p.add_argument("--caption", default="",
                   help="نص الكابشن (تُضاف الهاشتاجات تلقائيًا)")
    p.add_argument("--thumbnail", help="ملف الصورة المصغرة")
    p.add_argument("--platforms", default="facebook,youtube",
                   help="منصات مفصولة بفاصلة — المقبول: facebook, "
                        "youtube, tiktok, instagram (الافتراضي: "
                        "facebook,youtube)؛ وللربط: أمري tiktok-auth "
                        "و instagram-auth")
    p.add_argument("--preflight", action="store_true",
                   help="فحص ما قبل النشر على يوتيوب فقط: صلاحية "
                        "التوكن + إنشاء جلسة رفع قابلة للاستئناف بلا "
                        "إرسال أي بايت من الفيديو وبلا نشر — فإن فشل "
                        "بخطأ SSL (بروكسي الـVM) يطبع رسالة الرفع "
                        "اليدوي من YouTube Studio")
    p.add_argument("--page-id", help="معرّف صفحة فيسبوك (أو من config.yaml)")
    p.add_argument("--schedule",
                   help="موعد النشر المجدول بصيغة YYYY-MM-DD HH:MM "
                        "بتوقيت Africa/Cairo (مثال: 2026-11-23 19:00)؛ "
                        "أو Unix (ثوانٍ) للتوافق مع القديم — للجدولة "
                        "بدل النشر الآن")
    p.add_argument("--privacy", choices=["public", "unlisted", "private"],
                   help="خصوصية يوتيوب (الافتراضي من الإعداد: public)")
    p.add_argument("--tags",
                   help="وسوم يوتيوب مفصولة بفاصلة (الافتراضي: وسوم الصفحة)")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع الحمولة الدقيقة دون نشر أي شيء")
    p.add_argument("--skip-check", action="store_true",
                   help="تجاوز فحص الجودة المسبق (غير مستحسن)")
    p.add_argument("--skip-caption-check", action="store_true",
                   help="تجاوز فحص امتثال الكابشن (غير مستحسن — "
                        "بوابة المتابعة/التعليق ممنوعة)")
    p.add_argument("--allow-missing-manifest", action="store_true",
                   help="تجاوز بوابة بيان المصدر لفيديو جديد بلا بيان "
                        "(غير مستحسن — ولّد البيان بأمر manifest أولًا)")
    p.add_argument("--generate-meta", action="store_true",
                   help="ولّد العنوان والوصف والوسوم من نص القصة عبر "
                        "سلسلة LLM (مع بديل محلي بلا شبكة) — القيم "
                        "الصريحة --caption/--tags تغلب المولّدة")
    p.add_argument("--ai-voice", action="store_true",
                   help="ألحق سطر «صوت مولّد بالذكاء الاصطناعي» بالكابشن "
                        "والوصف (إلزامي لفيديوهات Supertonic — يُكتشف "
                        "من بيان الفيديو تلقائيًا أيضًا)")
    p.add_argument("--part", type=int, default=1,
                   help="رقم الجزء لعنوان مولّد (مع --generate-meta، "
                        "افتراضي 1)")
    p.add_argument("--parts", type=int, default=1,
                   help="عدد أجزاء القصة لعنوان مولّد (مع "
                        "--generate-meta، افتراضي 1)")
    p = sub.add_parser("youtube-auth",
                       help="تبادل OAuth ليوتيوب لمرة واحدة (يفتح المتصفح)")
    p.add_argument("--client-secrets",
                   help="ملف client_secrets.json (أو من config.yaml)")
    p.add_argument("--token",
                   help="مسار حفظ التوكن (أو من config.yaml)")
    p = sub.add_parser("youtube-reauth",
                       help="إعادة الموافقة على يوتيوب (التوكن في وضع "
                            "الاختبار ينتهي بعد 7 أيام)")
    p.add_argument("--client-secrets",
                   help="ملف client_secrets.json (أو من config.yaml)")
    p.add_argument("--token",
                   help="مسار حفظ التوكن (أو من config.yaml)")
    p = sub.add_parser("script", help="توليد هوك/كابشن عبر OmniRoute")
    p.add_argument("--story", required=True)
    p.add_argument("--allow-fallback", action="store_true")
    p = sub.add_parser("produce", help="تجهيز أصول مشروع OpenMontage")
    p.add_argument("--project", required=True)
    p.add_argument("--run", dest="run_id")
    p = sub.add_parser("assemble", help="تجميع وتصدير (Concat افتراضيًا)")
    p.add_argument("--run", dest="run_id", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--backend", default="concat",
                   choices=["concat", "headless", "mlt", "openreel"],
                   help="خلفية التجميع: concat (افتراضي) أو headless أو mlt "
                        "أو openreel (أبطأ ~3× بلا GPU)")
    p.add_argument("--grade", choices=sorted(lut_grade_lib.PRESETS),
                   help="تدرج لوني بعد الريندر وقبل الشعار: warm/vivid/"
                        "cinematic/soft")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p.add_argument("--no-title", action="store_true",
                   help="لا تحرق عنوان الهوك في Concat — للقصص التي "
                        "عنوانها هو الهوك نفسه، فيُحرق لاحقًا مرة "
                        "واحدة بـhook-title بدل تضاعفه (جولة v0.1.62)")
    p.add_argument("--cards-dir",
                   help="مجلد بطاقات الاقتباس (ibra/hikma/mawiza) "
                        "لإلحاقها ختامية 3×3 ثوانٍ")
    p.add_argument("--size",
                   help="مقاس الفيديو WxH — الافتراضي 720x1280 (عمودي)؛ "
                        "1280x720 للأفقي (الفيديو الطويل الأسبوعي)")
    p.add_argument("--sfx", action="append",
                   help="مؤثر صوتي عند ثانية معينة بصيغة NAME@SECONDS "
                        "(مثال: whoosh@2.5) — قابل للتكرار")
    p.add_argument("--overlay", action="append",
                   choices=["burn", "grain"],
                   help="طبقة بصرية فوق الفيديو: burn أو grain — "
                        "قابلة للتكرار")
    p.add_argument("--assets-dir",
                   help="مجلد أصول بديل (يتجاوز QISAS_ASSETS_DIR "
                        "والمجلد الافتراضي)")
    p = sub.add_parser("clean-audio",
                         help="قص صمت الصوت الخام عبر Auto-Editor "
                              "(أبدًا على السرد النهائي)")
    p.add_argument("--input", required=True, help="ملف الصوت الخام")
    p.add_argument("--out", required=True, help="ملف الصوت النظيف")
    p.add_argument("--threshold", type=float, default=0.02,
                   help="عتبة الصوت للقص (0.02 افتراضيًا)")
    p.add_argument("--margin", type=float, default=0.2,
                   help="هامش حول المقاطع الصاخبة بالثواني (0.2)")
    p.add_argument("--force", action="store_true",
                   help="اسمح بتنظيف ملف سرد نهائي (غير مستحسن)")
    p = sub.add_parser("fx",
                         help="تركيبة MoviePy: Ken Burns + نص عربي متحرك "
                              "(من بيئة .venv-moviepy)")
    p.add_argument("--image", required=True, help="صورة الخلفية")
    p.add_argument("--out", required=True, help="ملف mp4 الناتج")
    p.add_argument("--duration", type=float, default=5.0,
                   help="مدة المقطع بالثواني (5 افتراضيًا)")
    p.add_argument("--text", default=None,
                   help="نص عربي متحرك (اختياري)")
    p.add_argument("--audio", default=None,
                   help="ملف صوت (اختياري)")
    p.add_argument("--zoom-to", type=float, default=1.15,
                   help="التكبير النهائي (1.15 افتراضيًا)")
    p.add_argument("--fontsize", type=int, default=58,
                   help="حجم خط النص (58 افتراضيًا)")
    p = sub.add_parser("karaoke-ass",
                         help="كابشنات كاريوكي كلمة-بكلمة (منطق Capite "
                              "مُعاد تنفيذه — من بيئة .venv-whisper)")
    p.add_argument("--audio", required=True, help="ملف الصوت")
    p.add_argument("--out", required=True, help="ملف ASS الناتج")
    p.add_argument("--model", default="small",
                   help="موديل faster-whisper (small افتراضيًا)")
    p.add_argument("--max-chars", type=int, default=28,
                   help="أقصى حروف في السطر (28 افتراضيًا)")
    p.add_argument("--lang", choices=["ar", "en"], default=None,
                   dest="cmd_lang",
                   help="لغة الكابشن: ar (العربية، الافتراضي — مسار "
                        "الكاريوكي) أو en (الإنجليزية — مسار لاتيني "
                        "LTR). " + EN_VOICE_LICENSE_NOTE)
    p = sub.add_parser("trim",
                         help="قص مقطع بلا إعادة ترميز (تنظيف Veo قبل "
                              "التجميع)")
    p.add_argument("--input", required=True, help="ملف الفيديو")
    p.add_argument("--out", required=True, help="ملف الفيديو المقصوص")
    p.add_argument("--start", type=float, default=0.0,
                   help="زمن البداية بالثواني (0 افتراضيًا)")
    p.add_argument("--end", type=float, default=None,
                   help="زمن النهاية بالثواني")
    p.add_argument("--duration", type=float, default=None,
                   help="مدة القص بالثواني (بديل لـ --end)")
    p.add_argument("--exact", action="store_true",
                   help="قطع دقيق بالإطار بإعادة ترميز (أبطأ)")
    p = sub.add_parser("thumbnail",
                       help="توليد صورة مصغرة 720×1280 (أو 1280×720 مع --long)")
    p.add_argument("--video", help="مسار الفيديو (أو استخدم --run)")
    p.add_argument("--run", dest="run_id",
                   help="معرّف تشغيل سابق — يأخذ الفيديو والهوك منه")
    p.add_argument("--hook", help="نص الهوك الصادم أعلى الصورة")
    p.add_argument("--time", type=float,
                   help="ثانية اللقطة (الافتراضي: 40%% من مدة الفيديو)")
    p.add_argument("--out", help="مسار الصورة (الافتراضي: videos_dir)")
    p.add_argument("--long", action="store_true",
                   help="صورة أفقية 1280×720 للفيديو الطويل")
    p.add_argument("--size",
                   help="مقاس الصورة WxH — يتجاوز --long إن أُعطي")
    p = sub.add_parser("whisper-ass",
                         help="كابشنات ASS من faster-whisper (تجريبي)")
    p.add_argument("--audio", required=True,
                   help="ملف السرد (wav، أو أي صوت عبر ffmpeg)")
    p.add_argument("--out", required=True, help="مسار ملف ASS الناتج")
    p.add_argument("--model", default="small",
                   help="موديل whisper: tiny/base/small (الافتراضي: small)")
    p.add_argument("--max-words", type=int, default=6,
                   help="أقصى كلمات في العبارة (الافتراضي: 6)")
    p.add_argument("--max-gap", type=float, default=0.6,
                   help="فجوة الصمت التي تفصل عبارتين بالثواني (0.6)")
    p.add_argument("--font-size", type=int, default=52,
                   help="حجم الخط في ASS (الافتراضي: 52)")
    p = sub.add_parser("run", help="خط الإنتاج الكامل (أو --demo للتجربة)")
    p.add_argument("--story",
                   help="اسم القصة (غير مطلوب مع --demo)")
    p.add_argument("--project",
                   help="اسم مشروع OpenMontage (غير مطلوب مع --demo)")
    p.add_argument("--out",
                   help="مسار الفيديو الناتج (افتراضي للتجربة: videos_dir)")
    p.add_argument("--demo", action="store_true",
                   help="القصة التجريبية المدمجة — مسار مجاني فقط، "
                        "بلا Veo وبلا مفاتيح")
    p.add_argument("--allow-fallback", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="يطبع الخطوات فقط دون تنفيذ")
    p.add_argument("--backend", default="concat",
                   choices=["concat", "headless", "mlt", "openreel"],
                   help="خلفية التجميع: concat (افتراضي) أو headless أو mlt "
                        "أو openreel (أبطأ ~3× بلا GPU)")
    p.add_argument("--grade", choices=sorted(lut_grade_lib.PRESETS),
                   help="تدرج لوني بعد الريندر وقبل الشعار: warm/vivid/"
                        "cinematic/soft")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p.add_argument("--cards-dir",
                   help="مجلد بطاقات الاقتباس (ibra/hikma/mawiza) "
                        "لإلحاقها ختامية 3×3 ثوانٍ")
    p.add_argument("--size",
                   help="مقاس الفيديو WxH — الافتراضي 720x1280 (عمودي)؛ "
                        "1280x720 للأفقي (الفيديو الطويل الأسبوعي)")
    p.add_argument("--resume",
                   help="استئناف تشغيل منقطع بمعرّفه (run-...) من آخر "
                        "نقطة تفتيش — يُتخطى ما اكتمل ويُعاد ما تبقى فقط")
    p.add_argument("--lang", choices=["ar", "en"], default=None,
                   dest="cmd_lang",
                   help="لغة القصة: ar (العربية، الافتراضي) أو en "
                        "(الإنجليزية). " + EN_VOICE_LICENSE_NOTE)
    p.add_argument("--voice", default=None,
                   help="صوت الراوي: piper (الرجل) أو gtts أو "
                        "supertonic-M1 — أو اسم موديل Piper رجالي من "
                        "السجل (مثال en_US-ryan-medium للإنجليزية)؛ "
                        "وأي اسم غير معروف أو غير ذكوري يُرفض")
    p = sub.add_parser("quick",
                       help="أمر واحد: عنوان قصة ← فيديو قصير كامل "
                            "(بلا أسئلة — بلا نشر تلقائي)")
    p.add_argument("title", help="عنوان القصة (مثال: \"النجار الأمين\")")
    p.add_argument("--out", help="مسار الفيديو الناتج (افتراضي: videos_dir)")
    p.add_argument("--lang", choices=["ar", "en"], default=None,
                   dest="cmd_lang",
                   help="لغة القصة: ar (العربية، الافتراضي) أو en "
                        "(الإنجليزية). " + EN_VOICE_LICENSE_NOTE)
    p.add_argument("--voice", default=None,
                   help="صوت الراوي: piper (الرجل) أو gtts أو "
                        "supertonic-M1 — أو اسم موديل Piper رجالي من "
                        "السجل (مثال en_US-ryan-medium للإنجليزية)؛ "
                        "وأي اسم غير معروف أو غير ذكوري يُرفض")
    p.add_argument("--allow-fallback", action="store_true",
                   help="اسمح بقصة مدمجة من القوالب عند فشل LLM "
                        "(بدونه: يتوقف quick عند الفشل)")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع الخطة فقط دون إنتاج")
    p.add_argument("--publish", action="store_true",
                   help="انشر الفيديو بعد إنتاجه (بدونه: بلا نشر — "
                        "انشر لاحقًا بأمر publish الصريح)")
    p = sub.add_parser("expand-motion-prompts",
                       help="وسّع موجّهات حركة قصيرة من JSON إلى "
                            "موجّهات مفصلة (أمر صريح — بلا إنتاج)")
    p.add_argument("--prompts", required=True,
                   help="ملف JSON بقائمة موجّهات "
                        "([{\"id\"?, \"prompt\"}])")
    p.add_argument("--out", required=True,
                   help="ملف JSON الناتج بقائمة الموجّهات الموسّعة")
    p = sub.add_parser("seo-check",
                       help="فحص SEO قبل النشر: عنوان + وصف + وسوم "
                            "(خروج 1 عند ملاحظات)")
    p.add_argument("--title", required=True,
                   help="عنوان الفيديو")
    p.add_argument("--description", required=True,
                   help="وصف الفيديو (أول سطرين هما المقتطف الذي "
                        "يراه الباحث)")
    p.add_argument("--tags", required=True,
                   help="وسوم مفصولة بفواصل "
                        "(مثال: \"قصص وعبر،قصص واقعية\")")
    p.add_argument("--story-file",
                   help="ملف نص القصة (اختياري — لاشتقاق "
                        "الاستعلامات وفحص صلة الوسوم)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p = sub.add_parser("title-lint",
                       help="دقّق عنوانًا ومصغرة كوحدة واحدة (أو رتّب "
                            "عناوين من ملف)")
    p.add_argument("--title",
                   help="عنوان واحد لتدقيقه")
    p.add_argument("--thumb",
                   help="نص المصغرة (اختياري — لا يكرّر العنوان)")
    p.add_argument("--titles-file",
                   help="ملف عناوين (سطر لكل عنوان) لترتيبها "
                        "بالأقل مشكلات")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p = sub.add_parser("hook-score",
                       help="قيّم هوكًا (أو هوكات من ملف) ورتّبها — "
                            "أفضل اثنين مميزان")
    p.add_argument("--hook",
                   help="هوك واحد لتقييمه")
    p.add_argument("--hook-file",
                   help="ملف هوكات (سطر لكل هوك) لتقييمها وترتيبها")
    p.add_argument("--story-file",
                   help="ملف نص القصة (اختياري — لقياس العائد داخل "
                        "المقطع)")
    p.add_argument("--json", action="store_true",
                   help="اطبع اللوحة JSON خالصًا")
    p = sub.add_parser("viral-rank",
                       help="رتّب فيديوهات بمضاعف كل قناة على وسيطها "
                            "الخاص")
    p.add_argument("--videos-file", required=True,
                   help="ملف JSON بقائمة "
                        "[{channel, title, views, url?, duration?}]")
    p.add_argument("--top", type=int, default=5,
                   help="عدد الأوائل المطلوب (الافتراضي 5)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("retention-read",
                       help="اقرأ تصدير احتفاظ Studio (CSV) وشخّص "
                            "أكبر تسرب")
    p.add_argument("--csv", required=True,
                   help="ملف CSV لتصدير الاحتفاظ من YouTube Studio")
    p.add_argument("--duration", type=float, default=None,
                   help="مدة الفيديو بالثواني (اختياري — تُستنتج من "
                        "آخر نقطة)")
    p.add_argument("--transcript",
                   help="ملف نص مكتوب (SRT أو ASS) لطباعة ما كان "
                        "يُقال عند المنحدرات")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("channel-audit",
                       help="دقّق القناة وينتهِ في إصلاح واحد (آخر 10 "
                            "عناوين + هوكات + إيقاع + احتفاظ)")
    p.add_argument("--titles-file", required=True,
                   help="ملف فيه آخر 10 عناوين (عنوان في كل سطر، "
                        "الأحدث أولًا)")
    p.add_argument("--hooks-file",
                   help="ملف فيه الأسطر الأولى لأحدث الفيديوهات "
                        "(سطر لكل فيديو)")
    p.add_argument("--thumb-texts-file",
                   help="ملف فيه نصوص المصغرات (سطر لكل عنوان؛ سطر "
                        "فارغ يعني بلا نص)")
    p.add_argument("--dates-file",
                   help="ملف فيه تواريخ الرفع YYYY-MM-DD (تاريخ في "
                        "كل سطر)")
    p.add_argument("--retention-csv",
                   help="ملف CSV لتصدير الاحتفاظ من YouTube Studio")
    p.add_argument("--duration", type=float, default=None,
                   help="مدة فيديو الاحتفاظ بالثواني (اختياري)")
    p.add_argument("--title",
                   help="عنوان أحدث فيديو لفحص SEO (مع --description "
                        "و--tags)")
    p.add_argument("--description",
                   help="وصف أحدث فيديو لفحص SEO")
    p.add_argument("--tags",
                   help="وسوم أحدث فيديو لفحص SEO (مفصولة بفواصل)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("trend-scout",
                       help="كشّاف ترندات أسبوعي: رتّب فيديوهات عامة "
                            "واقترح إدخالات طابور (بلا كتابة فيه)")
    p.add_argument("--videos-file", required=True,
                   help="ملف JSON بقائمة فيديوهات عامة "
                        "[{channel, title, views?, likes?, saves?, "
                        "shares?, url?, duration?}]")
    p.add_argument("--top-n", type=int, default=5,
                   help="عدد اقتراحات الطابور المطلوبة (الافتراضي 5)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("scene-shorts",
                       help="قصّ فيديو طويل إلى أجزاء مشهدية عمودية "
                            "40–60 ثانية (مشاهد كاملة فقط)")
    p.add_argument("--video", required=True,
                   help="ملف الفيديو الطويل")
    p.add_argument("--scenes-file", required=True,
                   help="ملف JSON بحدود المشاهد "
                        "[{start, end, title?}] بالثواني")
    p.add_argument("--out",
                   help="مجلد الخرج (افتراضي: مجلد فيديو بتاريخ اليوم)")
    p.add_argument("--phrases",
                   help="ملف ASS بعبارات الفيديو الطويل (اختياري — "
                        "لهوك كل جزء وكابشناته)")
    p.add_argument("--full-hook",
                   help="هوك الفيديو الكامل (اختياري — للتقرير)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("tiktok-check",
                       help="افحص شورتًا قبل نشره على TikTok: هوك 3 "
                            "ثوانٍ + كابشن + ترند + خطة أسبوع (خروج 1 "
                            "عند ملاحظات)")
    p.add_argument("--title", required=True,
                   help="عنوان الفيديو")
    p.add_argument("--caption", required=True,
                   help="كابشن النشر")
    p.add_argument("--hook",
                   help="نص الهوك (اختياري — غيابه فشل فحص الهوك)")
    p.add_argument("--moral",
                   help="العبرة (اختياري — تُستنتج من الكابشن إن غابت)")
    p.add_argument("--story-file",
                   help="ملف نص القصة (اختياري)")
    p.add_argument("--queue-file",
                   help="ملف الطابور (اختياري — لفحص خطة الأسبوع)")
    p.add_argument("--needed", type=int, default=7,
                   help="عدد فيديوهات الأسبوع المطلوب (الافتراضي 7)")
    p.add_argument("--trend-keywords",
                   help="كلمات ترند مفصولة بفواصل (اختياري)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p = sub.add_parser("script-check",
                       help="بوابة سكريبت نصية قبل الإنتاج: هوك + عبرة "
                            "+ سؤال ختامي + مشاهد 5–7 (خروج 1 عند "
                            "ملاحظات)")
    p.add_argument("script",
                   help="ملف سكريبت JSON")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p.add_argument("--timed-phrases",
                   help="ملف JSON بعبارات موقوتة لتقدير المدة")
    p.add_argument("--narration-audio",
                   help="ملف صوت سرد (wav) لتقدير المدة")
    p.add_argument("--narration-wpm", type=float,
                   help="معدل سرد (كلمة/دقيقة) يمرره المشغّل")
    p.add_argument("--narration-duration", type=float,
                   help="مدة سرد مقاسة بالثواني يمررها المشغّل")
    p = sub.add_parser("topic-brief",
                       help="موجز بحث لموضوع قبل الكتابة: أنماط رابحة "
                            "+ هوكات ناجحة + زوايا غير مغطاة")
    p.add_argument("--input",
                   help="ملف JSON واحد {theme, candidates, "
                        "existing_titles}")
    p.add_argument("--theme",
                   help="نص الموضوع")
    p.add_argument("--candidates-file",
                   help="ملف JSON بقائمة مرشحي ترند (صيغة "
                        "trend-scout)")
    p.add_argument("--queue-file",
                   help="ملف الطابور (قراءة فقط — لعناوينه الحالية)")
    p.add_argument("--json", action="store_true",
                   help="اطبع الموجز JSON خالصًا")
    p = sub.add_parser("hook-title",
                       help="عنوان هوك كبير مكتوب أول 3 ثوانٍ على شورت "
                            "جاهز (النطاق الأوسط فقط — قرار 10:09)")
    p.add_argument("--video",
                   help="ملف فيديو الشورت الجاهز")
    p.add_argument("--title", required=True,
                   help="نص الهوك من السكريبت نفسه")
    p.add_argument("--out",
                   help="ملف الخرج (افتراضي: نفس الاسم + -hook-title)")
    p.add_argument("--json", action="store_true",
                   help="اعرض مواصفة العنوان فقط (بلا حرق)")
    p.add_argument("--force", action="store_true",
                   help="طبّق عنوان الهوك رغم وجود عنوان محروق أصلًا "
                        "في الفيديو")
    p = sub.add_parser("reliability-report",
                       help="تقرير موثوقية من سجلات تشغيل JSON "
                            "(قراءة/تشخيص فقط)")
    p.add_argument("--runs-json", required=True,
                   help="ملف JSON بقائمة سجلات تشغيل")
    p.add_argument("--window-days", type=int, default=30,
                   help="طول النافذة بالأيام (الافتراضي 30)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p = sub.add_parser("failure-classify",
                       help="صنّف نص فشل إلى بيئة/كود/خارجي/غير معروف")
    p.add_argument("--text",
                   help="نص الفشل مباشرة (أو --file)")
    p.add_argument("--file",
                   help="ملف فيه نص الفشل (أو --text)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التصنيف JSON خالصًا")
    p = sub.add_parser("incident-probe",
                       help="حقّق في حادثة من سياق JSON جاهز "
                            "(سبب جذري محتمل + فرضيات + أدلة)")
    p.add_argument("--context-json", required=True,
                   help="ملف JSON بسياق الحادثة")
    p.add_argument("--mask", action="store_true",
                   help="أخفِ الاقتباسات ونص الفشل في المخرجات")
    p.add_argument("--mapping-out",
                   help="ملف يُكتب فيه mapping الإخفاء (لا يُطبع أبدًا)")
    p.add_argument("--json", action="store_true",
                   help="اطبع التقرير JSON خالصًا")
    p = sub.add_parser("id-mask",
                       help="أخفِ معرّفات في نص (بريد/هاتف/أرقام طويلة) "
                            "أو أعد إظهارها، أو احجب الأسرار نهائيًا")
    p.add_argument("--text",
                   help="النص مباشرة (أو --file)")
    p.add_argument("--file",
                   help="ملف فيه النص (أو --text)")
    p.add_argument("--mapping-out",
                   help="ملف يُكتب فيه mapping الإخفاء (لا يُطبع أبدًا)")
    p.add_argument("--redact", action="store_true",
                   help="احجب الأسرار نهائيًا (بلا mapping ولا استرجاع)")
    p.add_argument("--unmask", action="store_true",
                   help="أعد إظهار نص مخفي (يحتاج --mapping)")
    p.add_argument("--mapping",
                   help="ملف الـmapping (مع --unmask)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("runbook-check",
                       help="افحص دفتر تشغيل (قراءة فقط — بلا أي إصلاح)")
    p.add_argument("--runbook",
                   help="اسم دفتر مدمج: env-restore أو publish-failure")
    p.add_argument("--runbook-file",
                   help="ملف دفتر JSON (بدل الاسم المدمج)")
    p.add_argument("--root", default=".",
                   help="الجذر الذي يستبدل {root} في المسارات "
                        "(الافتراضي: المجلد الحالي)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("failure-drill",
                       help="درّب على عطل اصطناعي وتحقّق من أن الكشف "
                            "يعمل (افتراضيًا كل الأعطال)")
    p.add_argument("--drill",
                   help="معرّف عطل واحد (أو --all)")
    p.add_argument("--all", action="store_true",
                   help="شغّل كل الأعطال المدمجة (الافتراضي)")
    p.add_argument("--workdir",
                   help="مجلد عمل التدريب (افتراضي: مؤقت يُنظَّف)")
    p.add_argument("--keep", action="store_true",
                   help="احتفظ بمجلد العمل المؤقت بعد التدريب")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("keyword-analyze",
                       help="حلّل كلمة مفتاحية: صعوبة ومنافسة ودرجات SERP")
    p.add_argument("--keyword",
                   help="كلمة واحدة (أو --keywords-json للدفعية)")
    p.add_argument("--metrics-json",
                   help="ملف JSON بمقاييس الكلمة: volume وcompetition "
                        "وgrowth_pct وserp")
    p.add_argument("--keywords-json",
                   help="ملف JSON بقائمة كلمات {keyword, metrics?} "
                        "للتحليل الدفعي")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("content-optimize",
                       help="قيّم محتوى ضد كلمة مفتاحية (درجة 0–100، "
                            "والنطاق الصحي 55–75)")
    p.add_argument("--title", required=True,
                   help="عنوان المحتوى")
    p.add_argument("--keyword", required=True,
                   help="الكلمة المفتاحية المستهدفة")
    p.add_argument("--body-file", required=True,
                   help="ملف فيه نص المحتوى")
    p.add_argument("--description", default="",
                   help="وصف المحتوى (اختياري)")
    p.add_argument("--phrases-json",
                   help="ملف JSON بعبارات موصى بها {phrase, used_by_top}")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("keyword-generate",
                       help="ولّد كلمات مفتاحية ذات صلة من بذرة")
    p.add_argument("--seed", required=True,
                   help="بذرة التوليد (موضوع القصة)")
    p.add_argument("--corpus-json",
                   help="ملف JSON بكلمات ذات صلة {keyword, volume?}")
    p.add_argument("--limit", type=int, default=20,
                   help="عدد النتائج المطلوبة (1–100، الافتراضي 20)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("micro-niche",
                       help="ابحث عن تخصصات دقيقة قليلة المنافسة")
    p.add_argument("--niches-json", required=True,
                   help="ملف JSON بتخصصات {name, keywords} (أو قاموس "
                        "فيه niches ومكتبة library)")
    p.add_argument("--library-json",
                   help="ملف JSON بمكتبة قصصنا {title, topic?} (اختياري)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("page-analyze",
                       help="حلّل صفحة/فيديو (عنوان + وصف + وسوم) "
                            "واقترح تحسينات")
    p.add_argument("--page-json", required=True,
                   help="ملف JSON بالصفحة {title, description, tags, "
                        "url?, duration?, keyword?}")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("fresh-keywords",
                       help="رتّب كلمات رائجة اليوم من بيانات ترند")
    p.add_argument("--trends-json", required=True,
                   help="ملف JSON بترندات {keyword, growth_pct?, "
                        "volume?, date, source?}")
    p.add_argument("--days", type=int, default=7,
                   help="نافذة الحداثة بالأيام (الافتراضي 7)")
    p.add_argument("--today",
                   help="تاريخ مرجعي بصيغة YYYY-MM-DD (افتراضيًا اليوم)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("topical-authority",
                       help="قس سلطة مكتبة القصص الموضوعية وحدّد فجواتها")
    p.add_argument("--library-json", required=True,
                   help="ملف JSON بمكتبة قصصنا {title, topic?}")
    p.add_argument("--topics-json",
                   help="ملف JSON بخريطة مواضيع مخصصة (اختياري)")
    p.add_argument("--json", action="store_true",
                   help="اطبع النتيجة JSON خالصًا")
    p = sub.add_parser("request", help="اطلب فيديو بنص عادي — قصة أو موضوع")
    p.add_argument("text", nargs="?",
                   help="نص القصة أو الموضوع (أو استخدم --text-file)")
    p.add_argument("--text-file",
                   help="ملف فيه نص الطلب (بدل الوسيط)")
    p.add_argument("--out", help="مسار الفيديو الناتج")
    p.add_argument("--project",
                   help="اسم مشروع OpenMontage الجاهز (اختياري — بلا "
                        "مشروع تُحفظ القصة في الطابور بحالة queued)")
    p.add_argument("--allow-fallback", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="يطبع الخطة فقط دون حفظ أو إنتاج")
    p = sub.add_parser("long-video",
                       help="فيديو طويل أفقي 1280×720 من عدة قصص (8–12 دقيقة)")
    p.add_argument("--out", required=True,
                   help="مسار الفيديو الطويل الناتج")
    p.add_argument("--title",
                   help="عنوان الفيديو الطويل (أو من ملف الفصول)")
    p.add_argument("--hook",
                   help="هوك المقدمة (الافتراضي: العنوان)")
    p.add_argument("--intro",
                   help="نص سرد المقدمة (الافتراضي: الهوك)")
    p.add_argument("--outro",
                   help="نص سرد الخاتمة (الافتراضي: دعوة اشتراك)")
    p.add_argument("--story", action="append", default=[],
                   help="قصة من الطابور بمشروع OpenMontage جاهز (تُكرَّر)")
    p.add_argument("--project", action="append", default=[],
                   help="اسم مشروع OpenMontage (يُكرَّر)")
    p.add_argument("--run", dest="run_id", action="append", default=[],
                   help="معرّف تشغيل سابق كمصدر فصل (يُكرَّر)")
    p.add_argument("--chapter-dir", action="append", default=[],
                   help="مجلد فصل مُعدّ (يُكرَّر)")
    p.add_argument("--chapter-text", action="append", default=[],
                   help="عنوان فصل نصي (يُكرَّر، مع --text-file)")
    p.add_argument("--text-file", action="append", default=[],
                   help="ملف نص فصل نصي (يُكرَّر، مع --chapter-text)")
    p.add_argument("--cover", action="append", default=[],
                   help="صورة غلاف فصل نصي (تُكرَّر، مع --chapter-text)")
    p.add_argument("--moral", action="append", default=[],
                   help="عبرة فصل نصي (تُكرَّر، مع --chapter-text)")
    p.add_argument("--chapters-file",
                   help="ملف JSON بمواصفات الفصول (يُدمج مع خيارات CLI)")
    p.add_argument("--music",
                   help="ملف موسيقى خلفية (اختياري — تُخفض تلقائيًا)")
    p.add_argument("--auto-week", action="store_true",
                   help="اختر قصص الأسبوع المنشورة من الطابور تلقائيًا "
                        "بدل مصادر فصول يدوية")
    p.add_argument("--since",
                   help="بداية نافذة الأسبوع بصيغة YYYY-MM-DD "
                        "(الافتراضي: قبل 6 أيام) — مع --auto-week")
    p.add_argument("--queue-file",
                   help="ملف طابور بديل (الافتراضي من config.yaml) — "
                        "مع --auto-week")
    p.add_argument("--voice", default=None,
                   help="صوت السرد: piper (الراوي الرجل) أو gtts أو "
                        "supertonic-M1 (صوت ثانٍ اختياري) — أو اسم موديل "
                        "Piper رجالي من السجل (مثال en_US-ryan-medium "
                        "للإنجليزية)؛ والافتراضي من الإعداد "
                        "(narration.voice)؛ وأي اسم غير معروف أو غير "
                        "ذكوري يُرفض")
    p.add_argument("--lang", choices=["ar", "en"], default=None,
                   dest="cmd_lang",
                   help="لغة السرد والكابشن: ar (العربية، الافتراضي) أو "
                        "en (الإنجليزية). " + EN_VOICE_LICENSE_NOTE)
    p.add_argument("--motion", default=long_video.FAST_MOTION_DEFAULT,
                   choices=["clips", "still", "kenburns", "youtube-long"],
                   help="وضع الحركة: kenburns (الافتراضي — المسار "
                        "السريع بلا GPU) = صور ثابتة بحركة Ken Burns "
                        "خفيفة؛ clips = مقاطع حركة مولّدة من المانيفست "
                        "(--motion-manifest) مع رجوع لصورة ثابتة بلا "
                        "Ken Burns عند غياب المقاطع؛ youtube-long = مثل "
                        "clips لكن الصور الاحتياطية 2.5 ثانية بدل 5 "
                        "(إيقاع قصص يوتيوب الطويلة)؛ still = صور ثابتة "
                        "بلا أي حركة")
    p.add_argument("--improve-motion", action="store_true",
                   help="حسّن الحركة: بدّل صور الفصول بمقاطع مولّدة من "
                        "مانيفست الحركة (--motion-manifest) مع إعادة "
                        "استخدام الإطارات المجمّدة (بلا توليد GPU هنا)")
    p.add_argument("--motion-manifest",
                   help="مسار مانيفست الحركة JSON أو CSV (مع --motion "
                        "clips)")
    p.add_argument("--motion-dir",
                   help="مجلد ملفات mp4 المولّدة (الافتراضي: مجلد ملف "
                        "المانيفست)")
    p.add_argument("--atempo", type=float, default=1.0,
                   help="سرعة السرد (1.0 افتراضيًا؛ 1.25 لإيقاع Kwai)")
    p.add_argument("--no-watermark", action="store_true",
                   help="تخطَّ شعار الصفحة (الشعار تلقائي افتراضيًا)")
    p = sub.add_parser("long-narration",
                       help="سرد طويل مقسّم بصوت Piper (رجل) — نص إلى WAV")
    p.add_argument("--text", help="نص السرد (أو استخدم --text-file)")
    p.add_argument("--text-file", help="ملف نص السرد")
    p.add_argument("--out", required=True, help="ملف WAV الناتج")
    p.add_argument("--gap", type=float, default=0.35,
                   help="فاصل الصمت بين الجمل بالثواني (0.35)")
    p.add_argument("--atempo", type=float, default=1.0,
                   help="سرعة السرد (1.0 افتراضيًا؛ 1.25 لإيقاع Kwai)")
    p.add_argument("--voice", default=None,
                   help="صوت السرد: piper (الراوي الرجل) أو gtts أو "
                        "supertonic-M1 (صوت ثانٍ اختياري) — أو اسم موديل "
                        "Piper رجالي من السجل (مثال en_US-ryan-medium "
                        "للإنجليزية)؛ والافتراضي من الإعداد "
                        "(narration.voice)؛ وأي اسم غير معروف أو غير "
                        "ذكوري يُرفض")
    p.add_argument("--lang", choices=["ar", "en"], default=None,
                   dest="cmd_lang",
                   help="لغة السرد: ar (العربية، الافتراضي) أو en "
                        "(الإنجليزية). " + EN_VOICE_LICENSE_NOTE)
    p = sub.add_parser("quote-cards",
                       help="توليد بطاقات الاقتباس الثلاث 720×1280")
    p.add_argument("--ibra", required=True, help="نص العبرة")
    p.add_argument("--hikma", required=True, help="نص الحكمة")
    p.add_argument("--mawiza", required=True, help="نص الموعظة الدينية")
    p.add_argument("--mawiza-source", default="",
                   help="مصدر الموعظة (مثال: سورة الإسراء: آية 23)")
    p.add_argument("--out-dir", required=True,
                   help="مجلد حفظ البطاقات الثلاث")
    p = sub.add_parser("run-queue",
                         help="دفعة جماعية من ملف الطابور (الجاهز فقط)")
    p.add_argument("--limit", type=int,
                   help="أقصى عدد قصص من بداية الطابور")
    p.add_argument("--continue-on-error", action="store_true",
                   help="أكمل بعد فشل قصة بدل التوقف")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع القصص وحالتها دون تنفيذ")
    p.add_argument("--allow-fallback", action="store_true",
                   help="اسمح بهوك بديل من السيناريو الجاهز عند فشل "
                        "OmniRoute")
    p = sub.add_parser("analyze-ref",
                         help="تحليل فيديو مرجعي (خاص فقط — بلا إعادة نشر)")
    p.add_argument("--url", required=True,
                   help="رابط فيديو يوتيوب عام")
    p.add_argument("--model", default="small",
                   help="موديل whisper للتفريغ: tiny/base/small "
                        "(الافتراضي: small)")
    p = sub.add_parser("analyze",
                       help="تحليل آخر فيديو منشور بأرقام حقيقية "
                            "(فيسبوك + يوتيوب) واقتراحات تحسين")
    p.add_argument("--page-id",
                   help="معرّف صفحة فيسبوك (أو من config.yaml)")
    p.add_argument("--channel-id",
                   help="معرّف قناة يوتيوب (أو من config.yaml)")
    p.add_argument("--dna", action="store_true",
                   help="تحليل DNA الفيروسي لفيديو واحد (مع --video)")
    p.add_argument("--snapshot", action="store_true",
                   help="أعد قياس DNA لفيديوهات مجموعة التقييم الثابتة "
                        "وقارن بالأساس (انحدار) — بلا --video")
    p.add_argument("--video",
                   help="ملف الفيديو لتحليل DNA (مع --dna)")
    p.add_argument("--hook",
                   help="نص الهوك لدرجة DNA (مع --dna؛ الافتراضي: "
                        "اسم الفيديو)")
    p.add_argument("--subs-dir",
                   help="مجلد ملفات ASS لكثافة الكلمات (مع --dna)")
    p.add_argument("--slug",
                   help="بادئة ملفات ASS لكثافة الكلمات (مع --dna؛ "
                        "الافتراضي: تُشتق من اسم الفيديو)")
    p.add_argument("--story-text",
                   help="ملف نص القصة لمعيار العائد (مع --dna)")
    p.add_argument("--reference",
                   help="ملف فيديو مرجعي محلي (مع --dna) لتحليل DNA "
                        "واقتراح إعادة بناء على نمطه")
    p.add_argument("--story",
                   help="ملف نص قصة عربية جديدة (مع --reference) "
                        "لاقتراح إعادة البناء")
    p.add_argument("--audio-profile", metavar="FILE",
                   help="ملف سرد wav — ملف أداء الصوت يُلحق بتقرير "
                        "DNA (مع --dna فقط؛ وبلا --dna يُتجاهل)")
    p = sub.add_parser("queue", help="إدارة طابور القصص")
    qp = p.add_subparsers(dest="queue_cmd", required=True)
    qa = qp.add_parser("add", help="إضافة قصة جديدة إلى الطابور")
    qa.add_argument("--title", required=True, help="عنوان القصة")
    qa.add_argument("--text-file", required=True,
                    help="ملف نص القصة الكامل")
    qa.add_argument("--parts", type=int, default=1,
                    help="عدد الأجزاء (1 = منشور واحد، الافتراضي)")
    qa.add_argument("--note", help="ملاحظة قصيرة تُلحق بمدخل الطابور")
    qa.add_argument("--queue-file",
                    help="ملف طابور بديل (الافتراضي من config.yaml)")
    qi = qp.add_parser("import",
                       help="استيراد قصة طويلة من ملف نصي — تقسيم "
                            "لأجزاء 40–60 ثانية سردًا")
    qi.add_argument("--file", required=True, help="ملف نص القصة")
    qi.add_argument("--title", required=True, help="عنوان القصة")
    qi.add_argument("--queue-file",
                    help="ملف طابور بديل (الافتراضي من config.yaml)")
    qi.add_argument("--start",
                    help="تاريخ بداية المواعيد المقترحة (YYYY-MM-DD — "
                         "الافتراضي: اليوم)")
    qv = qp.add_parser("validate",
                       help="تحقق بنية ملف الطابور (قراءة فقط)")
    qv.add_argument("--queue-file",
                    help="ملف طابور بديل (الافتراضي من config.yaml)")
    qps = qp.add_parser("publish-status",
                        help="حدّث حالة نشر قصة لمنصة واحدة")
    qps.add_argument("--number", type=int, required=True,
                     help="رقم القصة في الطابور")
    qps.add_argument("--platform", required=True,
                     choices=["facebook", "youtube", "tiktok",
                              "instagram"],
                     help="المنصة")
    qps.add_argument("--status", required=True,
                     choices=["pending", "published", "failed",
                              "skipped"],
                     help="الحالة الجديدة")
    qps.add_argument("--queue-file",
                     help="ملف طابور بديل (الافتراضي من config.yaml)")
    qsum = qp.add_parser("publish-summary",
                         help="ملخص حالات النشر لكل منصة (قراءة فقط)")
    qsum.add_argument("--queue-file",
                      help="ملف طابور بديل (الافتراضي من config.yaml)")
    qpend = qp.add_parser("pending",
                          help="اعرض القصص المعلقة النشر على منصة")
    qpend.add_argument("--platform", required=True,
                       choices=["facebook", "youtube", "tiktok",
                                "instagram"],
                       help="المنصة")
    qpend.add_argument("--queue-file",
                       help="ملف طابور بديل (الافتراضي من config.yaml)")
    p = sub.add_parser("client-run",
                       help="تنفيذ طلب فيديو عميل واحد (client-orders)")
    p.add_argument("--order", required=True, help="رقم الطلب")
    sub.add_parser("process-queue",
                   help="تنفيذ كل طلبات العملاء الجديدة (client-orders)")
    p = sub.add_parser("orders",
                       help="إدارة طلبات العملاء (تأكيد دفع/عرض)")
    op = p.add_subparsers(dest="orders_cmd", required=True)
    oc = op.add_parser("confirm",
                       help="تأكيد دفع طلب بعد التحقق من التحويل يدويًا")
    oc.add_argument("order_id", help="رقم الطلب (مثال QS-123456)")
    oc.add_argument("--by", default="owner",
                    help="من أكّد الدفع (افتراضي owner)")
    ol = op.add_parser("list",
                       help="عرض الطلبات (اختياريًا بحالة معينة)")
    ol.add_argument("--status", default=None,
                    help="تصفية بحالة (مثال awaiting_payment)")
    ot = op.add_parser("trial",
                       help="حالة التجربة المجانية لعميل (كم فيديو "
                            "مجاني بقي له)")
    ot.add_argument("whatsapp", help="رقم واتساب العميل")
    p = sub.add_parser("ideas", help="مولّد أفكار قصص بأسلوب الصفحة")
    p.add_argument("--count", type=int, default=5,
                   help="عدد الأفكار (افتراضي 5)")
    p.add_argument("--theme", default=None,
                   help="موضوع واحد من بنك المواضيع")
    p.add_argument("--add", type=int, default=None,
                   help="أضف الفكرة بهذا الرقم إلى الطابور")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p = sub.add_parser("daily",
                       help="أمر اليوم الواحد: إنتاج + فحص + مصغرة "
                            "+ نشر + أول تعليق")
    p.add_argument("--slot", choices=["morning", "evening"],
                   default="morning",
                   help="موعد اليوم (افتراضي الصباح)")
    p.add_argument("--execute", action="store_true",
                   help="تنفيذ حقيقي (بدونه: وضع تجريبي فقط)")
    p.add_argument("--dry-run", action="store_true",
                   help="وضع تجريبي صريح (هو الافتراضي)")
    p.add_argument("--video", default=None,
                   help="فيديو جاهز (مثلًا من Flow) بدل الإنتاج")
    p.add_argument("--moral", default="",
                   help="العبرة لنص أول تعليق والكابشن")
    p.add_argument("--question", default="",
                   help="سؤال المعضلة لنص أول تعليق")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p.add_argument("--auto-approve", action="store_true",
                   help="موافقة تلقائية على إنفاق Veo بخطة المشاهد "
                        "(بلا توقف تفاعلي)")
    p.add_argument("--backend", choices=("concat", "headless", "mlt",
                                        "openreel"),
                   default="concat",
                   help="خلفية التجميع عند الإنتاج (الافتراضي Concat) — "
                   "openreel: الوضع التلقائي لـOpenReel")
    p.add_argument("--grade", choices=("warm", "vivid", "cinematic",
                                       "soft"),
                   default=None,
                   help="تدرج لوني LUT بعد الريندر وقبل الشعار")
    p = sub.add_parser("schedule",
                       help="مراقبة منشور مجدول ونشر أول تعليق عند نشره")
    p.add_argument("--watch", action="store_true",
                   help="راقب المنشور المجدول (الوضع الوحيد حاليًا)")
    p.add_argument("--post-id", required=True,
                   help="معرّف المنشور المجدول (scheduled_post_id من إيصال النشر)")
    p.add_argument("--story", required=True,
                   help="معرّف القصة (slug) — لربط العبرة والسؤال بملف الطابور")
    p.add_argument("--slot", choices=["morning", "evening"],
                   default="morning",
                   help="موعد اليوم (افتراضي الصباح)")
    p.add_argument("--moral", required=True,
                   help="العبرة لنص أول تعليق")
    p.add_argument("--question", required=True,
                   help="السؤال المحيّر لنص أول تعليق")
    p.add_argument("--next-part-time", default=None,
                   help="موعد الجزء التالي (افتراضي «بكرة 7 مساءً»)")
    p.add_argument("--execute", action="store_true",
                   help="تنفيذ حقيقي (بدونه: وضع تجريبي فقط)")
    p = sub.add_parser("batch",
                       help="دفعة جماعية: القصص التالية من الطابور "
                            "في تشغيل واحد (إنتاج + فحص + مصغرة)")
    p.add_argument("--count", type=int, default=1,
                   help="عدد القصص من بداية الطابور (افتراضي 1)")
    p.add_argument("--source", choices=["veo", "openmontage"],
                   default="openmontage",
                   help="مصدر الإنتاج (افتراضي openmontage)")
    p.add_argument("--execute", action="store_true",
                   help="تنفيذ حقيقي (بدونه: وضع تجريبي فقط)")
    p.add_argument("--continue-on-error", action="store_true",
                   help="أكمل بعد فشل قصة بدل التوقف")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p.add_argument("--from-json", default=None,
                   help="ملف JSON لقائمة مهام الدفعة بدل الطابور "
                        "(يتخطى بوابة بنية الطابور)")
    p.add_argument("--no-spend", action="store_true",
                   help="محاكاة الدفعة كاملة بلا أي إنفاق: تقدير "
                        "الرصيد + فحص الكفاية + ما سيُعاد استخدامه "
                        "من الكاش — يرفض مع --execute")
    p.add_argument("--no-cache", action="store_true",
                   help="عطّل إعادة استخدام منتجات الريندر السابقة "
                        "في هذه الدفعة")
    p = sub.add_parser("scene-plan",
                       help="خطة مشاهد Veo مكتوبة لقصة من الطابور "
                            "قبل أي إنفاق (مع فحص السقف)")
    p.add_argument("--story", required=True,
                   help="رقم القصة في الطابور أو جزء من عنوانها")
    p.add_argument("--clips", type=int, default=6,
                   help="عدد المقاطع (افتراضي 6 — كل مقطع 20 وحدة)")
    p.add_argument("--queue-file", default=None,
                   help="ملف طابور بديل (للاختبار)")
    p.add_argument("--template", default=None,
                   help="قالب قصة جاهز للموجهات عند غياب نص الطابور "
                        "(من story_templates.list_templates)")
    p.add_argument("--hero", default=None,
                   help="بطل القصة لقالب --template (افتراضي: العنوان)")
    p.add_argument("--situation", default=None,
                   help="موقف القصة لقالب --template (افتراضي: أول "
                        "جملة نص أو العنوان)")
    p.add_argument("--moral", default=None,
                   help="عبرة القصة لقالب --template")
    p.add_argument("--template-lang", choices=["ar", "en"], default=None,
                   help="لغة قالب --template: ar (العربية، الافتراضي) "
                        "أو en (الإنجليزية) — بلا هذا الخيار يتبع "
                        "القالب لغة CLI (--lang)")
    p = sub.add_parser("tiktok-auth",
                       help="خطوات ربط TikTok يدويًا + حفظ التوكن")
    p.add_argument("--token", default=None,
                   help="توكن TikTok (يُحفظ بصلاحية 600 ولا يُعرض)")
    p = sub.add_parser("instagram-auth",
                       help="خطوات ربط Instagram يدويًا + حفظ التوكن")
    p.add_argument("--token", default=None,
                   help="توكن Instagram (يُحفظ بصلاحية 600 ولا يُعرض)")
    p = sub.add_parser("tiktok-bundle",
                       help="بناء حزمة رفع TikTok لمهمة متصفح "
                            "(كابشن + خطوات — بلا نشر)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--title", required=True, help="عنوان الفيديو")
    p.add_argument("--caption", default=None,
                   help="نص القصة للكابشن (افتراضي: العنوان فقط)")
    p.add_argument("--moral", default="",
                   help="العبرة تُلحق بالكابشن بعد «العبرة:»")
    p.add_argument("--next-part", action="store_true",
                   help="ألحق الدعوة اللطيفة للجزء التالي")
    p.add_argument("--next-part-time", default="بكرة 7 مساءً",
                   help="موعد الجزء التالي في الدعوة "
                        "(افتراضي: بكرة 7 مساءً)")
    p.add_argument("--ai-voice", action="store_true",
                   help="ألحق سطر إفصاح «صوت مولّد بالذكاء الاصطناعي»")
    p.add_argument("--out-dir", default=None,
                   help="مجلد الحزمة (افتراضي: videos/tiktok-bundle-<وقت>)")
    p.add_argument("--dry-run", action="store_true",
                   help="اطبع الكابشن والخطوات بلا أي كتابة ملفات")
    p = sub.add_parser("tiktok-long",
                       help="دمج فيديوهين في النسخة الطويلة اليومية "
                            "لـ TikTok (65–110 ث) + حزمة رفع")
    p.add_argument("--video-a", required=True,
                   help="الفيديو الأول (mp4 عمودي 40–60 ث)")
    p.add_argument("--video-b", required=True,
                   help="الفيديو الثاني (mp4 عمودي 40–60 ث)")
    p.add_argument("--title", required=True,
                   help="عنوان القصة (لـ«القصة كاملة») أو وصف الزوج "
                        "(مع --kind two)")
    p.add_argument("--caption", default=None,
                   help="نص القصة للكابشن (افتراضي: العنوان فقط)")
    p.add_argument("--moral", default="",
                   help="العبرة تُلحق بالكابشن بعد «العبرة:»")
    p.add_argument("--part-tags", default=None,
                   help="وسوم الأجزاء المدمجة مفصولة بمسافات "
                        "(مثال: \"#الجزء_الأول #الجزء_الثاني\") — "
                        "تُلحق سطرًا قبل الوسوم الأربعة")
    p.add_argument("--kind", choices=["full", "two"], default="full",
                   help="full: «القصة كاملة» لجزأي قصة واحدة؛ "
                        "two: «قصتان مؤثرتان» لقصتين منفردتين")
    p.add_argument("--out-dir", default=None,
                   help="مجلد الحزمة (افتراضي: videos/tiktok-long-<وقت>)")
    p.add_argument("--max-seconds", type=float, default=None,
                   help="الحد الأقصى لمدة الناتج (افتراضي: 110 ث)")
    p.add_argument("--dry-run", action="store_true",
                   help="افحص المدخلين واطبع مجموع المدتين بلا دمج")
    p = sub.add_parser("tiktok-status",
                       help="حالة إعداد TikTok: الحساب وطريقة الرفع "
                            "وربط API (قراءة فقط)")
    p = sub.add_parser("ab", help="اختبار A/B: هوكان ومصغرتان "
                                  "لفيديو واحد")
    p.add_argument("--video",
                   help="ملف الفيديو (غير مطلوب مع --eval-set)")
    p.add_argument("--eval-set", action="store_true",
                   help="اختبر هوكات بديلة لكل فيديو في مجموعة التقييم "
                        "الثابتة وقارن بالأساس")
    p.add_argument("--hook-a", default=None, help="هوك النسخة أ")
    p.add_argument("--hook-b", default=None, help="هوك النسخة ب")
    p.add_argument("--title", default=None, help="عنوان الفيديو")
    p.add_argument("--out-dir", default=None,
                   help="مجلد السجلات (افتراضي runs/)")
    p.add_argument("--cost-per-video", type=int, default=0,
                   help="تقدير وحدات Veo لإنتاج كل بديل من جديد "
                        "(افتراضي 0 — نفس الفيديو بلا توليد جديد؛ "
                        "وتوليد جديد كامل = 120)")
    p.add_argument("--variants", type=int, default=3,
                   help="عدد نسخ الهوك (افتراضي 3؛ 2 = السلوك السابق "
                        "بهوكين فقط)")
    p.add_argument("--engine", choices=["fast", "lite"], default="fast",
                   help="محرك Veo لتقدير التكلفة (fast ‏20 وحدة/مقطع "
                        "أو lite ‏10 — بعد تقاعد Fast في 5 ديسمبر "
                        "استخدم lite؛ افتراضي fast)")
    p = sub.add_parser("ab-results",
                       help="قارن مشاهدات نسختي اختبار A/B")
    p.add_argument("--ab-file", default=None,
                   help="ملف سجل ab-*.json (افتراضي: الأحدث)")
    p = sub.add_parser("update",
                       help="جلب آخر إصدار من GitHub وتطبيقه "
                            "(مع نسخة احتياطية)")
    p.add_argument("--dry-run", action="store_true",
                   help="اعرض ما سيتغير بلا كتابة")
    p.add_argument("--repo", default="aalhdydy550-ui/qisas-studio",
                   help="المستودع (افتراضي aalhdydy550-ui/qisas-studio)")
    p.add_argument("--branch", default="main",
                   help="الفرع (افتراضي main)")
    p = sub.add_parser("restore",
                       help="استعادة الإعداد والطابور وطلبات العملاء "
                            "من نسخة backup (أو تراجع من تحديث فاسد)")
    p.add_argument("--backup",
                   help="ملف zip النسخة (من `studio.py backup`) — "
                        "يسترجع الإعداد والطابور وطلبات العملاء فقط")
    p.add_argument("--file",
                   help="ملف zip نسخة «قبل التحديث» (تراجع من "
                        "تحديث فاسد — لا يسترجع ملفات محمية)")
    p.add_argument("--dry-run", action="store_true",
                   help="اعرض خطة الاستعادة دون كتابة (مع --backup)")
    p.add_argument("--yes", action="store_true",
                   help="تجاوز سؤال التأكيد (غير تفاعلي)")
    p = sub.add_parser("backup",
                       help="نسخة احتياطية zip للإعداد والطابور "
                            "والطلبات والسجلات")
    p.add_argument("--out-dir", default=None,
                   help="مجلد النسخ (افتراضي backups/)")
    p.add_argument("--keep", type=int, default=None,
                   help="عدد النسخ المحتفَظ بها (افتراضي 7)")
    p = sub.add_parser("preview",
                       help="صفحة معاينة HTML لفيديو قبل النشر "
                            "(إطارات + صوت + فحص جودة + كابشن)")
    p.add_argument("--video", required=True, help="ملف الفيديو mp4")
    p.add_argument("--caption", help="نص الكابشن")
    p.add_argument("--first-comment", help="نص أول تعليق")
    p.add_argument("--out-dir",
                   help="مجلد حفظ الصفحة (افتراضي: بجانب الفيديو)")
    p.add_argument("--title", help="عنوان الصفحة (افتراضي: اسم الفيديو)")
    p = sub.add_parser("logs",
                       help="آخر التشغيلات من runs/ ونتائجها بالعربي")
    p.add_argument("--today", action="store_true",
                   help="اليوم فقط (الافتراضي)")
    p.add_argument("--all", dest="all_logs", action="store_true",
                   help="كل الأيام بدل اليوم فقط")
    p.add_argument("--limit", type=int, default=20,
                   help="أقصى عدد تشغيلات (افتراضي 20)")
    p = sub.add_parser("jobs",
                       help="سجل المهام الدائم — اعرض مهام الدفعات "
                            "والتشغيلات المسجلة")
    jp = p.add_subparsers(dest="jobs_cmd", required=True)
    jl = jp.add_parser("list", help="اعرض المهام (الأحدث أولًا)")
    jl.add_argument("--status", default=None,
                    choices=["running", "done", "failed", "skipped",
                             "reused"],
                    help="تصفية بالحالة")
    jl.add_argument("--story", default=None,
                    help="تصفية برقم/عنوان قصة (مطابقة جزئية)")
    jl.add_argument("--date", default=None,
                    help="تصفية بتاريخ البدء YYYY-MM-DD")
    jl.add_argument("--kind", default=None,
                    choices=["run", "batch", "assemble"],
                    help="تصفية بالنوع")
    jl.add_argument("--limit", type=int, default=20,
                    help="أقصى عدد مهام (افتراضي 20)")
    js = jp.add_parser("show", help="اعرض مهمة واحدة بمعرّفها")
    js.add_argument("job_id", help="معرّف المهمة (مثال job-20261123-...)")
    p = sub.add_parser("reframe",
                       help="أعد تأطير مقطع أفقي إلى عمودي 720×1280 "
                            "(قصّ ذكي بلا تشويه)")
    p.add_argument("--video", required=True, help="ملف الفيديو الأفقي")
    p.add_argument("--out", required=True, help="ملف الفيديو العمودي")
    p.add_argument("--focus-x", type=float, default=0.5,
                   help="نقطة تركيز القصّ 0.0 (يسار) – 1.0 (يمين)، "
                        "افتراضي 0.5 (الوسط)")
    p.add_argument("--safety-margin", type=int, default=0,
                   help="هامش أمان بالبكسلات يمنع ملامسة الحواف "
                        "(افتراضي 0)")
    p = sub.add_parser("shorts-cut",
                       help="قطّع فيديو طويل إلى شورتات عمودية 40–60 "
                            "ثانية (للفيديو الأسبوعي)")
    p.add_argument("--video", required=True,
                   help="ملف الفيديو الطويل (8–12 دقيقة)")
    p.add_argument("--out", default=None,
                   help="مجلد المخرجات (افتراضي: videos/shorts-<وقت>)")
    p.add_argument("--count", type=int, default=3,
                   help="عدد الشورتات (افتراضي 3)")
    p.add_argument("--phrases", default=None,
                   help="ملف ASS بعبارات الفيديو الطويل لتحسين "
                        "الاختيار (اختياري)")
    p.add_argument("--min", type=float, default=None, dest="min_len",
                   help="أدنى مدة شورت بالثواني (افتراضي 40)")
    p.add_argument("--max", type=float, default=None, dest="max_len",
                   help="أقصى مدة شورت بالثواني (افتراضي 60)")
    p = sub.add_parser("balance",
                       help="توقع رصيد Veo بالأيام (مسجَّل لا حي)")
    p.add_argument("--balance", type=int, default=None,
                   help="رصيد حالي بديل (وحدة)")
    p.add_argument("--renew", default=None,
                   help="تاريخ تجديد بديل (YYYY-MM-DD)")
    p.add_argument("--cost-min", type=int, default=None,
                   help="أقل تكلفة فيديو يومي (وحدة)")
    p.add_argument("--cost-max", type=int, default=None,
                   help="أعلى تكلفة فيديو يومي (وحدة)")
    p.add_argument("--record", type=int, default=None,
                   help="سجّل إنفاقًا فعليًا بعد توليد في Flow (وحدة) "
                        "— مع --video")
    p.add_argument("--video", default=None,
                   help="اسم الفيديو للإنفاق المسجَّل (مع --record)")
    p.add_argument("--clips", type=int, default=None,
                   help="عدد مقاطع التوليد (مع --record)")
    p.add_argument("--history", action="store_true",
                   help="اعرض سجل التكاليف المسجَّلة")
    p.add_argument("--cap", type=int, default=None,
                   help="سقف الإنفاق: حد أقصى لوحدات Veo لكل توليد "
                        "(فيديو واحد) — يُحفظ في config.yaml؛ و0 "
                        "يلغي السقف")
    p.add_argument("--set", dest="set_balance", type=int, default=None,
                   help="اضبط الرصيد المسجَّل (وحدة) مع ختم وقت "
                        "التحديث بتوقيت القاهرة الآن")
    # أوامر الموجة ب (جولة v0.1.63): أغلفة رقيقة فوق وحدات الموجة أ.
    p = sub.add_parser("approval", help="مستويات الموافقة: عرض أو ضبط")
    _sp = p.add_subparsers(dest="approval_cmd", required=True)
    _sp.add_parser("show", help="اعرض مستوى الموافقة والوضع والمنح")
    p = _sp.add_parser("set", help="اضبط مستوى الموافقة أو الوضع")
    p.add_argument("--level",
                   choices=["ask", "edits", "auto", "full", "custom"],
                   help="مستوى الموافقة: ask أو edits أو auto أو full "
                        "أو custom")
    p.add_argument("--mode", choices=["normal", "read-and-draft"],
                   help="وضع التشغيل: normal أو read-and-draft")
    p.add_argument("--custom", action="append", default=[],
                   metavar="ACTION=DECISION",
                   help="قرار فعل في خريطة custom (يُكرَّر، مثال: "
                        "--custom publish=ask)")
    p = sub.add_parser("team", help="ملف الفريق الإعلاني: تطبيق/تصدير/فحص")
    _sp = p.add_subparsers(dest="team_cmd", required=True)
    p = _sp.add_parser("apply", help="اطبع الخطة ثم طبّق ملف فريق")
    p.add_argument("file", help="ملف team.yaml")
    p.add_argument("--dry-run", action="store_true",
                   help="الخطة فقط بلا أي تغيير")
    p.add_argument("--prune", action="store_true",
                   help="احذف البوتات غير المذكورة في فرق prune: true")
    p = _sp.add_parser("check", help="هل سيتغيّر شيء عند التطبيق؟ "
                                     "(خروج 6 إن نعم)")
    p.add_argument("file", help="ملف team.yaml")
    _sp.add_parser("export", help="صدّر الحالة المحفوظة للفريق")
    p = sub.add_parser("routines", help="سجل وقوعات الروتينات")
    _sp = p.add_subparsers(dest="routines_cmd", required=True)
    p = _sp.add_parser("ledger", help="اعرض سطور سجل الوقوعات")
    p.add_argument("--routine", help="فلترة باسم روتين")
    p.add_argument("--state",
                   choices=["ran", "failed", "missed", "skipped",
                            "queued", "running"],
                   help="فلترة بحالة وقوع")
    p.add_argument("--limit", type=int, default=50,
                   help="أقصى سطور (الافتراضي: 50)")
    p = _sp.add_parser("missed", help="لخّص الوقوعات الفائتة")
    p.add_argument("--routine", help="فلترة باسم روتين")
    p.add_argument("--limit", type=int, default=50,
                   help="أقصى سطور (الافتراضي: 50)")
    p = sub.add_parser("check-back", help="متابعة مؤجلة لمرة واحدة")
    _sp = p.add_subparsers(dest="check_back_cmd", required=True)
    p = _sp.add_parser("add", help="أضف check-back معلَّقًا")
    p.add_argument("--run-id", required=True, help="معرّف التشغيل")
    p.add_argument("--worker", required=True, help="اسم العامل")
    p.add_argument("--due", help="موعد الاستحقاق بصيغة ISO")
    p.add_argument("--in-minutes", type=int,
                   help="الاستحقاق بعد N دقيقة من الآن")
    p.add_argument("--note", help="ملاحظة قصيرة (≤500 حرف)")
    p = _sp.add_parser("list", help="اسرد check-backs")
    p.add_argument("--run-id", help="فلترة بمعرّف التشغيل")
    p.add_argument("--worker", help="فلترة باسم العامل")
    p.add_argument("--status",
                   choices=["pending", "consumed", "cancelled"],
                   help="فلترة بالحالة")
    p = _sp.add_parser("cancel", help="ألغِ check-back معلَّقًا")
    p.add_argument("--id", required=True, help="معرّف check-back")
    p = sub.add_parser("usage", help="حدود الاستخدام")
    _sp = p.add_subparsers(dest="usage_cmd", required=True)
    _p = _sp.add_parser("caps", help="حدود الاستخدام: عرض أو ضبط")
    _sp2 = _p.add_subparsers(dest="caps_cmd", required=True)
    _sp2.add_parser("show", help="اعرض الحدود والمجاميع الجارية")
    p = _sp2.add_parser("set", help="اضبط حدًا أو أكثر (0 يمسح الحد)")
    p.add_argument("--daily-usd", type=float, help="حد الدولار اليومي")
    p.add_argument("--monthly-usd", type=float, help="حد الدولار الشهري")
    p.add_argument("--daily-tokens", type=int, help="حد الرموز اليومي")
    p.add_argument("--monthly-tokens", type=int, help="حد الرموز الشهري")
    p.add_argument("--stops", choices=["unattended", "everything"],
                   help="ما يوقفه الحد: unattended أو everything")
    p = sub.add_parser("models", help="محركات النماذج: قائمة أو صحة")
    _sp = p.add_subparsers(dest="models_cmd", required=True)
    _sp.add_parser("list", help="اسرد المحركات المسجلة")
    _sp.add_parser("health", help="اعرض صحة كل محرك")
    p = sub.add_parser("round-pack", help="حزم الجولات: تصدير/استيراد/مراجعة")
    _sp = p.add_subparsers(dest="pack_cmd", required=True)
    p = _sp.add_parser("export", help="صدّر حزمة جولة إلى ملف .md واحد")
    p.add_argument("--dir", required=True, help="مجلد ملفات الحزمة")
    p.add_argument("--file", action="append", default=[], dest="files",
                   help="ملف نسبي في الحزمة (يُكرَّر)")
    p.add_argument("--name", required=True, help="اسم الحزمة")
    p.add_argument("--version", help="إصدار الحزمة (الافتراضي: إصدار studio)")
    p.add_argument("--change", action="append", default=[],
                   help="سطر تغيير (يُكرَّر)")
    p.add_argument("--test", action="append", default=[],
                   help="سطر اختبار (يُكرَّر)")
    p.add_argument("--out", required=True, help="ملف الحزمة .md الناتج")
    p = _sp.add_parser("import", help="استورد حزمة بعد مراجعتها")
    p.add_argument("--pack", required=True, help="ملف الحزمة .md")
    p.add_argument("--dest", required=True, help="مجلد الاستيراد")
    p.add_argument("--force", action="store_true",
                   help="اسمح باستبدال ملفات موجودة (مع نسخة .previous)")
    p = _sp.add_parser("review", help="راجع حزمة بلا كتابة")
    p.add_argument("--pack", required=True, help="ملف الحزمة .md")
    p = sub.add_parser("handoffs", help="تسليمات المنسّق")
    _sp = p.add_subparsers(dest="handoffs_cmd", required=True)
    p = _sp.add_parser("list", help="اسرد التسليمات وحالاتها")
    p.add_argument("--state",
                   choices=["source", "queued", "running", "waiting",
                            "resume", "completed", "failed", "cancelled"],
                   help="فلترة بالحالة")
    p.add_argument("--limit", type=int, default=20,
                   help="أقصى تسليمات (الافتراضي: 20)")
    p = sub.add_parser("keys", help="المفاتيح: كتابة فقط (ع12)")
    _sp = p.add_subparsers(dest="keys_cmd", required=True)
    p = _sp.add_parser("set", help="احفظ مفتاحًا بعد اختبار واحد")
    p.add_argument("--name", required=True, help="اسم المفتاح")
    p.add_argument("--provider", help="المزوّد (يُخمَّن من الصيغة إن غاب)")
    p.add_argument("--token-file", required=True,
                   help="ملف يحمل المفتاح (أبدًا --token)")
    p.add_argument("--token", default=None,
                   help="مرفوض دائمًا — استخدم --token-file")
    p = _sp.add_parser("test", help="اختبر مفتاحًا بلا حفظه")
    p.add_argument("--provider", required=True, help="المزوّد")
    p.add_argument("--token-file", required=True,
                   help="ملف يحمل المفتاح (أبدًا --token)")
    p = _sp.add_parser("rotate", help="دوّر مفتاحًا محفوظًا")
    p.add_argument("--name", required=True, help="اسم المفتاح")
    p.add_argument("--token-file", required=True,
                   help="ملف يحمل المفتاح الجديد (أبدًا --token)")
    p.add_argument("--token", default=None,
                   help="مرفوض دائمًا — استخدم --token-file")
    _sp.add_parser("list", help="اسرد المفاتيح (أسماء ووجود فقط)")
    p = sub.add_parser("sentinel", help="فاحص صحة يقرأ فقط (ع14)")
    p.add_argument("--data-dir", help="مجلد البيانات المقروء "
                                      "(الافتراضي: مجلد studio)")
    p.add_argument("--out", help="مجلد كتابة القضايا (يرفض داخل "
                                 "البيانات أو git)")
    p.add_argument("--once", action="store_true",
                   help="فحص واحد (السلوك الحالي دائمًا)")
    p.add_argument("--json", action="store_true",
                   default=argparse.SUPPRESS,
                   help="اطبع الملخص JSON بدل السطور")
    p = sub.add_parser("control", help="سطح تحكم محدود (بند 17)")
    p.add_argument("verb", help="الفعل (قراءة أو تعديل)")
    p.add_argument("--target", help="هدف صريح (إلزامي لأفعال التعديل)")
    p = sub.add_parser("inspect", help="قراءات محدودة: مهام أو تشغيلات")
    _sp = p.add_subparsers(dest="inspect_cmd", required=True)
    p = _sp.add_parser("jobs", help="اسرد مهام سجل التشغيل")
    p.add_argument("--status",
                   choices=["running", "done", "failed", "skipped",
                            "reused", "cancelled"],
                   help="فلترة بالحالة")
    p.add_argument("--limit", type=int, default=20,
                   help="أقصى مهام (الافتراضي: 20)")
    _sp.add_parser("runs", help="اسرد مجلدات التشغيل في runs/")
    p = sub.add_parser("read-log", help="اقرأ آخر مدخلات سجل (≤200)")
    p.add_argument("--file", help="ملف السجل (الافتراضي: runs/studio.log)")
    p.add_argument("--limit", type=int, default=200,
                   help="أقصى مدخلات (الافتراضي: 200)")
    p = sub.add_parser("search-log", help="ابحث في سجل (≤100 مطابقة)")
    p.add_argument("--file", help="ملف السجل (الافتراضي: runs/studio.log)")
    p.add_argument("--query", required=True, help="عبارة البحث")
    p.add_argument("--limit", type=int, default=100,
                   help="أقصى مطابقات (الافتراضي: 100)")
    p = sub.add_parser("send-work", help="سجّل تسليمًا جديدًا")
    p.add_argument("--title", required=True, help="عنوان التسليم")
    p.add_argument("--kind", default="run",
                   choices=["run", "batch", "assemble", "schedule"],
                   help="نوع التسليم (الافتراضي: run)")
    p.add_argument("--source", help="تسمية مصدر ع11 "
                                    "(الافتراضي: مصدر سطر الأوامر)")
    p = sub.add_parser("wait-job", help="انتظر مهمة حتى تنتهي")
    p.add_argument("--job-id", required=True, help="معرّف المهمة")
    p.add_argument("--timeout", type=float, default=60,
                   help="مهلة الانتظار بالثواني (الافتراضي: 60)")
    p.add_argument("--poll", type=float, default=2,
                   help="فاصل الاستطلاع بالثواني (الافتراضي: 2)")
    p = sub.add_parser("interrupt-job", help="قاطع مهمة وشجرتها")
    p.add_argument("--job-id", required=True, help="معرّف المهمة")
    p = sub.add_parser("switch-model", help="تحقق من محرك نموذج قبل التبديل")
    p.add_argument("--model", required=True, help="اسم المحرك/النموذج")
    p = sub.add_parser("wait", help="انتظر مهمة مع أحداثها")
    p.add_argument("--job-id", required=True, help="معرّف المهمة")
    p.add_argument("--timeout", type=float, default=60,
                   help="مهلة الانتظار بالثواني (الافتراضي: 60)")
    p.add_argument("--poll", type=float, default=2,
                   help="فاصل الاستطلاع بالثواني (الافتراضي: 2)")
    p.add_argument("--limit", type=int, default=200,
                   help="أقصى أحداث (الافتراضي: 200)")
    p = sub.add_parser("events", help="اقرأ أحداث مهمة")
    p.add_argument("--job-id", required=True, help="معرّف المهمة")
    p.add_argument("--limit", type=int, default=200,
                   help="أقصى أحداث (الافتراضي: 200)")
    p = sub.add_parser("brief", help="الموجز اليومي: عرض أو رفض صف")
    _sp = p.add_subparsers(dest="brief_cmd", required=True)
    _sp.add_parser("show", help="اعرض حالة الموجز")
    p = _sp.add_parser("dismiss", help="ارفض صفًا من الموجز (للمالك فقط)")
    p.add_argument("--row-id", required=True, help="معرّف الصف")
    p.add_argument("--owner", required=True, help="مالك الرفض")
    p.add_argument("--thread-owner", required=True, help="مالك الخيط")
    p = sub.add_parser("workers", help="إيقاف العمال: pause/resume/stop")
    _sp = p.add_subparsers(dest="workers_cmd", required=True)
    for _verb in ("pause", "resume", "stop"):
        p = _sp.add_parser(_verb, help="عامل: %s" % _verb)
        p.add_argument("--worker", help="اسم العامل")
        p.add_argument("--all", action="store_true",
                       help="طبّق على كل عامل مسجل")
    p = sub.add_parser("export", help="صدّر حزمة تشخيصية لمهمة")
    p.add_argument("--job", required=True, help="معرّف المهمة")
    p.add_argument("--out", required=True, help="مجلد الحزمة الناتج")
    p.add_argument("--force", action="store_true",
                   help="اسمح بمجلد غير فارغ (يحذف فقط ما في manifest)")
    p = sub.add_parser("features", help="مفاتيح المزايا: قائمة أو ضبط")
    _sp = p.add_subparsers(dest="features_cmd", required=True)
    _sp.add_parser("list", help="اسرد المفاتيح المعروفة وقيمها")
    p = _sp.add_parser("set", help="اضبط مفتاحًا واحدًا (دمج لا استبدال)")
    p.add_argument("--name", required=True, help="اسم المفتاح")
    p.add_argument("--value", required=True,
                   help="القيمة: true/false/عدد/نص")
    p = sub.add_parser("triage", help="فرز تعليقات/رسائل الصفحة")
    _sp = p.add_subparsers(dest="triage_cmd", required=True)
    p = _sp.add_parser("inbox", help="افرز عناصر بريد/تعليقات")
    p.add_argument("--file", help="ملف JSON بقائمة {id, text}")
    p.add_argument("--text", help="نص عنصر واحد للفرز")
    p = sub.add_parser("recipe", help="وصفات خطوات متكررة")
    p.add_argument("--dir", help="مجلد الوصفات "
                                 "(الافتراضي: recipes/ في studio)")
    _sp = p.add_subparsers(dest="recipe_cmd", required=True)
    p = _sp.add_parser("save", help="احفظ وصفة جديدة")
    p.add_argument("--dir", default=argparse.SUPPRESS,
                   help="مجلد الوصفات (الافتراضي: recipes/ في studio)")
    p.add_argument("--name", required=True, help="اسم الوصفة")
    p.add_argument("--description", default="", help="وصف الوصفة")
    p.add_argument("--step", action="append", default=[],
                   help="خطوة بصيغة «الاسم: الأمر...» (تُكرَّر)")
    p.add_argument("--force", action="store_true",
                   help="اكتب فوق وصفة موجودة بالاسم نفسه")
    p = _sp.add_parser("run", help="نفّذ وصفة بالترتيب بلا نموذج")
    p.add_argument("--dir", default=argparse.SUPPRESS,
                   help="مجلد الوصفات (الافتراضي: recipes/ في studio)")
    p.add_argument("--name", required=True, help="اسم الوصفة")
    p.add_argument("--dry-run", action="store_true",
                   help="اسرد الخطوات المخططة بلا تنفيذ")
    p = _sp.add_parser("list", help="اسرد الوصفات المحفوظة")
    p.add_argument("--dir", default=argparse.SUPPRESS,
                   help="مجلد الوصفات (الافتراضي: recipes/ في studio)")
    p = sub.add_parser("webhook", help="مستقبل webhooks (مطفأ افتراضيًا)")
    _sp = p.add_subparsers(dest="webhook_cmd", required=True)
    p = _sp.add_parser("serve", help="شغّل المستقبل على 127.0.0.1:8800")
    p.add_argument("--host", default="127.0.0.1", help="المضيف")
    p.add_argument("--port", type=int, default=8800, help="المنفذ")
    p = _sp.add_parser("token", help="أصدر رمزًا (يُعرض مرة واحدة)")
    p.add_argument("--path", help="مسار ملف التجزئة "
                                  "(الافتراضي: ~/.qisas-studio/"
                                  "webhook-token.json)")
    sub.add_parser("setup", help="إعداد أول تشغيل (مرة واحدة)")
    p = sub.add_parser("router", help="موجّه النماذج")
    _sp = p.add_subparsers(dest="router_cmd", required=True)
    p = _sp.add_parser("test", help="اختبار توجيه واحد (يرجع الافتراضي)")
    p.add_argument("--task", default="اختبار توجيه", help="المهمة")
    p.add_argument("--request", default="", help="الطلب")
    p.add_argument("--default", default="gemini/gemini-3-flash-preview",
                   help="النموذج الافتراضي عند الفشل المفتوح")
    p.add_argument("--role", action="append", default=[],
                   help="دور/نموذج معروض (يُكرَّر)")
    args = ap.parse_args()
    cfg = load_config()
    # لغة CLI (الجولة v0.1.41): --lang أولًا، ثم LANG/LANGUAGE،
    # ثم مفتاح lang في config.yaml، ثم العربي دائمًا.
    lang = i18n_lib.detect_lang(getattr(args, "lang", None),
                                env=os.environ, config=cfg)
    # لغة الأمر الصريحة (--lang في الأمر نفسه) تغلب لغة CLI العامة.
    eff_lang = i18n_lib.normalize_lang(
        getattr(args, "cmd_lang", None) or lang)
    # خيار --size (في run/assemble): يبدّل مقاس الفيديو لهذا التشغيل
    # فقط دون تعديل config.yaml (الافتراضي 720×1280 عمودي).
    size_arg = getattr(args, "size", None)
    if size_arg:
        try:
            width, height = parse_size(size_arg)
        except ValueError as e:
            print(i18n_lib.t("main_bad_size", lang, e))
            return 2
        cfg["video"]["width"] = width
        cfg["video"]["height"] = height
    # تحقق مبكر من slugs/معرّفات التشغيل القادمة من CLI (منع الخروج من
    # runs/) — قبل أي إنشاء مجلدات. التحقق داخل new_run/run_dir_for يبقى
    # كدفاع ثانٍ للمستدعين البرمجيين (run-queue والاختبارات).
    try:
        if args.cmd == "run" and getattr(args, "story", None):
            validate_run_component(args.story, "اسم القصة")
        elif args.cmd == "produce":
            if getattr(args, "run_id", None):
                validate_run_component(args.run_id, "معرّف التشغيل")
            if getattr(args, "project", None):
                validate_run_component(args.project, "اسم المشروع")
        elif args.cmd in ("assemble", "thumbnail"):
            if getattr(args, "run_id", None):
                validate_run_component(args.run_id, "معرّف التشغيل")
        elif args.cmd == "long-video":
            for slug in getattr(args, "story", []) or []:
                validate_run_component(slug, "اسم القصة")
            for proj in getattr(args, "project", []) or []:
                validate_run_component(proj, "اسم المشروع")
            for run in getattr(args, "run_id", []) or []:
                validate_run_component(run, "معرّف التشغيل")
    except ValueError as e:
        print(i18n_lib.t("main_bad_value", lang, e))
        return 2
    # doctor يقرأ الحالة الخام بلا إصلاح (وظيفته الإبلاغ لا الإصلاح).
    # أوامر القراءة فقط (version) لا تطلق أي استرداد إطلاقًا
    # (إصلاح بطء بدء التشغيل 2026-11-26: version كان يستغرق 323ث).
    if args.cmd != "doctor":
        _ensure_environment(
            read_only=(args.cmd in _READONLY_COMMANDS))

    # بوابة الترخيص (جولة v0.1.43): الاستخدام التجاري بعد 30 يومًا
    # من أول تشغيل يحتاج ترخيصًا مدفوعًا (1000 جنيه أفراد / 5000
    # شركات)؛ والاستخدام الشخصي غير التجاري معفى بعلَم
    # --noncommercial؛ وتثبيت صاحب المشروع (owner) معفى دائمًا.
    # الأوامر المعفاة (قراءة/تشخيص/صيانة) لا تبدأ الساعة أبدًا —
    # record_first_run() يُستدعى فقط داخل البوابة، فإن نُسي
    # بقي الاستخدام التجاري مسموحًا للأبد (فشل مفتوح موثَّق).
    if args.cmd in COMMERCIAL_COMMANDS \
            and not getattr(args, "noncommercial", False):
        if not (args.cmd == "run" and getattr(args, "demo", False)):
            license_lib.record_first_run()
            allowed, msg = license_lib.commercial_allowed()
            if not allowed:
                print(msg)
                return 1

    # بوابة النجمة (جولة v0.1.48؛ وأُضيف quick في v0.1.53): الأوامر التسعة في
    # STAR_GATED_COMMANDS فقط — تُتخطى مع --dry-run، وتسري
    # بغض النظر عن --noncommercial (ليست بوابة تجارية).
    # عند الرفض تطبع check_star_gate الرسالة العربية وتخرج 1.
    if args.cmd in STAR_GATED_COMMANDS \
            and not getattr(args, "dry_run", False):
        if not star_gate_lib.check_star_gate():
            return 1

    # تحقق وسائط run — بعد البوابتين عمدًا (جولة v0.1.48):
    # حتى يُقيَّم فحص النجمة ويُطبع تحذير fail-open قبل الخروج
    # برمز 2 عند نقص الوسائط، بدل تجاوز البوابة بصمت.
    if args.cmd == "run":
        if args.demo and (args.story or args.project):
            print(i18n_lib.t("main_demo_conflict", lang))
            return 2
        if not args.demo and not (args.story and args.project and args.out):
            print(i18n_lib.t("main_run_needs", lang))
            return 2

    if args.cmd == "doctor":
        return cmd_doctor(cfg, fix=args.fix, accounts_flag=args.accounts,
                          llm_flag=args.llm, lang=lang,
                          as_json=bool(getattr(args, "json", False)))
    # أوامر الموجة ب (جولة v0.1.63) — أغلفة رقيقة فوق وحدات الموجة أ.
    _out = _new_output(args)
    if args.cmd == "approval":
        return cmd_approval(args, _out)
    if args.cmd == "team":
        return cmd_team(cfg, args, _out)
    if args.cmd == "routines":
        return cmd_routines(cfg, args, _out)
    if args.cmd == "check-back":
        return cmd_check_back(cfg, args, _out)
    if args.cmd == "usage":
        return cmd_usage_caps(cfg, args, _out)
    if args.cmd == "models":
        return cmd_models(args, _out)
    if args.cmd == "round-pack":
        return cmd_round_pack(cfg, args, _out)
    if args.cmd == "handoffs":
        return cmd_handoffs(cfg, args, _out)
    if args.cmd == "keys":
        return cmd_keys(args, _out)
    if args.cmd == "sentinel":
        return cmd_sentinel(cfg, args, _out)
    if args.cmd == "control":
        return cmd_control(cfg, args, _out)
    if args.cmd == "inspect":
        return cmd_inspect(cfg, args, _out)
    if args.cmd == "read-log":
        return cmd_read_log(cfg, args, _out)
    if args.cmd == "search-log":
        return cmd_search_log(cfg, args, _out)
    if args.cmd == "send-work":
        return cmd_send_work(cfg, args, _out)
    if args.cmd == "wait-job":
        return cmd_wait_job(cfg, args, _out)
    if args.cmd == "interrupt-job":
        return cmd_interrupt_job(cfg, args, _out)
    if args.cmd == "switch-model":
        return cmd_switch_model(args, _out)
    if args.cmd == "wait":
        return cmd_wait(cfg, args, _out)
    if args.cmd == "events":
        return cmd_events(cfg, args, _out)
    if args.cmd == "brief":
        return cmd_brief(cfg, args, _out)
    if args.cmd == "workers":
        return cmd_workers(cfg, args, _out)
    if args.cmd == "export":
        return cmd_export_job(cfg, args, _out)
    if args.cmd == "features":
        return cmd_features(args, _out)
    if args.cmd == "triage":
        return cmd_triage(cfg, args, _out)
    if args.cmd == "recipe":
        return cmd_recipe(cfg, args, _out)
    if args.cmd == "webhook":
        return cmd_webhook(cfg, args, _out)
    if args.cmd == "setup":
        return cmd_setup(args, _out)
    if args.cmd == "router":
        return cmd_router_test(args, _out)
    if args.cmd == "llm-status":
        return cmd_llm_status(cfg, lang=lang)
    if args.cmd == "debug-config":
        return cmd_debug_config(args.profile, args.set)
    if args.cmd == "protect":
        return cmd_protect(cfg)
    if args.cmd == "manifest":
        return cmd_manifest(cfg, args.video, title=args.title,
                            hook=args.hook, story=args.story)
    if args.cmd == "avatar-job":
        return cmd_avatar_job(cfg, args)
    if args.cmd == "check":
        return cmd_check(cfg, args.video, long_mode=args.long,
                         as_json=args.json, captions_dir=args.captions,
                         avatar_image=args.avatar_image,
                         aspect_policy=args.aspect_policy)
    if args.cmd == "fix-audio":
        return cmd_fix_audio(cfg, args.video,
                             scene_audio=args.scene_audio or None,
                             out_path=args.out,
                             denoise=args.denoise,
                             loudnorm=args.loudnorm)
    if args.cmd == "grade":
        if not args.list_presets and not args.video:
            print("لازم --video (أو --list-presets لعرض المتاح)")
            return 2
        if not args.list_presets and not args.preset:
            print("لازم --preset (أو --list-presets لعرض المتاح)")
            return 2
        return cmd_grade(cfg, args.video, args.preset,
                         out_path=args.out,
                         list_presets=args.list_presets)
    if args.cmd == "srt-ass":
        return cmd_srt_ass(cfg, args.srt, args.out,
                           font_size=args.font_size)
    if args.cmd == "init":
        return cmd_init(cfg, args)
    if args.cmd == "status":
        return cmd_status(cfg, lang=lang)
    if args.cmd == "script":
        run_dir = None
        result, _ = cmd_script(cfg, args.story, args.allow_fallback,
                               run_dir, lang=lang)
        return 0 if result else 1
    if args.cmd == "produce":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        if args.run_id:
            run_dir = run_dir_for(runs_dir, args.run_id)
            os.makedirs(run_dir, exist_ok=True)
        else:
            _, run_dir = new_run(runs_dir, args.project)
        try:
            cmd_produce(cfg, args.project, run_dir)
        except openmontage_stage.StageError as e:
            print("فشل التجهيز: %s" % e)
            return 1
        except Exception as e:
            print("فشل التجهيز بخطأ غير متوقع: %s" % e)
            return 1
        print("مجلد التشغيل: %s" % run_dir)
        return 0
    if args.cmd == "assemble":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        run_dir = run_dir_for(runs_dir, args.run_id)
        script_path = os.path.join(run_dir, "script-ai.json")
        if not os.path.isfile(script_path):
            print("لا يوجد تشغيل بهذا المعرّف أو لم يُولَّد سيناريو له: %s"
                  % run_dir)
            return 1
        try:
            with open(script_path, encoding="utf-8") as f:
                title = json.load(f)["title"]
        except (ValueError, KeyError) as e:
            print("ملف السيناريو تالف أو بلا عنوان (%s): %s"
                  % (script_path, e))
            return 1
        if not title:
            print("عنوان السيناريو فارغ في %s — أعد توليد السيناريو أولًا"
                  % script_path)
            return 1
        try:
            if args.backend == "headless":
                cmd_assemble_headless(cfg, run_dir, title, expand(args.out),
                                      not args.no_watermark,
                                      expand(args.cards_dir)
                                      if args.cards_dir else None,
                                      args.grade)
            elif args.backend == "mlt":
                cmd_assemble_mlt(cfg, run_dir, title, expand(args.out),
                                 not args.no_watermark,
                                 expand(args.cards_dir)
                                 if args.cards_dir else None,
                                 args.grade)
            elif args.backend == "openreel":
                cmd_assemble_openreel(cfg, run_dir, title,
                                      expand(args.out),
                                      not args.no_watermark,
                                      expand(args.cards_dir)
                                      if args.cards_dir else None,
                                      args.grade)
            else:
                sfx_events = []
                for spec in args.sfx or []:
                    if "@" not in spec:
                        print("صيغة --sfx خاطئة: %s — الصيغة NAME@SECONDS "
                              "(مثال: whoosh@2.5)" % spec)
                        return 2
                    name, _, at = spec.rpartition("@")
                    try:
                        seconds = float(at)
                    except ValueError:
                        print("صيغة --sfx خاطئة: %s — الزمن يجب أن يكون "
                              "رقمًا بالثواني (مثال: whoosh@2.5)" % spec)
                        return 2
                    if not name or seconds < 0:
                        print("صيغة --sfx خاطئة: %s — الاسم فارغ أو "
                              "الزمن سالب (مثال: whoosh@2.5)" % spec)
                        return 2
                    sfx_events.append((name, seconds))
                cmd_assemble(cfg, run_dir, title, expand(args.out),
                             not args.no_watermark,
                             expand(args.cards_dir)
                             if args.cards_dir else None,
                             args.grade,
                             sfx_events=sfx_events,
                             overlays=args.overlay,
                             assets_dir=expand(args.assets_dir)
                             if args.assets_dir else None,
                             no_title=args.no_title)
        except concat_mcp.ConcatError as e:
            _print_translated("فشل التجميع", e, "assemble")
            return 1
        except headless_stage.HeadlessError as e:
            print("فشل التجميع عبر headless-editor: %s" % e)
            return 1
        except mlt_stage.MltError as e:
            print("فشل التجميع عبر MLT/melt: %s" % e)
            return 1
        except openreel_lib.OpenReelError as e:
            print("فشل التجميع عبر OpenReel: %s" % e)
            return 1
        except lut_grade_lib.LutError as e:
            print("فشل التدرج اللوني: %s" % e)
            return 1
        except watermark.WatermarkError as e:
            print("فشل الإنهاء (شعار/بطاقات): %s" % e)
            return 1
        return 0
    if args.cmd == "clean-audio":
        try:
            cmd_clean_audio(cfg, expand(args.input), expand(args.out),
                            args.threshold, args.margin, args.force)
        except autoedit.AutoEditError as e:
            print("فشل تنظيف الصوت: %s" % e)
            return 1
        return 0
    if args.cmd == "fx":
        try:
            cmd_fx(cfg, expand(args.image), expand(args.out),
                   args.duration, args.text, args.audio,
                   args.zoom_to, args.fontsize)
        except moviepy_fx.MoviePyFxError as e:
            print("فشل التركيب: %s" % e)
            return 1
        return 0
    if args.cmd == "karaoke-ass":
        try:
            cmd_karaoke_ass(cfg, expand(args.audio), expand(args.out),
                            args.model, args.max_chars, lang=eff_lang)
        except capite_captions.CapiteError as e:
            print("فشل توليد الكاريوكي: %s" % e)
            return 1
        except latin_captions.LatinCaptionError as e:
            print("فشل توليد الكابشن اللاتيني: %s" % e)
            return 1
        except whisper_captions.WhisperError as e:
            print("فشل النسخ: %s" % e)
            return 1
        return 0
    if args.cmd == "trim":
        try:
            cmd_trim(cfg, expand(args.input), expand(args.out),
                     args.start, args.end, args.duration, args.exact)
        except trim.TrimError as e:
            print("فشل القص: %s" % e)
            return 1
        return 0
    if args.cmd == "thumbnail":
        runs_dir = expand(cfg["paths"]["runs_dir"])
        video_path, hook = args.video, args.hook
        if args.run_id:
            run_dir = run_dir_for(runs_dir, args.run_id)
            log_path = os.path.join(run_dir, "run-log.json")
            script_path = os.path.join(run_dir, "script-ai.json")
            if not os.path.isdir(run_dir):
                print("لا يوجد تشغيل بهذا المعرّف: %s" % run_dir)
                return 1
            try:
                with open(log_path, encoding="utf-8") as f:
                    video_path = (json.load(f)["steps"]["assemble"]
                                  ["output"])
            except (OSError, ValueError, KeyError) as e:
                print("تعذر قراءة مسار الفيديو من سجل التشغيل (%s)" % e)
                return 1
            if not hook:
                try:
                    with open(script_path, encoding="utf-8") as f:
                        hook = json.load(f)["title"]
                except (OSError, ValueError, KeyError) as e:
                    print("تعذر قراءة الهوك من السيناريو (%s)" % e)
                    return 1
        if not video_path or not hook:
            print("لازم --video و--hook، أو --run لتشغيل سابق")
            return 1
        if not args.out:
            base = os.path.splitext(os.path.basename(video_path))[0]
            suffix = ("-long-thumbnail.jpg" if args.long
                      else "-thumbnail.jpg")
            out_path = os.path.join(expand(cfg["paths"]["videos_dir"]),
                                    base + suffix)
        else:
            out_path = expand(args.out)
        width, height = thumbnail.WIDTH, thumbnail.HEIGHT
        fontsize, margin_v, max_chars = (thumbnail.FONTSIZE,
                                         thumbnail.MARGIN_V, 20)
        if args.long:
            width, height = thumbnail.LONG_WIDTH, thumbnail.LONG_HEIGHT
            fontsize, margin_v, max_chars = (thumbnail.LONG_FONTSIZE,
                                             thumbnail.LONG_MARGIN_V,
                                             thumbnail.LONG_MAX_CHARS)
        if args.size:
            try:
                width, height = parse_size(args.size)
            except ValueError as e:
                print("مقاس غير صالح --size: %s" % e)
                return 2
            if (width, height) == (thumbnail.LONG_WIDTH,
                                   thumbnail.LONG_HEIGHT):
                fontsize, margin_v, max_chars = (thumbnail.LONG_FONTSIZE,
                                                 thumbnail.LONG_MARGIN_V,
                                                 thumbnail.LONG_MAX_CHARS)
        try:
            cmd_thumbnail(cfg, expand(video_path), hook, out_path,
                          args.time, width=width, height=height,
                          fontsize=fontsize, margin_v=margin_v,
                          max_chars=max_chars)
        except thumbnail.ThumbnailError as e:
            print("فشل توليد الصورة المصغرة: %s" % e)
            return 1
        return 0
    if args.cmd == "whisper-ass":
        # خيار تجريبي: يعمل فقط من بيئة faster-whisper
        # (.venv-whisper) — انظر WHISPER-TEST.md. لا يمس خط
        # silencedetect الافتراضي، ولا يُستخدم حين يختلف النص
        # المعروض عن النص المنطوق.
        try:
            phrases, text = whisper_captions.whisper_ass(
                expand(args.audio), expand(args.out), model=args.model,
                max_words=args.max_words, max_gap=args.max_gap,
                font_size=args.font_size)
        except whisper_captions.WhisperError as e:
            print("فشل توليد الكابشنات: %s" % e)
            return 1
        print("كُتب %d عبارة في %s" % (len(phrases), expand(args.out)))
        print("النص المسموع: %s" % text)
        print("راجع النص قبل النشر — حتى موديل small يخطئ في ~22% "
              "من كلمات سرد Piper (WHISPER-TEST.md).")
        return 0
    if args.cmd == "run":
        if args.demo:
            try:
                # التجربة تعمل بخلفية headless دائمًا (المسار المجاني)
                # — لا يُمرَّر افتراضي --backend (concat) هنا.
                cmd_demo(cfg, args.out)
            except demo.DemoError as e:
                print("فشلت التجربة: %s" % e)
                return 1
            except headless_stage.HeadlessError as e:
                print("فشل ريندر التجربة: %s" % e)
                return 1
            except long_narration.LongNarrationError as e:
                print("فشل سرد التجربة: %s" % e)
                return 1
            except watermark.WatermarkError as e:
                print("فشل إنهاء التجربة (شعار): %s" % e)
                return 1
            return 0
        return cmd_run(cfg, args.story, args.project,
                       expand(args.out) if args.out else None,
                       args.allow_fallback, args.dry_run, args.backend,
                       not args.no_watermark,
                       expand(args.cards_dir) if args.cards_dir else None,
                       args.grade, lang=eff_lang, resume=args.resume,
                       voice=args.voice)
    if args.cmd == "quick":
        return cmd_quick(cfg, args.title, lang=eff_lang,
                         voice=args.voice,
                         out_path=expand(args.out) if args.out else None,
                         dry_run=args.dry_run,
                         allow_fallback=args.allow_fallback,
                         publish=args.publish)
    if args.cmd == "expand-motion-prompts":
        return cmd_expand_motion_prompts(cfg, args.prompts, args.out)
    if args.cmd == "seo-check":
        return cmd_seo_check(cfg, args.title, args.description,
                             args.tags, story_file=args.story_file,
                             as_json=args.json)
    if args.cmd == "title-lint":
        return cmd_title_lint(cfg, title=args.title, thumb=args.thumb,
                              titles_file=args.titles_file,
                              as_json=args.json)
    if args.cmd == "hook-score":
        return cmd_hook_score(cfg, hook=args.hook,
                              hook_file=args.hook_file,
                              story_file=args.story_file,
                              as_json=args.json)
    if args.cmd == "viral-rank":
        return cmd_viral_rank(cfg, args.videos_file, top=args.top,
                              as_json=args.json)
    if args.cmd == "retention-read":
        return cmd_retention_read(cfg, args.csv, duration=args.duration,
                                  transcript_file=args.transcript,
                                  as_json=args.json)
    if args.cmd == "channel-audit":
        return cmd_channel_audit(cfg, args.titles_file,
                                 hooks_file=args.hooks_file,
                                 thumb_texts_file=args.thumb_texts_file,
                                 dates_file=args.dates_file,
                                 retention_csv=args.retention_csv,
                                 duration=args.duration,
                                 title=args.title,
                                 description=args.description,
                                 tags=args.tags,
                                 as_json=args.json)
    if args.cmd == "trend-scout":
        return cmd_trend_scout(cfg, args.videos_file, top_n=args.top_n,
                               as_json=args.json)
    if args.cmd == "scene-shorts":
        return cmd_scene_shorts(cfg, args.video, args.scenes_file,
                                out_dir=args.out, phrases=args.phrases,
                                full_hook=args.full_hook or "",
                                as_json=args.json)
    if args.cmd == "tiktok-check":
        return cmd_tiktok_check(cfg, args.title, args.caption,
                                hook=args.hook, moral=args.moral or "",
                                story_file=args.story_file,
                                queue_file=args.queue_file,
                                needed=args.needed,
                                trend_keywords=args.trend_keywords,
                                as_json=args.json)
    if args.cmd == "script-check":
        return cmd_script_check(cfg, args.script, as_json=args.json,
                                timed_phrases=args.timed_phrases,
                                narration_audio=args.narration_audio,
                                narration_wpm=args.narration_wpm,
                                narration_duration=args.narration_duration)
    if args.cmd == "topic-brief":
        return cmd_topic_brief(cfg, theme=args.theme, input_file=args.input,
                               candidates_file=args.candidates_file,
                               queue_file=args.queue_file,
                               as_json=args.json)
    if args.cmd == "hook-title":
        return cmd_hook_title(cfg, args.video, args.title, out=args.out,
                              as_json=args.json, force=args.force)
    if args.cmd == "reliability-report":
        return cmd_reliability_report(cfg, args.runs_json,
                                      window_days=args.window_days,
                                      as_json=args.json)
    if args.cmd == "failure-classify":
        return cmd_failure_classify(cfg, text=args.text, file=args.file,
                                    as_json=args.json)
    if args.cmd == "incident-probe":
        return cmd_incident_probe(cfg, args.context_json, mask=args.mask,
                                  mapping_out=args.mapping_out,
                                  as_json=args.json)
    if args.cmd == "id-mask":
        return cmd_id_mask(cfg, text=args.text, file=args.file,
                           mapping_out=args.mapping_out,
                           redact=args.redact, unmask=args.unmask,
                           mapping_file=args.mapping, as_json=args.json)
    if args.cmd == "runbook-check":
        return cmd_runbook_check(cfg, runbook=args.runbook,
                                 runbook_file=args.runbook_file,
                                 root=args.root, as_json=args.json)
    if args.cmd == "failure-drill":
        return cmd_failure_drill(cfg, drill=args.drill,
                                 all_drills=args.all,
                                 workdir=args.workdir, keep=args.keep,
                                 as_json=args.json)
    if args.cmd == "keyword-analyze":
        return cmd_keyword_analyze(cfg, keyword=args.keyword,
                                   metrics_json=args.metrics_json,
                                   keywords_json=args.keywords_json,
                                   as_json=args.json)
    if args.cmd == "content-optimize":
        return cmd_content_optimize(cfg, title=args.title,
                                    keyword=args.keyword,
                                    body_file=args.body_file,
                                    description=args.description,
                                    phrases_json=args.phrases_json,
                                    as_json=args.json)
    if args.cmd == "keyword-generate":
        return cmd_keyword_generate(cfg, seed=args.seed,
                                    corpus_json=args.corpus_json,
                                    limit=args.limit, as_json=args.json)
    if args.cmd == "micro-niche":
        return cmd_micro_niche(cfg, niches_json=args.niches_json,
                               library_json=args.library_json,
                               as_json=args.json)
    if args.cmd == "page-analyze":
        return cmd_page_analyze(cfg, page_json=args.page_json,
                                as_json=args.json)
    if args.cmd == "fresh-keywords":
        return cmd_fresh_keywords(cfg, trends_json=args.trends_json,
                                  days=args.days, today=args.today,
                                  as_json=args.json)
    if args.cmd == "topical-authority":
        return cmd_topical_authority(cfg, library_json=args.library_json,
                                     topics_json=args.topics_json,
                                     as_json=args.json)
    if args.cmd == "version":
        return cmd_version()
    if args.cmd == "license":
        print("\n".join(license_lib.status_lines()))
        return 0
    if args.cmd == "request":
        if bool(args.text) == bool(args.text_file):
            print("اكتب الطلب نصًا أو مرّر --text-file (أحدهما فقط)")
            return 2
        text = args.text
        if args.text_file:
            try:
                with open(expand(args.text_file), encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                print("تعذّر قراءة ملف الطلب: %s" % e)
                return 2
        try:
            result = request_flow.request_to_run(
                cfg, text, _request_chat_fn(cfg),
                expand(args.out) if args.out else None,
                run_fn=_request_run_fn(cfg), project=args.project,
                dry_run=args.dry_run, allow_fallback=args.allow_fallback)
        except request_flow.UsageCapError as e:
            # قرار موثّق (عقد ع1): لا رمز خروج 429/409 في ع1؛
            # فالرفع يرجع 1 (فشل) مع طباعة الحالة (429/409)
            # والرمز spend_cap ومهلة إعادة الضبط ليقرأها
            # السكربت — و4 مرفوض لأنه يعني في ع1 «يحتاج تسجيل
            # دخول/مهلة» لا «بُلغ حد إنفاق».
            print(str(e))
            print("الحالة: %s — الرمز: %s%s"
                  % (e.status, e.code,
                     (" — إعادة الضبط بعد %s ثانية" % e.retry_after)
                     if e.retry_after is not None else ""))
            return 1
        except request_flow.RequestFlowError as e:
            print(str(e))
            code = getattr(e, "exit_code", 1)
            if code not in (0, 1, 2, 3, 4, 5, 6, 7, 8, 130):
                code = 1
            return code
        except ValueError as e:
            print(str(e))
            return 2
        if result["status"] == "done":
            print("اكتمل الفيديو: %s" % result.get("output"))
        elif result["status"] == "queued":
            print("حُفظت القصة في الطابور (رقم %s) بلا مشروع جاهز — "
                  "جهّز مشروع OpenMontage ثم شغّل run"
                  % result.get("queue_number"))
        return 0
    if args.cmd == "publish":
        if args.preflight:
            return cmd_publish_preflight(cfg, args.video, args.title,
                                         args.caption, tags=args.tags,
                                         ai_voice=args.ai_voice)
        platforms = [pl.strip() for pl in args.platforms.split(",")
                     if pl.strip()]
        bad = [pl for pl in platforms
               if pl not in ("facebook", "youtube", "tiktok",
                             "instagram")]
        if bad:
            print(i18n_lib.t("publish_unknown_platforms", lang,
                             ", ".join(bad)))
            return 2
        if not platforms:
            print(i18n_lib.t("publish_need_platform", lang))
            return 2
        tags = ([t.strip() for t in args.tags.split(",") if t.strip()]
                if args.tags else None)
        schedule = None
        if args.schedule:
            try:
                schedule = publish.parse_schedule(args.schedule)
            except publish.PublishError as e:
                print(i18n_lib.t("publish_schedule_error", lang, e))
                return 2
        return cmd_publish(cfg, args.video, args.title, args.caption,
                           thumbnail=args.thumbnail, platforms=platforms,
                           page_id=args.page_id, schedule=schedule,
                           privacy=args.privacy, tags=tags,
                           dry_run=args.dry_run,
                           skip_check=args.skip_check,
                           skip_caption_check=args.skip_caption_check,
                           allow_missing_manifest=(
                               args.allow_missing_manifest),
                           generate_meta=args.generate_meta,
                           part=args.part, parts=args.parts, lang=lang,
                           ai_voice=args.ai_voice)
    if args.cmd == "youtube-auth":
        return cmd_youtube_auth(cfg, args.client_secrets, args.token)
    if args.cmd == "youtube-reauth":
        return cmd_youtube_reauth(cfg, args.client_secrets, args.token)
    if args.cmd == "long-video":
        try:
            return cmd_long_video(cfg, args, lang=lang)
        except long_video.LongVideoError as e:
            print("فشل الفيديو الطويل: %s" % e)
            return 1
        except long_narration.LongNarrationError as e:
            print("فشل سرد الفيديو الطويل: %s" % e)
            return 1
    if args.cmd == "help-ar":
        help_ar.print_help()
        return 0
    if args.cmd == "queue":
        if args.queue_cmd == "add":
            return cmd_queue_add(cfg, args.title, args.text_file,
                                 parts=args.parts, note=args.note,
                                 queue_file=args.queue_file)
        if args.queue_cmd == "import":
            return cmd_queue_import(cfg, args.file, args.title,
                                    queue_file=args.queue_file,
                                    start=args.start)
        if args.queue_cmd == "validate":
            return cmd_queue_validate(cfg, queue_file=args.queue_file)
        if args.queue_cmd == "publish-status":
            return cmd_queue_publish_status(
                cfg, args.number, args.platform, args.status,
                queue_file=args.queue_file)
        if args.queue_cmd == "publish-summary":
            return cmd_queue_publish_summary(
                cfg, queue_file=args.queue_file)
        if args.queue_cmd == "pending":
            return cmd_queue_pending(cfg, args.platform,
                                     queue_file=args.queue_file)
        return 2
    if args.cmd == "analyze":
        if args.snapshot:
            return cmd_analyze_snapshot(cfg)
        return cmd_analyze(cfg, page_id=args.page_id,
                           channel_id=args.channel_id, dna=args.dna,
                           video=args.video, hook=args.hook,
                           subs_dir=args.subs_dir,
                           story_text=args.story_text,
                           slug=args.slug,
                           reference=args.reference,
                           story=args.story,
                           audio_profile=args.audio_profile)
    if args.cmd == "long-narration":
        try:
            cmd_long_narration(cfg, args.text, args.text_file,
                               args.out, args.gap, args.atempo,
                               voice=args.voice or _default_voice(cfg),
                               lang=eff_lang)
        except long_narration.LongNarrationError as e:
            print("فشل السرد الطويل: %s" % e)
            return 1
        except OSError as e:
            print("فشل قراءة ملف النص: %s" % e)
            return 1
        except ValueError as e:
            print(str(e))
            return 2
        return 0
    if args.cmd == "quote-cards":
        try:
            paths = watermark.generate_quote_cards(
                args.ibra, args.hikma, args.mawiza, args.mawiza_source,
                expand(args.out_dir))
        except watermark.WatermarkError as e:
            print("فشل توليد البطاقات: %s" % e)
            return 1
        for pth in paths:
            print("بطاقة: %s" % pth)
        return 0
    if args.cmd == "run-queue":
        return cmd_run_queue(cfg, limit=args.limit,
                             continue_on_error=args.continue_on_error,
                             dry_run=args.dry_run,
                             allow_fallback=args.allow_fallback)
    if args.cmd == "analyze-ref":
        return cmd_analyze_ref(cfg, args.url, model=args.model)
    if args.cmd == "client-run":
        import client_orders
        return client_orders.cmd_client_run(cfg, args.order)
    if args.cmd == "process-queue":
        import client_orders
        return client_orders.cmd_process_queue(cfg)
    if args.cmd == "orders":
        import client_orders
        if args.orders_cmd == "confirm":
            return client_orders.cmd_confirm_payment(cfg, args.order_id,
                                                     confirmed_by=args.by)
        if args.orders_cmd == "list":
            return client_orders.cmd_list_orders(status=args.status)
        if args.orders_cmd == "trial":
            return client_orders.cmd_trial_status(args.whatsapp)
    if args.cmd == "ideas":
        return cmd_ideas(cfg, count=args.count, theme=args.theme,
                         add=args.add, queue_file=args.queue_file)
    if args.cmd == "daily":
        return cmd_daily(cfg, slot=args.slot,
                         execute=args.execute and not args.dry_run,
                         video=args.video, moral=args.moral,
                         question=args.question,
                         queue_file=args.queue_file,
                         auto_approve=args.auto_approve,
                         backend=args.backend, grade=args.grade)
    if args.cmd == "schedule":
        if not args.watch:
            ap.error("الأمر schedule يحتاج --watch")
        return cmd_schedule_watch(cfg, post_id=args.post_id,
                                  story_slug=args.story,
                                  slot=args.slot,
                                  moral=args.moral,
                                  question=args.question,
                                  next_part_time=args.next_part_time,
                                  execute=args.execute)
    if args.cmd == "batch":
        return cmd_batch(cfg, count=args.count, source=args.source,
                         execute=args.execute,
                         continue_on_error=args.continue_on_error,
                         queue_file=args.queue_file,
                         from_json=args.from_json,
                         no_spend=args.no_spend,
                         no_cache=args.no_cache)
    if args.cmd == "scene-plan":
        return cmd_scene_plan(cfg, story=args.story,
                              clips=args.clips,
                              queue_file=args.queue_file,
                              template=args.template,
                              template_hero=args.hero,
                              template_situation=args.situation,
                              template_moral=args.moral,
                              lang=lang,
                              template_lang=args.template_lang)
    if args.cmd == "tiktok-auth":
        return cmd_social_auth(cfg, "tiktok", token=args.token)
    if args.cmd == "instagram-auth":
        return cmd_social_auth(cfg, "instagram", token=args.token)
    if args.cmd == "tiktok-bundle":
        return cmd_tiktok_bundle(
            cfg, args.video, args.title, caption=args.caption,
            moral=args.moral, next_part=args.next_part,
            next_part_time=args.next_part_time, ai_voice=args.ai_voice,
            out_dir=args.out_dir, dry_run=args.dry_run)
    if args.cmd == "tiktok-status":
        return cmd_tiktok_status(cfg)
    if args.cmd == "tiktok-long":
        return cmd_tiktok_long(
            cfg, args.video_a, args.video_b, args.title,
            caption=args.caption, moral=args.moral, kind=args.kind,
            out_dir=args.out_dir, max_seconds=args.max_seconds,
            dry_run=args.dry_run, part_tags=args.part_tags)
    if args.cmd == "ab":
        if args.eval_set:
            return cmd_ab_eval_set(cfg, variants=args.variants,
                                   cost_per_video=args.cost_per_video)
        if not args.video:
            print("اختبار A/B يحتاج --video <ملف mp4> أو --eval-set")
            return 2
        return cmd_ab(cfg, args.video, args.hook_a, args.hook_b,
                      args.title, args.out_dir,
                      cost_per_video=args.cost_per_video,
                      variants=args.variants,
                      engine=args.engine,
                      balance_units=(cfg.get("veo") or {}).get(
                          "balance_units"),
                      ledger_entries=cost_ledger_lib.history(STUDIO_DIR))
    if args.cmd == "ab-results":
        return cmd_ab_results(cfg, args.ab_file)
    if args.cmd == "update":
        return cmd_update(cfg, dry_run=args.dry_run, repo=args.repo,
                          branch=args.branch)
    if args.cmd == "restore":
        if args.backup and args.file:
            print("حدد إما --backup أو --file، لا كليهما")
            return 1
        if args.backup:
            return cmd_restore_backup(cfg, args.backup,
                                      dry_run=args.dry_run, yes=args.yes)
        if args.file:
            return cmd_restore(cfg, args.file)
        print("حدد ملف النسخة: --backup <ملف.zip> أو --file <ملف.zip>")
        return 1
    if args.cmd == "backup":
        return cmd_backup(cfg, args.out_dir, keep=args.keep)
    if args.cmd == "preview":
        return cmd_preview(cfg, args.video, caption=args.caption,
                           first_comment=args.first_comment,
                           out_dir=args.out_dir, title=args.title)
    if args.cmd == "logs":
        return cmd_logs(cfg, today=not args.all_logs,
                        limit=args.limit)
    if args.cmd == "balance":
        return cmd_balance(cfg, balance=args.balance, renew=args.renew,
                           cost_min=args.cost_min,
                           cost_max=args.cost_max,
                           record=args.record, video=args.video,
                           clips=args.clips,
                           history_flag=args.history,
                           cap=args.cap,
                           set_balance=args.set_balance)
    if args.cmd == "jobs":
        if args.jobs_cmd == "list":
            return cmd_jobs_list(cfg, status=args.status,
                                 story=args.story, date=args.date,
                                 kind=args.kind, limit=args.limit)
        if args.jobs_cmd == "show":
            return cmd_jobs_show(cfg, args.job_id)
        return 2
    if args.cmd == "reframe":
        return cmd_reframe(cfg, args.video, args.out,
                           focus_x=args.focus_x,
                           safety_margin=args.safety_margin)
    if args.cmd == "shorts-cut":
        return cmd_shorts_cut(cfg, args.video, out_dir=args.out,
                              count=args.count, phrases=args.phrases,
                              min_len=args.min_len, max_len=args.max_len)
    return 0


if __name__ == "__main__":
    sys.exit(main())
