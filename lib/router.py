#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""موجّه نماذج سريع يفشل مفتوحًا — جولة v0.1.63 (بند 5 + بند 32).

مصنّف رخيص يختار لكل مهمة فرعية: أي نموذج وأي جهد — بعتبة
0.6 ومهلة 1.5 ثانية، ويفشل مفتوحًا إلى الافتراضي الحالي عند
أي عطل، فلا يتعطل خط الإنتاج أبدًا إن تعطل الموجّه.

القواعد (عقد ع8):
- ميزانيات قصّ ثابتة: الاسم 80، العنوان 120، الوصف 400،
  السطر 500، السياق الأخير 6,000 حرف (من الأحدث رجوعًا
  حتى الميزانية)، الطلب 8,000 حرف.
- `route()` لا ترمي أبدًا — أي عطل يرجع الافتراضي بسبب
  مسمّى (`low_confidence` / `no_choice` / `malformed` /
  `timeout` / `provider_error`).
- كل إجابة تُتحقق قبل استخدامها: اختيار معروض، واحتمال
  رقم، والأرجح فوق العتبة.
- ترتيب المزوّدين: مفتاح Flash-Lite الخاص → مفتاح
  Gemini Flash الخاص → OpenRouter المجاني.
- السجل `runs/decider-log/YYYY-MM.ndjson` (0600): تجزئة
  16 حرفًا للحالة + النموذج + زمن الاستجابة + سبب الفشل
  فقط — بلا نص طلب ولا أوصاف أدوار ولا مفاتيح.
- الاحتفاظ: حذف ما هو أقدم من 180 يومًا
  (`prune_old_logs()`).
- الإعداد `~/.qisas-studio/router.json` (المزوّد، المفتاح
  كمرجع `{env|file}` فقط — مفتاح مكتوب صراحةً يُتجاهل
  ولا يُحفظ أبدًا، العتبة).

