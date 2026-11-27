#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حدود استخدام يومية/شهرية — جولة v0.1.63 (بند 8).

فوق `lib/cost_ledger.py`: يقرأ إجماليات دفتر الاستخدام
(`runs/cost-ledger.jsonl` — سطور JSONL؛ والأسطر التالفة
تُتخطى كما في الدفتر نفسه) ويمنع بدء عمل جديد حين يُبلغ
حد — بلا قطع أي دور جارٍ.

القواعد (عقد ع9):
- الحدود `{dailyUsd, monthlyUsd, dailyTokens, monthlyTokens}`
  على مستوى الاستوديو وكل مهمة/عامل؛ فارغ أو 0 = بلا حد.
- `stops` ∈ `unattended` (افتراضي: يوقف العمل غير المراقب
  فقط — رسالة المنسّق المباشرة تعمل دائمًا) / `everything`.
- الفحص فقط قبل بدء عمل جديد (الدور الجاري يُكمل).
- عند 80%: سطر سجل واحد. عند البلوغ: إشعار واحد (عبر
  ع5 `notify_once` باستيراد كسول داخل الدالة ومخزن إزالة
  التكرار في `runs/notify-dedup.json` لجذر الاستوديو —
  وغياب الوحدة يُتجاهل بهدوء) + سطر سجل.
- الاستئناف تلقائي عند إعادة الضبط (منتصف الليل / أول
  الشهر بتوقيت Africa/Cairo).
- متغيرات البيئة `QISAS_USAGE_CAP_DAILY_USD` /
  `MONTHLY_USD` / `DAILY_TOKENS` / `MONTHLY_TOKENS` /
  `STOPS` تفوز على الملف حقلًا بحقلًا؛ وقيمة ليست رقمًا تُتجاهل.
- المجاميع الجارية: قراءة ملف دفتر الشهر مرة ثم السطور
  الملحقة فقط، وإعادة الفحص على الأكثر كل 15 ثانية
  (يُعاد القراءة فورًا إن تغيّر حجم الملف أو وقته).
- مهمة لمرة واحدة عند الحد لا تُستهلك — ينتقل وقتها إلى
  إعادة الضبط (`defer_one_shot`).
- رفض بأسلوب API: 429 + `Retry-After` للعمل غير المراقب؛
  ورسالة مباشرة تحت `everything`: 409 برمز `spend_cap`.

ملاحظة: دفتر التكلفة الحالي يسجّل وحدات Veo (`units`)؛
ومجاميع الدولار/الرموز تُحسب من حقول `usd` و`tokens`
(أو `prompt_tokens` + `completion_tokens`) في السطور —
فهي صفر حتى تسجّل المزوّدات تلك الحقول، وتُعرض وحدات
Veo في المجاميع للشفافية لا للحد.
"""
import json
import os
import time
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python قديم بلا zoneinfo
    ZoneInfo = None

__all__ = [
    "DEFAULT_STOPS", "WARN_RATIO", "CACHE_TTL_SECONDS",
    "ENV_VARS", "load_caps", "current_totals",
    "check", "defer_one_shot", "next_reset",
    "format_caps", "ledger_summary", "reset_state",
]

DEFAULT_STOPS = "unattended"
WARN_RATIO = 0.8
CACHE_TTL_SECONDS = 15

ENV_VARS = {
    "dailyUsd": "QISAS_USAGE_CAP_DAILY_USD",
    "monthlyUsd": "QISAS_USAGE_CAP_MONTHLY_USD",
    "dailyTokens": "QISAS_USAGE_CAP_DAILY_TOKENS",
    "monthlyTokens": "QISAS_USAGE_CAP_MONTHLY_TOKENS",
    "stops": "QISAS_USAGE_CAP_STOPS",
}

_CONFIG_FILENAME = "usage-caps.json"
_LOG_FILENAME = "usage-caps.log"

# حالة إزالة تكرار التحذيرات/الإشعارات داخل العملية:
# (النطاق، الحد، الفترة) — والملف + notify_once يغطيان
# إزالة التكرار عبر إعادة التشغيل.
_WARNED = set()
_NOTIFIED = set()

# ذاكرة المجاميع الجارية: {مسار الدفتر: {...}}.
_TOTALS_CACHE = {}


def reset_state():
    """صفّر حالة إزالة التكرار وذاكرة المجاميع (للاختبارات)."""
    _WARNED.clear()
    _NOTIFIED.clear()
    _TOTALS_CACHE.clear()


def _cairo_now(now=None):
    """الآن بتوقيت Africa/Cairo (أو المحلي إن غابت zoneinfo)."""
    if now is not None:
        return now
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Africa/Cairo"))
        except Exception:  # noqa: BLE001 — رجوع للمحلي
            pass
    return datetime.now()


def _studio_root(studio_root):
    if studio_root:
        return studio_root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config_path(studio_root=None, config_path=None):
    if config_path:
        return config_path
    return os.path.expanduser(
        os.path.join("~", ".qisas-studio", _CONFIG_FILENAME))


def _to_number(value):
    """حوّل قيمة إلى رقم — أو None إن لم تكن رقمًا صالحًا."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            text = value.strip()
            if not text:
                return None
            return float(text) if "." in text else int(text)
        except ValueError:
            return None
    return None


