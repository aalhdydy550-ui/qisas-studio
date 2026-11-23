#!/usr/bin/env python3
"""صوت ثانٍ اختياري — Supertonic 3 (راوٍ عربي ذكوري، الصوت M1 فقط).

الراوي الافتراضي يبقى Piper Kareem (رجل) دائمًا — هذا صوت ثانٍ
فقط عبر `--voice supertonic-M1` (التوصيل في studio.py مهمة
المنسّق؛ هذه الوحدة لا تغيّر أي افتراضي).

المسار المُتحقَّق (من `~/workspace/supertonic-test/REPORT-AR.md`،
2026-11-23): حزمة PyPI الرسمية `supertonic` ‏1.3.1، والنموذج
`Supertone/supertonic-3` من المستودع الرسمي، يُحمَّل عبر
`TTS(model="supertonic-3")` بسرعة 1.05 ولغة `ar`، والأصوات
المسبقة فقط (M1–M5) — لا استنساخ صوت إطلاقًا.

نتائج اختبار A/B الموثقة (لا تُعاد هنا): M1 الأوضح
(WER ‏0.078 / CER ‏0.021 / F0 ‏131 هرتز) وهو المدمج؛ M2
(نفس الوضوح، أعمق 91 هرتز) بديل لاحق غير مدمج؛ M3/M4
مرفوضان. Piper ما زال الأول رقميًا بفارق كلمة واحدة من 128.

أين النموذج؟ مخزّن في `~/.cache/supertonic3` (386MB، 26 ملفًا)
ولا يُنسخ إلى الشجرة ولا يُنزَّل من جديد. المسار قابل للضبط
بمتغير البيئة `SUPERTONIC_CACHE_DIR` (يحترمه SDK نفسه) أو
بوسيط `model_dir`. مفسّر بايثون الذي فيه حزمة `supertonic`
يُحلّ بترتيب: متغير `SUPERTONIC_VENV_PYTHON`، ثم
`.venv-supertonic/bin/python` في مجلد الاستوديو، ثم بيئة
الاختبار المُتحقَّقة `~/workspace/supertonic-test/venv/bin/python`،
ثم مفسّر العملية الحالية إن كانت فيه الحزمة.

التطبيع الإلزامي قبل التوليف (موثّق في التقرير): Supertonic
يرفض الفاصلة المنقوطة العربية `؛` (`ValueError`) فيُستبدل
بفاصلة `،`؛ والأرقام تُحوَّل إلى كلمات (ضعف موثّق في النموذج
لم يُختبَر في تقرير A/B). التشكيل الجزئي مقبول بلا خطأ.

الرخصة: النموذج OpenRAIL-M (BigScience، 18 أغسطس 2022) —
نسختها الكاملة مشحونة في `lib/supertonic/LICENSE.txt`، وكود
الـSDK ‏MIT. المادة 4(أ): عند توزيع النموذج أو مشتقاته يجب
تضمين قيود الاستخدام (المادة 5) كبند نافذ في الاتفاقية
الحاكمة وإشعار المستخدمين اللاحقين بأن النموذج خاضع لها،
والمادة 4(ب): تسليم نسخة من الرخصة لكل متلقٍّ. الملحق أ(هـ):
أي فيديو بصوت Supertonic يجب أن يحمل في وصفه إفصاحًا صريحًا
بأن الصوت مولّد آليًا — انظر `DISCLOSURE_LINE`.

العينات: 44100 هرتز أحادي 16-bit (مقابل 22050 لـPiper) —
من يدمج المخرجات في تجميع واحد عليه إعادة التشفير/التوحيد
(انظر مواصفة التوصيل في تقرير البند).
"""
import os
import re
import subprocess
import sys
import tempfile

STUDIO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_NAME = "supertonic-3"
MODEL_REPO = "Supertone/supertonic-3"
MODEL_URL = "https://huggingface.co/Supertone/supertonic-3"
SDK_PACKAGE = "supertonic"
SDK_VERSION_TESTED = "1.3.1"
DEFAULT_SPEED = 1.05  # سرعة Supertonic الافتراضية في اختبار A/B
DEFAULT_LANG = "ar"