الربط في `lib/omniroute_client.py` و`lib/llm_state.py`
و`lib/request_flow.py` يقوم به عامل آخر (الموجة ب) — هذه
الوحدة تقدّم دوالًا نظيفة قابلة للربط فقط، وتقبل `decider`
قابلًا للحقن (دالة تستدعي المزوّد الفعلي) فتبقى بلا شبكة
في الاختبارات.
"""
import hashlib
import json
import os
import threading
import time

__all__ = [
    "CLIP_NAME", "CLIP_TITLE", "CLIP_DESCRIPTION", "CLIP_LINE",
    "CLIP_CONTEXT", "CLIP_REQUEST", "CLIP_LIMITS",
    "DEFAULT_THRESHOLD", "DEFAULT_TIMEOUT", "RETENTION_DAYS",
    "PROVIDER_ORDER", "EFFORTS",
    "clip", "clip_name", "clip_title", "clip_description",
    "clip_line", "clip_context", "clip_request",
    "build_state", "load_config", "key_ref",
    "route", "log_decision", "prune_old_logs",
    "decider_log_dir", "state_hash",
]

# ─── ميزانيات القصّ الثابتة (بند 32) ───
CLIP_NAME = 80
CLIP_TITLE = 120
CLIP_DESCRIPTION = 400
CLIP_LINE = 500
CLIP_CONTEXT = 6000
CLIP_REQUEST = 8000

CLIP_LIMITS = {
    "name": CLIP_NAME,
    "title": CLIP_TITLE,
    "description": CLIP_DESCRIPTION,
    "line": CLIP_LINE,
    "context": CLIP_CONTEXT,
    "request": CLIP_REQUEST,
}

DEFAULT_THRESHOLD = 0.6
DEFAULT_TIMEOUT = 1.5
RETENTION_DAYS = 180

# ترتيب المزوّدين الثابت: Flash-Lite الخاص → Gemini Flash
# الخاص → OpenRouter المجاني.
PROVIDER_ORDER = ("gemini-flash-lite", "gemini-flash",
                  "openrouter-free")

EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")

# أسباب الفشل المسماة التي يرجع بها route() إلى الافتراضي.
FALLBACK_REASONS = ("low_confidence", "no_choice", "malformed",
                    "timeout", "provider_error", "internal_error")


def clip(text, limit):
    """قصّ نص إلى `limit` حرفًا من البداية ("" لغير النص)."""
    if text is None:
        return ""
    text = text if isinstance(text, str) else str(text)
    if limit is None or limit < 0:
        return text
    return text[:limit]


def clip_name(text):
    """قصّ اسم إلى 80 حرفًا."""
    return clip(text, CLIP_NAME)


def clip_title(text):
    """قصّ عنوان إلى 120 حرفًا."""
    return clip(text, CLIP_TITLE)


def clip_description(text):
    """قصّ وصف إلى 400 حرف."""
    return clip(text, CLIP_DESCRIPTION)


def clip_line(text):
    """قصّ سطر إلى 500 حرف."""
    return clip(text, CLIP_LINE)


def clip_request(text):
    """قصّ طلب إلى 8,000 حرف (من البداية)."""
    return clip(text, CLIP_REQUEST)


def clip_context(context, limit=CLIP_CONTEXT):
    """قصّ السياق الأخير إلى `limit` حرفًا من الأحدث رجوعًا.

    يقبل نصًا (يُؤخذ ذيله — الأحدث في النهاية) أو قائمة
    أسطر (تُؤخذ الأسطر من الأحدث رجوعًا حتى الميزانية،
    وتُعاد بترتيبها الأصلي). سطر واحد أطول من الميزانية
    وحدها يُقصّ ذيله.
    """
    if context is None:
        return ""
    if isinstance(context, str):
        return context[-limit:] if len(context) > limit else context
    lines = [line if isinstance(line, str) else str(line)
             for line in context]
    kept = []
    total = 0
    for line in reversed(lines):
        need = len(line) + (1 if kept else 0)
        if total + need <= limit:
            kept.append(line)
            total += need
        elif not kept and len(line) > limit:
            kept.append(line[-limit:])
            total = limit
        else:
            break
    kept.reverse()
    return "\n".join(kept)


def _clip_role(role):
    """قصّ دور واحد (قاموس أو نص) إلى ميزانياته الثابتة."""
    if isinstance(role, str):
        return {"name": clip_name(role)}
    if not isinstance(role, dict):
        return {"name": clip_name(role)}
    clipped = {}
    if "name" in role:
        clipped["name"] = clip_name(role.get("name"))
    if "title" in role:
        clipped["title"] = clip_title(role.get("title"))
    if "description" in role:
        clipped["description"] = clip_description(
            role.get("description"))
    if "model" in role:
        clipped["model"] = clip_line(role.get("model"))
    if "effort" in role:
        clipped["effort"] = clip_line(role.get("effort"))
    return clipped


def build_state(task, roles, context, request):
    """ابنِ حالة الموجّه بمفاتيح ثابتة وميزانيات قصّ ثابتة.

    الحالة: المهمة، الأدوار المعروضة (مقصوصة)، السياق
    الأخير (≤6,000 حرف من الأحدث)، الطلب (≤8,000 حرف).
    لا مفاتيح ولا أسرار في الحالة أبدًا.
    """
    if isinstance(roles, (list, tuple)):
        clipped_roles = [_clip_role(role) for role in roles]
    elif roles is None:
        clipped_roles = []
    else:
        clipped_roles = [_clip_role(roles)]
    return {
        "task": clip_line(task),
        "roles": clipped_roles,
        "recent_messages": clip_context(context),
        "new_message": clip_request(request),
    }


def state_hash(state):
    """تجزئة 16 حرفًا للحالة (للسجل — بلا نصوص أصلية)."""
    try:
        blob = json.dumps(state, sort_keys=True,
                          ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError):
        blob = repr(state).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _studio_root(studio_root):
    if studio_root:
        return studio_root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def decider_log_dir(studio_root=None):
    """مجلد سجل القرارات `runs/decider-log`."""
    return os.path.join(_studio_root(studio_root), "runs",
                        "decider-log")


def load_config(path=None):
    """حمّل إعداد الموجّه من `~/.qisas-studio/router.json`.

    ملف غائب أو تالف ← إعداد افتراضي. المفتاح يُقبل
    كمرجع `{env: NAME}` أو `{file: PATH}` فقط — قيمة
    نصية صريحة تُتجاهل ولا تُحفظ أبدًا. العتبة خارج
    [0, 1] تُتجاهل وتُستبدل بالافتراضي 0.6.
    """
    config = {"provider": PROVIDER_ORDER[0],
              "threshold": DEFAULT_THRESHOLD,
              "key_ref": None}
    path = path or os.path.expanduser(
        "~/.qisas-studio/router.json")
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return config
    if not isinstance(raw, dict):
        return config
    provider = raw.get("provider")
    if isinstance(provider, str) and provider.strip():
        config["provider"] = provider.strip()
    threshold = raw.get("threshold")
    if isinstance(threshold, bool):
        pass
    elif isinstance(threshold, (int, float)) and 0 <= threshold <= 1:
        config["threshold"] = float(threshold)
    ref = key_ref(raw)
    if ref is not None:
        config["key_ref"] = ref
    return config


def key_ref(config):
    """استخرج مرجع المفتاح `{env|file}` من إعداد — أو None.

    مفتاح مكتوب صراحةً (نص) ليس مرجعًا فيُرفض: يرجع None
    فلا يُحفظ ولا يُمرَّر أبدًا.
    """
    if not isinstance(config, dict):
        return None
    ref = config.get("key") or config.get("key_ref")
    if not isinstance(ref, dict):
        return None
    if isinstance(ref.get("env"), str) and ref["env"].strip():
        return {"env": ref["env"].strip()}
    if isinstance(ref.get("file"), str) and ref["file"].strip():
        return {"file": ref["file"].strip()}
    return None


def _normalize_default(default):
    """طبّع الافتراضي إلى {"model", "effort"}."""
    if isinstance(default, str) and default.strip():
        return {"model": default.strip(), "effort": "medium"}
    if isinstance(default, dict):
        model = default.get("model")
        effort = default.get("effort")
        if not isinstance(model, str) or not model.strip():
            model = ""
        if effort not in EFFORTS:
            effort = "medium"
        return {"model": model.strip(), "effort": effort}
    return {"model": "", "effort": "medium"}


def _offered_models(roles):
    """معرّفات النماذج المعروضة من الأدوار."""
    offered = []
    if isinstance(roles, (list, tuple)):
        items = roles
    elif roles is None:
        items = []
    else:
        items = [roles]
    for role in items:
        if isinstance(role, str) and role.strip():
            offered.append(role.strip())
        elif isinstance(role, dict):
            model = role.get("model")
            if isinstance(model, str) and model.strip():
                offered.append(model.strip())
    return offered


def _fallback(default, reason, confidence=0.0):
    """نتيجة رجوع للافتراضي بسبب مسمّى."""
    return {"model": default["model"],
            "effort": default["effort"],
            "source": "fallback",
            "confidence": float(confidence),
            "attribution": "Picked by fallback · 0%",
            "reason": reason}


def _validate_decision(decision, offered, threshold):
    """تحقق من إجابة الموجّه قبل استخدامها.

    يرجع (نموذج، جهد، ثقة، سبب_فشل): سبب الفشل None عند
    القبول. اختيار غير معروض ← no_choice؛ واحتمال ليس
    رقمًا أو بنية مشوّهة ← malformed؛ وتحت العتبة ←
    low_confidence؛ وجهد غير معروف ← malformed.
    """
    if not isinstance(decision, dict):
        return None, None, None, "malformed"
    model = decision.get("model")
    if not isinstance(model, str) or not model.strip():
        return None, None, None, "malformed"
    model = model.strip()
    if offered and model not in offered:
        return None, None, None, "no_choice"
    confidence = decision.get("confidence")
    if isinstance(confidence, bool) or \
            not isinstance(confidence, (int, float)):
        return None, None, None, "malformed"
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        return None, None, None, "malformed"
    if confidence < threshold:
        return None, None, None, "low_confidence"
    effort = decision.get("effort", "medium")
    if effort not in EFFORTS:
        return None, None, None, "malformed"
    return model, effort, confidence, None


def _run_decider(decider, state, timeout):
    """شغّل الموجّه في خيط مع مهلة — (نتيجة، خطأ، انتهت_المهلة)."""
    box = {}

    def _target():
        try:
            box["result"] = decider(state)
        except Exception as exc:  # noqa: BLE001 — يُترجم لفشل مفتوح
            box["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return None, None, True
    if "error" in box:
        return None, box["error"], False
    return box.get("result"), None, False


def log_decision(studio_root=None, log_dir=None, state=None,
                 model=None, latency_ms=None, reason=None,
                 source="router", now=None):
    """سجّل سطر قرار واحد — بلا نص طلب ولا أوصاف أدوار ولا مفاتيح.

    السطر: {"ts", "state_hash", "model", "latency_ms",
    "source", "reason"}. لا يرمي أبدًا: فشل الكتابة صامت.
    يرجع مسار ملف السجل أو None عند الفشل.
    """
    try:
        directory = log_dir or decider_log_dir(studio_root)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        if isinstance(now, str):
            stamp = now
        elif now is not None:
            try:
                stamp = time.strftime("%Y-%m", now)
            except Exception:  # noqa: BLE001 — طابع افتراضي
                stamp = time.strftime("%Y-%m")
        else:
            stamp = time.strftime("%Y-%m")
        path = os.path.join(directory, stamp + ".ndjson")
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "state_hash": state_hash(state) if state is not None
                          else None,
            "model": model,
            "latency_ms": latency_ms,
            "source": source,
            "reason": reason,
        }
        line = (json.dumps(entry, ensure_ascii=False) + "\n"
                ).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                     0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return path
    except Exception:  # noqa: BLE001 — فشل السجل لا يكسر الموجّه
        return None


def prune_old_logs(log_dir=None, studio_root=None,
                   retention_days=RETENTION_DAYS, now=None):
    """احذف سجلات قرارات أقدم من `retention_days` (افتراضي 180).

    يقرأ الشهر من اسم الملف `YYYY-MM.ndjson`؛ والملفات
    بأسماء غير مطابقة تُترك. يرجع قائمة الملفات المحذوفة.
    لا يرمي على خطأ ملف واحد — يتابع الباقي.
    """
    directory = log_dir or decider_log_dir(studio_root)
    if now is None:
        now = time.localtime()
    import datetime as _datetime
    cutoff_date = (_datetime.date(now.tm_year, now.tm_mon, 1)
                   - _datetime.timedelta(days=retention_days))
    cutoff = (cutoff_date.year, cutoff_date.month)
    deleted = []
    try:
        names = os.listdir(directory)
    except OSError:
        return deleted
    for name in names:
        if not name.endswith(".ndjson"):
            continue
        stem = name[:-len(".ndjson")]
        try:
            year_s, month_s = stem.split("-", 1)
            year = int(year_s)
            month = int(month_s)
            if not 1 <= month <= 12:
                continue
        except ValueError:
            continue
        if (year, month) < cutoff:
            path = os.path.join(directory, name)
            try:
                os.remove(path)
                deleted.append(name)
            except OSError:
                continue
    return deleted


def route(task, roles, context, request, default, decider=None,
          config=None, studio_root=None, log_dir=None,
          threshold=None, timeout=None, decider_name=None,
          now=None):
    """اختر نموذجًا وجهدًا للمهمة — ولا ترمي أبدًا.

    decider: دالة قابلة للحقن `decider(state) -> {"model",
    "effort", "confidence"}` تستدعي المزوّد الفعلي (يمرّرها
    الربط لاحقًا)؛ وبلا decider يُرجع الافتراضي بسبب
    `no_choice`. أي عطل — مهلة، خطأ مزوّد، إجابة مشوّهة،
    ثقة تحت العتبة — يرجع الافتراضي بسبب مسمّى.

    يرجع {"model", "effort", "source": "router"|"fallback",
    "confidence", "attribution": "Picked by … · NN%",
    "reason"} حيث reason هو None عند الاختيار الناجح.
    """
    try:
        cfg = config if isinstance(config, dict) else load_config()
        limit = DEFAULT_THRESHOLD
        if threshold is not None:
            limit = threshold
        elif isinstance(cfg.get("threshold"), (int, float)):
            limit = float(cfg["threshold"])
        limit = max(0.0, min(1.0, float(limit)))
        wait = DEFAULT_TIMEOUT if timeout is None else float(timeout)
        wait = max(0.0, wait)
        default_norm = _normalize_default(default)
        state = build_state(task, roles, context, request)
        offered = _offered_models(roles)
        label = decider_name
        if not label:
            label = cfg.get("provider") or PROVIDER_ORDER[0]
        if decider is None:
            return _fallback(default_norm, "no_choice")
        started = time.monotonic()
        result, error, timed_out = _run_decider(
            decider, state, wait)
        latency_ms = int((time.monotonic() - started) * 1000)
        if timed_out:
            log_decision(studio_root=studio_root, log_dir=log_dir,
                         state=state, model=default_norm["model"],
                         latency_ms=latency_ms, reason="timeout",
                         source="fallback", now=now)
            return _fallback(default_norm, "timeout")
        if error is not None:
            log_decision(studio_root=studio_root, log_dir=log_dir,
                         state=state, model=default_norm["model"],
                         latency_ms=latency_ms,
                         reason="provider_error", source="fallback",
                         now=now)
            return _fallback(default_norm, "provider_error")
        model, effort, confidence, reason = _validate_decision(
            result, offered, limit)
        if reason is not None:
            log_decision(studio_root=studio_root, log_dir=log_dir,
                         state=state, model=default_norm["model"],
                         latency_ms=latency_ms, reason=reason,
                         source="fallback", now=now)
            return _fallback(default_norm, reason)
        pct = int(round(confidence * 100))
        log_decision(studio_root=studio_root, log_dir=log_dir,
                     state=state, model=model,
                     latency_ms=latency_ms, reason=None,
                     source="router", now=now)
        return {"model": model,
                "effort": effort,
                "source": "router",
                "confidence": confidence,
                "attribution": "Picked by %s · %d%%" % (label, pct),
                "reason": None}
    except Exception:  # noqa: BLE001 — الفشل المفتوح يشملنا نحن
        try:
            return _fallback(_normalize_default(default),
                             "internal_error")
        except Exception:  # noqa: BLE001 — آخر خط دفاع
            return {"model": "", "effort": "medium",
                    "source": "fallback", "confidence": 0.0,
                    "attribution": "Picked by fallback · 0%",
                    "reason": "internal_error"}
