#!/usr/bin/env python3
"""ثنائية اللغة للـCLI — `lib/i18n.py` (الجولة v0.1.41).

العربي هو الافتراضي دائمًا: أي تشغيل بلا `--lang` وبلا LANG
يتصرف كما اليوم حرفيًا (كل رسالة عربية كما كانت). الإنجليزي
اختياري صريح فقط:

- `--lang ar|en` على مستوى التطبيق (`python3 studio.py
  --lang en status`) — يغلب كل شيء.
- متغيرا البيئة LANG / LANGUAGE (مثال `LANG=en_US.UTF-8`) —
  تُقرأ البادئة قبل `_`/`.`/`-`؛ وقيم مثل C/POSIX أو لغة
  غير مدعومة تعني العربي.
- مفتاح `lang:` في config.yaml (اختياري) — يُقرأ إن غاب
  المفتاح والمتغير معًا.

`detect_lang(cli=None, env=None, config=None)` يحسم اللغة
بهذا الترتيب. `t(key, lang, *args)` يرجع الرسالة المترجمة
(تنسيق `%` بالوسائط)؛ ومفتاح مجهول يرجع نصه العربي كما هو
(بلا رفع أبدًا — الأمان أولًا في مسار الطباعة).

تغطية هذه الجولة (انظر `COVERED` / `NOT_COVERED` أدناه):
الأوامر والرسائل الأكثر ظهورًا — status وdoctor (سطري
الغلاف فقط) وllm-status وpublish (البوابات ونتائج المنصات)
وrun (التحقق والوضع التجريبي وبدء/اكتمال التشغيل) وscene-plan
(أخطاؤه) وخطأ «فشلت كل مزودات الذكاء» (عبر
`translate_llm_all_failed`). باقي رسائل studio.py ورسائل
المكتبات (doctor وllm_state وerrors وcaption_check
وpublish_meta وcheck ...) تبقى عربية في هذه الجولة — موثقة
في `NOT_COVERED`.

الصوت (الراوي الإنجليزي الذكوري): سجل `PIPER_VOICES` —
العربي ar_JO-kareem-medium (الافتراضي دائمًا) والإنجليزي
en_US-ryan-medium (ذكوري أمريكي، مؤكد من توثيق Piper:
Ryan male / Lessac female / Alan male؛ و`en_US-lessac-medium`
أنثى فلا تصلح راويًا). `voice_model_for_lang` /
`voice_model_path` / `voice_available` /
`voice_download_url` (مصدر Piper العام على HuggingFace،
بلا مصادقة). الملف الإنجليزي نُزّل وتحقَّق منه حيًا في
2026-11-23 (`~/workspace/tts-models/en_US-ryan-medium.onnx`
63,221,984 بايت + json؛ وPiper ركّب منه جملة إنجليزية
3.44 ثانية). التوصيل الفعلي للسرد الإنجليزي في
`lib/long_narration.py` خارج هذه الحزمة — بقي خيارًا
موثقًا هنا يُفحص وجود ملفه فقط.
"""
import os
import re

SUPPORTED_LANGS = ("ar", "en")
DEFAULT_LANG = "ar"

# الأوامر/الرسائل المغطاة بالإنجليزي في هذه الجولة.
COVERED = (
    "status", "doctor (wrapper lines only)", "llm-status",
    "publish (gates + platform results + dry-run header)",
    "run (validation + dry-run + start/done + unknown backend)",
    "scene-plan (errors)", "LLM all-providers-failed error",
    "main dispatch validation errors", "--lang / LANG detection",
)
# ما لم يُغطَّ بعد (يبقى عربيًا): أجسام تقارير doctor وllm_state،
# ورسائل lib/errors.py، وفحوص check/caption_check، وبيانات
# publish_meta المولدة، وhelp_ar، وباقي الأوامر.
NOT_COVERED = (
    "doctor report body (lib/doctor.py)",
    "llm_state.status_lines (lib/llm_state.py)",
    "lib/errors.py messages", "check / caption_check reports",
    "publish_meta generated text", "help_ar",
    "all other commands' prints",
)

