#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""ملف الفريق الإعلاني ``team.yaml`` — جولة v0.1.63، بند 4 (ع17)
+ بند 31 (سقوف القوائم).

ملف YAML واحد يعرّف ما يجب أن تكون عليه مساحة العمل: فرق
وبوتات بتعليماتها الدائمة ونماذجها ومستويات موافقتها وأدواتها
ومهاراتها. ثم:

- ``parse`` / ``validate`` — تحليل الملف والتحقق منه.
- ``plan`` — الخطة: ما الذي سيتغيّر، حقلًا بحقل، قبل أي تطبيق.
- ``apply`` — يطبع الخطة (عبر القيمة المرجعة) ثم يطبّقها؛
  و``dry_run`` للخطة فقط؛ و``check`` يخبر إن كان شيء سيتغيّر
  (ليخرج المستدعي 6 عند تغيير معلّق).

القواعد (ع17):

- إعادة التطبيق بلا تغييرات تطبع ``No changes.``.
- المطابقة بالاسم (بأي حالة أحرف) أو بـ ``was:`` عند إعادة
  التسمية؛ وإعادة تسمية فوق اسم موجود مرفوضة.
- حقل يُترك في الملف يُترك كما هو (ونموذج جديد على نفس المحرك
  يحافظ على جهد البوت).
- الفرق لا تُحذف أبدًا؛ والبوتات غير المذكورة تُحذف فقط مع
  ``prune`` وفقط في فريق موسوم ``prune: true``.
- التطبيق ليس ذريًا: يتوقف عند أول رفض ويقول ما أُنجز،
  وإعادة التطبيق تكمل من حيث توقف.
- بوت مشغول يُغيَّر حين يهدأ (انتظار حتى دقيقتين افتراضيًا).
- المفاتيح كمراجع سرّية فقط ``{env: NAME}`` أو ``{file: PATH}``
  — مفتاح مكتوب في الملف **مرفوض** (خروج 2 مع ذكر الموضع).
- الحاسوب ``local|off`` فقط في v1 — أي قيمة أخرى مرفوضة.
- ``cwd`` مسار كامل موجود (لا ``~``).

حقول البوت: ``name`` (1–100 حرفًا، فريد)، ``team``،
``title``، ``description``، ``chief: true`` (رئيس واحد لكل
فريق)، ``manages``، ``soul`` (≤24,000 بايت)، ``model``
بصيغة ``INSTANCE/MODEL``، ``effort``، ``approval``،
``computer``، ``cwd``، ``browser``، ``tools: {allow, deny}``،
``skills: [{file, enabled}]``، و``key`` كمرجع سرّي فقط.

سقوف القوائم (بند 31): ``ROSTER_MAX_BOTS = 40`` و
``OTHERS_MIN_BOTS = 8``. الأول قيد يُفحص هنا (رفض فريق
بأكثر من 40 عاملًا)؛ والثاني حد أدنى لغير الرئيس يستخدمه
المنسّق عند إضافة متخصص تلقائيًا، ويُعرَّف هنا ليبقى القيد
العددي موثقًا في موضع واحد لا ضمنيًا.