def load_caps(studio_root=None, config_path=None, env=None):
    """حمّل الحدود: ملف ثم متغيرات بيئة تفوز حقلًا بحقلًا.

    ملف غائب أو تالف ← بلا حدود. قيمة بيئة ليست رقمًا
    تُتجاهل. حد فارغ أو 0 أو سالب = بلا حد.
    يرجع {"dailyUsd", "monthlyUsd", "dailyTokens",
    "monthlyTokens", "stops"}.
    """
    caps = {"dailyUsd": None, "monthlyUsd": None,
            "dailyTokens": None, "monthlyTokens": None,
            "stops": DEFAULT_STOPS}
    path = _config_path(studio_root, config_path)
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = None
    if isinstance(raw, dict):
        for key in ("dailyUsd", "monthlyUsd",
                    "dailyTokens", "monthlyTokens"):
            number = _to_number(raw.get(key))
            if number is not None and number > 0:
                caps[key] = number
        stops = raw.get("stops")
        if stops in ("unattended", "everything"):
            caps["stops"] = stops
    environ = env if env is not None else os.environ
    for key, var in ENV_VARS.items():
        value = environ.get(var)
        if value is None:
            continue
        if key == "stops":
            if value.strip() in ("unattended", "everything"):
                caps["stops"] = value.strip()
            continue
        number = _to_number(value)
        if number is not None and number > 0:
            caps[key] = number
    return caps


def _entry_amounts(entry):
    """(دولار، رموز، وحدات) من سطر دفتر واحد."""
    usd = _to_number(entry.get("usd"))
    if usd is None:
        usd = _to_number(entry.get("dollars"))
    tokens = _to_number(entry.get("tokens"))
    if tokens is None:
        prompt = _to_number(entry.get("prompt_tokens")) or 0
        completion = _to_number(entry.get("completion_tokens")) or 0
        tokens = prompt + completion
    units = _to_number(entry.get("units")) or 0
    return (usd or 0, tokens or 0, units or 0)


def _entry_date(entry):
    """تاريخ السطر "YYYY-MM-DD" من حقل date — أو None."""
    date = entry.get("date")
    if not isinstance(date, str):
        return None
    text = date.strip()[:10]
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        return None
    if not (text[:4].isdigit() and text[5:7].isdigit()
            and text[8:10].isdigit()):
        return None
    return text