# --- أصوات Piper للراوي (ذكورية فقط — قاعدة الخط: الراوي رجل) ---
PIPER_VOICES_BASE = ("https://huggingface.co/rhasspy/piper-voices"
                     "/resolve/main")
PIPER_VOICES = {
    "ar": {"model": "ar_JO-kareem-medium",
           "gender": "male",
           "locale": "ar_JO",
           "lang_dir": "ar",
           "voice_dir": "kareem",
           "quality": "medium",
           "language_name": "Arabic"},
    "en": {"model": "en_US-ryan-medium",
           "gender": "male",
           "locale": "en_US",
           "lang_dir": "en",
           "voice_dir": "ryan",
           "quality": "medium",
           "language_name": "English (US)"},
}
PIPER_MODELS_DIR = os.path.expanduser("~/workspace/tts-models")


def voice_model_for_lang(lang="ar"):
    """اسم موديل Piper للراوي بلغة معطاة (العربي افتراضيًا)."""
    lang = normalize_lang(lang)
    return PIPER_VOICES[lang]["model"]


def voice_download_url(lang="ar", ext=".onnx"):
    """رابط التنزيل العام لموديل Piper (HuggingFace — بلا مصادقة)."""
    lang = normalize_lang(lang)
    voice = PIPER_VOICES[lang]
    name = voice["model"] + ext
    return ("%s/%s/%s/%s/%s/%s"
            % (PIPER_VOICES_BASE, voice["lang_dir"], voice["locale"],
               voice["voice_dir"], voice["quality"], name))


def voice_model_path(lang="ar", models_dir=None):
    """المسار المتوقع لملف موديل Piper بلغة معطاة."""
    base = models_dir or PIPER_MODELS_DIR
    return os.path.join(os.path.expanduser(str(base)),
                        voice_model_for_lang(lang) + ".onnx")


def voice_available(lang="ar", models_dir=None):
    """هل ملف موديل Piper للغة موجود على القرص؟"""
    return os.path.isfile(voice_model_path(lang, models_dir))


def resolve_voice_model(cfg=None, lang="ar"):
    """موديل Piper من الإعداد (narration.piper_model_ar/en)
    أو من السجل الافتراضي؛ يرجع (الاسم، المسار المتوقع)."""
    lang = normalize_lang(lang)
    cfg_n = ((cfg or {}).get("narration") or {}
             if isinstance(cfg, dict) else {})
    key = "piper_model_%s" % lang
    name = cfg_n.get(key) or PIPER_VOICES[lang]["model"]
    path = os.path.join(PIPER_MODELS_DIR, str(name) + ".onnx")
    return name, path


def normalize_lang(value):
    """طبّع قيمة لغة إلى ar/en؛ وأي قيمة غير معروفة تعني ar."""
    if not isinstance(value, str):
        return DEFAULT_LANG
    head = re.split(r"[-_.:]", value.strip(), 1)[0].lower()
    return head if head in SUPPORTED_LANGS else DEFAULT_LANG


def _lang_from_env(env):
    """لغة من LANG/LANGUAGE (الأول المعروف) أو None."""
    env = os.environ if env is None else env
    for key in ("LANG", "LANGUAGE"):
        raw = env.get(key) if hasattr(env, "get") else None
        if not raw:
            continue
        # LANGUAGE قد تكون قائمة مفصولة بنقطتين: خذ أولها.
        for part in str(raw).split(":"):
            head = re.split(r"[-_.]", part.strip(), 1)[0].lower()
            if head in SUPPORTED_LANGS:
                return head
    return None