الحالة (``state``) التي تعمل عليها ``plan``/``apply`` هي
قاموس بايثون عادي — ``{"teams": {...}, "bots": {...}}``
بمفاتيح أسماء صغيرة — يبنيه المستدعي (ومنها أمر ``team``
في ``studio.py`` لاحقًا) ويحفظه؛ فهذه الوحدة لا تقرأ ولا
تكتب أي ملف حالة بنفسها، ولا تستورد أي وحدة ``lib`` أخرى
(استيراد ``lib.tool_selection`` كسول داخل الدالة فقط).
"""

import copy
import os
import re
import time

__all__ = [
    "ROSTER_MAX_BOTS",
    "OTHERS_MIN_BOTS",
    "NO_CHANGES_MESSAGE",
    "TeamFileError",
    "TeamApplyError",
    "parse_team_text",
    "load_team_file",
    "validate",
    "validate_all",
    "plan",
    "apply",
    "check",
    "empty_state",
    "export_state",
]

# سقوف القوائم (بند 31 / ع4).
ROSTER_MAX_BOTS = 40
OTHERS_MIN_BOTS = 8

# رسالة إعادة التطبيق بلا تغييرات (ع17).
NO_CHANGES_MESSAGE = "No changes."

# حدود الحقول (ع17).
MAX_NAME_LENGTH = 100
MAX_SOUL_BYTES = 24000
DEFAULT_WAIT_IDLE_SECONDS = 120

_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
_APPROVALS = ("ask", "edits", "auto", "full")
_COMPUTERS = ("local", "off")
_MODEL_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TEAM_FIELDS = {"name", "was", "description", "prune"}
_BOT_FIELDS = {
    "name", "was", "team", "title", "description", "chief",
    "manages", "soul", "model", "effort", "approval",
    "computer", "cwd", "browser", "tools", "skills", "key",
}
_TOOL_FIELDS = {"allow", "deny"}
_SKILL_FIELDS = {"file", "enabled"}
# مفاتيح يُعامل أي نص تحتهما كمفتاح مكتوب مرفوض.
_SECRET_KEYS = {"key", "secret", "api_key", "apikey", "token", "password", "api-key"}


class TeamFileError(Exception):
    """خطأ في ملف الفريق (رسالته عربية، ويحمل رمز خروج ع1).

    رمز الخروج 2 لمحتوى ملف مرفوض (ومنها مفتاح مكتوب في
    الملف)، و8 لمشكلة بيانات (مثل YAML مشوّه).
    """

    def __init__(self, message, exit_code=2):
        super().__init__(message)
        self.exit_code = exit_code


class TeamApplyError(Exception):
    """فشل تطبيق جزئي: توقف عند أول رفض بعد إنجاز بعض الخطوات.

    يحمل ``applied`` (ما أُنجز من إجراءات) و``state`` (الحالة
    الجزئية بعد ما أُنجز) فتعيد إعادة التطبيق الإكمال.
    """

    def __init__(self, message, applied=None, state=None):
        super().__init__(message)
        self.applied = list(applied or [])
        self.state = state


def parse_team_text(text):
    """حلّل نص YAML إلى قاموس؛ وYAML مشوّه يرفع ``TeamFileError`` (8)."""
    import yaml

    try:
        data = yaml.safe_load(text)
    except Exception as exc:  # yaml.YAMLError وأخواتها
        raise TeamFileError("ملف الفريق YAML مشوّه: %s." % (exc,), 8)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TeamFileError(
            "ملف الفريق يجب أن يكون خريطة YAML (teams/bots)، لا %s."
            % type(data).__name__,
            8,
        )
    return data


def load_team_file(path):
    """اقرأ ملف فريق من القرص وحلّله."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise TeamFileError("تعذّرت قراءة ملف الفريق «%s»: %s." % (path, exc), 7)
    return parse_team_text(text)


def empty_state():
    """حالة فارغة: بلا فرق وبلا بوتات."""
    return {"teams": {}, "bots": {}}


def export_state(state):
    """حوّل حالة داخلية إلى قاموس صالح لـ YAML (لأمر ``team export``)."""
    state = state or empty_state()
    teams = [
        dict(team)
        for _key, team in sorted(state.get("teams", {}).items())
    ]
    bots = [
        dict(bot)
        for _key, bot in sorted(state.get("bots", {}).items())
    ]
    return {"teams": teams, "bots": bots}


# ---------------------------------------------------------------- تحقق


def _is_name(value):
    return (
        isinstance(value, str)
        and 1 <= len(value.strip()) <= MAX_NAME_LENGTH
    )


