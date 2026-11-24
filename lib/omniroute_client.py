#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""عميل OmniRoute — طبقة الذكاء في studio.

مساران لاستدعاء نماذج البوابة:
1. أمر `omniroute chat` (CLI) — يعمل بلا مفتاح بوابة، لأنه يصادق داخليًا
   على الخادم المحلي. هذا هو المسار الافتراضي.
2. واجهة HTTP ‏/v1/chat/completions — تحتاج مفتاح بوابة في متغير البيئة
   OMNIROUTE_API_KEY (يُنشأ مرة واحدة من لوحة تحكم OmniRoute أو من CLI).

ملحوظة واقعية (اتحقق منها 2026-11-20): المسار المجاني الحقيقي بلا مفتاح
وبلا حساب هو DuckDuckGo AI Chat عبر `ddgw` (مثل `ddgw/gpt-5.4-mini` —
رد بالعربي في ~2–11 ثانية). مزوّد Pollinations الأصلي صار يطلب مفتاح API
حقيقي (حساب على enter.pollinations.ai)، ومزوّد g4f-pollinations نفد
رصيده المجاني (402). عند فشل الاستدعاء تُرجَع رسالة خطأ واضحة بدل الادعاء.

Ollama المحلي (جولة v0.1.39 — مقترح MoneyPrinterV2 §4.2):
ساق أخيرة في السلسلة بعد Gemini، لا قبلها: محلي $0 بلا حدود
وبلا شبكة، لكنه يحتاج تثبيتًا وتشغيلًا يدويًا (`ollama serve` +
`ollama pull qwen2.5:7b`) وجودة موديل 7B أقل من Gemini في
صياغة القصص العربية — فهو احتياطي دون اتصال عند فشل كل
السحابيين، لا بديل أول. خادم متوقف أو موديل غير مثبّت =
مزود غير متاح يُتخطى بهدوء (خطأ network/not_found، بلا
تهدئة) ولا يكسر السلسلة أبدًا.

منهجية تناوب المسار المجاني (جولة v0.1.41 — بند 2 من
استخراج AlphaCLI، تنفيذ من الصفر على الأركنة الرسمية فقط):
أهلية بالسعر لا بالاسم (prompt وcompletion صفران معًا، وسعر
مفقود = ليس مجانيًا أبدًا) + تدوير عند 429 إلى النموذج المجاني
التالي بدل إعادة المحاولة على النموذج نفسه + اكتشاف حي من
‎/v1/models مع أرضية مثبّتة لا تنقص أبدًا + عرض اسم المنتج
«المسار المجاني» لا هوية المنبع. المسار المجاني Alphax Free
نفسه (بوابة Kilo Code بلا مفتاح) مرفوض نهائيًا ولا يُبنى هنا
أبدًا — المنهجية فقط، على ركن رسمي مجاني (OpenRouter ‎:free
أولًا عند اكتمال ربطه).
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from lib import llm_state


class OmniRouteError(Exception):
    pass


class LLMAllFailedError(OmniRouteError):
    """فشل كل مزودي LLM — رسالة عربية + تفاصيل كل مزود.

    .failures: قائمة (المزود، نوع الخطأ، تفصيل مختصر) لكل
    مزود جُرِّب. تُمسك كـ OmniRouteError في كل المواضع
    القديمة (except OmniRouteError ما زال يعمل).
    """

    def __init__(self, failures):
        self.failures = list(failures or [])
        parts = ["%s (%s)" % (provider, kind)
                 for provider, kind, _detail in self.failures]
        message = ("فشلت كل مزودات الذكاء (%d): %s — جرّب لاحقًا "
                   "أو تحقق من الشبكة ومن حالة المزودين "
                   "بـ `python3 studio.py llm-status`"
                   % (len(self.failures), "؛ ".join(parts) or "بلا مزود"))
        super().__init__(message)


# مساعد Gemini الآمن (مفتاح بديل عبر الـconnector — لا يظهر أبدًا
# في أي ملف أو وسيط أو سجل).
GEMINI_HELPER = os.path.expanduser(
    "~/workspace/custom-connectors/custom.gemini/bin/gemini.py")
