#!/usr/bin/env python3
"""برومبت الأداء المنظَّم للأفاتار الناطق — جولة v0.1.38 (بند 8).

يبني برومبت أداء إنجليزيًا (برومبتات LongCat إنجليزية) بأربع
خانات: الشخصية والتعبير والإيماءة والكاميرا. نوع المشهد
يضبط افتراضيات الإيماءة/التعبير:

- narration (سرد): هادئ دافئ، حركات رأس خفيفة ونظرة ثابتة.
- dialogue (حوار): معبّر، يدير رأسه قليلًا عند مخاطبة المستمع.
- singing (غناء): إيقاعي عاطفي.

الشخصية الافتراضية راوٍ مصري هادئ دافئ (رجل — قاعدة الخط:
الراوي دائمًا رجل). أي خانة فارغة صراحةً (سلسلة فارغة) تُرفض
بخطأ عربي؛ أما الغائب (None) فيُستبدل بالافتراضي.
"""
# أنواع المشاهد الصالحة.
SCENE_TYPES = ("narration", "dialogue", "singing")

# الشخصية الافتراضية: راوٍ مصري هادئ دافئ (رجل).
DEFAULT_PERSONA = (
    "A middle-aged Egyptian male storyteller, warm and calm")

# الكاميرا الافتراضية: ثابتة، لقطة متوسطة قريبة، على مستوى العين.
DEFAULT_CAMERA = "static camera, medium close-up, eye level"

# افتراضيات التعبير/الإيماءة لكل نوع مشهد.
SCENE_DEFAULTS = {
    "narration": {
        "expression": "calm and warm, storytelling tone",
        "gesture": "subtle head movements, steady gaze",
    },
    "dialogue": {
        "expression": "expressive and engaged",
        "gesture": "turns head slightly when addressing the listener",
    },
    "singing": {
        "expression": "emotive",
        "gesture": "rhythmic head movement, emotive expression",
    },
}


class AvatarPromptError(Exception):
    """خطأ برومبت أداء — رسالة عربية."""


def _slot(value, default, name):
    """خانة برومبت: None ← افتراضي؛ فارغة ← خطأ؛ غير ذلك ← كما هي."""
    if value is None:
        return default
    if not isinstance(value, str) or not value.strip():
        raise AvatarPromptError(
            "خانة برومبت الأداء «%s» فارغة — اكتب وصفًا أو اتركها "
            "بلا قيمة للافتراضي" % name)
    return value.strip()


def _validate_scene_type(scene_type):
    if scene_type not in SCENE_TYPES:
        raise AvatarPromptError(
            "نوع المشهد غير معروف: %s (الصالح: %s)"
            % (scene_type, "، ".join(SCENE_TYPES)))
    return scene_type


def build_performance_prompt(persona=None, expression=None,
                             gesture=None, camera=None,
                             scene_type="narration"):
    """ابنِ برومبت أداء إنجليزيًا بأربع خانات.

    persona/expression/gesture/camera: نص أو None للافتراضي؛
    وسلسلة فارغة تُرفض. scene_type يضبط افتراضيات التعبير
    والإيماءة (narration/dialogue/singing).
    يرجع نص البرومبت الإنجليزي.
    """
    scene_type = _validate_scene_type(scene_type)
    defaults = SCENE_DEFAULTS[scene_type]
    persona = _slot(persona, DEFAULT_PERSONA, "الشخصية")
    expression = _slot(expression, defaults["expression"], "التعبير")
    gesture = _slot(gesture, defaults["gesture"], "الإيماءة")
    camera = _slot(camera, DEFAULT_CAMERA, "الكاميرا")
    return ("Persona: %s. Expression: %s. Gesture: %s. Camera: %s."
            % (persona, expression, gesture, camera))


def prompt_from_scene(scene):
    """برومبت من قاموس مشهد {type, persona?, expression?,
    gesture?, camera?} — type هو scene_type (افتراضي narration)."""
    if not isinstance(scene, dict):
        raise AvatarPromptError(
            "المشهد يجب أن يكون قاموسًا (القيمة: %s)" % (scene,))
    return build_performance_prompt(
        persona=scene.get("persona"),
        expression=scene.get("expression"),
        gesture=scene.get("gesture"),
        camera=scene.get("camera"),
        scene_type=scene.get("type") or "narration")


def prompt_to_manifest(prompt, scene_type="narration"):
    """حوّل برومبتًا إلى حقلي بيان: performance_prompt + scene_type."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise AvatarPromptError("برومبت الأداء فارغ — لا يُسجَّل في البيان")
    scene_type = _validate_scene_type(scene_type)
    return {"performance_prompt": prompt.strip(),
            "scene_type": scene_type}
