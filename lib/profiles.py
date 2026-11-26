#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""بروفايلات إعداد مسماة + سلسلة أولوية + تشخيص الإعداد الفعّال.

نمط منقول كفكرة فقط (بلا أي كود منسوخ): بروفايل مسمّى يجمع
إعدادات مرحلة كاملة (ريندر/نشر/مراجعة) بدل أعلام متناثرة،
وترتيب أولوية صريح يُعرف منه مصدر كل قيمة، وأمر تشخيص يعرض
القيمة الفعّالة ومصدرها.

سلسلة الأولوية (اللاحق يغلب السابق):

    افتراضي ← نظام ← مستخدم ← مشروع ← بروفايل ← تجاوزات CLI

  - افتراضي: DEFAULT_SETTINGS أدناه (الأكثر أمانًا دائمًا:
    قراءة فقط، ويسأل قبل أي تغيير، وشبكة مغلقة).
  - نظام: /etc/qisas-studio/profiles.toml (إعداد الجهاز كله).
  - مستخدم: ~/.config/qisas-studio/profiles.toml.
  - مشروع: profiles.toml في جذر شجرة studio (يُشحَن مع المشروع).
  - بروفايل: جدول [profiles.<name>] من أي طبقة من الطبقات
    السابقة (تُدمَج جداول البروفايلات بالترتيب نفسه).
  - تجاوزات CLI: أزواج KEY=VALUE من --set (لتشغيل واحد فقط).

كل طبقة ملف TOML اختياري يحوي جدول [settings] و/أو جداول
[profiles.<name>]؛ والملف الغائب يُتخطى بصمت، والملف التالف
خطأ عربي واضح (لا رجوع صامت لافتراضي يخفي المشكلة).

قواعد أمان تُفرَض هنا (لا تُوثَّق فقط):
  - sandbox لا يقبل إلا read-only أو workspace-write — الوصول
    الكامل (full) مرفوض في خط الإنتاج رفضًا قاطعًا.
  - لا أسرار مضمّنة: أي مفتاح يحمل اسم key/token/secret/
    password في أي ملف إعداد يرفض الملف كله.
  - أدوات MCP المدمرة على prompt دائمًا مهما كان الوضع
    الافتراضي للخادم (انظر mcp_approval_for).
  - خادم MCP غير معروف → prompt (فشل مغلق: السؤال قبل الفعل).

