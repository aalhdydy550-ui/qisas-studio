#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""سياسة إعادة محاولة HTTP موحّدة للاستوديو — جولة الأنماط (W1).

الفكرة من PRAW/prawcore (§2 من مسح PRAW) ومن Firecrawl (§3-4
من مسح firecrawl) — منقولة كمفهوم تصميم لا ككود: إعادة محاولة
محدودة + تراجع أسّي مع jitter + احترام `Retry-After` + تصنيف
الأخطاء + قراءة ترويسات حدود المعدل وتسجيلها. كل شيء هنا
بايثون من الصفر بالمكتبة القياسية فقط.

قواعد ثابتة:
- حدّ أقصى 3–5 محاولات إجمالًا (لا حلقات بلا نهاية).
- خطأ منطقي (400/401/403/404...) لا يُعاد أبدًا — خطأ إعداد
  لا تُصلحه إعادة المحاولة.
- `Retry-After` يُحترم لكن بسقف نوم قصير (30 ثانية افتراضيًا):
  فوق السقف لا ننام — نرفع `RetryAfterTooLong` فيعيد المستدعي
  الجدولة في كرون لاحق بدل تفويت موعد النشر (لا ننسخ
  `ratelimit_seconds=300` حرفيًا أبدًا).
- ميزانية زمنية إجمالية: عند تجاوزها نتوقف ونرفع
  `RetryBudgetExceeded` بدل الاستمرار.
- ترويسات حدود المعدل تُقرأ من كل استجابة (محوّل لكل مزود)
  وتُسجَّل في السجل — لا تُخمَّن الحدود.