def _read_appended(path, cache):
    """اقرأ السطور الملحقة فقط منذ آخر قراءة.

    أول قراءة: الملف كاملًا. لاحقًا: من الإزاحة المحفوظة
    فقط؛ وإن صغر الملف (تدوير) أُعيد من البداية. الأسطر
    التالفة تُتخطى. يحدّث الذاكرة ويرجع قائمة القيود الكاملة.
    """
    try:
        stat = os.stat(path)
    except OSError:
        cache["entries"] = []
        cache["offset"] = 0
        cache["size"] = 0
        cache["mtime"] = 0
        return cache["entries"]
    if stat.st_size < cache.get("offset", 0):
        cache["offset"] = 0
        cache["entries"] = []
    entries = cache.get("entries", [])
    try:
        with open(path, encoding="utf-8") as fh:
            fh.seek(cache.get("offset", 0))
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
            cache["offset"] = fh.tell()
    except OSError:
        return entries
    cache["entries"] = entries
    cache["size"] = stat.st_size
    cache["mtime"] = stat.st_mtime
    return entries


def current_totals(studio_root=None, now=None, scope="studio",
                   refresh=False):
    """مجاميع دفتر الاستخدام الجارية (يوم/شهر) لنطاق.

    تقرأ ملف الدفتر مرة ثم الملحق فقط، وتعيد الفحص على
    الأكثر كل 15 ثانية ما لم يتغيّر حجم الملف أو وقته.
    يرجع {"dailyUsd", "monthlyUsd", "dailyTokens",
    "monthlyTokens", "dailyUnits", "monthlyUnits",
    "entries"} — والمدخلات بلا تاريخ صالح لا تُحسب في
    مجاميع اليوم/الشهر.
    """
    from lib import cost_ledger
    root = _studio_root(studio_root)
    path = cost_ledger.ledger_path(root)
    moment = _cairo_now(now)
    today = moment.strftime("%Y-%m-%d")
    month = moment.strftime("%Y-%m")
    cache = _TOTALS_CACHE.setdefault(
        path, {"entries": [], "offset": 0, "size": 0,
               "mtime": 0, "checked_at": 0.0})
    now_mono = time.monotonic()
    try:
        stat = os.stat(path)
        changed = (stat.st_size != cache.get("size")
                   or stat.st_mtime != cache.get("mtime"))
    except OSError:
        changed = cache.get("size") not in (0, None)
        if not cache.get("entries") and not changed:
            cache["checked_at"] = now_mono
            return {"dailyUsd": 0, "monthlyUsd": 0,
                    "dailyTokens": 0, "monthlyTokens": 0,
                    "dailyUnits": 0, "monthlyUnits": 0,
                    "entries": 0}
    if refresh or changed or \
            (now_mono - cache.get("checked_at", 0.0)
             >= CACHE_TTL_SECONDS):
        _read_appended(path, cache)
        cache["checked_at"] = now_mono
    totals = {"dailyUsd": 0, "monthlyUsd": 0,
              "dailyTokens": 0, "monthlyTokens": 0,
              "dailyUnits": 0, "monthlyUnits": 0,
              "entries": 0}
    for entry in cache.get("entries", []):
        if scope != "studio":
            entry_scope = entry.get("scope") or entry.get("task")
            if entry_scope != scope:
                continue
        day = _entry_date(entry)
        if day is None:
            continue
        usd, tokens, units = _entry_amounts(entry)
        totals["entries"] += 1
        if day[:7] == month:
            totals["monthlyUsd"] += usd
            totals["monthlyTokens"] += tokens
            totals["monthlyUnits"] += units
            if day == today:
                totals["dailyUsd"] += usd
                totals["dailyTokens"] += tokens
                totals["dailyUnits"] += units
    return totals