#: الصوت الوحيد المدعوم الآن — M1 (الأوضح في اختبار A/B).
SUPPORTED_VOICES = ("M1",)

#: سطر الإفصاح الإلزامي في وصف أي فيديو يستخدم صوت Supertonic
#: (ترخيص OpenRAIL-M، الملحق أ(هـ)).
DISCLOSURE_LINE = "صوت مولّد بالذكاء الاصطناعي"

#: ملفات النموذج المطلوبة داخل مجلد الكاش (مسارات نسبية).
REQUIRED_MODEL_FILES = (
    "onnx/text_encoder.onnx",
    "onnx/duration_predictor.onnx",
    "onnx/vector_estimator.onnx",
    "onnx/vocoder.onnx",
    "onnx/tts.json",
    "onnx/unicode_indexer.json",
    "voice_styles/M1.json",
)

#: بيئة الاختبار المُتحقَّقة التي فيها حزمة supertonic ‏1.3.1.
TEST_VENV_PYTHON = os.path.join(
    os.path.expanduser("~"), "workspace", "supertonic-test",
    "venv", "bin", "python")


class SupertonicError(Exception):
    """خطأ في توليد الصوت بـSupertonic (رسالته عربية)."""


# ------------------------------------------------------------- التطبيع

def normalize_text(text):
    """طبّع نصًا عربيًا قبل توليف Supertonic.

    القاعدة الوحيدة الموثقة في تقرير الاختبار: الفاصلة
    المنقوطة العربية `؛` تُستبدل بفاصلة `،` لأن Supertonic
    يرفض `؛` أصلًا. أي نص بلا `؛` يرجع كما هو حرفيًا.
    """
    if text is None:
        return ""
    return text.replace("؛", "،")


# ------------------------------------------------------- الأرقام إلى كلمات

_ONES = ("صفر", "واحد", "اثنان", "ثلاثة", "أربعة", "خمسة",
         "ستة", "سبعة", "ثمانية", "تسعة", "عشرة")
_TEENS = {11: "أحد عشر", 12: "اثنا عشر", 13: "ثلاثة عشر",
          14: "أربعة عشر", 15: "خمسة عشر", 16: "ستة عشر",
          17: "سبعة عشر", 18: "ثمانية عشر", 19: "تسعة عشر"}
_TENS = {20: "عشرون", 30: "ثلاثون", 40: "أربعون", 50: "خمسون",
         60: "ستون", 70: "سبعون", 80: "ثمانون", 90: "تسعون"}
_HUNDREDS = {100: "مئة", 200: "مئتان", 300: "ثلاثمئة",
             400: "أربعمئة", 500: "خمسمئة", 600: "ستمئة",
             700: "سبعمئة", 800: "ثمانمئة", 900: "تسعمئة"}
_EASTERN_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_MAX_NUMBER = 999999