هذه الوحدة تشخيص وإعداد فقط — لا تنفّذ أي أمر ولا تفتح أي
شبكة ولا تفرض العزل بنفسها؛ فرض العزل مواصفة في
docs/security-design.md ينفذها الغلاف لاحقًا.
"""
import os
import tomllib

# ---------------------------------------------------------------- ثوابت

#: مسار إعداد النظام (طبقة «نظام» في السلسلة).
SYSTEM_PROFILES_PATH = "/etc/qisas-studio/profiles.toml"

#: مسار إعداد المستخدم (طبقة «مستخدم») — يُبنى من HOME وقت الاستدعاء.
USER_PROFILES_REL = os.path.join(".config", "qisas-studio",
                                 "profiles.toml")

#: أسماء المصادر كما تظهر في التشخيص — بالترتيب نفسه للسلسلة.
SOURCE_DEFAULT = "افتراضي"
SOURCE_SYSTEM = "نظام"
SOURCE_USER = "مستخدم"
SOURCE_PROJECT = "مشروع"
SOURCE_CLI = "سطر الأوامر"


def _profile_source(name):
    return "بروفايل:%s" % name


#: القيم المسموحة لكل إعداد مقيّد.
VALID_SANDBOX = ("read-only", "workspace-write")
VALID_APPROVAL = ("untrusted", "on-request", "never")
VALID_NETWORK = ("closed", "publish-only")
VALID_EFFORT = ("low", "medium", "high")
VALID_MCP_MODES = ("prompt", "allow", "deny")

#: مفاتيح الإعداد المعروفة في [settings] أو في جدول بروفايل.
KNOWN_SETTINGS = (
    "sandbox", "approval", "network", "effort", "allow_publish",
    "allow_delete", "max_steps", "timeout_seconds",
    "network_domains", "mcp",
)

#: مفاتيح خادم MCP المعروفة داخل جدول [mcp.<server>].
KNOWN_MCP_KEYS = (
    "default_tools_approval_mode", "destructive_tools",
    "enabled_tools", "disabled_tools",
)

#: أي مفتاح يحوي إحدى هذه الكلمات يُعامَل كسرّ مضمّن ويُرفَض.
SECRET_KEY_WORDS = ("key", "token", "secret", "password", "passwd",
                    "credential", "private")

#: الإعداد الافتراضي — الأكثر أمانًا: قراءة فقط، ويسأل قبل أي
#: تغيير، وشبكة مغلقة، وبلا نشر وبلا حذف.
DEFAULT_SETTINGS = {
    "sandbox": "read-only",
    "approval": "untrusted",
    "network": "closed",
    "effort": "medium",
    "allow_publish": False,
    "allow_delete": False,
    "max_steps": 20,
    "timeout_seconds": 600,
    "network_domains": [],
    "mcp": {
        "concat": {
            "default_tools_approval_mode": "prompt",
            "destructive_tools": ["publish", "delete", "overwrite"],
            "enabled_tools": [],
            "disabled_tools": [],
        },
    },
}


class ProfileError(ValueError):
    """خطأ إعداد/بروفايل برسالة عربية واضحة (للطباعة والخروج 2)."""


# ---------------------------------------------------------------- قراءة

def _studio_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_profiles_path():
    return os.path.join(os.path.expanduser("~"), USER_PROFILES_REL)


def _load_toml(path, where):
    """اقرأ ملف TOML؛ الغائب ← {}، والتالف ← ProfileError عربي."""
    if path is None or not os.path.isfile(path):
        return {}
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError, ValueError) as e:
        raise ProfileError(
            "ملف الإعداد %s (%s) تالف أو غير مقروء: %s — أصلحه أو "
            "احذفه ليُستخدم الإعداد الافتراضي" % (where, path, e))
    if not isinstance(data, dict):
        raise ProfileError(
            "ملف الإعداد %s (%s) يجب أن يكون جداول TOML (وصل نوع "
            "غير قاموس)" % (where, path))
    _check_no_secrets(data, where)
    return data


def _check_no_secrets(node, where):
    """ارفض أي مفتاح يحمل اسم سرّ (key/token/secret/...) أينما ظهر."""
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if any(word in lowered for word in SECRET_KEY_WORDS):
                raise ProfileError(
                    "ملف الإعداد %s يحوي مفتاحًا باسم سرّ («%s») — "
                    "الأسرار لا تُكتب في ملفات الإعداد أبدًا؛ مرّرها "
                    "عبر متغير بيئة فقط" % (where, key))
            _check_no_secrets(value, where)
    elif isinstance(node, list):
        for item in node:
            _check_no_secrets(item, where)


def _validate_settings_table(table, where):
    """تحقق من جدول إعدادات (settings أو بروفايل) قبل دمجه."""
    if not isinstance(table, dict):
        raise ProfileError("جدول الإعداد في %s يجب أن يكون قاموسًا"
                           % where)
    for key, value in table.items():
        if key == "description":
            if not isinstance(value, str):
                raise ProfileError(
                    "حقل description في %s يجب أن يكون نصًا" % where)
            continue
        if key not in KNOWN_SETTINGS:
            raise ProfileError(
                "إعداد غير معروف «%s» في %s — المعروف: %s"
                % (key, where, ", ".join(KNOWN_SETTINGS)))
        if key == "sandbox" and value not in VALID_SANDBOX:
            if value == "full":
                raise ProfileError(
                    "قيمة sandbox ‏«full» مرفوضة في %s — الوصول "
                    "الكامل ممنوع في خط الإنتاج؛ المسموح: %s"
                    % (where, ", ".join(VALID_SANDBOX)))
            raise ProfileError(
                "قيمة sandbox غير صالحة «%s» في %s — المسموح: %s"
                % (value, where, ", ".join(VALID_SANDBOX)))
        if key == "approval" and value not in VALID_APPROVAL:
            raise ProfileError(
                "قيمة approval غير صالحة «%s» في %s — المسموح: %s"
                % (value, where, ", ".join(VALID_APPROVAL)))
        if key == "network" and value not in VALID_NETWORK:
            raise ProfileError(
                "قيمة network غير صالحة «%s» في %s — المسموح: %s"
                % (value, where, ", ".join(VALID_NETWORK)))
        if key == "effort" and value not in VALID_EFFORT:
            raise ProfileError(
                "قيمة effort غير صالحة «%s» في %s — المسموح: %s"
                % (value, where, ", ".join(VALID_EFFORT)))
        if key in ("allow_publish", "allow_delete"):
            if not isinstance(value, bool):
                raise ProfileError(
                    "قيمة %s في %s يجب أن تكون true/false (وصل: %s)"
                    % (key, where, value))
        if key in ("max_steps", "timeout_seconds"):
            if (not isinstance(value, int) or isinstance(value, bool)
                    or value <= 0):
                raise ProfileError(
                    "قيمة %s في %s يجب أن تكون عددًا صحيحًا موجبًا "
                    "(وصل: %s)" % (key, where, value))
        if key == "network_domains":
            if (not isinstance(value, list)
                    or not all(isinstance(d, str) for d in value)):
                raise ProfileError(
                    "قيمة network_domains في %s يجب أن تكون قائمة "
                    "نطاقات نصية" % where)
        if key == "mcp":
            _validate_mcp_table(value, where)


def _validate_mcp_table(table, where):
    if not isinstance(table, dict):
        raise ProfileError("جدول mcp في %s يجب أن يكون قاموسًا "
                           "(خادم ← إعداد)" % where)
    for server, cfg in table.items():
        if not isinstance(cfg, dict):
            raise ProfileError(
                "إعداد خادم MCP ‏«%s» في %s يجب أن يكون جدولًا"
                % (server, where))
        for key, value in cfg.items():
            if key not in KNOWN_MCP_KEYS:
                raise ProfileError(
                    "مفتاح MCP غير معروف «%s» للخادم «%s» في %s — "
                    "المعروف: %s"
                    % (key, server, where, ", ".join(KNOWN_MCP_KEYS)))
            if key == "default_tools_approval_mode":
                if value not in VALID_MCP_MODES:
                    raise ProfileError(
                        "وضع موافقة MCP غير صالح «%s» للخادم «%s» "
                        "في %s — المسموح: %s"
                        % (value, server, where,
                           ", ".join(VALID_MCP_MODES)))
            else:
                if (not isinstance(value, list)
                        or not all(isinstance(t, str) for t in value)):
                    raise ProfileError(
                        "قيمة %s للخادم «%s» في %s يجب أن تكون قائمة "
                        "أدوات نصية" % (key, server, where))


# ---------------------------------------------------------------- دمج

def _deep_merge(base, overlay, source, sources, prefix=""):
    """ادمج overlay فوق base (قوائم تُستبدَل لا تُلصَق) وسجّل المصدر."""
    for key, value in overlay.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if (isinstance(value, dict)
                and isinstance(base.get(key), dict)):
            _deep_merge(base[key], value, source, sources, dotted)
        else:
            base[key] = value
            sources[dotted] = source


def _flatten(node, prefix=""):
    """سطّح قاموسًا متداخلًا إلى {مفتاح منقّط: قيمة ورقية}."""
    out = {}
    for key, value in node.items():
        dotted = "%s.%s" % (prefix, key) if prefix else key
        if isinstance(value, dict):
            out.update(_flatten(value, dotted))
        else:
            out[dotted] = value
    return out


def _coerce_cli_value(text):
    """فسّر قيمة --set نصية: true/false/عدد، وإلا نص كما هو."""
    lowered = text.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def parse_cli_overrides(pairs):
    """حوّل قائمة «KEY=VALUE» (منقّطة) إلى قاموس متداخل.

    يرفع ProfileError برسالة عربية عند صيغة بلا «=» أو مفتاح
    غير معروف (أول مكوّن ليس من KNOWN_SETTINGS).
    """
    nested = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise ProfileError(
                "تجاوز سطر الأوامر «%s» بلا «=» — الصيغة KEY=VALUE "
                "(مثال: --set effort=high)" % pair)
        dotted, _, raw = pair.partition("=")
        dotted = dotted.strip()
        if not dotted or dotted.startswith(".") or dotted.endswith("."):
            raise ProfileError(
                "تجاوز سطر الأوامر «%s» بمفتاح فارغ أو منقّط خطأ"
                % pair)
        head = dotted.split(".", 1)[0]
        if head not in KNOWN_SETTINGS:
            raise ProfileError(
                "تجاوز سطر الأوامر بمفتاح غير معروف «%s» — المعروف: "
                "%s" % (dotted, ", ".join(KNOWN_SETTINGS)))
        parts = dotted.split(".")
        node = nested
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ProfileError(
                    "تجاوز سطر الأوامر «%s» يتعارض مع قيمة سابقة"
                    % pair)
        node[parts[-1]] = _coerce_cli_value(raw)
    return nested


def _validate_cli_tree(tree):
    """تحقق من شجرة تجاوزات CLI بعد بنائها (أنواع وقيم مقيّدة)."""
    flat = _flatten(tree)
    for dotted, value in flat.items():
        head = dotted.split(".")[0]
        if head == "mcp":
            parts = dotted.split(".")
            if len(parts) != 3 or parts[2] not in KNOWN_MCP_KEYS:
                raise ProfileError(
                    "تجاوز MCP غير صالح «%s» — الصيغة "
                    "mcp.<server>.default_tools_approval_mode أو "
                    "mcp.<server>.destructive_tools" % dotted)
            if (parts[2] == "default_tools_approval_mode"
                    and value not in VALID_MCP_MODES):
                raise ProfileError(
                    "وضع موافقة MCP غير صالح «%s» — المسموح: %s"
                    % (value, ", ".join(VALID_MCP_MODES)))
            continue
        _validate_settings_table({head: value}
                                 if "." not in dotted else
                                 {head: _rebuild(head, dotted, value)},
                                 "سطر الأوامر")


def _rebuild(head, dotted, value):
    """أعد بناء فرع متداخل من مفتاح منقّط واحد للتحقق منه."""
    parts = dotted.split(".")[1:]
    node = value
    for part in reversed(parts):
        node = {part: node}
    return node


# ---------------------------------------------------------------- حلّ

def resolve(profile=None, studio_root=None, system_path=None,
            user_path=None, project_path=None, cli_overrides=None):
    """حلّ الإعداد الفعّال عبر السلسلة كاملة.

    يرجع قاموسًا فيه:
      "profile": اسم البروفايل المختار أو None،
      "settings": الإعداد الفعّال (قاموس متداخل)،
      "sources": {مفتاح منقّط: مصدر القيمة} لكل ورقة،
      "profiles": أسماء البروفايلات المتاحة مرتبة،
      "layers": [(المصدر، المسار)] للملفات المقروءة فعلًا.
    بروفايل غير موجود ← ProfileError عربي يسرد المتاح.
    """
    root = studio_root or _studio_root()
    if system_path is None:
        system_path = SYSTEM_PROFILES_PATH
    if user_path is None:
        user_path = _user_profiles_path()
    if project_path is None:
        project_path = os.path.join(root, "profiles.toml")

    import copy
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    sources = {key: SOURCE_DEFAULT for key in _flatten(settings)}
    profiles = {}
    layers = []

    for path, label in ((system_path, SOURCE_SYSTEM),
                        (user_path, SOURCE_USER),
                        (project_path, SOURCE_PROJECT)):
        data = _load_toml(path, label)
        if not data:
            continue
        layers.append((label, path))
        base = data.get("settings", {})
        _validate_settings_table(base, label)
        _deep_merge(settings, base, label, sources)
        for name, table in (data.get("profiles") or {}).items():
            if not isinstance(table, dict):
                raise ProfileError(
                    "بروفايل «%s» في %s يجب أن يكون جدولًا"
                    % (name, label))
            _validate_settings_table(table, "بروفايل %s (%s)"
                                     % (name, label))
            merged = profiles.setdefault(name, {})
            _deep_merge(merged, table, label, {})

    if profile is not None:
        if profile not in profiles:
            available = ", ".join(sorted(profiles)) or "لا يوجد"
            raise ProfileError(
                "البروفايل «%s» غير موجود — البروفايلات المتاحة: %s "
                "(مثال: --profile render)" % (profile, available))
        table = {k: v for k, v in profiles[profile].items()
                 if k != "description"}
        _deep_merge(settings, table, _profile_source(profile), sources)

    cli_tree = parse_cli_overrides(cli_overrides)
    if cli_tree:
        _validate_cli_tree(cli_tree)
        _deep_merge(settings, cli_tree, SOURCE_CLI, sources)

    return {"profile": profile,
            "settings": settings,
            "sources": sources,
            "profiles": sorted(profiles),
            "layers": layers}


def list_profiles(studio_root=None, system_path=None, user_path=None,
                  project_path=None):
    """أسماء البروفايلات المتاحة (بلا اختيار بروفايل)."""
    return resolve(studio_root=studio_root, system_path=system_path,
                   user_path=user_path,
                   project_path=project_path)["profiles"]


# ---------------------------------------------------------------- تشخيص

def diagnose(resolved):
    """قائمة (المفتاح، القيمة، المصدر) مرتبة بالمفتاح."""
    flat = _flatten(resolved["settings"])
    sources = resolved["sources"]
    return [(key, flat[key], sources.get(key, SOURCE_DEFAULT))
            for key in sorted(flat)]


def _format_value(value):
    if isinstance(value, bool):
        return "نعم" if value else "لا"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    return str(value)


def format_diagnosis(resolved):
    """نص التشخيص كما يطبعه `debug-config` (عربي، سطر لكل قيمة)."""
    lines = []
    if resolved["profile"]:
        lines.append("البروفايل: %s" % resolved["profile"])
    else:
        lines.append("البروفايل: بلا بروفايل "
                     "(الافتراضي + ملفات الإعداد فقط)")
    for label, _path in resolved["layers"]:
        lines.append("  طبقة مقروءة: %s" % label)
    for key, value, source in diagnose(resolved):
        lines.append("  %s = %s (المصدر: %s)"
                     % (key, _format_value(value), source))
    return "\n".join(lines)


# ---------------------------------------------------------------- مسارات

def check_workspace_path(path, roots=None, what="المسار"):
    """حلّ المسار وارفضه إن خرج من جذور مساحة العمل المسموحة.

    roots الافتراضي [~/workspace]. يرجع المسار الحقيقي بعد
    حلّ الروابط الرمزية؛ وخارج الجذور ← ProfileError عربي.
    """
    if roots is None:
        roots = [os.path.expanduser("~/workspace")]
    target = os.path.realpath(os.path.expanduser(
        os.path.expandvars(str(path))))
    for root in roots:
        base = os.path.realpath(os.path.expanduser(
            os.path.expandvars(str(root))))
        if target == base or target.startswith(base + os.sep):
            return target
    raise ProfileError(
        "%s خارج مساحة العمل المسموحة: %s — الكتابة مقيدة بجذور "
        "مساحة العمل فقط (%s)"
        % (what, path, ", ".join(str(r) for r in roots)))


# ---------------------------------------------------------------- MCP

def mcp_approval_for(settings, server, tool):
    """وضع الموافقة لأداة MCP: prompt/allow/deny.

    القواعد بالترتيب (الأولى تغلب):
      1. أداة مدمرة (في destructive_tools للخادم) → prompt دائمًا،
         مهما كان الوضع الافتراضي — حتى لو allow.
      2. أداة في disabled_tools → deny.
      3. enabled_tools غير فارغة والأداة ليست فيها → deny.
      4. خادم غير معروف → prompt (فشل مغلق).
      5. وإلا: default_tools_approval_mode للخادم.
    """
    servers = settings.get("mcp") or {}
    cfg = servers.get(server)
    if not isinstance(cfg, dict):
        return "prompt"
    destructive = cfg.get("destructive_tools") or []
    if tool in destructive:
        return "prompt"
    if tool in (cfg.get("disabled_tools") or []):
        return "deny"
    enabled = cfg.get("enabled_tools") or []
    if enabled and tool not in enabled:
        return "deny"
    mode = cfg.get("default_tools_approval_mode", "prompt")
    return mode if mode in VALID_MCP_MODES else "prompt"
