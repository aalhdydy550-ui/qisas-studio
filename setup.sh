#!/bin/bash
# setup.sh — مثبّت studio لمرة واحدة (آمن لإعادة التشغيل).
#
# ما يفعله:
#   1) يتحقق من python3.
#   2) يشغّل `studio.py doctor --fix` (ينشئ config.yaml من المثال
#      إن غاب، ويفحص كل شيء: أدوات، موديل الصوت، الخطوط، الشعار).
#   3) ينشئ بيئة YouTube (.venv-youtube) مع مكتبات Data API v3
#      إن غابت — best-effort: فشلها تحذير فقط، لا يوقف التثبيت.
#   4) ينشئ بيئة gTTS (.venv-gtts) للصوت الثاني الاختياري — نفس
#      المبدأ: فشلها تحذير فقط (الصوت الافتراضي Piper لا يتأثر).
# ما لا يفعله أبدًا: لا يثبّت حزم apt تلقائيًا، ولا ينشئ حسابات،
# ولا مفاتيح، ولا ينفق مالًا. ما يحتاج خطوة يدوية يظهر كـ [FAIL]
# مع الأمر الدقيق لإصلاحه.
# الخروج: 0 إن نجحت كل الفحوصات الأساسية، و1 إن فشل أي منها.
set -u
cd "$(dirname "$0")" || exit 1

echo "== تثبيت studio — خطوة واحدة =="
if ! command -v python3 >/dev/null 2>&1; then
    echo "[FAIL] python3 غير موجود — ثبّته أولًا (sudo apt-get install -y python3)"
    exit 1
fi

python3 studio.py doctor --fix
DOCTOR_STATUS=$?

echo ""
echo "== بيئة YouTube (لأمر publish على يوتيوب عبر API) =="
if [ -x ".venv-youtube/bin/python" ] && .venv-youtube/bin/python -c "import googleapiclient" 2>/dev/null; then
    echo "[PASS] بيئة YouTube جاهزة (.venv-youtube)"
else
    echo "إنشاء .venv-youtube وتثبيت مكتبات Google…"
    if python3 -m venv .venv-youtube 2>/dev/null && \
       .venv-youtube/bin/pip install -q google-api-python-client google-auth-oauthlib google-auth-httplib2 2>/dev/null && \
       .venv-youtube/bin/python -c "import googleapiclient" 2>/dev/null; then
        echo "[PASS] بيئة YouTube جاهزة (.venv-youtube)"
    else
        echo "[WARN] تعذر إنشاء بيئة YouTube — النشر على يوتيوب سيعمل"
        echo "       بحزمة الرفع اليدوي فقط حتى تُنشأ البيئة يدويًا:"
        echo "       python3 -m venv .venv-youtube && .venv-youtube/bin/pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
    fi
fi

echo ""
echo "== بيئة gTTS (صوت ثانٍ اختياري --voice gtts) =="
if [ -x ".venv-gtts/bin/python" ] && .venv-gtts/bin/python -c "import gtts" 2>/dev/null; then
    echo "[PASS] بيئة gTTS جاهزة (.venv-gtts)"
else
    echo "إنشاء .venv-gtts وتثبيت gTTS…"
    if python3 -m venv .venv-gtts 2>/dev/null && \
       .venv-gtts/bin/pip install -q gtts 2>/dev/null && \
       .venv-gtts/bin/python -c "import gtts" 2>/dev/null; then
        echo "[PASS] بيئة gTTS جاهزة (.venv-gtts)"
    else
        echo "[WARN] تعذر إنشاء بيئة gTTS — الصوت الثاني الاختياري"
        echo "       غير متاح، والصوت الافتراضي (Piper) يعمل كما هو:"
        echo "       python3 -m venv .venv-gtts && .venv-gtts/bin/pip install gtts"
    fi
fi

echo ""
if [ "$DOCTOR_STATUS" -eq 0 ]; then
    echo "التثبيت اكتمل — النظام جاهز."
    echo "جرّب الآن:  python3 studio.py run --demo"
    echo "ثم انشرها تجريبيًا:  python3 studio.py publish --video ~/workspace/videos/demo-*.mp4 --title \"باع بقرته ووزّع البذور\" --dry-run"
else
    echo "التثبيت غير مكتمل — أصلح سطور [FAIL] أعلاه ثم أعد تشغيل setup.sh."
    echo "(إعادة التشغيل آمنة: لا يعيد ما اكتمل.)"
fi
exit "$DOCTOR_STATUS"
