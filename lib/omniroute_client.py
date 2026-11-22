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
import time
import urllib.error
import urllib.request


class OmniRouteError(Exception):
    pass


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


def chat(prompt, model, fallback_model=None, base_url="http://localhost:20128",
         system=None, max_tokens=200, temperature=0.7,
         retries=1, retry_delay=5):
    """يحاول CLI أولًا، ثم HTTP لو وُجد مفتاح، ثم الموديل البديل.

    كل محاولة تُعاد تلقائيًا `retries` مرة بفاصل انتظار متضاعف
    (retry_delay ثم ضعفاه...) قبل الانتقال للمحاولة التالية، حتى
    تتجاوز الانقطاعات العابرة بدل اللجوء فورًا للبديل.
    يرجع (النص، المسار المستخدم، الموديل المستخدم).
    يرفع OmniRouteError لو فشلت كل المحاولات مع تجميع رسائل الخطأ.
    بلا موجّه نظام صريح يُحمَّل الموجّه المشترك حرفيًا من
    `lib/prompts/story_system.md` (جولة v0.1.37) — كل الأوامر
    (script/ideas/ab/analyze) تتكلم بنفس قواعد الأسلوب.
    """
    if system is None:
        system = load_system_prompt() or None
    errors = []

    def _try(fn, label):
        for attempt in range(retries + 1):
            try:
                return fn()
            except OmniRouteError as e:
                errors.append("%s: %s" % (label, e))
                if attempt < retries:
                    time.sleep(retry_delay * (2 ** attempt))
        return None

    attempts = [(model, "cli")]
    if fallback_model and fallback_model != model:
        attempts.append((fallback_model, "cli"))
    for m, _ in attempts:
        got = _try(lambda m=m: chat_cli(m, prompt, system, max_tokens,
                                        temperature),
                   "%s عبر CLI" % m)
        if got is not None:
            return got, "cli", m
    if os.environ.get("OMNIROUTE_API_KEY", "").strip():
        http_models = []
        for m in [model, fallback_model]:
            if m and m not in http_models:
                http_models.append(m)
        for m in http_models:
            got = _try(lambda m=m: chat_http(base_url, m, prompt, system,
                                             max_tokens, temperature),
                       "%s عبر HTTP" % m)
            if got is not None:
                return got, "http", m
    raise OmniRouteError("؛ ".join(errors))