"""
import json
import logging
import math
import random
import time
import urllib.error
from email.utils import parsedate_to_datetime

__all__ = [
    "HttpStatusError", "TransportError", "RetryAfterTooLong",
    "RetryBudgetExceeded", "RetryPolicy", "classify_status",
    "classify_exception", "parse_retry_after",
    "parse_rate_limit_headers", "format_rate_limit_log",
    "log_rate_limit", "call_with_retry",
    "routine_backoff_delay", "routine_backoff_sequence",
    "ROUTINE_BACKOFF_FIRST_SECONDS", "ROUTINE_BACKOFF_MAX_SECONDS",
]

_LOG = logging.getLogger("studio.retry_policy")

# ─── التصنيف ───
# نقل: بلا استجابة (مهلة/اتصال) — يُعاد.
# rate_limited: 429 (و402 — حصة/رصيد منتهٍ بتصنيف llm_state
# نفسه) — يُعاد بعد انتظار.
# server: 5xx — يُعاد.
# logical: كل 4xx الأخرى (400/401/403/404...) — لا يُعاد أبدًا.
RETRYABLE_KINDS = frozenset({"transport", "rate_limited", "server"})
LOGICAL_STATUSES = frozenset({
    400, 401, 403, 404, 405, 406, 409, 410, 411, 412, 413, 414, 415,
    416, 422, 423, 424, 426, 428, 431, 451,
})
SERVER_STATUSES = frozenset({500, 501, 502, 503, 504, 505, 507, 508})

# حدود السياسة الافتراضية (جولة الأنماط — W1).
DEFAULT_MAX_ATTEMPTS = 3
MAX_ATTEMPTS_LIMIT = 5
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0
# سقف النوم عند Retry-After: فوقه إعادة جدولة لا نوم.
DEFAULT_MAX_RETRY_AFTER = 30.0
DEFAULT_TOTAL_BUDGET = 120.0


class HttpStatusError(Exception):
    """خطأ HTTP بردّ فعلي: الحالة + الترويسات + تفصيل مختصر.

    يرفعه محوّل HTTP (urllib وغيره) بدل الاستثناء الخام حتى
    تعرف السياسة الحالة والترويسات دون تحليل نص.
    """

    def __init__(self, status, headers=None, detail=""):
        self.status = int(status) if status is not None else None
        self.headers = dict(headers or {})
        self.detail = detail or ""
        super().__init__("HTTP %s: %s" % (self.status, self.detail))

    @property
    def retry_after(self):
        return parse_retry_after(self.headers)


class TransportError(Exception):
    """خطأ نقل بلا ردّ (مهلة/اتصال/تحليل اسم) — قابل لإعادة المحاولة."""


class RetryAfterTooLong(Exception):
    """المزود طلب انتظارًا أطول من سقف النوم — أعد الجدولة لاحقًا.

    .retry_after: الثواني المطلوبة. لا تنمها داخل الكرون.
    """

    def __init__(self, retry_after):
        self.retry_after = float(retry_after)
        super().__init__(
            "المزود طلب الانتظار %.0f ثانية — أطول من سقف النوم "
            "(%.0f ثانية)؛ أعد جدولة المحاولة في كرون لاحق بدل "
            "النوم داخل الكرون" % (self.retry_after,
                                   DEFAULT_MAX_RETRY_AFTER))


class RetryBudgetExceeded(Exception):
    """نفدت الميزانية الزمنية الإجمالية لإعادة المحاولة."""

    def __init__(self, last_error=None):
        self.last_error = last_error
        super().__init__(
            "نفدت الميزانية الزمنية لإعادة المحاولة (%s)"
            % (last_error or "بلا تفاصيل"))


def classify_status(status):
    """صنّف حالة HTTP: transport|rate_limited|server|logical.

    status=None (بلا ردّ) = transport. 429/402 = rate_limited؛
    5xx = server؛ أي 4xx آخر = logical.
    """
    if status is None:
        return "transport"
    try:
        code = int(status)
    except (TypeError, ValueError):
        return "logical"
    if code == 429 or code == 402:
        return "rate_limited"
    if code in SERVER_STATUSES or 500 <= code <= 599:
        return "server"
    if code == 408 or code == 425:
        return "transport"
    if 400 <= code <= 499:
        return "logical"
    return "logical"


def _headers_get(headers, name):
    """قراءة ترويسة بلا حساسية لحالة الأحرف.

    يقبل قاموسًا عاديًا أو كائن ترويسات (HTTPMessage) أو
    قائمة أزواج.
    """
    if headers is None:
        return None
    lowered = name.lower()
    if hasattr(headers, "get"):
        try:
            value = headers.get(name)
        except Exception:
            value = None
        if value is not None:
            return value
        try:
            items = headers.items()
        except Exception:
            items = None
        if items:
            for key, value in items:
                if str(key).lower() == lowered:
                    return value
        return None
    if isinstance(headers, (list, tuple)):
        for key, value in headers:
            if str(key).lower() == lowered:
                return value
    return None


def parse_retry_after(headers):
    """ثواني `Retry-After` من الترويسات، أو None.

    يقبل عدد ثوانٍ ("120") أو تاريخ HTTP ("Wed, 21 Oct ...").
    قيمة تالفة أو سالبة ← None (لا تُخمَّن).
    """
    raw = _headers_get(headers, "Retry-After")
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
        return seconds if seconds >= 0 else None
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    try:
        delta = (when.timestamp() - time.time())
    except (OverflowError, OSError, ValueError):
        return None
    return max(delta, 0.0) if delta >= 0 else 0.0


def _parse_duration_seconds(raw):
    """مدّة مثل "120" أو "1m30s" أو "2h" ← ثوانٍ، أو None."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    try:
        value = float(text)
        return value if value >= 0 else None
    except ValueError:
        pass
    total = 0.0
    number = ""
    seen_unit = False
    units = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
    for char in text:
        if char.isdigit() or char == ".":
            number += char
        elif char in units and number:
            total += float(number) * units[char]
            number = ""
            seen_unit = True
        elif char in (" ",):
            continue
        else:
            return None
    if number and seen_unit:
        total += float(number)
    return total if seen_unit else None