def detect_lang(cli=None, env=None, config=None):
    """حسم لغة CLI: --lang أولًا، ثم LANG/LANGUAGE، ثم
    مفتاح lang في الإعداد، ثم العربي دائمًا."""
    if isinstance(cli, str) and cli.strip():
        head = re.split(r"[-_.]", cli.strip(), 1)[0].lower()
        if head in SUPPORTED_LANGS:
            return head
    env_lang = _lang_from_env(env)
    if env_lang:
        return env_lang
    if isinstance(config, dict):
        cfg_lang = config.get("lang")
        if isinstance(cfg_lang, str) and cfg_lang.strip():
            head = re.split(r"[-_.]", cfg_lang.strip(), 1)[0].lower()
            if head in SUPPORTED_LANGS:
                return head
    return DEFAULT_LANG


# --- قاموس الرسائل: (العربية، الإنجليزية) ---
MESSAGES = {
    # status
    "status_llm_section": ("== OmniRoute (الذكاء) ==",
                           "== OmniRoute (AI) =="),
    "status_server_up": ("  الخادم يعمل على %s (HTTP %s)",
                         "  Server is up at %s (HTTP %s)"),
    "status_server_down": ("  الخادم لا يرد على %s: %s",
                           "  Server not responding at %s: %s"),
    "status_bind": ("  الربط: %s", "  Bind: %s"),
    "status_providers": ("  المزودون: %s", "  Providers: %s"),
    "status_no_providers": ("لا يوجد مزود مفعّل",
                            "no provider enabled"),
    "status_providers_error": ("  تعذر فحص المزودين: %s",
                               "  Could not list providers: %s"),
    "status_openmontage": ("== OpenMontage (الإنتاج) ==",
                           "== OpenMontage (production) =="),
    "status_concat": ("== Concat (التجميع) ==",
                      "== Concat (assembly) =="),
    "status_headless": ("== headless-editor (تجميع بديل) ==",
                        "== headless-editor (alternate assembly) =="),
    "status_mlt": ("== MLT/melt (تجميع بديل — تايم لاين XML) ==",
                   "== MLT/melt (alternate assembly — XML timeline) =="),
    "status_ffmpeg": ("== ffmpeg ==", "== ffmpeg =="),
    "status_memory": ("== الذاكرة ==", "== Memory =="),
    "status_exists": ("موجود", "exists"),
    "status_missing": ("غير موجود", "missing"),
    "status_available": ("متاح", "available"),
    "status_unavailable": ("غير متاح", "not available"),
    "status_melt_missing": ("غير متاح — sudo apt-get install -y melt",
                            "not available — sudo apt-get install -y melt"),
    "status_memory_free": ("  المتاح: %s ميجا",
                           "  Available: %s MB"),
    "status_loopback": ("127.0.0.1 فقط (loopback — آمن)",
                        "127.0.0.1 only (loopback — safe)"),
    "status_bind_warn": ("%s — تحذير: ليس loopback!",
                         "%s — warning: not loopback!"),
    "status_bind_unknown": ("غير معروف (الخادم متوقف أو بلا /proc/net/tcp)",
                            "unknown (server stopped or no /proc/net/tcp)"),
    # llm-status
    "llm_chain": ("سلسلة المزودين (بالترتيب):",
                  "Provider chain (in order):"),
    "llm_ollama_ok": ("Ollama: متاح — الموديل %s (ساق أخيرة محلية)",
                      "Ollama: available — model %s (last-resort local leg)"),
    "llm_ollama_down": ("Ollama: غير متاح — %s",
                        "Ollama: unavailable — %s"),
    "llm_ollama_down_default": ("الخادم متوقف أو الموديل غير مثبّت",
                                "server stopped or model not installed"),
    # doctor (سطري الغلاف فقط — جسم التقرير في lib/doctor.py عربي)
    "doctor_config_created": ("أُنشئ config.yaml من المثال",
                              "config.yaml created from the example"),
    "doctor_accounts_section": ("== فحوصات الحسابات (%d) ==",
                                "== Account checks (%d) =="),
    "doctor_llm_section": ("== فحوصات LLM (%d) ==",
                           "== LLM checks (%d) =="),
    # publish — البوابات والنتائج
    "publish_unknown_platforms": (
        "منصات غير معروفة: %s (المسموح: facebook,youtube,"
        "tiktok,instagram)",
        "Unknown platforms: %s (allowed: facebook,youtube,"
        "tiktok,instagram)"),
    "publish_need_platform": ("حدد منصة واحدة على الأقل في --platforms",
                              "Specify at least one platform in --platforms"),
    "publish_schedule_error": ("خطأ في موعد الجدولة: %s",
                               "Scheduling error: %s"),
    "publish_video_missing": ("ملف الفيديو غير موجود: %s",
                              "Video file not found: %s"),
    "publish_manifest_reject": ("رفض النشر: %s", "Publish refused: %s"),
    "publish_manifest_hint": (
        "ولّد البيان بـ: python3 studio.py manifest --video %s",
        "Generate the manifest with: python3 studio.py manifest --video %s"),
    "publish_manifest_allow": (
        "أو استخدم --allow-missing-manifest للتجاوز على مسؤوليتك",
        "Or use --allow-missing-manifest to override at your own risk"),
    "publish_manifest_warn": ("تحذير — بيان المصدر: %s",
                              "Warning — source manifest: %s"),
    "publish_schedule_past": (
        "موعد الجدولة في الماضي — يجب أن يكون في المستقبل",
        "Scheduled time is in the past — it must be in the future"),
    "publish_meta_generated": (
        "بيانات النشر المولّدة (المصدر: %s): العنوان «%s»",
        "Generated publish data (source: %s): title \"%s\""),
    "publish_meta_error": ("خطأ في بيانات النشر: %s",
                           "Publish data error: %s"),
    "publish_thumb_missing": ("ملف الصورة المصغرة غير موجود: %s",
                              "Thumbnail file not found: %s"),
    "publish_caption_final": ("الكابشن النهائي (%d حرفًا):",
                              "Final caption (%d chars):"),
    "publish_caption_final_skipped": (
        "الكابشن النهائي (%d حرفًا) — فحص الامتثال متخطَّى "
        "(--skip-caption-check):",
        "Final caption (%d chars) — compliance check skipped "
        "(--skip-caption-check):"),
    "publish_caption_rejected": (
        "الكابشن مرفوض — جمل مشروطة بالمتابعة/التعليق:",
        "Caption rejected — sentences conditioned on follow/comment:"),
    "publish_caption_suggested": ("الكابشن المقترح:",
                                  "Suggested caption:"),
    "publish_caption_hook_blocked": (
        "الجملة المحظورة في الهوك نفسه — أعد كتابة الكابشن كاملًا.",
        "The banned sentence is in the hook itself — rewrite the "
        "whole caption."),
    "publish_caption_retry": (
        "أعد النشر بالكابشن المصحح، أو استخدم --skip-caption-check "
        "للتجاوز على مسؤوليتك",
        "Republish with the fixed caption, or use --skip-caption-check "
        "to override at your own risk"),
    "publish_check_fix_hint": (
        "أصلح الفيديو أو استخدم --skip-check للتجاوز",
        "Fix the video or use --skip-check to override"),
    "publish_check_failed": (
        "فشل فحص الجودة قبل النشر — أصلح الملاحظات أعلاه أو استخدم "
        "--skip-check للتجاوز على مسؤوليتك",
        "Pre-publish quality check failed — fix the notes above or "
        "use --skip-check to override at your own risk"),
    "publish_dry_header": ("== وضع تجريبي — لن يُنشر شيء ==",
                           "== Dry run — nothing will be published =="),
    "publish_fb_build_fail": ("فيسبوك: لا يمكن بناء الأمر — %s",
                              "Facebook: cannot build the command — %s"),
    "publish_fb_reel": ("-- فيسبوك (Reel على الصفحة %s):",
                        "-- Facebook (Reel on page %s):"),
    "publish_scheduled_at": ("   موعد النشر المجدول: %s",
                             "   Scheduled publish time: %s"),
    "publish_caption_chars": ("   الكابشن (%d حرفًا):",
                              "   Caption (%d chars):"),
    "publish_yt_payload": ("-- يوتيوب (videos.insert):",
                           "-- YouTube (videos.insert):"),
    "publish_tiktok_build_fail": ("تيك توك: لا يمكن بناء الحمولة — %s",
                                  "TikTok: cannot build the payload — %s"),
    "publish_tiktok_header": (
        "-- تيك توك (Content Posting API — video/init):",
        "-- TikTok (Content Posting API — video/init):"),
    "publish_tiktok_unverified": (
        "   تنبيه: الرفع الحقيقي غير مختبَر حيًا — لا حساب TikTok "
        "مربوط بعد.",
        "   Note: real upload is untested live — no TikTok account "
        "linked yet."),
    "publish_ig_build_fail": ("إنستغرام: لا يمكن بناء الحمولة — %s",
                              "Instagram: cannot build the payload — %s"),
    "publish_ig_header": (
        "-- إنستغرام (Graph API — Reels، رفع قابل للاستئناف):",
        "-- Instagram (Graph API — Reels, resumable upload):"),
    "publish_ig_unverified": (
        "   تنبيه: الرفع الحقيقي غير مختبَر حيًا — لا حساب Instagram "
        "مربوط بعد.",
        "   Note: real upload is untested live — no Instagram account "
        "linked yet."),
    "publish_fb_done": ("فيسبوك: %s (post_id=%s)",
                        "Facebook: %s (post_id=%s)"),
    "publish_fb_scheduled": ("مجدول", "scheduled"),
    "publish_fb_published": ("نُشر", "published"),
    "publish_fb_failed": ("فيسبوك: فشل — %s", "Facebook: failed — %s"),
    "publish_yt_done": ("يوتيوب: رُفع — %s", "YouTube: uploaded — %s"),
    "publish_yt_failed": ("يوتيوب: فشل — %s", "YouTube: failed — %s"),
    "publish_yt_no_creds": ("يوتيوب: بلا بيانات اعتماد — لم يُرفع شيء.",
                            "YouTube: no credentials — nothing uploaded."),
    "publish_bundle_ready": ("حزمة الرفع اليدوي جاهزة في: %s",
                             "Manual upload bundle ready at: %s"),
    "publish_yt_auth_hint": (
        "اتبع steps.txt داخل الحزمة، أو أكمل `studio.py youtube-auth` "
        "ثم أعد الأمر.",
        "Follow steps.txt inside the bundle, or finish "
        "`studio.py youtube-auth` then retry."),
    "publish_tiktok_failed": ("تيك توك: فشل — %s", "TikTok: failed — %s"),
    "publish_tiktok_no_token": ("تيك توك: بلا توكن — لم يُرفع شيء.",
                                "TikTok: no token — nothing uploaded."),
    "publish_ig_failed": ("إنستغرام: فشل — %s",
                          "Instagram: failed — %s"),
    "publish_ig_no_token": (
        "إنستغرام: بلا توكن أو معرّف حساب — لم يُرفع شيء.",
        "Instagram: no token or account id — nothing uploaded."),
    "publish_check_verify_fb": (
        "   تحقق من ظهور الفيديو على الحساب — أول رفع حقيقي عبر API "
        "غير مختبَر حيًا بعد.",
        "   Verify the video shows on the account — the first real "
        "API upload is still untested live."),
    "publish_check_verify_ig": (
        "   تحقق من ظهور الريل على الحساب — أول رفع حقيقي عبر API "
        "غير مختبَر حيًا بعد.",
        "   Verify the Reel shows on the account — the first real "
        "API upload is still untested live."),
    # run
    "run_unknown_backend": (
        "خلفية التجميع غير معروفة: %s (المسموح: "
        "concat/headless/mlt/openreel)",
        "Unknown assemble backend: %s (allowed: "
        "concat/headless/mlt/openreel)"),
    "run_dry_header": (
        "== وضع تجريبي — لن يُستدعى OmniRoute ولا Concat ولا OpenMontage ==",
        "== Dry run — OmniRoute, Concat and OpenMontage will not be called =="),
    "run_dry_scenario": (
        "1) سيناريو: story=%s عبر %s (بديل: %s؛ إعادة محاولة: %s)",
        "1) Script: story=%s via %s (fallback: %s; retries: %s)"),
    "run_dry_fallback_allowed": ("مسموح (هوك من السيناريو الجاهز)",
                                 "allowed (hook from the ready scenario)"),
    "run_dry_fallback_denied": ("غير مسموح — يتوقف عند الفشل",
                                "not allowed — stops on failure"),
    "run_dry_fallback_line": ("   البديل عند الفشل: %s",
                              "   Fallback on failure: %s"),
    "run_dry_produce": ("2) إنتاج: مشروع OpenMontage %s — %s",
                        "2) Production: OpenMontage project %s — %s"),
    "run_dry_assemble": ("3) تجميع (%s): تصدير إلى %s — مقاس %dx%d",
                         "3) Assemble (%s): export to %s — size %dx%d"),
    "run_dry_logo": ("4) شعار الصفحة أعلى اليمين: %s",
                     "4) Page logo, top right: %s"),
    "run_dry_logo_yes": ("نعم (تلقائي)", "yes (automatic)"),
    "run_dry_logo_no": ("لا (--no-watermark)", "no (--no-watermark)"),
    "run_dry_cards": ("5) بطاقات اقتباس ختامية (3×3 ثوانٍ): %s",
                      "5) Closing quote cards (3x3 seconds): %s"),
    "run_dry_cards_no": ("لا — مرّر --cards-dir بمجلد البطاقات",
                         "no — pass --cards-dir with a cards folder"),
    "run_dry_grade": ("6) تدرج لوني: preset %s (%s)",
                      "6) Color grade: preset %s (%s)"),
    "run_dry_exists": ("موجود", "exists"),
    "run_dry_missing": ("غير موجود!", "missing!"),
    "run_dry_concat_bin": ("   ثنائي Concat: %s — %s",
                           "   Concat binary: %s — %s"),
    "run_dry_headless": ("   محرر headless: %s — %s",
                         "   Headless editor: %s — %s"),
    "run_dry_melt": ("   ثنائي melt: %s", "   melt binary: %s"),
    "run_dry_openreel": ("   ريندر OpenReel: %s — %s",
                         "   OpenReel render: %s — %s"),
    "run_dry_rundir": ("   مجلد التشغيل: %s/<story>-<وقت>/",
                       "   Run folder: %s/<story>-<time>/"),
    "run_started": ("تشغيل: %s", "Run: %s"),
    "run_done": ("اكتمل خط الإنتاج: %s", "Pipeline finished: %s"),
    # scene-plan
    "sceneplan_need_story": (
        "حدد القصة: --story <رقم في الطابور أو جزء من العنوان>",
        "Specify the story: --story <queue number or part of the title>"),
    "sceneplan_unknown_template": ("قالب غير معروف: %s (المتاح: %s)",
                                   "Unknown template: %s (available: %s)"),
    "sceneplan_queue_missing": ("ملف الطابور غير موجود: %s",
                                "Queue file not found: %s"),
    "sceneplan_queue_unreadable": ("تعذر قراءة ملف الطابور: %s",
                                   "Could not read the queue file: %s"),
    "sceneplan_no_match": ("لا توجد قصة مطابقة في الانتظار: %s",
                           "No matching story in the queue: %s"),
    "sceneplan_cap_rejected": ("رفضت خطة المشاهد: %s",
                               "Scene plan rejected: %s"),
    "sceneplan_invalid": ("خطة مشاهد غير صالحة: %s",
                          "Invalid scene plan: %s"),
    "sceneplan_saved": ("حُفظت الخطة في: %s", "Plan saved to: %s"),
    "sceneplan_template_lang_invalid": (
        "لغة قالب غير معروفة: %s (المتاح: ar, en)",
        "Unknown template language: %s (available: ar, en)"),
    # main dispatch
    "main_demo_conflict": ("--demo لا يُجمع مع --story/--project",
                           "--demo cannot be combined with --story/--project"),
    "main_run_needs": (
        "خط الإنتاج يحتاج --story و--project و--out (أو --demo للتجربة)",
        "The pipeline needs --story, --project and --out "
        "(or --demo to try it)"),
    "main_bad_size": ("مقاس غير صالح --size: %s", "Invalid --size: %s"),
    "main_bad_value": ("قيمة غير صالحة: %s", "Invalid value: %s"),
    # LLM
    "llm_all_failed": (
        "فشلت كل مزودات الذكاء (%d): %s — جرّب لاحقًا أو تحقق من "
        "الشبكة ومن حالة المزودين بـ `python3 studio.py llm-status`",
        "All AI providers failed (%d): %s — retry later or check the "
        "network and provider status with "
        "`python3 studio.py llm-status`"),
    "llm_all_failed_none": ("بلا مزود", "no provider"),
}

