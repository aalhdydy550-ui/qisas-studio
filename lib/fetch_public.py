#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""جلب صفحات عامة مع احترام robots.txt — جولة الأنماط (W1).

الفكرة من Firecrawl (§3-2 و§3-4 من مسح firecrawl) — منقولة
كمفهوم تصميم لا ككود: فحص `robots.txt` قبل أي جلب (حارس لا
ميزة)، وإعادة محاولة منضبطة عند 429 عبر lib.retry_policy
بحد 3 محاولات وميزانية زمنية إجمالية. بايثون من الصفر
بالمكتبة القياسية فقط.

القواعد:
- المضيف خارج قائمة السماح اليدوية ← رفض بلا أي اتصال.
- robots.txt يمنع المسار ← رفض + تسجيل، بلا جلب.
- robots.txt غير متاح (404/شبكة) ← سماح مع تسجيل (fail-open
  المتعارف عليه — غياب الملف ليس منعًا).
- 429/5xx/نقل ← إعادة محاولة بحد 3 محاولات؛ و4xx منطقي ←
  بلا إعادة. Retry-After فوق 30 ثانية ← RetryAfterTooLong
  (أعد الجدولة لاحقًا بدل النوم).
- طلب واحد لكل مضيف في المرة (بلا تزامن)؛ وrobots.txt
  يُخزَّن مؤقتًا ساعة لكل مضيف.