def _parse_epoch_reset(raw):
    """إعادة ضبط كطابع زمني (ثوانٍ أو ملّي ثانية أو ISO) ← ثوانٍ متبقية."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        try:
            when = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if when is None:
            return None
        return max(when.timestamp() - time.time(), 0.0)
    if value > 1e12:  # ملّي ثانية
        value /= 1000.0
    if value > 1e9:  # طابع Unix (ثوانٍ)
        return max(value - time.time(), 0.0)
    return value if value >= 0 else None


# ─── محوّلات ترويسات حدود المعدل (محوّل لكل مزود) ───
# كل مزود يسمّي ترويساته بشكل مختلف؛ المحوّل يترجمها إلى
# قرار واحد: {remaining, limit, reset_in, retry_after}.
_PROVIDER_HEADER_NAMES = {
    # (remaining, limit, reset) — أسماء الترويسات بالترتيب.
    "gemini": (("x-ratelimit-remaining", "ratelimit-remaining"),
               ("x-ratelimit-limit", "ratelimit-limit"),
               ("x-ratelimit-reset", "ratelimit-reset")),
    "groq": (("x-ratelimit-remaining-requests",
              "x-ratelimit-remaining-tokens",
              "x-ratelimit-remaining"),
             ("x-ratelimit-limit-requests",
              "x-ratelimit-limit-tokens",
              "x-ratelimit-limit"),
             ("x-ratelimit-reset-requests",
              "x-ratelimit-reset-tokens",
              "x-ratelimit-reset")),
    "openrouter": (("x-ratelimit-remaining", "ratelimit-remaining"),
                   ("x-ratelimit-limit", "ratelimit-limit"),
                   ("x-ratelimit-reset", "ratelimit-reset")),
    "facebook": ((), (), ()),
    "omniroute": (("x-ratelimit-remaining", "ratelimit-remaining"),
                  ("x-ratelimit-limit", "ratelimit-limit"),
                  ("x-ratelimit-reset", "ratelimit-reset")),
}


def _first_present(headers, names):
    for name in names:
        value = _headers_get(headers, name)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _to_int(raw):
    if raw is None:
        return None
    try:
        return int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def parse_rate_limit_headers(provider, headers):
    """ترجم ترويسات حدود المعدل لمزود إلى قاموس موحّد.

    يرجع {"provider", "remaining", "limit", "reset_in",
    "retry_after", "usage_percent"} — كل قيمة None إن غابت.
    facebook بلا X-RateLimit-*: يقرأ `x-app-usage` /
    `x-page-usage` (JSON بنسب مئوية) فيعيد usage_percent
    (أعلى نسبة). مزود غير معروف: مسح عام لأي ترويسة تحوي
    "ratelimit".
    """
    provider = (provider or "").strip().lower() or "unknown"
    info = {"provider": provider, "remaining": None, "limit": None,
            "reset_in": None, "retry_after": parse_retry_after(headers),
            "usage_percent": None}
    if provider == "facebook":
        for name in ("x-app-usage", "x-page-usage",
                     "x-ad-account-usage"):
            raw = _headers_get(headers, name)
            if raw is None:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except ValueError:
                continue
            if isinstance(data, dict):
                percents = [v for v in data.values()
                            if isinstance(v, (int, float))]
                if percents:
                    top = max(percents)
                    if info["usage_percent"] is None:
                        info["usage_percent"] = top
                    else:
                        info["usage_percent"] = max(
                            info["usage_percent"], top)
        return info
    names = _PROVIDER_HEADER_NAMES.get(provider)
    if names is None:
        # مسح عام: أي ترويسة تحوي ratelimit + الكلمة المفتاحية.
        remaining = limit = reset = None
        items = []
        try:
            items = list(headers.items())
        except Exception:
            items = []
        for key, value in items:
            low = str(key).lower()
            if "ratelimit" not in low:
                continue
            if "remaining" in low and remaining is None:
                remaining = value
            elif "limit" in low and limit is None:
                limit = value
            elif "reset" in low and reset is None:
                reset = value
        info["remaining"] = _to_int(remaining)
        info["limit"] = _to_int(limit)
        info["reset_in"] = _parse_duration_seconds(reset)
        if info["reset_in"] is None:
            info["reset_in"] = _parse_epoch_reset(reset)
        return info
    rem_names, limit_names, reset_names = names
    info["remaining"] = _to_int(_first_present(headers, rem_names))
    info["limit"] = _to_int(_first_present(headers, limit_names))
    reset_raw = _first_present(headers, reset_names)
    info["reset_in"] = _parse_duration_seconds(reset_raw)
    if info["reset_in"] is None:
        info["reset_in"] = _parse_epoch_reset(reset_raw)
    return info


def format_rate_limit_log(provider, info):
    """سطر سجل عربي واحد من معلومات حدّ المعدل — "" إن غابت كلها."""
    if not isinstance(info, dict):
        return ""
    parts = []
    if info.get("remaining") is not None:
        if info.get("limit") is not None:
            parts.append("المتبقي %s/%s" % (info["remaining"],
                                            info["limit"]))
        else:
            parts.append("المتبقي %s" % info["remaining"])
    if info.get("reset_in") is not None:
        parts.append("إعادة الضبط خلال %.0f ثانية"
                     % info["reset_in"])
    if info.get("retry_after") is not None:
        parts.append("Retry-After ‏%.0f ثانية"
                     % info["retry_after"])
    if info.get("usage_percent") is not None:
        parts.append("الاستخدام %s%%" % info["usage_percent"])
    if not parts:
        return ""
    return "حد المعدل [%s]: %s" % (provider, "، ".join(parts))


def log_rate_limit(provider, headers, logger=None):
    """اقرأ ترويسات حدّ المعدل وسجّلها؛ يرجع قاموس المعلومات.

    logger: دالة logger(msg) أو None (يستخدم logging).
    """
    info = parse_rate_limit_headers(provider, headers)
    line = format_rate_limit_log(provider, info)
    if line:
        if logger is not None:
            logger(line)
        else:
            _LOG.info(line)
    return info


# ─── السياسة ───

class RetryPolicy:
    """إعادة محاولة محدودة + تراجع أسّي مع jitter + ميزانية إجمالية.

    max_attempts: إجمالي المحاولات (1–5؛ الافتراضي 3).
    base_delay: فاصل أول محاولة إعادة (ثوانٍ).
    max_delay: سقف أي فاصل واحد.
    max_retry_after: سقف النوم عند Retry-After — فوقه يرفع
      call_with_retry ‏RetryAfterTooLong بدل النوم.
    total_budget_seconds: الميزانية الزمنية الإجمالية لكل
      المحاولات + فواصلها.
    jitter: تراجع أسّي مع jitter كامل (uniform(0, delay)) —
      يمنع تزامن إعادة المحاولات.
    rng: مولّد عشوائي قابل للحقن (للاختبارات).
    """

    def __init__(self, max_attempts=DEFAULT_MAX_ATTEMPTS,
                 base_delay=DEFAULT_BASE_DELAY,
                 max_delay=DEFAULT_MAX_DELAY,
                 max_retry_after=DEFAULT_MAX_RETRY_AFTER,
                 total_budget_seconds=DEFAULT_TOTAL_BUDGET,
                 jitter=True, rng=None):
        max_attempts = int(max_attempts)
        if max_attempts < 1 or max_attempts > MAX_ATTEMPTS_LIMIT:
            raise ValueError(
                "max_attempts يجب أن يكون بين 1 و%d (أُعطي %d)"
                % (MAX_ATTEMPTS_LIMIT, max_attempts))
        if base_delay < 0 or max_delay < 0 or max_retry_after < 0:
            raise ValueError("الفواصل الزمنية لا تكون سالبة")
        if total_budget_seconds <= 0:
            raise ValueError("الميزانية الزمنية يجب أن تكون موجبة")
        self.max_attempts = max_attempts
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)
        self.max_retry_after = float(max_retry_after)
        self.total_budget_seconds = float(total_budget_seconds)
        self.jitter = bool(jitter)
        self._rng = rng or random

    def delay_for(self, attempt, retry_after=None):
        """فاصل الانتظار قبل إعادة المحاولة رقم attempt (0-based).

        بلا Retry-After: أسّي base * 2**attempt مسقوفًا
        بـ max_delay. مع Retry-After: يُحترم كما هو مسقوفًا
        بـ max_delay (تجاوز سقف النوم يُبتّ فيه قبل الاستدعاء
        — انظر should_retry). مع jitter: uniform(0, delay).
        """
        if retry_after is not None:
            delay = min(max(float(retry_after), 0.0), self.max_delay)
        else:
            delay = min(self.base_delay * (2 ** max(int(attempt), 0)),
                        self.max_delay)
        if self.jitter and delay > 0:
            delay = self._rng.uniform(0, delay)
        return delay

    def should_retry(self, kind, attempts_made, elapsed,
                     retry_after=None):
        """هل تُعاد المحاولة؟ kind من classify_*؛ attempts_made
        عدد المحاولات المنفَّذة فعلًا؛ elapsed ثوانٍ منذ البداية."""
        if kind not in RETRYABLE_KINDS:
            return False
        if attempts_made >= self.max_attempts:
            return False
        if elapsed >= self.total_budget_seconds:
            return False
        if retry_after is not None and \
                retry_after > self.max_retry_after:
            return False
        return True


def classify_exception(exc):
    """صنّف استثناءً إلى (kind, retry_after) أو None إن لم يُعرف.

    يعرف: HttpStatusError وTransportError (من هذه الوحدة)،
    وurllib.error.HTTPError/URLError، وTimeoutError/
    ConnectionError/OSError (نقل). غير ذلك ← None (لا إعادة
    محاولة عمياء على خطأ غير مصنَّف).
    """
    if isinstance(exc, HttpStatusError):
        return (classify_status(exc.status), exc.retry_after)
    if isinstance(exc, TransportError):
        return ("transport", None)
    if isinstance(exc, urllib.error.HTTPError):
        try:
            headers = exc.headers
        except Exception:
            headers = None
        return (classify_status(exc.code),
                parse_retry_after(headers))
    if isinstance(exc, urllib.error.URLError):
        return ("transport", None)
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return ("transport", None)
    return None


def call_with_retry(fn, policy=None, sleep=time.sleep,
                    clock=time.monotonic, on_retry=None,
                    classify=None):
    """نفّذ fn() مع إعادة محاولة حسب السياسة؛ يرجع نتيجتها.

    fn: دالة بلا وسيطات ترفع HttpStatusError/TransportError
      (أو ما يعرفه classify) عند الفشل القابل لإعادة المحاولة.
    classify: دالة classify(exc) -> (kind, retry_after) أو None
      — الافتراضي classify_exception. تُستخدم لمحوّلات ترفع
      استثناءاتها الخاصة (مثل SocialPublishError).
    on_retry(attempt, kind, delay, exc): تُستدعى قبل كل نوم.
    عند Retry-After فوق سقف النوم يرفع RetryAfterTooLong
    (أعد الجدولة لاحقًا)؛ وعند نفاد الميزانية يرفع
    RetryBudgetExceeded؛ وعند استنفاد المحاولات يعيد رفع
    آخر خطأ كما هو.
    """
    policy = policy or RetryPolicy()
    classify = classify or classify_exception
    start = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:
            classified = classify(exc)
            if classified is None:
                raise
            kind, retry_after = classified
            elapsed = clock() - start
            if retry_after is not None and \
                    retry_after > policy.max_retry_after:
                raise RetryAfterTooLong(retry_after) from exc
            if not policy.should_retry(kind, attempt, elapsed,
                                       retry_after):
                raise
            delay = policy.delay_for(attempt - 1, retry_after)
            if elapsed + delay > policy.total_budget_seconds:
                raise RetryBudgetExceeded(exc) from exc
            if on_retry is not None:
                on_retry(attempt, kind, delay, exc)
            sleep(delay)


# ─── تراجع موثوقية الروتينات (جولة v0.1.63 — بند 38) ───
# بعد جولة روتين فاشلة: انتظار 15 دقيقة ثم مضاعفة حتى
# سقف 4 ساعات، مع jitter كامل (uniform(0, delay) — نفس
# نمط RetryPolicy.delay_for فيمنع تزامن إعادة المحاولات).
# هذا تسلسل زمني لا سياسة HTTP: بلا حد محاولات هنا —
# المستدعي (lib/schedule_watch.py) يقرر متى يتوقف.
ROUTINE_BACKOFF_FIRST_SECONDS = 900.0   # 15 دقيقة
ROUTINE_BACKOFF_MAX_SECONDS = 14400.0   # 4 ساعات


def routine_backoff_delay(failure_index, jitter=True, rng=None):
    """فاصل الانتظار بعد الفشل رقم failure_index (0-based).

    failure_index=0 ← 15 دقيقة؛ ثم 30م، 60م، 120م، 240م
    (سقف 4 ساعات)؛ وبعدها يبقى السقف. مع jitter (الافتراضي):
    uniform(0, delay)؛ وبلا jitter يرجع القيمة الدقيقة
    (للتخطيط والاختبار). failure_index سالب يُعامل كصفر.
    """
    index = max(int(failure_index), 0)
    delay = min(ROUTINE_BACKOFF_FIRST_SECONDS * (2 ** index),
                ROUTINE_BACKOFF_MAX_SECONDS)
    if jitter and delay > 0:
        delay = (rng or random).uniform(0, delay)
    return delay


def routine_backoff_sequence(count, jitter=False, rng=None):
    """تسلسل فواصل التراجع لأول count فشلًا (قائمة ثوانٍ).

    بلا jitter (الافتراضي): [900, 1800, 3600, 7200, 14400,
    14400, ...] — القيم الدقيقة. count ≤ 0 ← قائمة فارغة.
    """
    count = int(count)
    if count <= 0:
        return []
    return [routine_backoff_delay(i, jitter=jitter, rng=rng)
            for i in range(count)]