def _check_secret_refs(node, location, errors):
    """امسح الشجرة بحثًا عن مفاتيح مكتوبة (ع17).

    المرجع السرّي الصحيح وحده مقبول: قاموس بمفتاح واحد
    ``{env: NAME}`` أو ``{file: PATH}``. وأي نص تحت مفتاح
    سرّي (``key``/``secret``/``token``/…) مرفوض مع ذكر الموضع.
    """
    if isinstance(node, dict):
        keys = set(node)
        if keys <= {"env", "file"}:
            if len(keys) == 1:
                kind = next(iter(keys))
                value = node[kind]
                if kind == "env":
                    if not isinstance(value, str) or not _ENV_NAME_RE.match(value):
                        errors.append(
                            "مرجع سرّي باطل في %s: ‏{env: …}‏ يجب أن يحمل "
                            "اسم متغير بيئة صالح." % location
                        )
                elif not isinstance(value, str) or not value:
                    errors.append(
                        "مرجع سرّي باطل في %s: ‏{file: …}‏ يجب أن يحمل "
                        "مسار ملف غير فارغ." % location
                    )
            else:
                errors.append(
                    "مرجع سرّي باطل في %s: ‏{env|file}‏ يجب أن يكون وحده "
                    "في القاموس." % location
                )
            return
        for key, value in node.items():
            child = "%s.%s" % (location, key)
            if (
                isinstance(key, str)
                and key.lower() in _SECRET_KEYS
                and isinstance(value, str)
            ):
                errors.append(
                    "مفتاح مكتوب مرفوض في %s: المفاتيح كمراجع سرّية "
                    "فقط ‏{env: NAME}‏ أو ‏{file: PATH}‏ — لا تكتب "
                    "المفتاح نفسه في الملف." % child
                )
            elif (
                isinstance(key, str)
                and key.lower() in _SECRET_KEYS
                and isinstance(value, dict)
            ):
                _check_secret_refs(value, child, errors)
            else:
                _check_secret_refs(value, child, errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _check_secret_refs(item, "%s[%d]" % (location, index), errors)


def _validate_tools(tools, location, errors):
    from lib.tool_selection import ToolSelectionError, validate_selectors

    if not isinstance(tools, dict):
        errors.append("حقل tools في %s يجب أن يكون خريطة {allow, deny}." % location)
        return
    unknown = set(tools) - _TOOL_FIELDS
    if unknown:
        errors.append(
            "حقل tools في %s فيه مفاتيح مجهولة: %s."
            % (location, ", ".join(sorted(unknown)))
        )
    for label in ("allow", "deny"):
        if label in tools:
            try:
                validate_selectors(tools[label], label)
            except ToolSelectionError as exc:
                errors.append("أدوات %s: %s" % (location, exc))


def _validate_skills(skills, location, errors):
    if not isinstance(skills, list):
        errors.append("حقل skills في %s يجب أن يكون قائمة." % location)
        return
    for index, skill in enumerate(skills):
        where = "%s[%d]" % (location, index)
        if not isinstance(skill, dict):
            errors.append("مهارة %s يجب أن تكون خريطة {file, enabled}." % where)
            continue
        unknown = set(skill) - _SKILL_FIELDS
        if unknown:
            errors.append(
                "مهارة %s فيها حقول مجهولة: %s."
                % (where, ", ".join(sorted(unknown)))
            )
        if "file" not in skill or not isinstance(skill["file"], str) or not skill["file"]:
            errors.append("مهارة %s يجب أن تحمل file نصًا غير فارغ." % where)
        if "enabled" in skill and not isinstance(skill["enabled"], bool):
            errors.append("مهارة %s: ‏enabled‏ يجب أن تكون true أو false." % where)


def _validate_team(team, index, errors):
    where = "teams[%d]" % index
    if not isinstance(team, dict):
        errors.append("فريق %s يجب أن يكون خريطة." % where)
        return
    unknown = set(team) - _TEAM_FIELDS
    if unknown:
        errors.append(
            "فريق %s فيه حقول مجهولة: %s."
            % (where, ", ".join(sorted(unknown)))
        )
    if not _is_name(team.get("name")):
        errors.append(
            "فريق %s: الاسم يجب أن يكون نصًا بين حرف و%d حرفًا."
            % (where, MAX_NAME_LENGTH)
        )
    if "was" in team and not _is_name(team["was"]):
        errors.append("فريق %s: ‏was‏ يجب أن يكون اسمًا صالحًا." % where)
    if "description" in team and not isinstance(team["description"], str):
        errors.append("فريق %s: الوصف يجب أن يكون نصًا." % where)
    if "prune" in team and not isinstance(team["prune"], bool):
        errors.append("فريق %s: ‏prune‏ يجب أن تكون true أو false." % where)


def _validate_bot(bot, index, team_names, errors):
    where = "bots[%d]" % index
    if not isinstance(bot, dict):
        errors.append("بوت %s يجب أن يكون خريطة." % where)
        return
    unknown = set(bot) - _BOT_FIELDS
    if unknown:
        errors.append(
            "بوت %s فيه حقول مجهولة: %s."
            % (where, ", ".join(sorted(unknown)))
        )
    if not _is_name(bot.get("name")):
        errors.append(
            "بوت %s: الاسم يجب أن يكون نصًا بين حرف و%d حرفًا."
            % (where, MAX_NAME_LENGTH)
        )
    if "was" in bot and not _is_name(bot["was"]):
        errors.append("بوت %s: ‏was‏ يجب أن يكون اسمًا صالحًا." % where)
    team = bot.get("team")
    if not isinstance(team, str) or not team:
        errors.append("بوت %s: ‏team‏ مطلوب نصًا غير فارغ." % where)
    elif team_names is not None and team.lower() not in team_names:
        errors.append(
            "بوت %s: الفريق «%s» غير معرَّف في الملف." % (where, team)
        )
    if "title" in bot and not isinstance(bot["title"], str):
        errors.append("بوت %s: العنوان يجب أن يكون نصًا." % where)
    if "description" in bot and not isinstance(bot["description"], str):
        errors.append("بوت %s: الوصف يجب أن يكون نصًا." % where)
    if "chief" in bot and not isinstance(bot["chief"], bool):
        errors.append("بوت %s: ‏chief‏ يجب أن تكون true أو false." % where)
    if "manages" in bot:
        manages = bot["manages"]
        if not isinstance(manages, list) or not all(
            isinstance(item, str) for item in manages
        ):
            errors.append("بوت %s: ‏manages‏ يجب أن تكون قائمة أسماء فرق." % where)
        elif team_names is not None:
            for item in manages:
                if item.lower() not in team_names:
                    errors.append(
                        "بوت %s: ‏manages‏ فيه فريق غير معرَّف «%s»."
                        % (where, item)
                    )
    if "soul" in bot:
        soul = bot["soul"]
        if not isinstance(soul, str):
            errors.append("بوت %s: ‏soul‏ يجب أن تكون نصًا." % where)
        elif len(soul.encode("utf-8")) > MAX_SOUL_BYTES:
            errors.append(
                "بوت %s: ‏soul‏ أطول من %d بايت."
                % (where, MAX_SOUL_BYTES)
            )
    if "model" in bot:
        model = bot["model"]
        if not isinstance(model, str) or not _MODEL_RE.match(model):
            errors.append(
                "بوت %s: النموذج «%s» باطل — الصيغة INSTANCE/MODEL "
                "مثل gemini/gemini-3-flash-preview." % (where, model)
            )
    if "effort" in bot and bot["effort"] not in _EFFORTS:
        errors.append(
            "بوت %s: الجهد «%s» باطل — المسموح %s."
            % (where, bot["effort"], "/".join(_EFFORTS))
        )
    if "approval" in bot and bot["approval"] not in _APPROVALS:
        errors.append(
            "بوت %s: مستوى الموافقة «%s» باطل — المسموح %s."
            % (where, bot["approval"], "/".join(_APPROVALS))
        )
    if "computer" in bot and bot["computer"] not in _COMPUTERS:
        errors.append(
            "بوت %s: الحاسوب «%s» مرفوض في v1 — المسموح local أو off فقط."
            % (where, bot["computer"])
        )
    if "cwd" in bot:
        cwd = bot["cwd"]
        if not isinstance(cwd, str) or not cwd:
            errors.append("بوت %s: ‏cwd‏ يجب أن يكون مسارًا غير فارغ." % where)
        elif cwd.startswith("~"):
            errors.append(
                "بوت %s: ‏cwd‏ لا يقبل «~» — اكتب المسار الكامل." % where
            )
        elif not os.path.isabs(cwd):
            errors.append(
                "بوت %s: ‏cwd‏ «%s» ليس مسارًا كاملًا." % (where, cwd)
            )
        elif not os.path.exists(cwd):
            errors.append(
                "بوت %s: ‏cwd‏ «%s» غير موجود على الخادم." % (where, cwd)
            )
    if "browser" in bot and not isinstance(bot["browser"], str):
        errors.append("بوت %s: ‏browser‏ يجب أن يكون نصًا." % where)
    if "tools" in bot:
        _validate_tools(bot["tools"], where, errors)
    if "skills" in bot:
        _validate_skills(bot["skills"], where, errors)


def _normalize_data(data):
    """طبّع نسخة من الملف قبل التحقق/التخطيط.

    خدعة YAML 1.1: ``computer: off`` يحلّلها PyYAML إلى
    المنطقية ``False`` (و``on`` إلى ``True``) — فتُعاد إلى
    نصها قبل أي فحص، وإلا رُفضت قيمة ``off`` الصحيحة.
    """
    data = copy.deepcopy(data)
    if isinstance(data, dict):
        for bot in data.get("bots", []) or []:
            if isinstance(bot, dict) and "computer" in bot:
                if bot["computer"] is False:
                    bot["computer"] = "off"
                elif bot["computer"] is True:
                    bot["computer"] = "on"
    return data


def validate_all(data):
    """ارجع قائمة كل أخطاء التحقق في الملف (فارغة إن كان سليمًا).

    يجمع كل الأخطاء بدل التوقف عند أولها، ليعرضها المستدعي
    دفعة واحدة. مفتاح مكتوب في الملف خطأ هنا أيضًا (خروج 2
    عند رفعه عبر ``validate``).
    """
    errors = []
    data = _normalize_data(data)
    if not isinstance(data, dict):
        return ["ملف الفريق يجب أن يكون خريطة YAML (teams/bots)."]
    unknown = set(data) - {"teams", "bots"}
    if unknown:
        errors.append(
            "ملف الفريق فيه مفاتيح عليا مجهولة: %s."
            % ", ".join(sorted(unknown))
        )
    teams = data.get("teams", [])
    bots = data.get("bots", [])
    if not isinstance(teams, list):
        errors.append("حقل teams يجب أن يكون قائمة.")
        teams = []
    if not isinstance(bots, list):
        errors.append("حقل bots يجب أن يكون قائمة.")
        bots = []

    _check_secret_refs(data, "الملف", errors)

    team_names = set()
    seen_teams = set()
    for index, team in enumerate(teams):
        _validate_team(team, index, errors)
        if isinstance(team, dict) and _is_name(team.get("name")):
            lowered = team["name"].strip().lower()
            team_names.add(lowered)
            if lowered in seen_teams:
                errors.append(
                    "اسم فريق مكرر: «%s» (المطابقة بلا اعتبار لحالة الأحرف)."
                    % team["name"]
                )
            seen_teams.add(lowered)

    if len(bots) > ROSTER_MAX_BOTS:
        errors.append(
            "القائمة فيها %d بوتًا، والحد الأقصى %d (ROSTER_MAX_BOTS)."
            % (len(bots), ROSTER_MAX_BOTS)
        )
    seen_bots = set()
    chiefs = {}
    for index, bot in enumerate(bots):
        _validate_bot(
            bot, index,
            team_names if "teams" in data else None,
            errors,
        )
        if isinstance(bot, dict) and _is_name(bot.get("name")):
            lowered = bot["name"].strip().lower()
            if lowered in seen_bots:
                errors.append(
                    "اسم بوت مكرر: «%s» (المطابقة بلا اعتبار لحالة الأحرف)."
                    % bot["name"]
                )
            seen_bots.add(lowered)
            if bot.get("chief") is True:
                team = bot.get("team")
                team_key = team.strip().lower() if isinstance(team, str) else ""
                if team_key in chiefs:
                    errors.append(
                        "رئيسان في فريق «%s»: «%s» و«%s» — رئيس واحد "
                        "لكل فريق." % (team, chiefs[team_key], bot["name"])
                    )
                else:
                    chiefs[team_key] = bot["name"]
    return errors


def validate(data):
    """تحقق من الملف؛ وارفع ``TeamFileError`` (خروج 2) عند أول خطأ."""
    errors = validate_all(data)
    if errors:
        raise TeamFileError(errors[0], 2)
    return True


# ---------------------------------------------------------------- خطة


def _norm_teams(data):
    teams = {}
    for team in data.get("teams", []) or []:
        if isinstance(team, dict) and _is_name(team.get("name")):
            teams[team["name"].strip().lower()] = dict(team)
    return teams


def _norm_bots(data):
    bots = {}
    for bot in data.get("bots", []) or []:
        if isinstance(bot, dict) and _is_name(bot.get("name")):
            bots[bot["name"].strip().lower()] = dict(bot)
    return bots


def _diff_fields(wanted, current):
    """الحقول الحاضرة في المطلوب وتختلف عن الحالي (حقل يُترك يُترك)."""
    changes = []
    for key, value in wanted.items():
        if key in ("name", "was"):
            continue
        if current.get(key) != value:
            changes.append(key)
    return changes


def plan(data, state=None, prune=False):
    """احسب خطة التطبيق من الملف مقابل الحالة الحالية.

    ترجع ``{"actions": [...], "changed": bool, "message": str}``.
    كل إجراء: ``{"action", "kind", "name", "changes", "detail"}``.
    لا تغيّر الحالة ولا تلمس القرص. ترفع ``TeamFileError``
    عند ملف باطل أو إعادة تسمية فوق اسم موجود أو تجاوز سقف
    القائمة بعد التطبيق. ومع ``prune=True`` تتضمن الخطة حذف
    البوتات غير المذكورة في فرق موسومة ``prune: true``.
    """
    validate(data)
    data = _normalize_data(data)
    state = state or empty_state()
    state_teams = state.get("teams", {})
    state_bots = state.get("bots", {})
    wanted_teams = _norm_teams(data)
    wanted_bots = _norm_bots(data)

    # سقف القائمة بعد التطبيق: الحالي + الجدد − المحذوفون (بلا حذف
    # هنا، فالحساب محافظ: الحالي + الجدد).
    new_names = set(wanted_bots) - set(state_bots)
    # إعادة التسمية عبر was: لا تُحسب جديدًا.
    for bot in wanted_bots.values():
        if bot.get("was") and bot["was"].strip().lower() in state_bots:
            new_names.discard(bot["name"].strip().lower())
    if len(state_bots) + len(new_names) > ROSTER_MAX_BOTS:
        raise TeamFileError(
            "التطبيق سيجعل القائمة %d بوتًا، والحد الأقصى %d."
            % (len(state_bots) + len(new_names), ROSTER_MAX_BOTS),
            2,
        )

    actions = []

    # الفرق: إنشاء فقط — الفرق لا تُحذف أبدًا.
    for lowered, team in wanted_teams.items():
        current = state_teams.get(lowered)
        if current is None:
            actions.append({
                "action": "create", "kind": "team",
                "name": team["name"],
                "changes": [k for k in team if k not in ("name", "was")],
                "detail": "إنشاء فريق «%s»." % team["name"],
            })
        else:
            changes = _diff_fields(team, current)
            if changes:
                actions.append({
                    "action": "update", "kind": "team",
                    "name": team["name"], "changes": changes,
                    "detail": "تحديث فريق «%s»: %s."
                    % (team["name"], ", ".join(changes)),
                })

    # فرق ضمنية لبوتات تشير إلى فريق غير معرَّف في الملف ولا في الحالة.
    for bot in wanted_bots.values():
        team = bot.get("team")
        if isinstance(team, str):
            lowered = team.strip().lower()
            if lowered not in wanted_teams and lowered not in state_teams:
                actions.append({
                    "action": "create", "kind": "team",
                    "name": team, "changes": [],
                    "detail": "إنشاء فريق ضمني «%s»." % team,
                })

    # البوتات: إنشاء أو تحديث أو إعادة تسمية.
    for lowered, bot in wanted_bots.items():
        old_name = bot.get("was")
        target = None
        if old_name and old_name.strip().lower() in state_bots:
            target = state_bots[old_name.strip().lower()]
            if (
                lowered != old_name.strip().lower()
                and lowered in state_bots
            ):
                raise TeamFileError(
                    "إعادة تسمية «%s» إلى «%s» مرفوضة: الاسم الجديد "
                    "موجود أصلًا." % (old_name, bot["name"]),
                    2,
                )
        elif lowered in state_bots:
            target = state_bots[lowered]
        if target is None:
            actions.append({
                "action": "create", "kind": "bot",
                "name": bot["name"],
                "changes": [k for k in bot if k not in ("name", "was")],
                "detail": "إنشاء بوت «%s» في فريق «%s»."
                % (bot["name"], bot.get("team")),
            })
        else:
            changes = _diff_fields(bot, target)
            if old_name and lowered != old_name.strip().lower():
                changes = ["name"] + changes
            if changes:
                actions.append({
                    "action": "update", "kind": "bot",
                    "name": bot["name"], "changes": changes,
                    "detail": "تحديث بوت «%s»: %s."
                    % (bot["name"], ", ".join(changes)),
                })
            # رئيس جديد يزيح رئيسًا قديمًا في الفريق نفسه.
            if bot.get("chief") is True:
                team_key = (
                    bot["team"].strip().lower()
                    if isinstance(bot.get("team"), str) else ""
                )
                for other_key, other in state_bots.items():
                    if (
                        other_key != lowered
                        and other.get("chief") is True
                        and isinstance(other.get("team"), str)
                        and other["team"].strip().lower() == team_key
                        and other_key not in wanted_bots
                        and not (
                            old_name
                            and other_key == old_name.strip().lower()
                        )
                    ):
                        actions.append({
                            "action": "update", "kind": "bot",
                            "name": other["name"], "changes": ["chief"],
                            "detail": "إزاحة رئيس فريق «%s»: «%s» لم يعد رئيسًا."
                            % (bot["team"], other["name"]),
                        })

    # الحذف: فقط مع prune وفقط في فريق موسوم prune: true.
    # (الفرق لا تُحذف أبدًا.) يُحسب هنا في الخطة نفسها،
    # وإلا تخطّاه التطبيق حين لا تغييرات أخرى.
    if prune:
        prune_teams = set()
        for lowered, team in wanted_teams.items():
            if team.get("prune") is True:
                prune_teams.add(lowered)
        for lowered, team in state_teams.items():
            if team.get("prune") is True:
                prune_teams.add(lowered)
        for key, bot in state_bots.items():
            team_key = (
                bot.get("team", "").strip().lower()
                if isinstance(bot.get("team"), str) else ""
            )
            if key not in wanted_bots and team_key in prune_teams:
                actions.append({
                    "action": "delete", "kind": "bot",
                    "name": bot["name"], "changes": [],
                    "detail": "حذف بوت «%s» (غير مذكور، وفريقه موسوم prune)."
                    % bot["name"],
                })

    changed = bool(actions)
    message = NO_CHANGES_MESSAGE
    if changed:
        message = "الخطة: %d تغييرًا (%s)." % (
            len(actions),
            ", ".join(a["detail"] for a in actions),
        )
    return {"actions": actions, "changed": changed, "message": message}


def check(data, state=None):
    """هل سيتغيّر شيء عند التطبيق؟ (ليخرج المستدعي 6 إن نعم)."""
    return plan(data, state)["changed"]


# ---------------------------------------------------------------- تطبيق


def _wait_until_idle(name, busy_check, wait_idle_seconds):
    """انتظر بوتًا مشغولًا حتى يهدأ (حتى ``wait_idle_seconds``).

    ``busy_check`` دالة ترجع True ما دام البوت مشغولًا؛ وغيابها
    يعني: لا انتظار. ترجع True إن هدأ، وFalse إن انتهت المهلة.
    """
    if busy_check is None:
        return True
    deadline = time.monotonic() + max(0, wait_idle_seconds)
    while True:
        if not busy_check(name):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def apply(data, state=None, dry_run=False, prune=False,
          wait_idle_seconds=DEFAULT_WAIT_IDLE_SECONDS, busy_check=None):
    """طبّق ملف فريق على الحالة؛ وارجع النتيجة.

    ترجع ``{"state", "applied", "changed", "message"}``. ومع
    ``dry_run=True`` ترجع الخطة فقط بلا أي تغيير.
    التطبيق ليس ذريًا: عند أول رفض يتوقف ويرفع
    ``TeamApplyError`` حاملًا ما أُنجز والحالة الجزئية،
    فإعادة التطبيق تكمل من حيث توقف.
    """
    planned = plan(data, state, prune=prune)
    data = _normalize_data(data)
    working = copy.deepcopy(state or empty_state())
    working.setdefault("teams", {})
    working.setdefault("bots", {})
    if dry_run or not planned["changed"]:
        return {
            "state": working,
            "applied": [],
            "changed": planned["changed"],
            "message": planned["message"],
        }

    wanted_teams = _norm_teams(data)
    wanted_bots = _norm_bots(data)
    applied = []

    def _fail(message):
        raise TeamApplyError(message, applied=applied, state=working)

    try:
        for action in planned["actions"]:
            kind = action["kind"]
            name = action["name"]
            lowered = name.strip().lower()
            if kind == "team":
                if action["action"] == "create":
                    team = wanted_teams.get(lowered)
                    if team is None:
                        # فريق ضمني: بلا حقول إضافية.
                        working["teams"][lowered] = {"name": name}
                    else:
                        stored = {
                            k: v for k, v in team.items() if k != "was"
                        }
                        working["teams"][lowered] = stored
                else:
                    current = working["teams"].get(lowered, {"name": name})
                    for field in action["changes"]:
                        current[field] = wanted_teams[lowered][field]
                    working["teams"][lowered] = current
                applied.append(action)
                continue

            # بوت: حذف أو انتظار الهدوء قبل تغيير بوت موجود.
            if action["action"] == "delete":
                target_key = lowered
                if lowered not in working["bots"]:
                    for key, bot in working["bots"].items():
                        if bot.get("name") == name:
                            target_key = key
                            break
                working["bots"].pop(target_key, None)
                applied.append(action)
                continue
            old_key = None
            wanted = wanted_bots.get(lowered)
            if wanted is None:
                # إزاحة رئيس قديم — الاسم وحده يكفي.
                for key, bot in working["bots"].items():
                    if bot.get("name") == name:
                        old_key = key
                        wanted = {"chief": False}
                        break
            if wanted is None:
                _fail("بوت «%s» غير موجود في الملف عند التطبيق." % name)
            if action["action"] == "update":
                target_key = lowered
                if (
                    wanted.get("was")
                    and wanted["was"].strip().lower() in working["bots"]
                ):
                    target_key = wanted["was"].strip().lower()
                elif old_key is not None:
                    target_key = old_key
                elif lowered not in working["bots"]:
                    target_key = lowered
                if not _wait_until_idle(
                    name, busy_check, wait_idle_seconds
                ):
                    _fail(
                        "بوت «%s» ما زال مشغولًا بعد %d ثانية؛ "
                        "أُنجز %d تغييرًا، وأعد التطبيق للإكمال."
                        % (name, wait_idle_seconds, len(applied))
                    )
                current = working["bots"].pop(target_key, {"name": name})
                for field in action["changes"]:
                    if field == "name":
                        current["name"] = wanted["name"]
                    else:
                        current[field] = wanted[field]
                working["bots"][current["name"].strip().lower()] = current
            else:
                stored = {
                    k: v for k, v in wanted.items() if k != "was"
                }
                working["bots"][lowered] = stored
            applied.append(action)

    except TeamApplyError:
        raise
    except TeamFileError:
        raise
    except Exception as exc:
        _fail("فشل التطبيق عند «%s»: %s." % (name if "name" in dir() else "؟", exc))

    message = NO_CHANGES_MESSAGE
    if applied:
        message = "طُبّق %d تغييرًا: %s." % (
            len(applied),
            ", ".join(a["detail"] for a in applied),
        )
    return {
        "state": working,
        "applied": applied,
        "changed": bool(applied),
        "message": message,
    }