"""
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from urllib.robotparser import RobotFileParser

from lib import retry_policy as retry_lib

__all__ = [
    "FetchBlockedError", "RobotsBlockedError",
    "AllowlistBlockedError", "fetch_public",
]

_LOG = logging.getLogger("studio.fetch_public")

DEFAULT_USER_AGENT = (
    "qisas-studio/0.1 (+https://github.com/aalhdydy550-ui/qisas-studio)")
# قائمة سماح يدوية — يمرّرها المستدعي صراحةً؛ الافتراضي فارغ
# (لا جلب بلا سماح صريح).
DEFAULT_ALLOWLIST = ()
ROBOTS_CACHE_TTL = 3600.0
FETCH_TIMEOUT = 30
# ميزانية الجلب الإجمالية (محاولات + فواصل) — جلب بحثي عرضي
# لا يعلّق الكرون.
FETCH_TOTAL_BUDGET = 60.0

# ذاكرة robots.txt لكل مضيف: {host: (rules_text, fetched_at)}.
_ROBOTS_CACHE = {}


class FetchBlockedError(Exception):
    """جلب مرفوض (خارج السماح أو ممنوع في robots.txt)."""


class AllowlistBlockedError(FetchBlockedError):
    """المضيف خارج قائمة السماح اليدوية — بلا أي اتصال."""


class RobotsBlockedError(FetchBlockedError):
    """robots.txt يمنع هذا المسار لهذا الوكيل."""


def _default_fetcher(url, headers, timeout):
    """جلب urllib الافتراضي: يرجع (status, headers, body).

    HTTPError ← HttpStatusError (بالحالة والترويسات)؛
    URLError ← TransportError.
    """
    req = urllib.request.Request(url, headers=headers or {},
                                 method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (resp.status, dict(resp.headers),
                    resp.read())
    except urllib.error.HTTPError as e:
        raise retry_lib.HttpStatusError(
            e.code, dict(e.headers or {}),
            e.read().decode("utf-8", "ignore")[:300])
    except urllib.error.URLError as e:
        raise retry_lib.TransportError(
            "تعذر الوصول إلى %s: %s" % (url, e.reason))


def _default_robots_fetcher(robots_url, headers, timeout):
    """جلب robots.txt: يرجع نصه أو None عند غيابه/تعذّره.

    لا يرفع أبدًا — غياب الملف fail-open مع تسجيل.
    """
    try:
        status, _headers, body = _default_fetcher(
            robots_url, headers, timeout)
    except retry_lib.HttpStatusError as e:
        _LOG.info("robots.txt غير متاح لـ %s (HTTP %s) — سماح "
                  "مع تسجيل" % (robots_url, e.status))
        return None
    except retry_lib.TransportError as e:
        _LOG.info("تعذر جلب robots.txt لـ %s (%s) — سماح مع "
                  "تسجيل" % (robots_url, e))
        return None
    if status != 200:
        _LOG.info("robots.txt رد HTTP %s لـ %s — سماح مع تسجيل"
                  % (status, robots_url))
        return None
    return body.decode("utf-8", "ignore")


def _robots_rules(host, user_agent, robots_fetcher, timeout,
                  robots_cache, now):
    """نص robots.txt للمضيف (من الذاكرة إن صلح) أو None."""
    cached = (robots_cache or {}).get(host)
    if cached is not None:
        rules, fetched_at = cached
        if now - fetched_at < ROBOTS_CACHE_TTL:
            return rules
    robots_url = "https://%s/robots.txt" % host
    rules = robots_fetcher(robots_url,
                           {"User-Agent": user_agent}, timeout)
    if robots_cache is not None:
        robots_cache[host] = (rules, now)
    return rules


def _robots_allows(rules, user_agent, url):
    """هل يسمح robots.txt بجلب url؟ None (بلا ملف) ← سماح."""
    if rules is None:
        return True
    parser = RobotFileParser()
    try:
        parser.parse(rules.splitlines())
    except Exception:
        # ملف تالف لا يُقرأ — سماح مع تسجيل لا منع صامت.
        _LOG.info("robots.txt تالف — سماح مع تسجيل")
        return True
    return parser.can_fetch(user_agent, url)


def fetch_public(url, allowlist=DEFAULT_ALLOWLIST,
                 user_agent=DEFAULT_USER_AGENT, timeout=FETCH_TIMEOUT,
                 policy=None, fetcher=None, robots_fetcher=None,
                 robots_cache=None, logger=None, now=None):
    """اجلب صفحة عامة بعد فحص السماح وrobots.txt.

    allowlist: مضيفون مسموحون صراحةً (قائمة يدوية) — بلا
      سماح يُرفض الجلب قبل أي اتصال.
    fetcher(url, headers, timeout) -> (status, headers, body):
      قابل للحقن في الاختبارات؛ الافتراضي urllib.
    robots_fetcher(robots_url, headers, timeout) -> نص أو None:
      قابل للحقن؛ الافتراضي يجلب robots.txt ولا يرفع أبدًا.
    robots_cache: قاموس ذاكرة robots.txt (الافتراضي ذاكرة
      الوحدة)؛ مرّر {} لعزل الاختبارات.
    logger: دالة logger(msg) أو None (يستخدم logging).
    يرجع {"url", "status", "headers", "body"} — body بايتات.
    يرفع AllowlistBlockedError / RobotsBlockedError عند الرفض،
    وHttpStatusError عند 4xx منطقي، وRetryAfterTooLong عند
    Retry-After فوق سقف النوم، وRetryBudgetExceeded عند نفاد
    الميزانية.
    """
    log = logger or _LOG.info
    parsed = urllib.parse.urlparse(url or "")
    host = (parsed.netloc or "").lower().split(":")[0]
    if not host or parsed.scheme not in ("http", "https"):
        raise FetchBlockedError("رابط غير صالح للجلب العام: %s"
                                % (url or ""))
    allowed = {str(h).strip().lower() for h in (allowlist or ())
               if str(h).strip()}
    if host not in allowed:
        log("جلب مرفوض — المضيف %s خارج قائمة السماح اليدوية"
            % host)
        raise AllowlistBlockedError(
            "المضيف %s خارج قائمة السماح اليدوية — أضفه صراحةً "
            "قبل الجلب" % host)
    fetch = fetcher or _default_fetcher
    robots_fetch = robots_fetcher or _default_robots_fetcher
    cache = _ROBOTS_CACHE if robots_cache is None else robots_cache
    moment = time.time() if now is None else float(now)
    rules = _robots_rules(host, user_agent, robots_fetch, timeout,
                          cache, moment)
    if not _robots_allows(rules, user_agent, url):
        log("جلب مرفوض — robots.txt يمنع %s" % url)
        raise RobotsBlockedError(
            "robots.txt يمنع جلب %s (User-agent: %s)"
            % (url, user_agent))
    retry_policy = policy or retry_lib.RetryPolicy(
        max_attempts=3, base_delay=1.0,
        total_budget_seconds=FETCH_TOTAL_BUDGET)
    headers = {"User-Agent": user_agent,
               "Accept": "text/html,application/xhtml+xml,*/*"}
    status, resp_headers, body = retry_lib.call_with_retry(
        lambda: fetch(url, headers, timeout),
        policy=retry_policy)
    retry_lib.log_rate_limit(host, resp_headers, logger=log)
    return {"url": url, "status": status,
            "headers": dict(resp_headers or {}), "body": body}
