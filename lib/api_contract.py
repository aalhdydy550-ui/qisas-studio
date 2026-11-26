#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""عقد APIs الخارجية — جولة تطبيق الأنماط (W3، فكرة Newman §2.3).

جدول Python واحد (مزود × نموذج × توقع) تقرأه اختبارات
الدخان الحي (`tests/test_api_smoke_live.py`) عبر `subTest`
— بلا ملف JSON ثانٍ وبلا مزامنة يدوية مع كود Python
(فكرة `--iteration-data` في Newman بلا CSV خارجي).

كل مدخل يصف توقعًا واحدًا قابلًا للتحقق الحي:
- provider: اسم المزود كما في `lib/llm_state.py`
  (مفتاح التهدئة) أو اسم المنصة الاجتماعية.
- model: معرّف النموذج، أو "-" للمنصات بلا نموذج.
- via: دالة الاستوديو نفسها التي يستدعيها الدخان
  (`lib/omniroute_client.py` أو `lib/social_publish.py`)
  — الدخان يختبر السلوك لا HTTP خامًا.
- method / path: الطريقة والمسار المتوقعان.
- expected_status: حالة HTTP المتوقعة (200 دائمًا هنا).
- required_fields: حقول يجب وجودها في الرد (مسار بنقاط
  داخل القاموس، مثل "data.user.open_id").
- time_budget_ms: ميزانية الزمن بالمللي ثانية — تجاوزها
  فشل في العقد حتى مع نجاح الرد.
- key: ما الذي يجب تهيئته قبل أن يُجرَّب المدخل حيًا
  (مفتاح/ملف توكن/مساعد/خادم محلي) — غيابه يعني التخطي
  لا الفشل.
- smoke: هل هذا هو الاختيار الواحد للدخان الحي من هذا
  المزود (مكالمة واحدة صغيرة لكل مزود كحد أقصى)؟

ملاحظات على المدخلات:
- Gemini: الاختيار الحي هو Flash-Lite (حدّه المجاني 500
  طلب/يوم مقابل ~20 لـ Flash) — Flash الرئيسي في العقد
  كبديل موثّق لا يُستدعى في الدخان.
- OmniRoute: المسار CLI أولًا (بلا مفتاح) ثم HTTP بالمفتاح
  — الدخان يستدعي مسارًا واحدًا فقط منهما.
- OpenRouter: الكتالوج العام GET /v1/models بلا مفتاح —
  قراءة فقط، والدخان يجلب مرة واحدة ثم يحلّل محليًا
  بـ `free_model_ids` (بلا جلب ثانٍ).
- Instagram: قراءة فقط GET /me?fields=id عبر مساعد
  `social_publish._http_json` نفسه — بلا أي نشر.
- TikTok: قراءة فقط GET /v2/user/info/ عبر المساعد نفسه.
  توكن النشر قد لا يحمل نطاق user.info.basic أصلًا،
  فـ 401/403 هنا تعني «تخطَّ» لا «فشل» (انظر note).
