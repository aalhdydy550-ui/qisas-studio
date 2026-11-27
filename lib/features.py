#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""مفاتيح مزايا موحدة — جولة v0.1.63، بند 24 (ع7) + بند 23.

كائن ``features`` واحد في ``~/.qisas-studio/config.json`` لكل
راية تجريبية في الاستوديو، بدل رايات سطر أوامر مبعثرة.

القواعد (من §4.14):

- التغيير **دمج لا استبدال**: تُدمج المفاتيح المطلوبة فقط في
  كائن ``features`` الموجود، بعد نسخ احتياطي للملف.
- الافتراض يعني أن المفتاح محذوف؛ والقيمة **ثلاثية الحالات**:
  محذوف (``None``) ≠ ``false`` ≠ ``true`` — فـ ``get`` يحفظ
  الفرق ولا يطمسه بقيمة افتراضية.
- تجاوزات بيئة بمطابقة دقيقة ``1`` أو ``0`` فقط، باسم
  ``QISAS_FEATURE_<NAME>`` (أحرف كبيرة)؛ وسلاسل أخرى لا تعمل
  كتجاوزات وتُتجاهل.
- المفاتيح لا تتجاوز الأذونات أبدًا ولا قدرات المحرك ولا
  إعدادات كل بوت — هذه الوحدة تخزّن الرايات فقط، والتطبيق
  عند موضع الاستخدام هو من يفحص الأذونات.

هذه الوحدة تحسم مسار إعداداتها بنفسها
(``~/.qisas-studio/config.json``)؛ ولا تعديل في
``lib/license.py`` لبند 24 (انحراف موثّق في خطة الجولة).
وللاختبارات المعزولة يقبل كل استدعاء مسار إعدادات صريحًا،
أو متغير البيئة ``QISAS_CONFIG_PATH``.

المفاتيح المعروفة وقيمها:

- ``parallelRoomJobs`` (افتراضي True — بند 23): مهام أعضاء
  غرفة جنبًا إلى جنب كل في خيطه؛ و``false`` = واحدة تلو الأخرى
  في خيط المنسّق. دالة ``parallel_enabled()`` المساعدة تقرأه.
- ``skillReview`` (منطقي، بلا افتراض).
- ``skillReviewSteps`` (صحيح 3–100).
- ``shareLearnedSkills`` (‏``off|ask|auto``).
- ``autoRecall`` (منطقي، بلا افتراض).
- ``roomMemoryCapture`` (منطقي، بلا افتراض).
- ``agentsToolBridge`` (منطقي، بلا افتراض).
- ``webhookReceiver`` (افتراضي False — بوابة بند 36).