GEMINI_DEFAULT_MODEL = "gemini-3-flash-preview"
# Gemini Flash-Lite (جولة v0.1.40 — §7.1 من تقرير Claude):
# الحد المجاني 500 طلب/يوم مقابل ~20 لـ Flash، فيُجرَّب قبل
# Flash الرئيسي بنفس المساعد الآمن (kind ‏"gemini" نفسه).
GEMINI_LITE_DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Ollama المحلي — خادم وموديل افتراضيان (قابلان للضبط من
# قسم omniroute في config: ollama_base_url / ollama_model).
# qwen2.5:7b: صغير شائع (~4.7GB) ويقرأ/يكتب العربية جيدًا
# مقارنة بحجمه، ويعمل على CPU بلا GPU — مناسب كاحتياطي
# محلي لسيناريو قصير، لا كبديل أول عن Gemini.
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_DEFAULT_MODEL = "qwen2.5:7b"

# أنماط تصنيف أخطاء LLM: حصة (429/402) مقابل مصادقة (401/403)
# مقابل خادم (5xx) مقابل شبكة — التصنيف يقرر التهدئة.
_QUOTA_PATTERNS = ("429", "402", "rate limit", "rate_limit", "quota",
                   "too many requests", "payment required",
                   "resource exhausted", "resource_exhausted")
_AUTH_PATTERNS = ("401", "403", "unauthorized", "invalid api key",
                  "invalid_api_key", "api key not valid",
                  "authentication", "permission denied")
_SERVER_PATTERNS = ("500", "502", "503", "504", "internal error",
                    "overloaded", "service unavailable", "bad gateway")
# مورد غير موجود (404 / موديل غير مثبّت في Ollama): خطأ إعداد
# لا حصة — يُسجَّل بلا تهدئة ويُتخطى المزود.
_NOT_FOUND_PATTERNS = ("404", "not found", "model not found",
                       "غير موجود في ollama")
_NETWORK_PATTERNS = ("timed out", "timeout", "connection",
                     "unreachable", "name resolution",
                     "temporary failure", "timedout")


def classify_llm_error(text):
    """صنّف رسالة خطأ LLM: quota|auth|server|network|not_found|unknown.

    quota = حصة/معدل (429/402) → تهدئة؛ auth = مصادقة
    (401/403) → لا تهدئة (خطأ إعداد)؛ server = 5xx؛
    network = مهلة/اتصال؛ not_found = مورد غير موجود
    (404 / موديل Ollama غير مثبّت) → لا تهدئة (خطأ إعداد).
    """
    low = (text or "").lower()
    for pattern in _QUOTA_PATTERNS:
        if pattern in low:
            return "quota"
    for pattern in _AUTH_PATTERNS:
        if pattern in low:
            return "auth"
    for pattern in _SERVER_PATTERNS:
        if pattern in low:
            return "server"
    for pattern in _NOT_FOUND_PATTERNS:
        if pattern in low:
            return "not_found"
    for pattern in _NETWORK_PATTERNS:
        if pattern in low:
            return "network"
    return "unknown"


# ─── منهجية تناوب المسار المجاني (جولة v0.1.41، بند 2) ───
# الفكرة من AlphaCLI (v1.1.19 — free_pool.rs)، منقولة المفهوم
# لا الكود حرفيًا، ومنفَّذة من الصفر على الأركنة الرسمية فقط.

# الاسم المعروض للمستخدم حين يخدم طلبًا نموذج من مسار التناوب
# المجاني: اسم المنتج لا هوية نموذج المنبع — والمعرّف الحقيقي
# يبقى في الحالة (llm_state) عبر on_attempt.
FREE_LANE_DISPLAY_NAME = "المسار المجاني"

# قاعدة OpenRouter الافتراضية للاكتشاف الحي (كتالوجه العام
# /v1/models لا يحتاج مفتاحًا).
OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

# القائمة الأرضية المثبّتة — لا تنقص أبدًا: الاكتشاف الحي يضيف
# عليها ولا يحذف منها، وإن فشل الاكتشاف كله رجعت هي وحدها.
# الأرضية اسم توجيه لا نموذج: ‎`openrouter/free` يوجّهه المزود
# نفسه من جهة الخادم إلى نموذج مجاني فعلي، فلا يتقادم بتقادم
# معرّفات بعينها — والكتالوج يدور سريعًا (16 نموذجًا مجانيًا
# في 2026-10-28 بعد 17 في 2026-10-05)، فالمعرّفات البعينها
# تأتي من الاكتشاف الحي وحده (أسعار مُتحقَّق منها لحظتها).
# تحقّقتُ من وجود الاسم 2026-11-23 من مصادر ثانوية موثّقة
# مقابل الكتالوج العام؛ والاختبار الحي على OpenRouter معلّق
# على مفتاح (التسجيل يحتاج هاتف المستخدم).
PINNED_FREE_MODELS = ("openrouter/free",)


def _price_is_zero(value):
    """سعر صفري؟ يقبل عددًا أو نصًا عدديًا ("0" / "0.00").

    None أو نص غير عددي أو قيمة مفقودة ← ليست صفرًا.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, str):
        try:
            return float(value.strip()) == 0
        except ValueError:
            return False
    return False


def is_free_pricing(pricing):
    """هل التسعيرة مجانية؟ prompt وcompletion صفران معًا.

    سعر مفقود أو null = ليس مجانيًا أبدًا — الاتجاه الخطر هو
    إنفاق رصيد المستخدم بالخطأ، فالغياب يُقرأ «مدفوع».
    """
    if not isinstance(pricing, dict):
        return False
    if "prompt" not in pricing or "completion" not in pricing:
        return False
    return (_price_is_zero(pricing.get("prompt"))
            and _price_is_zero(pricing.get("completion")))


def is_free_model(entry):
    """هل مدخل كتالوج /v1/models نموذج مجاني؟

    مدخل بلا pricing أو بسعر مفقود ← ليس مجانيًا أبدًا.
    """
    if not isinstance(entry, dict):
        return False
    return is_free_pricing(entry.get("pricing"))


def free_model_ids(catalog):
    """معرّفات النماذج المجانية من كتالوج /v1/models.

    يقبل قاموس {"data": [...]} أو قائمة مباشرة؛ يرجع
    المعرّفات المجانية بالترتيب بلا تكرار. اسم مستعار مُقاس
    (سعر غير صفري) يُستبعَد ولو حمل لاحقة :free — الأهلية
    بالسعر لا بالاسم.
    """
    if isinstance(catalog, dict):
        entries = catalog.get("data")
    else:
        entries = catalog
    if not isinstance(entries, list):
        return []
    seen = set()
    ids = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        if model_id in seen:
            continue
        if is_free_model(entry):
            seen.add(model_id)
            ids.append(model_id)
    return ids


def merge_free_models(discovered, floor=PINNED_FREE_MODELS):
    """ادمج المكتشَف مع الأرضية المثبّتة — بلا إنقاص أبدًا.

    المكتشَف أولًا بالترتيب، ثم أي عنصر من الأرضية غاب عنه
    يُلحَق في النهاية؛ فالقائمة لا تنقص تحت الأرضية حتى لو
    أعاد الاكتشاف قائمة أقصر أو فارغة.
    """
    merged = list(discovered or [])
    for model_id in (floor or []):
        if model_id not in merged:
            merged.append(model_id)
    return merged


def _default_models_fetcher(url, headers, timeout):
    """جلب افتراضي لكتالوج /v1/models: GET ثم JSON."""
    req = urllib.request.Request(url, headers=headers or {},
                                 method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_free_models(base_url, api_key=None, fetcher=None,
                         timeout=15, floor=PINNED_FREE_MODELS):
    """اكتشاف حي للنماذج المجانية من {base_url}/v1/models.

    يرجع معرّفات النماذج صفرية السعر مدموجة مع الأرضية
    المثبّتة (فلا تنقص عنها أبدًا). أي فشل — شبكة، HTTP،
    JSON تالف، شكل غير متوقع — يرجع الأرضية وحدها.
    بلا مفتاح يُرسَل الطلب بلا ترويسة مصادقة (كتالوج
    OpenRouter العام لا يحتاج مفتاحًا)؛ وإن وُجد مفتاح يُرسَل
    Bearer. fetcher قابل للحقن في الاختبارات:
    fetcher(url, headers, timeout) ← كتالوج محلَّل.
    """
    base_url = (base_url or "").rstrip("/")
    url = base_url + "/v1/models"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    fetch = fetcher or _default_models_fetcher
    try:
        catalog = fetch(url, headers, timeout)
    except Exception:
        return list(floor or [])
    try:
        discovered = free_model_ids(catalog)
    except Exception:
        return list(floor or [])
    return merge_free_models(discovered, floor=floor)


def free_rotation_providers(models, base_url=None):
    """ساق تناوب مجاني من معرّفات نماذج: كل نموذج ركن
    omniroute بعلَم free_rotation — عند 429 يُدوَّر عنه إلى
    التالي بلا إعادة محاولة عليه، ويُعرض للمستخدم باسم
    المنتج «المسار المجاني» لا معرّف المنبع. base_url محفوظ
    للتوافق المستقبلي (ساق OpenRouter المخصصة) ولا يُستخدم
    بعد — ركن omniroute يستخدم base_url العام للسلسلة.
    """
    providers = []
    for model in (models or []):
        if isinstance(model, str) and model.strip():
            providers.append({"kind": "omniroute",
                              "model": model.strip(),
                              "free_rotation": True})
    return providers


def _record_free_rotation(state, provider, now=None):
    """سجّل تدويرًا عن نموذج مجاني بعد 429 في الحالة.

    يرفع عدّاد التدوير ويثبّت وقت آخر تدوير، ويضع النموذج
    في تهدئة (نفس مدة llm_state) حتى لا يُعاد اختياره قبل
    انتهائها. لا يمسّ العدادات اليومية (يسجّلها on_attempt
    مرة واحدة عبر record_attempt) — فلا ازدواج في العدّ.
    """
    if state is None:
        return state
    now = now if now is not None else time.time()
    entry = (state.setdefault("providers", {})
             .setdefault(str(provider), {}))
    entry["free_rotations"] = entry.get("free_rotations", 0) + 1
    entry["last_free_rotation_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(now))
    entry["cooldown_until"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S",
        time.localtime(now + llm_state.COOLDOWN_SECONDS))
    return state


def chat_gemini(prompt, model=GEMINI_DEFAULT_MODEL, system=None,
                max_tokens=200, temperature=0.7, timeout=120,
                helper=None):
    """استدعاء واحد عبر مساعد Gemini الآمن. يرجع نص الرد.

    المساعد يستدعي Gemini API بمفتاح بديل (surrogate) من
    الـconnector — المفتاح الخام لا يظهر في أي ملف أو وسيط
    أو سجل أبدًا. مهلة 120ث (داخل المساعد 30ث للشبكة).
    ملاحظة: المساعد لا يدعم max_tokens/temperature فيُتجاهلان
    (يُقبلان لتوحيد الواجهة مع chat_cli)؛ وموجّه النظام
    يُدمج في أول البرومبت (المساعد بلا وسيط system).
    """
    helper = helper or GEMINI_HELPER
    if not os.path.isfile(helper):
        raise OmniRouteError("مساعد Gemini غير موجود: %s" % helper)
    full_prompt = prompt
    if system and system.strip():
        full_prompt = system.strip() + "\n\n" + prompt
    cmd = [sys.executable, helper, "generate",
           "--model", model, "--prompt", full_prompt]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OmniRouteError(
            "انتهت المهلة (%dث) أثناء انتظار رد Gemini" % timeout)
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        detail = " | ".join(x for x in [out, err] if x)[:600]
        raise OmniRouteError(
            "فشل استدعاء Gemini: %s" % (detail or "خطأ غير معروف"))
    if not out:
        raise OmniRouteError(
            "رد Gemini فارغ: %s" % (err[:300] or "بلا تفاصيل"))
    if out.startswith("{"):
        try:
            data = json.loads(out)
        except ValueError:
            data = None
        if isinstance(data, dict):
            if data.get("error"):
                raise OmniRouteError(
                    "فشل استدعاء Gemini: %s"
                    % str(data["error"])[:400])
            if "candidates" in data and not data["candidates"]:
                raise OmniRouteError(
                    "رد Gemini بلا نص (ربما حُجب المحتوى)")
    return out


def chat_ollama(prompt, model=OLLAMA_DEFAULT_MODEL,
                base_url=OLLAMA_DEFAULT_BASE_URL, system=None,
                max_tokens=200, temperature=0.7, timeout=120):
    """استدعاء واحد عبر Ollama المحلي (POST /api/chat). يرجع نص الرد.

    خادم متوقف (URLError) أو موديل غير مثبّت (HTTP 404) =
    مزود غير متاح: يُرفع OmniRouteError برسالة عربية واضحة
    (تُصنَّف network / not_found — بلا تهدئة) فيتخطاه
    محرك السلسلة بهدوء إلى التالي، ولا يكسر السلسلة أبدًا.
    بلا مفاتيح ولا حسابات — الخادم محلي بالكامل.
    """
    base_url = (base_url or OLLAMA_DEFAULT_BASE_URL).rstrip("/")
    model = (model or OLLAMA_DEFAULT_MODEL).strip()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature,
                    "num_predict": max_tokens},
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        if e.code == 404:
            raise OmniRouteError(
                "الموديل %s غير موجود في Ollama — نزّله بـ: "
                "ollama pull %s (%s)"
                % (model, model, detail or "model not found"))
        raise OmniRouteError("HTTP %s من Ollama: %s"
                             % (e.code, detail or "بلا تفاصيل"))
    except urllib.error.URLError as e:
        raise OmniRouteError(
            "خادم Ollama غير متاح على %s — شغّله بـ: ollama "
            "serve (%s)" % (base_url, e.reason))
    try:
        content = data["message"]["content"]
    except (KeyError, TypeError):
        raise OmniRouteError("رد غير متوقع من Ollama: %s"
                             % str(data)[:300])
    if not isinstance(content, str) or not content.strip():
        raise OmniRouteError("رد غير متوقع من Ollama: %s"
                             % str(data)[:300])
    return content.strip()


def ollama_status(base_url=OLLAMA_DEFAULT_BASE_URL,
                  model=OLLAMA_DEFAULT_MODEL, timeout=5):
    """فحص خفيف لتوفر Ollama (لأمر llm-status): GET /api/tags.

    بلا توليد وبلا إنفاق وبلا أي استدعاء LLM. يرجع قاموسًا
    {available, model, base_url, detail} ولا يرفع أبدًا:
    available=True فقط إن كان الخادم شغالًا والموديل مثبّتًا.
    """
    base_url = (base_url or OLLAMA_DEFAULT_BASE_URL).rstrip("/")
    model = (model or OLLAMA_DEFAULT_MODEL).strip()
    try:
        req = urllib.request.Request(base_url + "/api/tags",
                                     method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"available": False, "model": model,
                "base_url": base_url,
                "detail": "خادم Ollama رد HTTP %s" % e.code}
    except urllib.error.URLError:
        return {"available": False, "model": model,
                "base_url": base_url,
                "detail": "خادم Ollama غير شغال — شغّله بـ: "
                          "ollama serve"}
    except (ValueError, OSError) as e:
        return {"available": False, "model": model,
                "base_url": base_url,
                "detail": "تعذّر فحص Ollama: %s" % str(e)[:200]}
    names = [m.get("name") for m in (data.get("models") or [])
             if isinstance(m, dict) and m.get("name")]
    installed = (model in names
                 or any(n.startswith(model + ":") for n in names))
    if installed:
        return {"available": True, "model": model,
                "base_url": base_url,
                "detail": "متاح — الموديل %s مثبّت" % model}
    return {"available": False, "model": model,
            "base_url": base_url,
            "detail": "الخادم شغال لكن الموديل %s غير مثبّت — "
                      "نزّله بـ: ollama pull %s" % (model, model)}


def providers_from_config(cfg_o):
    """سلسلة المزودين من قسم omniroute في config.

    [الموديل، البديل (إن اختلف)، Gemini Flash-Lite (إن لم
    يُعطَّل)، Gemini الرئيسي (إن لم يُعطَّل)، Ollama المحلي
    (إن لم يُعطَّل — ساق أخيرة)].
    الترتيب الحالي (جولة v0.1.40): ddgw ← Groq ← Gemini
    Flash-Lite ← Gemini ← Ollama. Cloudflare/OpenRouter
    مؤجلان — بلا مفاتيح بعد.
    بلا gemini_enabled صريحًا تكون الساق مفعّلة (أمر المستخدم
    «توصيل Gemini»)؛ وبلا gemini_lite_enabled صريحًا تكون
    ساق Flash-Lite مفعّلة هي الأخرى (الحد 500/يوم مقابل
    ~20 لـ Flash) — وgemini_enabled: false مفتاح رئيسي
    يُسقط ساقي Gemini معًا (نفس الـAPI ونفس المساعد)؛
    وبلا ollama_enabled صريحًا تكون ساق Ollama مفعّلة هي
    الأخرى (الخادم المتوقف يُتخطى بهدوء فلا أثر لها على
    من لم يثبّت Ollama).

    موضع Ollama أخيرًا عمدًا: محلي $0 بلا حدود لكنه يحتاج
    تثبيتًا وتشغيلًا يدويًا، وموديل 7B أضعف صياغةً من Gemini
    في القصص العربية — فهو احتياطي دون اتصال عند فشل كل
    السحابيين، لا بديل أول. إعداداته: ollama_enabled /
    ollama_model (افتراضي qwen2.5:7b) / ollama_base_url
    (افتراضي http://localhost:11434).
    إعدادات Flash-Lite: gemini_lite_enabled /
    gemini_lite_model (افتراضي gemini-3.1-flash-lite).
    """
    cfg_o = cfg_o or {}
    providers = []
    for key in ("model", "fallback_model"):
        value = cfg_o.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value and all(p["model"] != value for p in providers):
            providers.append({"kind": "omniroute", "model": value})
    if cfg_o.get("gemini_enabled", True) and \
            cfg_o.get("gemini_lite_enabled", True):
        lite_model = cfg_o.get("gemini_lite_model") \
            or GEMINI_LITE_DEFAULT_MODEL
        if isinstance(lite_model, str):
            lite_model = lite_model.strip() or GEMINI_LITE_DEFAULT_MODEL
        if all(p["model"] != lite_model for p in providers):
            providers.append({"kind": "gemini",
                              "model": lite_model})
    if cfg_o.get("gemini_enabled", True):
        gemini_model = cfg_o.get("gemini_model") or GEMINI_DEFAULT_MODEL
        if isinstance(gemini_model, str):
            gemini_model = gemini_model.strip() or GEMINI_DEFAULT_MODEL
        if all(p["model"] != gemini_model for p in providers):
            providers.append({"kind": "gemini",
                              "model": gemini_model})
    if cfg_o.get("ollama_enabled", True):
        ollama_model = cfg_o.get("ollama_model") or OLLAMA_DEFAULT_MODEL
        if isinstance(ollama_model, str):
            ollama_model = ollama_model.strip() or OLLAMA_DEFAULT_MODEL
        ollama_url = (cfg_o.get("ollama_base_url")
                      or OLLAMA_DEFAULT_BASE_URL)
        if isinstance(ollama_url, str):
            ollama_url = ollama_url.strip() or OLLAMA_DEFAULT_BASE_URL
        if all(p["model"] != ollama_model for p in providers):
            providers.append({"kind": "ollama",
                              "model": ollama_model,
                              "base_url": ollama_url})
    return providers


def _run_attempts(prompt, attempts, retries, retry_delay,
                  state=None, on_attempt=None):
    """محرك المحاولات المشترك: يجرّب كل محاولة بالترتيب.

    attempts: [{"label", "provider", "via", "model", "fn"}].
    كل محاولة تُعاد `retries` مرة بفاصل متضاعف؛ والمزود في
    تهدئة (state) يُتخطى مع تسجيل سبب التخطي. on_attempt
    (إن وُجد) تُستدعى مرة واحدة لكل مزود بنتيجته النهائية
    (provider, ok, error_kind) لتسجيل الحالة.
    محاولة بعلَم rotate_on_quota (ركن تناوب مجاني): عند 429
    لا تُعاد على النموذج نفسه أبدًا — يُدوَّر فورًا إلى
    النموذج التالي، وتُتخطى كل محاولات النموذج المتبقية
    (مثلًا HTTP بعد CLI)، ويُسجَّل التدوير في الحالة
    (عدّاد + تهدئة لكل نموذج). واسم العرض display_model
    (إن وُجد) هو ما يرجع بدل معرّف الموديل.
    يرجع (النص، المسار، الموديل) أو يرفع LLMAllFailedError.
    """
    if not attempts:
        raise OmniRouteError("لا يوجد مزود للتجربة")
    failures = []
    rotated_away = set()
    for att in attempts:
        provider = att["provider"]
        if provider in rotated_away:
            # نموذج دُوِّر عنه بعد 429: تُتخطى كل محاولاته
            # المتبقية — التدوير إلى نموذج آخر لا إعادة
            # المحاولة على النموذج نفسه بأي مسار.
            continue
        if state is not None:
            cooling, remaining = llm_state.cooling_down(
                state, provider)
            if cooling:
                note = ("في تهدئة (حصة) — متبقٍ %d ثانية"
                        % remaining)
                failures.append((provider, "quota", note))
                continue
        got = None
        last_error = None
        last_kind = "unknown"
        rotate = bool(att.get("rotate_on_quota"))
        for attempt in range(retries + 1):
            try:
                got = att["fn"]()
                break
            except OmniRouteError as e:
                last_error = e
                last_kind = classify_llm_error(str(e))
                if rotate and last_kind == "quota":
                    # 429 على نموذج مجاني: لا إعادة محاولة
                    # عليه — يُدوَّر فورًا إلى التالي.
                    break
                if attempt < retries:
                    time.sleep(retry_delay * (2 ** attempt))
        if got is not None:
            if on_attempt is not None:
                on_attempt(provider, True, None)
            return got, att["via"], att.get("display_model",
                                            att["model"])
        if rotate and last_kind == "quota":
            rotated_away.add(provider)
            if state is not None:
                _record_free_rotation(state, provider)
        failures.append((provider, last_kind,
                         str(last_error)[:300] if last_error
                         else "خطأ غير معروف"))
        if on_attempt is not None:
            on_attempt(provider, False, last_kind)
    raise LLMAllFailedError(failures)


_SYSTEM_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "prompts",
    "story_system.md")


def load_system_prompt():
    """حمّل موجّه النظام المشترك حرفيًا (جولة v0.1.37).

    ملف واحد `lib/prompts/story_system.md` هو مصدر قواعد
    الأسلوب لكل استدعاء LLM في المشروع — أي تعديل فيه
    يسري على كل الأوامر دفعة واحدة. يرجع النص كما هو
    (بلا تعديل) أو "" إن غاب الملف.
    """
    try:
        with open(_SYSTEM_PROMPT_PATH, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def _strip_ansi(text):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


# سطور ضجيج يطبعها CLI على stdout قبل الرد الحقيقي (اتحقق منها
# 2026-11-20: سطر "📋 Loaded env from ..." تسرّب مرة إلى عنوان الفيديو).
_NOISE_MARKERS = ("loaded env from", "update check", "update available",
                  "checking for update", "new version available",
                  "a new version", "chown")
# أحرف رسم الصناديق التي يستخدمها CLI في تحذيراته
_BOX_CHARS = "│└┌┐┘─━┃┏┓┗┛"


def _clean_cli_output(text):
    """يحذف سطور ضجيج CLI من مخرجات stdout ويبقي الرد فقط."""
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(m in low for m in _NOISE_MARKERS):
            continue
        # أي سطر فيه أحرف رسم صناديق هو جزء من تحذير CLI لا من الرد
        # (النص العربي لا يحتوي هذه الأحرف أبدًا).
        if any(c in s for c in _BOX_CHARS):
            continue
        kept.append(s)
    return "\n".join(kept)


def chat_cli(model, prompt, system=None, max_tokens=200, temperature=0.7,
             timeout=180):
    """استدعاء واحد عبر `omniroute chat`. يرجع نص الرد."""
    cmd = ["omniroute", "chat", "-m", model,
           "--max-tokens", str(max_tokens),
           "--temperature", str(temperature),
           "--no-history"]
    if system:
        cmd += ["-s", system]
    cmd.append(prompt)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError:
        raise OmniRouteError("أمر omniroute غير موجود في PATH")
    except subprocess.TimeoutExpired:
        raise OmniRouteError("انتهت المهلة أثناء انتظار رد OmniRoute")
    out = _clean_cli_output(_strip_ansi(proc.stdout or ""))
    err = _strip_ansi(proc.stderr or "").strip()
    if proc.returncode != 0 or not out:
        # اجمع stdout وstderr معًا؛ تحذيرات CLI تذهب لـ stderr بينما
        # سبب الفشل الحقيقي غالبًا في stdout أو رمز الخروج.
        detail = " | ".join(x for x in [out, err] if x) or "خطأ غير معروف"
        raise OmniRouteError("فشل استدعاء omniroute chat: %s" % detail[:600])
    return out


def chat_http(base_url, model, prompt, system=None, max_tokens=200,
              temperature=0.7, timeout=120):
    """استدعاء واحد عبر واجهة /v1/chat/completions. يرجع نص الرد."""
    key = os.environ.get("OMNIROUTE_API_KEY", "").strip()
    if not key:
        raise OmniRouteError("متغير البيئة OMNIROUTE_API_KEY غير مضبوط")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        raise OmniRouteError("HTTP %s: %s" % (e.code, detail))
    except urllib.error.URLError as e:
        raise OmniRouteError("تعذر الوصول إلى %s: %s" % (base_url, e.reason))
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise OmniRouteError("رد غير متوقع من البوابة: %s" % str(data)[:300])
    if not isinstance(content, str) or not content.strip():
        raise OmniRouteError("رد غير متوقع من البوابة: %s" % str(data)[:300])
    return content.strip()


def _omniroute_attempts(prompt, models, base_url, system,
                        max_tokens, temperature):
    """محاولات OmniRoute لموديلات: CLI لكل موديل ثم HTTP لكل
    موديل (إن وُجد مفتاح) — الترتيب القديم محفوظ."""
    attempts = []
    for m in models:
        attempts.append({"label": "%s عبر CLI" % m, "provider": m,
                         "via": "cli", "model": m,
                         "fn": (lambda m=m: chat_cli(
                             m, prompt, system, max_tokens,
                             temperature))})
    if os.environ.get("OMNIROUTE_API_KEY", "").strip():
        for m in models:
            attempts.append({"label": "%s عبر HTTP" % m,
                             "provider": m, "via": "http", "model": m,
                             "fn": (lambda m=m: chat_http(
                                 base_url, m, prompt, system,
                                 max_tokens, temperature))})
    return attempts


def _provider_attempts(prompt, providers, base_url, system,
                       max_tokens, temperature):
    """محاولات سلسلة N-provider: كل مزود كاملًا بالترتيب
    (OmniRoute: CLI ثم HTTP؛ Gemini: المساعد الآمن؛
    Ollama: /api/chat المحلي — ساق أخيرة).
    مزود بعلَم free_rotation (ركن تناوب مجاني): كل محاولاته
    تحمل rotate_on_quota (‏429 يدوّر عنه لا يعيد المحاولة
    عليه) وdisplay_model (اسم المنتج للمستخدم لا المنبع)."""
    attempts = []
    for prov in providers or []:
        kind = (prov or {}).get("kind")
        model = (prov or {}).get("model")
        if not model:
            continue
        if kind == "ollama":
            ollama_url = ((prov or {}).get("base_url")
                          or OLLAMA_DEFAULT_BASE_URL)
            prov_attempts = [
                {"label": "%s عبر Ollama المحلي" % model,
                 "provider": model, "via": "ollama", "model": model,
                 "fn": (lambda m=model, u=ollama_url: chat_ollama(
                     prompt, model=m, base_url=u, system=system,
                     max_tokens=max_tokens, temperature=temperature))}]
        elif kind == "gemini":
            prov_attempts = [
                {"label": "%s عبر Gemini" % model,
                 "provider": model, "via": "gemini", "model": model,
                 "fn": (lambda m=model: chat_gemini(
                     prompt, model=m, system=system,
                     max_tokens=max_tokens, temperature=temperature))}]
        else:
            prov_attempts = _omniroute_attempts(
                prompt, [model], base_url, system, max_tokens,
                temperature)
        if (prov or {}).get("free_rotation"):
            for att in prov_attempts:
                att["rotate_on_quota"] = True
                att["display_model"] = FREE_LANE_DISPLAY_NAME
        attempts.extend(prov_attempts)
    return attempts


def chat_chain(prompt, providers, system=None, max_tokens=200,
               temperature=0.7, retries=1, retry_delay=5,
               base_url="http://localhost:20128", state=None,
               on_attempt=None):
    """سلسلة بدائل LLM: يجرّب كل مزود بالترتيب حتى ينجح أحدها.

    providers: [{"kind": "omniroute"|"gemini"|"ollama", "model": ...}].
    state: حالة llm_state (اختياري) — مزود في تهدئة يُتخطى.
    on_attempt: (provider, ok, error_kind) بعد كل مزود.
    يرجع (النص، المسار، الموديل)؛ ويرفع LLMAllFailedError
    (عربي) لو فشل الكل. بلا موجّه نظام صريح يُحمَّل الموجّه
    المشترك حرفيًا.
    """
    if not providers:
        raise OmniRouteError("سلسلة المزودين فارغة — لا مزود للتجربة")
    if system is None:
        system = load_system_prompt() or None
    attempts = _provider_attempts(prompt, providers, base_url, system,
                                  max_tokens, temperature)
    return _run_attempts(prompt, attempts, retries, retry_delay,
                         state=state, on_attempt=on_attempt)


def chat_free_rotation(prompt, models, system=None, max_tokens=200,
                       temperature=0.7, retries=1, retry_delay=5,
                       base_url="http://localhost:20128", state=None,
                       on_attempt=None):
    """سلسلة تناوب على نماذج مجانية رسمية (OpenRouter ‎:free
    أولًا عند اكتمال ربطه، ثم أي ركن رسمي مجاني).

    models: معرّفات مجانية بالترتيب — الأفضل من
    discover_free_models (أسعار مُتحقَّق منها حيًا) مدموجة
    مع الأرضية المثبّتة. عند 429 على نموذج يُدوَّر فورًا إلى
    التالي بلا إعادة محاولة عليه، ويُسجَّل التدوير في الحالة
    (عدّاد تدوير + تهدئة لكل نموذج). يرجع (النص، المسار،
    الاسم المعروض للمستخدم) — الاسم المعروض «المسار
    المجاني» لا معرّف نموذج المنبع؛ والمعرّف الحقيقي يبقى
    في الحالة عبر on_attempt.
    """
    providers = free_rotation_providers(models)
    if not providers:
        raise OmniRouteError(
            "لا نماذج مجانية في قائمة التناوب — اكتشفها بـ "
            "discover_free_models أو مرّر الأرضية المثبّتة")
    return chat_chain(prompt, providers, system=system,
                      max_tokens=max_tokens, temperature=temperature,
                      retries=retries, retry_delay=retry_delay,
                      base_url=base_url, state=state,
                      on_attempt=on_attempt)


def chat(prompt, model, fallback_model=None, base_url="http://localhost:20128",
         system=None, max_tokens=200, temperature=0.7,
         retries=1, retry_delay=5, providers=None, state=None,
         on_attempt=None):
    """يحاول CLI أولًا، ثم HTTP لو وُجد مفتاح، ثم الموديل البديل.

    كل محاولة تُعاد تلقائيًا `retries` مرة بفاصل انتظار متضاعف
    (retry_delay ثم ضعفاه...) قبل الانتقال للمحاولة التالية، حتى
    تتجاوز الانقطاعات العابرة بدل اللجوء فورًا للبديل.
    يرجع (النص، المسار المستخدم، الموديل المستخدم).
    يرفع LLMAllFailedError (عربي، فئة OmniRouteError) لو فشلت
    كل المحاولات مع تجميع رسائل الخطأ.
    بلا موجّه نظام صريح يُحمَّل الموجّه المشترك حرفيًا من
    `lib/prompts/story_system.md` (جولة v0.1.37) — كل الأوامر
    (script/ideas/ab/analyze) تتكلم بنفس قواعد الأسلوب.
    providers (اختياري): سلسلة N-provider صريحة
    [{"kind", "model"}] — عند تمريرها تُستخدم بدل
    model/fallback_model (وتضيف ساق Gemini عادةً).
    state/on_attempt (اختياريان): تسجيل حالة المزودين
    (حصة/تهدئة) عبر lib/llm_state.
    """
    if system is None:
        system = load_system_prompt() or None
    if providers is not None:
        attempts = _provider_attempts(prompt, providers, base_url,
                                      system, max_tokens, temperature)
        return _run_attempts(prompt, attempts, retries, retry_delay,
                             state=state, on_attempt=on_attempt)
    models = []
    for m in (model, fallback_model):
        if m and m not in models:
            models.append(m)
    attempts = _omniroute_attempts(prompt, models, base_url, system,
                                   max_tokens, temperature)
    return _run_attempts(prompt, attempts, retries, retry_delay,
                         state=state, on_attempt=on_attempt)