def next_reset(period, now=None):
    """وقت إعادة الضبط التالي: منتصف ليل اليوم / أول الشهر."""
    moment = _cairo_now(now)
    if period == "monthly":
        year = moment.year + (1 if moment.month == 12 else 0)
        month = 1 if moment.month == 12 else moment.month + 1
        target = moment.replace(year=year, month=month, day=1,
                                hour=0, minute=0, second=0,
                                microsecond=0)
    else:
        target = (moment + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
    return target


def _log_line(studio_root, message, now=None):
    """ألحق سطرًا بسجل الحدود `runs/usage-caps.log` (0600)."""
    root = _studio_root(studio_root)
    path = os.path.join(root, "runs", _LOG_FILENAME)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        stamp = _cairo_now(now).strftime("%Y-%m-%d %H:%M:%S")
        line = ("[%s] %s\n" % (stamp, message)).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                     0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        return path
    except OSError:
        return None


def _notify_once(key, message, studio_root=None):
    """إشعار واحد عبر ع5 — باستيراد كسول؛ وغياب الوحدة يُتجاهل.

    مخزن إزالة التكرار يُنطَّق بمجلد runs لجذر الاستوديو
    (فيمرّر runs_dir) فيبقى الاختبار في مجلد مؤقت بلا
    مساس بمخزن الشجرة الحقيقية؛ وإن رفضت نسخة notify
    وسيط runs_dir يُعاد الاستدعاء بدونه.
    """
    if key in _NOTIFIED:
        return False
    try:
        from lib import notify
        try:
            runs_dir = os.path.join(_studio_root(studio_root),
                                    "runs")
            sent = notify.notify_once(key, message, channel="log",
                                      runs_dir=runs_dir)
        except TypeError:
            sent = notify.notify_once(key, message, channel="log")
    except Exception:  # noqa: BLE001 — الإشعار لا يكسر الفحص أبدًا
        return False
    if sent:
        _NOTIFIED.add(key)
    return bool(sent)


# (مفتاح الحد، مفتاح المجموع، الفترة، التسمية العربية)
_CAP_FIELDS = (
    ("dailyUsd", "dailyUsd", "daily", "الحد اليومي بالدولار"),
    ("monthlyUsd", "monthlyUsd", "monthly", "الحد الشهري بالدولار"),
    ("dailyTokens", "dailyTokens", "daily", "الحد اليومي بالرموز"),
    ("monthlyTokens", "monthlyTokens", "monthly",
     "الحد الشهري بالرموز"),
)


def check(kind, scope="studio", studio_root=None, caps=None,
          now=None, totals=None):
    """افحص حدود الاستخدام قبل بدء عمل جديد.

    kind: "unattended" (روتين/webhook/تسليم) أو "direct"
    (رسالة المنسّق المباشرة). scope: "studio" أو اسم مهمة/
    عامل. يرجع {"allowed", "reason", "retry_after",
    "code", "status", "usage", "caps", "resets_at",
    "blocked_by"} حيث code هو "spend_cap" عند الرفض،
    وstatus هو 429 للعمل غير المراقب و409 للرسالة المباشرة
    تحت `everything`. الدور الجاري لا يقطعه هذا الفحص —
    المستدعي يفحص فقط قبل بدء عمل جديد.
    """
    moment = _cairo_now(now)
    caps = caps if isinstance(caps, dict) else load_caps(
        studio_root=studio_root)
    stops = caps.get("stops") or DEFAULT_STOPS
    if stops not in ("unattended", "everything"):
        stops = DEFAULT_STOPS
    usage = totals if isinstance(totals, dict) else current_totals(
        studio_root=studio_root, now=moment, scope=scope)
    period_label = {"daily": moment.strftime("%Y-%m-%d"),
                    "monthly": moment.strftime("%Y-%m")}
    blocked_by = None
    blocked_limit = None
    blocked_period = None
    warned = []
    for cap_key, total_key, period, label in _CAP_FIELDS:
        limit = caps.get(cap_key)
        if limit is None:
            continue
        try:
            limit = float(limit)
        except (TypeError, ValueError):
            continue
        if limit <= 0:
            continue
        used = usage.get(total_key) or 0
        if used >= limit and blocked_by is None:
            blocked_by = cap_key
            blocked_limit = limit
            blocked_period = period
        elif used >= WARN_RATIO * limit:
            warned.append((cap_key, period, label, used, limit))
    for cap_key, period, label, used, limit in warned:
        key = (scope, cap_key, period_label[period])
        if key not in _WARNED:
            _WARNED.add(key)
            _log_line(studio_root,
                      "تحذير: بلغ الاستخدام %s%% من %s "
                      "(%s من %s) — النطاق %s"
                      % (int(used / limit * 100), label, used,
                         limit, scope),
                      now=moment)
    if blocked_by is None:
        return {"allowed": True,
                "reason": "ضمن حدود الاستخدام",
                "retry_after": None, "code": None, "status": None,
                "usage": usage, "caps": caps, "resets_at": None,
                "blocked_by": None}
    reset = next_reset(blocked_period, now=moment)
    retry_after = max(0, int((reset - moment).total_seconds()))
    resets_at = reset.strftime("%Y-%m-%dT%H:%M:%S")
    label = dict((c, l) for c, _t, _p, l in _CAP_FIELDS)[blocked_by]
    reason = ("بُلغ %s (%s من %s) — النطاق %s؛ يستأنف العمل "
              "عند %s" % (label, usage.get(
                  dict((c, t) for c, t, _p, _l in _CAP_FIELDS)
                  [blocked_by]) or 0, blocked_limit, scope,
                  resets_at))
    if kind == "direct" and stops == "unattended":
        # الرسالة المباشرة تعمل دائمًا تحت unattended.
        return {"allowed": True,
                "reason": "الحد مُبلَّغ لكن الرسالة المباشرة "
                          "تعمل دائمًا",
                "retry_after": retry_after, "code": "spend_cap",
                "status": None, "usage": usage, "caps": caps,
                "resets_at": resets_at, "blocked_by": blocked_by}
    key = (scope, blocked_by, period_label[blocked_period])
    if key not in _NOTIFIED:
        _log_line(studio_root,
                  "بُلغ %s (%s) — النطاق %s؛ العمل الجديد "
                  "موقوف حتى %s"
                  % (label, blocked_by, scope, resets_at),
                  now=moment)
        _notify_once("usage-cap:%s:%s:%s"
                     % (scope, blocked_by,
                        period_label[blocked_period]),
                     "بُلغ %s — النطاق %s؛ يستأنف العمل عند %s"
                     % (label, scope, resets_at),
                     studio_root=studio_root)
        _NOTIFIED.add(key)
    status = 409 if kind == "direct" else 429
    return {"allowed": False, "reason": reason,
            "retry_after": retry_after, "code": "spend_cap",
            "status": status, "usage": usage, "caps": caps,
            "resets_at": resets_at, "blocked_by": blocked_by}


def defer_one_shot(result):
    """هل تُؤجَّل مهمة لمرة واحدة؟ — لا تُستهلك عند الحد.

    يرجع {"deferred": bool, "run_at": وقت إعادة الضبط أو
    None}. مهمة مرفوضة تنتقل إلى إعادة الضبط فتعمل حينها؛
    ومهمة مسموحة تعمل الآن.
    """
    if not isinstance(result, dict):
        return {"deferred": False, "run_at": None}
    if result.get("allowed"):
        return {"deferred": False, "run_at": None}
    return {"deferred": True, "run_at": result.get("resets_at")}


def format_caps(caps, usage=None):
    """نص عربي للحدود والمجاميع (لأمر `usage caps show` لاحقًا)."""
    caps = caps or {}
    lines = ["حدود الاستخدام (stops=%s):"
             % (caps.get("stops") or DEFAULT_STOPS)]
    for cap_key, _total_key, _period, label in _CAP_FIELDS:
        limit = caps.get(cap_key)
        lines.append("  %s: %s" % (
            label, "بلا حد" if limit in (None, 0) else str(limit)))
    if isinstance(usage, dict):
        lines.append("المجاميع الجارية: %s دولار اليوم / %s "
                     "هذا الشهر؛ %s رمزًا اليوم / %s هذا الشهر"
                     % (usage.get("dailyUsd") or 0,
                        usage.get("monthlyUsd") or 0,
                        usage.get("dailyTokens") or 0,
                        usage.get("monthlyTokens") or 0))
    return "\n".join(lines)


def ledger_summary(studio_root=None):
    """ملخص دفتر التكلفة كاملًا عبر lib/cost_ledger (كل الأوقات)."""
    from lib import cost_ledger
    root = _studio_root(studio_root)
    return cost_ledger.totals(cost_ledger.history(root))