الوحدة مستقلة: مكتبة قياسية فقط، ولا تستورد أي وحدة ``lib``
أخرى ولا ``studio``. الاستيرادات المتقاطعة — حين يحتاجها
مستهلك — كسولة داخل الدالة.
"""

import json
import os
import shutil
import tempfile

__all__ = [
    "CONFIG_FILENAME",
    "KNOWN_FEATURES",
    "FeatureError",
    "config_path",
    "get",
    "is_set",
    "set",
    "list_features",
    "parallel_enabled",
]

CONFIG_FILENAME = "config.json"

# المفاتيح المعروفة: الاسم → (النوع، الافتراضي).
# الافتراضي ``None`` يعني: المفتاح محذوف = بلا قيمة افتراضية.
KNOWN_FEATURES = {
    "parallelRoomJobs": ("bool", True),
    "skillReview": ("bool", None),
    "skillReviewSteps": ("int_3_100", None),
    "shareLearnedSkills": ("off_ask_auto", None),
    "autoRecall": ("bool", None),
    "roomMemoryCapture": ("bool", None),
    "agentsToolBridge": ("bool", None),
    "webhookReceiver": ("bool", False),
}

# بادئة متغيرات بيئة التجاوز.
_ENV_PREFIX = "QISAS_FEATURE_"


class FeatureError(Exception):
    """خطأ في مفاتيح المزايا (رسالته عربية)."""


def config_path(path=None):
    """مسار ملف الإعدادات.

    مسار صريح إن مُرّر؛ وإلا متغير البيئة ``QISAS_CONFIG_PATH``
    (للتوجيه في الاختبارات إلى ملف مؤقت)؛ وإلا
    ``~/.qisas-studio/config.json``.
    """
    if path:
        return os.path.expanduser(str(path))
    env_path = os.environ.get("QISAS_CONFIG_PATH")
    if env_path:
        return os.path.expanduser(env_path)
    return os.path.join(
        os.path.expanduser("~"), ".qisas-studio", CONFIG_FILENAME
    )


def _env_override_name(name):
    """اسم متغير بيئة التجاوز لمفتاح: ``QISAS_FEATURE_<NAME>``."""
    return _ENV_PREFIX + str(name).upper()


def _env_override(name):
    """تجاوز البيئة: مطابقة دقيقة ``1`` → True و``0`` → False.

    أي سلسلة أخرى (ومنها ``true`` و``yes``) تُتجاهل وتُعامل
    كأن لا تجاوز — حسب عقد ع7.
    """
    raw = os.environ.get(_env_override_name(name))
    if raw == "1":
        return True
    if raw == "0":
        return False
    return None


def _validate_value(name, value):
    """تحقق من قيمة مفتاح معروف؛ وارفع ``FeatureError`` عند بطلانها."""
    spec = KNOWN_FEATURES.get(name)
    if spec is None:
        return value
    kind, _default = spec
    if kind == "bool":
        if not isinstance(value, bool):
            raise FeatureError(
                "قيمة المفتاح «%s» يجب أن تكون true أو false، لا %r."
                % (name, value)
            )
    elif kind == "int_3_100":
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 3 <= value <= 100
        ):
            raise FeatureError(
                "قيمة المفتاح «%s» يجب أن تكون عددًا صحيحًا بين 3 و100، لا %r."
                % (name, value)
            )
    elif kind == "off_ask_auto":
        if value not in ("off", "ask", "auto"):
            raise FeatureError(
                "قيمة المفتاح «%s» يجب أن تكون off أو ask أو auto، لا %r."
                % (name, value)
            )
    return value


def _read_config(path):
    """اقرأ ملف الإعدادات كاملًا؛ وملف غائب أو تالف يرجع ``{}``.

    ملف تالف يُعامل كغياب (مع ``corrupt`` في سجل الاستدعاء؟ لا —
    هذه الوحدة لا تسجّل؛ والكتابة التالية تعيد بناءه سليمًا).
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_config(path, data):
    """اكتب الإعدادات ذريًا (ملف مؤقت + ``os.replace``) بصلاحية 0600."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=directory or ".", prefix=".config-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def get(name, default=None, path=None):
    """اقرأ مفتاح مزايا مع حفظ حالته الثلاثية.

    - تجاوز بيئة ``1``/``0`` يفوز على الملف.
    - مفتاح محذوف من الملف يرجع ``default`` — و``default`` نفسه
      هو ``None`` ما لم يُمرَّر غيره، فيبقى الغائب مميزًا عن
      ``false``.
    - قيمة مخزنة تالفة النوع (مثل نص بدل منطقي) تُتجاهل وتُعامل
      كمحذوفة.
    """
    if not isinstance(name, str) or not name:
        raise FeatureError("اسم المفتاح يجب أن يكون نصًا غير فارغ.")
    override = _env_override(name)
    if override is not None:
        return override
    data = _read_config(config_path(path))
    features = data.get("features")
    if not isinstance(features, dict) or name not in features:
        return default
    value = features[name]
    spec = KNOWN_FEATURES.get(name)
    if spec is not None:
        try:
            _validate_value(name, value)
        except FeatureError:
            return default
    return value


def is_set(name, path=None):
    """هل المفتاح موجود فعلًا في الملف (محذوف ≠ false)؟

    تجاوز البيئة لا يُحتسب هنا — هذه قراءة حالة الملف وحده.
    """
    data = _read_config(config_path(path))
    features = data.get("features")
    return isinstance(features, dict) and name in features


def set(name, value, path=None):
    """اضبط مفتاحًا واحدًا — دمج لا استبدال، بعد نسخ احتياطي.

    تُدمج القيمة في كائن ``features`` الموجود ويبقى كل مفتاح
    آخر كما هو؛ ويُنسخ الملف القديم إلى ``config.json.bak``
    قبل الكتابة. يرجع القيمة الفعالة بعد الضبط.
    """
    if not isinstance(name, str) or not name:
        raise FeatureError("اسم المفتاح يجب أن يكون نصًا غير فارغ.")
    _validate_value(name, value)
    resolved = config_path(path)
    if os.path.isfile(resolved):
        shutil.copyfile(resolved, resolved + ".bak")
    data = _read_config(resolved)
    features = data.get("features")
    if not isinstance(features, dict):
        features = {}
        data["features"] = features
    features[name] = value
    _write_config(resolved, data)
    return get(name, path=path)


def list_features(path=None):
    """ارجع كل المفاتيح المعروفة بقيمها الفعالة.

    المفتاح المحذوف يظهر بقيمته الافتراضية إن وُجدت
    (``parallelRoomJobs`` → True، و``webhookReceiver`` → False)
    وإلا ``None`` — فالغائب يبقى مميزًا عن ``false``.
    """
    result = {}
    for name, (_kind, default) in KNOWN_FEATURES.items():
        result[name] = get(name, default=default, path=path)
    return result


def parallel_enabled(path=None):
    """هل مهام أعضاء الغرفة متوازية؟ (بند 23 — افتراضي True).

    ``parallelRoomJobs`` مفعّلة افتراضيًا: مهام معيَّنة لعدة
    عمّال تعمل جنبًا إلى جنب كل في خيطه؛ و``false`` (أو تجاوز
    بيئة ``0``) = واحدة تلو الأخرى في خيط المنسّق.
    """
    return bool(get("parallelRoomJobs", default=True, path=path))