def _under_100(n):
    if n <= 10:
        return _ONES[n]
    if n in _TEENS:
        return _TEENS[n]
    tens = (n // 10) * 10
    ones = n % 10
    if ones == 0:
        return _TENS[tens]
    return "%s و%s" % (_ONES[ones], _TENS[tens])


def _under_1000(n):
    hundreds = (n // 100) * 100
    rest = n % 100
    if hundreds == 0:
        return _under_100(rest)
    word = _HUNDREDS[hundreds]
    if rest == 0:
        return word
    return "%s و%s" % (word, _under_100(rest))


def _number_words(n):
    """حوّل عددًا صحيحًا (0–999999) إلى كلمات عربية منطوقة.

    صيغ مذكرة (الراوي رجل، ونصوص القصص أعدادها مذكرة في
    الغالب). السنوات الأربع أرقام تُقرأ بالطريقة نفسها:
    2026 ← «ألفان وستة وعشرون».
    """
    if n < 0 or n > _MAX_NUMBER:
        raise ValueError("العدد خارج النطاق المدعوم (0–999999): %d" % n)
    if n < 1000:
        return _under_1000(n)
    thousands = n // 1000
    rest = n % 1000
    if thousands == 1:
        word = "ألف"
    elif thousands == 2:
        word = "ألفان"
    elif thousands <= 10:
        word = "%s آلاف" % _under_1000(thousands)
    else:
        word = "%s ألفًا" % _under_1000(thousands)
    if rest == 0:
        return word
    return "%s و%s" % (word, _under_1000(rest))


_DIGITS_RE = re.compile(r"[0-9٠-٩]+")


def numbers_to_words(text):
    """حوّل الأرقام في النص إلى كلمات عربية منطوقة.

    يغطي الأرقام العربية (0–9) والمشرقية (٠–٩)، والأعداد
    الصحيحة والسنوات الأربع أرقام، حتى 999999.

    الحدود الموثقة (لا تُتجاوز بصمت):
    - الأعداد الأكبر من 999999 تُترك أرقامًا كما هي.
    - الكسور العشرية (مثل 2.5) تُترك كما هي — النقطة فاصل
      لا يُفسَّر هنا.
    - الإعراب مذكّر دائمًا (صيغة واحدة: «ألفان وستة وعشرون»
      لا «ألفين وستة وعشرين»)؛ والعدد المفرد لا يُطابَق مع
      المعدود تأنيثًا/تذكيرًا — فإن احتاج نص صيغة مؤنثة
      (مثل «ثلاث نساء») فليُكتب العدد كلمةً في المصدر.
    - لا يُفسَّر سياق الرقم (سنة/عدد/هاتف) — كل عدد يُقرأ
      بالصيغة العددية نفسها.
    """
    if text is None:
        return ""

    def _replace(match):
        token = match.group(0)
        try:
            n = int(token.translate(_EASTERN_DIGITS))
        except ValueError:
            return token
        if n > _MAX_NUMBER:
            return token
        return _number_words(n)

    return _DIGITS_RE.sub(_replace, text)


def prepare_text(text):
    """التطبيع الكامل قبل التوليف: `؛`→`،` ثم الأرقام إلى كلمات."""
    return numbers_to_words(normalize_text(text))


# ------------------------------------------------------- اكتشاف النموذج

def default_model_dir():
    """مجلد نموذج Supertonic-3: `SUPERTONIC_CACHE_DIR` إن ضُبط
    (يحترمه SDK نفسه)، وإلا `~/.cache/supertonic3` المُتحقَّق."""
    override = os.environ.get("SUPERTONIC_CACHE_DIR")
    if override:
        return os.path.expanduser(override)
    return os.path.join(os.path.expanduser("~"), ".cache", "supertonic3")


def model_available(model_dir=None):
    """هل ملفات النموذج المطلوبة (ومنها صوت M1) موجودة محليًا؟"""
    base = model_dir or default_model_dir()
    return all(os.path.isfile(os.path.join(base, rel))
               for rel in REQUIRED_MODEL_FILES)


def missing_model_files(model_dir=None):
    """قائمة ملفات النموذج الغائبة (فارغة إن كان النموذج كاملًا)."""
    base = model_dir or default_model_dir()
    return [rel for rel in REQUIRED_MODEL_FILES
            if not os.path.isfile(os.path.join(base, rel))]


def find_supertonic_python():
    """مفسّر بايثون فيه حزمة supertonic، أو None إن لم يوجد.

    الترتيب: `SUPERTONIC_VENV_PYTHON`، ثم
    `.venv-supertonic/bin/python` في مجلد الاستوديو، ثم بيئة
    الاختبار المُتحقَّقة، ثم مفسّر العملية الحالية.
    """
    candidates = []
    env_py = os.environ.get("SUPERTONIC_VENV_PYTHON")
    if env_py:
        candidates.append(env_py)
    candidates.append(os.path.join(STUDIO_DIR, ".venv-supertonic",
                                   "bin", "python"))
    candidates.append(TEST_VENV_PYTHON)
    for path in candidates:
        if os.path.isfile(path):
            return path
    try:
        import importlib.util
        if importlib.util.find_spec(SDK_PACKAGE) is not None:
            return sys.executable
    except (ImportError, ValueError):
        pass
    return None


def available_voices():
    """الأصوات المدعومة الآن: M1 فقط."""
    return list(SUPPORTED_VOICES)


# ------------------------------------------------------------- التوليف

_SYNTH_HELPER = (
    "import sys\n"
    "from supertonic import TTS\n"
    "text = open(sys.argv[1], encoding='utf-8').read()\n"
    "out = sys.argv[2]\n"
    "model_dir = sys.argv[3]\n"
    "speed = float(sys.argv[4])\n"
    "tts = TTS(model='supertonic-3', model_dir=model_dir,"
    " auto_download=False)\n"
    "style = tts.get_voice_style('M1')\n"
    "wav, dur = tts.synthesize(text, voice_style=style,"
    " lang='ar', speed=speed)\n"
    "tts.save_audio(wav, out)\n"
    "print('OK')\n"
)


def synthesize(text, voice="M1", out_path=None, speed=DEFAULT_SPEED,
               timeout=600, model_dir=None, venv_python=None):
    """ركّب نصًا عربيًا بصوت Supertonic M1 إلى ملف WAV.

    يطبّق التطبيع + تحويل الأرقام تلقائيًا قبل التوليف.
    الصوت الوحيد المدعوم الآن `M1`؛ أي قيمة أخرى ترفع
    `ValueError` برسالة عربية. يرفع `SupertonicError` برسالة
    عربية واضحة إن غاب النموذج أو مفسّر الحزمة أو فشل التوليف.
    لا ينزّل النموذج أبدًا — إن غاب فالرسالة تشرح كيف يُجلَب.

    يرجع مسار ملف WAV الناتج (44100 هرتز أحادي 16-bit).
    """
    if voice == "M2":
        raise ValueError(
            "الصوت M2 بديل لاحق غير مدمج بعد — المدعوم الآن: M1 فقط")
    if voice != "M1":
        raise ValueError(
            "الصوت غير مدعوم: %s (المدعوم الآن: M1 فقط)" % voice)
    if out_path is None:
        raise SupertonicError("مسار ملف الإخراج غير محدد")
    prepared = prepare_text(text)
    if not prepared.strip():
        raise SupertonicError("نص المقطع فارغ")
    base = model_dir or default_model_dir()
    missing = missing_model_files(base)
    if missing:
        raise SupertonicError(
            "نموذج Supertonic-3 غير موجود أو ناقص في %s "
            "(ينقص: %s) — نزّله مرة واحدة من المستودع الرسمي "
            "Supertone/supertonic-3 (أو اضبط SUPERTONIC_CACHE_DIR "
            "على مجلد نموذج جاهز)؛ ولا يُنزَّل تلقائيًا أثناء التوليف"
            % (base, ", ".join(missing)))
    python = venv_python or find_supertonic_python()
    if python is None:
        raise SupertonicError(
            "حزمة supertonic غير مثبّتة في أي بيئة بايثون — ثبّتها بـ:\n"
            "  python3 -m venv .venv-supertonic && "
            ".venv-supertonic/bin/pip install supertonic\n"
            "أو اضبط SUPERTONIC_VENV_PYTHON على مفسّر بيئة فيها الحزمة")
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="supertonic-")
    try:
        text_path = os.path.join(tmp, "text.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(prepared)
        cmd = [python, "-c", _SYNTH_HELPER, text_path,
               os.path.abspath(out_path), base, str(speed)]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            raise SupertonicError(
                "توليف Supertonic انتهت مهلته (%d ثانية)" % timeout)
        except FileNotFoundError:
            raise SupertonicError(
                "مفسّر بايثون غير موجود: %s" % python)
        if proc.returncode != 0:
            raise SupertonicError(
                "فشل توليف Supertonic (رمز الخروج %d): %s"
                % (proc.returncode,
                   (proc.stderr or proc.stdout or "").strip()[-500:]))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise SupertonicError(
            "انتهى التوليف دون إنشاء WAV: %s" % out_path)
    return os.path.abspath(out_path)