"""
import os

# مدخل العقد: قاموس واحد لكل (مزود × نموذج × توقع).
API_CONTRACT = [
    {
        "provider": "gemini",
        "model": "gemini-3.1-flash-lite",
        "via": "chat_gemini",
        "method": "POST",
        "path": "/v1beta/models/gemini-3.1-flash-lite:generateContent",
        "expected_status": 200,
        "required_fields": ["text"],
        "time_budget_ms": 120000,
        "key": "مساعد Gemini الآمن (lib/omniroute_client.GEMINI_HELPER)",
        "smoke": True,
        "note": "الاختيار الحي — Flash-Lite قبل Flash الرئيسي "
                "(الحد المجاني 500/يوم). المساعد يرجع نصًا لا JSON، "
                "فالحقل المطلوب هو نص غير فارغ.",
    },
    {
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
        "via": "chat_gemini",
        "method": "POST",
        "path": "/v1beta/models/gemini-3-flash-preview:generateContent",
        "expected_status": 200,
        "required_fields": ["text"],
        "time_budget_ms": 120000,
        "key": "مساعد Gemini الآمن (lib/omniroute_client.GEMINI_HELPER)",
        "smoke": False,
        "note": "بديل موثّق في العقد فقط — لا يُستدعى في الدخان "
                "(مكالمة واحدة لكل مزود).",
    },
    {
        "provider": "omniroute",
        "model": "ddgw/gpt-5.4-mini",
        "via": "chat_cli",
        "method": "POST",
        "path": "/v1/chat/completions",
        "expected_status": 200,
        "required_fields": ["choices", "message", "content"],
        "time_budget_ms": 180000,
        "key": "أمر omniroute في PATH (بلا مفتاح) أو "
               "OMNIROUTE_API_KEY لمسار HTTP",
        "smoke": True,
        "note": "الدخان يستدعي chat_cli إن وُجد الأمر، وإلا "
                "chat_http بالمفتاح — مسار واحد فقط في كل تشغيل.",
    },
    {
        "provider": "ollama",
        "model": "qwen2.5:7b",
        "via": "chat_ollama",
        "method": "POST",
        "path": "/api/chat",
        "expected_status": 200,
        "required_fields": ["message", "content"],
        "time_budget_ms": 120000,
        "key": "خادم Ollama المحلي (ollama serve) + الموديل مثبّت",
        "smoke": True,
        "note": "خادم متوقف أو موديل غير مثبّت = «تخطَّ» لا فشل "
                "(خطأ network/not_found بلا تهدئة).",
    },
    {
        "provider": "openrouter",
        "model": "openrouter/free",
        "via": "_default_models_fetcher",
        "method": "GET",
        "path": "/v1/models",
        "expected_status": 200,
        "required_fields": ["data"],
        "time_budget_ms": 20000,
        "key": "بلا مفتاح — الكتالوج العام لا يحتاج مصادقة",
        "smoke": True,
        "note": "قراءة فقط. جلب واحد للكتالوج ثم تحليل محلي "
                "بـ free_model_ids — بلا جلب ثانٍ وبلا توليد.",
    },
    {
        "provider": "instagram",
        "model": "-",
        "via": "_http_json",
        "method": "GET",
        "path": "/v21.0/me?fields=id",
        "expected_status": 200,
        "required_fields": ["id"],
        "time_budget_ms": 30000,
        "key": "ملف instagram-token.json (توكن محفوظ)",
        "smoke": True,
        "note": "قراءة فقط عبر مساعد social_publish نفسه — "
                "قراءة معرّف الحساب، بلا أي نشر أو كتابة.",
    },
    {
        "provider": "tiktok",
        "model": "-",
        "via": "_http_json",
        "method": "GET",
        "path": "/v2/user/info/?fields=open_id,display_name",
        "expected_status": 200,
        "required_fields": ["data", "user", "open_id"],
        "time_budget_ms": 30000,
        "key": "ملف tiktok-token.json (توكن محفوظ)",
        "smoke": True,
        "note": "قراءة فقط عبر مساعد social_publish نفسه. "
                "401/403 تعني «تخطَّ» لا فشل: توكن النشر "
                "(video.upload) قد لا يحمل نطاق user.info.basic.",
    },
]

# حقول كل مدخل — يتحقق منها اختبار شكل العقد.
REQUIRED_KEYS = ("provider", "model", "via", "method", "path",
                 "expected_status", "required_fields",
                 "time_budget_ms", "key", "smoke", "note")


def providers():
    """أسماء المزودين بالترتيب، بلا تكرار."""
    seen = []
    for entry in API_CONTRACT:
        if entry["provider"] not in seen:
            seen.append(entry["provider"])
    return seen


def entries_for_provider(provider):
    """كل مدخلات مزود واحد بالترتيب."""
    return [e for e in API_CONTRACT if e["provider"] == provider]


def smoke_entries():
    """الاختيار الواحد للدخان الحي من كل مزود (smoke=True).

    مكالمة واحدة صغيرة لكل مزود كحد أقصى — أول مدخل
    smoke=True من كل مزود بالترتيب الثابت للعقد.
    """
    picks = []
    for provider in providers():
        for entry in entries_for_provider(provider):
            if entry.get("smoke"):
                picks.append(entry)
                break
    return picks


def has_nested_field(data, dotted):
    """هل يوجد حقل منقّط (مثل "data.user.open_id") في قاموس؟

    يرجع False عند غياب أي مستوى أو عند قيمة None —
    يستخدمه الدخان للتحقق من required_fields بلا افتراض
    شكل الرد كاملًا.
    """
    current = data
    for part in (dotted or "").split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
        if current is None:
            return False
    return True


def contract_path_for(provider, model=None):
    """مسار العقد لمزود (ونموذج إن أُعطي) — لرسائل الخطأ."""
    for entry in API_CONTRACT:
        if entry["provider"] != provider:
            continue
        if model is not None and entry["model"] != model:
            continue
        return "%s %s" % (entry["method"], entry["path"])
    return None


# مسار تقرير نتائج الدخان الحي (JSON) — يضبطه المشغّل
# بـ STUDIO_SMOKE_REPORT_JSON ليقرأه مولّد التقرير؛
# بلا قيمة لا يُكتب أي ملف.
RESULTS_JSON_ENV = "STUDIO_SMOKE_REPORT_JSON"


def results_json_path():
    """مسار ملف نتائج JSON من البيئة، أو None."""
    value = os.environ.get(RESULTS_JSON_ENV, "").strip()
    return value or None
