#!/usr/bin/env python3
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
_NETWORK_PATTERNS = ("timed out", "timeout", "connection",
                     "unreachable", "name resolution",
                     "temporary failure", "timedout")


def classify_llm_error(text):
    """صنّف رسالة خطأ LLM: quota|auth|server|network|unknown.

    quota = حصة/معدل (429/402) → تهدئة؛ auth = مصادقة
    (401/403) → لا تهدئة (خطأ إعداد)؛ server = 5xx؛
    network = مهلة/اتصال.
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
    for pattern in _NETWORK_PATTERNS:
        if pattern in low:
            return "network"
    return "unknown"


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


def providers_from_config(cfg_o):
    """سلسلة المزودين من قسم omniroute في config.

    [الموديل، البديل (إن اختلف)، Gemini (إن لم يُعطَّل)].
    بلا gemini_enabled صريحًا تكون الساق مفعّلة (أمر المستخدم
    «توصيل Gemini»).
    """
    cfg_o = cfg_o or {}
    providers = []
    for key in ("model", "fallback_model"):
        value = cfg_o.get(key)
        if isinstance(value, str):
            value = value.strip()
        if value and all(p["model"] != value for p in providers):
            providers.append({"kind": "omniroute", "model": value})
    if cfg_o.get("gemini_enabled", True):
        gemini_model = cfg_o.get("gemini_model") or GEMINI_DEFAULT_MODEL
        if isinstance(gemini_model, str):
            gemini_model = gemini_model.strip() or GEMINI_DEFAULT_MODEL
        if all(p["model"] != gemini_model for p in providers):
            providers.append({"kind": "gemini",
                              "model": gemini_model})
    return providers


def _run_attempts(prompt, attempts, retries, retry_delay,
                  state=None, on_attempt=None):
    """محرك المحاولات المشترك: يجرّب كل محاولة بالترتيب.

    attempts: [{"label", "provider", "via", "model", "fn"}].
    كل محاولة تُعاد `retries` مرة بفاصل متضاعف؛ والمزود في
    تهدئة (state) يُتخطى مع تسجيل سبب التخطي. on_attempt
    (إن وُجد) تُستدعى مرة واحدة لكل مزود بنتيجته النهائية
    (provider, ok, error_kind) لتسجيل الحالة.
    يرجع (النص، المسار، الموديل) أو يرفع LLMAllFailedError.
    """
    if not attempts:
        raise OmniRouteError("لا يوجد مزود للتجربة")
    failures = []
    for att in attempts:
        provider = att["provider"]
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
        for attempt in range(retries + 1):
            try:
                got = att["fn"]()
                break
            except OmniRouteError as e:
                last_error = e
                last_kind = classify_llm_error(str(e))
                if attempt < retries:
                    time.sleep(retry_delay * (2 ** attempt))
        if got is not None:
            if on_attempt is not None:
                on_attempt(provider, True, None)
            return got, att["via"], att["model"]
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
    (OmniRoute: CLI ثم HTTP؛ Gemini: المساعد الآمن)."""
    attempts = []
    for prov in providers or []:
        kind = (prov or {}).get("kind")
        model = (prov or {}).get("model")
        if not model:
            continue
        if kind == "gemini":
            attempts.append(
                {"label": "%s عبر Gemini" % model,
                 "provider": model, "via": "gemini", "model": model,
                 "fn": (lambda m=model: chat_gemini(
                     prompt, model=m, system=system,
                     max_tokens=max_tokens, temperature=temperature))})
        else:
            attempts.extend(_omniroute_attempts(
                prompt, [model], base_url, system, max_tokens,
                temperature))
    return attempts


def chat_chain(prompt, providers, system=None, max_tokens=200,
               temperature=0.7, retries=1, retry_delay=5,
               base_url="http://localhost:20128", state=None,
               on_attempt=None):
    """سلسلة بدائل LLM: يجرّب كل مزود بالترتيب حتى ينجح أحدها.

    providers: [{"kind": "omniroute"|"gemini", "model": ...}].
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