# بادئات الأخطاء المعروفة في studio.py (لترجمة سطر البادئة فقط
# في _print_translated — جسم الخطأ المترجم في lib/errors.py عربي).
ERROR_PREFIXES = {
    "فشل خط الإنتاج": "Pipeline failed",
    "تعذر فحص الفيديو": "Could not check the video",
    "تعذر فحص الجودة قبل النشر": "Could not run the pre-publish quality check",
    "فشل التجميع": "Assembly failed",
    "فشل الفيديو الطويل": "Long video failed",
    "فشل سرد الفيديو الطويل": "Long-video narration failed",
    "فشل السرد الطويل": "Long narration failed",
    "فشل توليد البطاقات": "Quote-card generation failed",
    "فشل حفظ التوكن": "Could not save the token",
}

_LLM_ALL_FAILED_RE = re.compile(
    r"فشلت كل مزودات الذكاء \((\d+)\): (.*?) — جرّب لاحقًا")


def t(key, lang="ar", *args):
    """رجّع رسالة مفتاح بلغة معطاة (العربي افتراضيًا).

    مفتاح مجهول يرجع نفسه (بلا رفع)؛ ووسائط التنسيق تُطبق
    بـ `%` فقط عند وجودها.
    """
    pair = MESSAGES.get(key)
    if pair is None:
        return key
    text = pair[1 if normalize_lang(lang) == "en" else 0]
    if args:
        try:
            return text % args
        except (TypeError, ValueError):
            return text
    return text


def translate_prefix(prefix, lang="ar"):
    """ترجم بادئة خطأ معروفة؛ وغير المعروفة ترجع كما هي."""
    if normalize_lang(lang) != "en":
        return prefix
    return ERROR_PREFIXES.get(prefix, prefix)


def translate_llm_all_failed(text, lang="ar"):
    """ترجم رسالة «فشلت كل مزودات الذكاء (N): …» إلى الإنجليزية.

    تطابق صيغة `LLMAllFailedError` الحرفية في
    lib/omniroute_client.py؛ وأي نص لا يطابقها يرجع كما هو.
    """
    if normalize_lang(lang) != "en":
        return text
    m = _LLM_ALL_FAILED_RE.search(text or "")
    if not m:
        return text
    count = int(m.group(1))
    parts = m.group(2).strip() or t("llm_all_failed_none", "en")
    return t("llm_all_failed", "en", count, parts)
