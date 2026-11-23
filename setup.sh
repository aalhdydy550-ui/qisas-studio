#!/bin/bash
# setup.sh — مثبّت studio في أمر واحد (v0.1.41).
#
# الاستخدام (من جذر المستودع):
#   bash setup.sh                 # تثبيت كامل: كل شيء إلا الثقيل (كسول)
#   bash setup.sh --dry-run       # اعرض الخطوات فقط — بلا أي تنفيذ
#   bash setup.sh --check         # افحص الحالة الحالية فقط — بلا تثبيت
#   bash setup.sh --with whisper  # وثبّت أيضًا بيئة ثقيلة مقدمًا
#   bash setup.sh --full          # كل شيء بما فيه البيئتان الثقيلتان
#   bash setup.sh --path-dry-run  # اعرض تغييرات PATH فقط — بلا كتابة
#   bash setup.sh --path-only     # طبّق كتلة PATH فقط + تحقق منها
#   bash setup.sh --remove-path   # احذف كتلة PATH (تراجع)
#   bash setup.sh --no-path       # تثبيت كامل بلا لمس ملفات بدء التشغيل
#   bash setup.sh --help
#
# ما يفعله، خطوة بخطوة (مع تقدّم [n/7]):
#   [1/7] python3 (‏3.10+‏) وصلاحية إنشاء البيئات.
#   [2/7] حزم النظام: ffmpeg وffprobe وpython3-venv وfontconfig
#         وخط عربي — يثبّتها تلقائيًا فقط إن وُجد sudo بلا كلمة
#         سر؛ وإلا يطبع الأمر الدقيق ويكمل (تحذير لا فشل).
#         (تخطَّ هذه الخطوة بـ STUDIO_SETUP_NO_APT=1.)
#   [3/7] بيئة خفيفة واحدة مشتركة تسكن في .venv-youtube
#         للأدوات الثلاث الخفيفة (gTTS + يوتيوب API + القص
#         التلقائي) بدل ثلاث بيئات — مع روابط رمزية من
#         المسارين القديمين (.venv-gtts و.venv-autoeditor)
#         إليها حتى تعمل الأوامر الحالية بلا تعديل، ثم تحقق
#         SHA-256 من الملفات المثبّتة (فشل التحقق = إيقاف).
#         (الاسم التاريخي مقصود: هو وحده مستثنى أصلًا في
#         .gitignore وحارس الأسرار والنسخ الاحتياطي.)
#   [4/7] البيئتان الثقيلتان (whisper ‏~478M وmoviepy ‏~269M):
#         افتراضيًا كسولتان — لا تُثبَّتان مقدمًا، بل عند أول
#         استدعاء لأمرهما (أو بـ --with/--full). هكذا يبدأ
#         مستخدم جديد بنحو 200 ميجا بدل ~984 ميجا. والإصدارات
#         مثبّتة؛ وفشل المثبّت يجرّب أحدث إصدار (احتياطي متدرج).
#   [5/7] فحص خادم الذكاء المحلي (قراءة فقط — لا يشغّل شيئًا؛
#         يبدأ الخادم تلقائيًا عند أول أمر studio يحتاجه).
#   [6/7] فحص doctor الكامل (مع --fix) + ملخص بالوضع النهائي.
#   [7/7] كتلة PATH معلَّمة في ملفات بدء التشغيل (‏~/.local/bin
#         و~/.npm-global/bin — نفس المجلدين اللذين يضيفهما
#         الإصلاح الذاتي وقت التشغيل): تُستبدل في مكانها عند
#         إعادة التشغيل بلا تكرار، وتُحذف بـ --remove-path
#         للتراجع؛ ثم تحقق من shell جديدة أن التعديل يعمل.
#
# ما لا يفعله أبدًا: لا يثبّت حزمًا مدفوعة، ولا ينشئ حسابات،
# ولا مفاتيح، ولا ينفق مالًا، ولا يلمس المنشورات المجدولة
# ولا الطابور ولا بيانات العملاء. وما يحتاج خطوة يدوية يظهر
# كـ [FAIL] مع الأمر الدقيق لإصلاحه. ويلمس ملفات بدء التشغيل
# فقط لإضافة كتلة PATH المعلَّمة (قابلة للحذف بـ --remove-path).
#
# الخروج: 0 إن نجحت الفحوصات الأساسية، و1 إن فشل أي منها.
# --dry-run يخرج 0 دائمًا، و--check يخرج 1 إن كان شيء أساسي
# غائبًا. إعادة التشغيل آمنة: لا يعيد ما اكتمل.
#
# ملاحظة توافق: آليات الإصلاح الذاتي الحالية (سكربت استعادة
# البيئة + حارس البيئة + خطافا الدخول) لا تمس البيئات
# الافتراضية أصلًا، فلا شيء من عملها يتغير بهذا المثبّت.
# وإن وُجدت بيئة قديمة حقيقية (.venv-gtts مثلًا) تُحترم
# كما هي ولا تُستبدل برابط رمزي. والبيئة المشتركة تسكن
# في .venv-youtube نفسه (الاسم التاريخي) لنفس سبب الاستثناء
# الموثَّق في lib/ensure_env.py.
#
# بنية السكربت (نمط AlphaCLI): كل التنفيذ داخل main() تُستدعى
# في السطر الأخير — فإن انقطع تنزيل السكربت نفسه لا يُنفَّذ
# نصف مثبّت. الأنماط الستة موثَّقة في docs/SETUP.md.
set -u

usage() {
    awk 'NR==1{next} /^set -u/{exit} {sub(/^# ?/, ""); print}' "$0"
}

# ---------- كتلة PATH المعلَّمة (نمط AlphaCLI) ----------
PATH_BEGIN='# >>> qisas-studio >>>'
PATH_END='# <<< qisas-studio <<<'
PATH_TOOLS="ffmpeg ffprobe yt-dlp omniroute piper melt"

path_rc_files() {
    case "${SHELL:-/bin/bash}" in
        *fish*) echo "$HOME/.config/fish/config.fish" ;;
        *zsh*) echo "$HOME/.zshrc" ;;
        *) echo "$HOME/.bashrc $HOME/.profile" ;;
    esac
}

path_block_content() {
    # $1: fish أو sh — نص الكتلة كاملًا بلا سطر فارغ أخير.
    if [ "$1" = "fish" ]; then
        printf '%s\n# أضافها setup.sh — أدوات studio في ~/.local/bin و~/.npm-global/bin.\nfish_add_path "$HOME/.local/bin"\nfish_add_path "$HOME/.npm-global/bin"\n%s' \
            "$PATH_BEGIN" "$PATH_END"
    else
        printf '%s\n# أضافها setup.sh — أدوات studio في ~/.local/bin و~/.npm-global/bin.\ncase ":$PATH:" in\n  *":$HOME/.local/bin:"*) ;;\n  *) export PATH="$HOME/.local/bin:$PATH" ;;\nesac\ncase ":$PATH:" in\n  *":$HOME/.npm-global/bin:"*) ;;\n  *) export PATH="$HOME/.npm-global/bin:$PATH" ;;\nesac\n%s' \
            "$PATH_BEGIN" "$PATH_END"
    fi
}

path_file_kind() {
    case "$1" in
        *.fish|*/fish/*) echo "fish" ;;
        *) echo "sh" ;;
    esac
}

# حالة الكتلة في ملف: missing-file | absent | identical | different.
path_status_file() {
    local file="$1" kind block current
    [ -f "$file" ] || { echo "missing-file"; return; }
    grep -qF "$PATH_BEGIN" "$file" || { echo "absent"; return; }
    kind="$(path_file_kind "$file")"
    block="$(path_block_content "$kind")"
    current="$(sed -n "/$(printf '%s' "$PATH_BEGIN" | sed 's/[][\.*^$]/\\&/g')/,/$(printf '%s' "$PATH_END" | sed 's/[][\.*^$]/\\&/g')/p" "$file")"
    if [ "$current" = "$block" ]; then echo "identical"; else echo "different"; fi
}

# طبّق الكتلة على ملف واحد ذريًا (ملف مؤقت + mv) عبر python3.
# يطبع: added | replaced | identical | failed.
path_apply_file() {
    local file="$1" kind block tmpdir tmpfile
    kind="$(path_file_kind "$file")"
    block="$(path_block_content "$kind")"
    tmpdir="$(dirname "$file")"
    mkdir -p "$tmpdir" 2>/dev/null || { echo "failed"; return; }
    tmpfile="$(mktemp "$tmpdir/.qisas-path.XXXXXX" 2>/dev/null)" || { echo "failed"; return; }
    PATH_BLOCK="$block" python3 - "$file" "$tmpfile" <<'PYEOF' 2>/dev/null
import os, sys
path, tmp = sys.argv[1], sys.argv[2]
block = os.environ["PATH_BLOCK"]
begin = "# >>> qisas-studio >>>"
end = "# <<< qisas-studio <<<"
try:
    with open(path, encoding="utf-8") as f:
        text = f.read()
except FileNotFoundError:
    text = ""
except OSError:
    print("failed")
    sys.exit(0)
if begin in text and end in text:
    before, rest = text.split(begin, 1)
    _old, after = rest.split(end, 1)
    new = before + block + after
    status = "replaced" if (before + block + after) != text else "identical"
    if status == "identical":
        print("identical")
        sys.exit(0)
else:
    new = text if (not text or text.endswith("\n")) else text + "\n"
    new = new + block + "\n"
    status = "added"
try:
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
    print(status)
except OSError:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    print("failed")
PYEOF
    rm -f "$tmpfile" 2>/dev/null
}

# احذف الكتلة من ملف واحد ذريًا. يطبع: removed | absent | failed.
path_remove_file() {
    local file="$1" tmpdir tmpfile
    [ -f "$file" ] || { echo "absent"; return; }
    grep -qF "$PATH_BEGIN" "$file" || { echo "absent"; return; }
    tmpdir="$(dirname "$file")"
    tmpfile="$(mktemp "$tmpdir/.qisas-path.XXXXXX" 2>/dev/null)" || { echo "failed"; return; }
    python3 - "$file" "$tmpfile" <<'PYEOF' 2>/dev/null
import os, sys
path, tmp = sys.argv[1], sys.argv[2]
begin = "# >>> qisas-studio >>>"
end = "# <<< qisas-studio <<<"
try:
    with open(path, encoding="utf-8") as f:
        text = f.read()
except OSError:
    print("failed")
    sys.exit(0)
if begin not in text or end not in text:
    print("absent")
    sys.exit(0)
before, rest = text.split(begin, 1)
_old, after = rest.split(end, 1)
new = before.rstrip("\n") + ("\n" if before.strip() and after.strip() else "") + after.lstrip("\n")
if text.endswith("\n") and new and not new.endswith("\n"):
    new += "\n"
try:
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, path)
    print("removed")
except OSError:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    print("failed")
PYEOF
    rm -f "$tmpfile" 2>/dev/null
}

# تحقق من shell جديدة أن الكتلة تعمل (نمط AlphaCLI).
# يطلق shell نظيفة (بيئة فارغة، PATH أدنى) ويسألها عن المجلدين
# وعن أدوات studio؛ ويحذّر إن وجد ثنائيًا آخر يفوز على أداة في
# مجلدي studio. يرجع 0 إن كان المجلدان على PATH في shell
# الدخول أو التفاعلية، وإلا 1. يطبع سطور [PASS]/[WARN].
path_verify_fresh_shell() {
    local shell_bin probe out login_out inter_out ok=0
    case "${SHELL:-/bin/bash}" in
        *fish*) shell_bin="fish" ;;
        *zsh*) shell_bin="zsh" ;;
        *) shell_bin="bash" ;;
    esac
    command -v "$shell_bin" >/dev/null 2>&1 || {
        warn "لا يمكن التحقق من shell جديدة ($shell_bin غائب)"
        return 0
    }
    if [ "$shell_bin" = "fish" ]; then
        probe='for d in $HOME/.local/bin $HOME/.npm-global/bin; if contains $d $PATH; echo "PATH-OK $d"; else; echo "PATH-MISS $d"; end; end; for t in ffmpeg ffprobe yt-dlp omniroute piper melt; if command -v $t >/dev/null; echo "FOUND $t "(command -v $t); end; end'
        login_out="$(env -i HOME="$HOME" PATH=/usr/bin:/bin "$shell_bin" -l -c "$probe" 2>/dev/null)"
        inter_out="$(env -i HOME="$HOME" PATH=/usr/bin:/bin "$shell_bin" -c "$probe" 2>/dev/null)"
    else
        probe='for d in "$HOME/.local/bin" "$HOME/.npm-global/bin"; do case ":$PATH:" in *":$d:"*) echo "PATH-OK $d";; *) echo "PATH-MISS $d";; esac; done; for t in ffmpeg ffprobe yt-dlp omniroute piper melt; do p=$(command -v "$t" 2>/dev/null); [ -n "$p" ] && echo "FOUND $t $p"; done'
        login_out="$(env -i HOME="$HOME" PATH=/usr/bin:/bin "$shell_bin" --login -c "$probe" 2>/dev/null)"
        inter_out="$(env -i HOME="$HOME" PATH=/usr/bin:/bin "$shell_bin" -i -c "$probe" 2>/dev/null)"
    fi
    out="$login_out
$inter_out"
    for d in "$HOME/.local/bin" "$HOME/.npm-global/bin"; do
        if printf '%s\n' "$out" | grep -qF "PATH-OK $d"; then
            pass "shell جديدة ترى $d على PATH"
            ok=1
        else
            warn "shell جديدة لا ترى $d على PATH — افتح shell جديدة وتحقق"
        fi
    done
    # تحذير الظل: أداة موجودة في مجلدي studio لكن ثنائيًا آخر يفوز.
    printf '%s\n' "$out" | grep "^FOUND " | while read -r _ tool path; do
        case "$path" in
            "$HOME/.local/bin/"*|"$HOME/.npm-global/bin/"*) ;;
            *)
                for d in "$HOME/.local/bin" "$HOME/.npm-global/bin"; do
                    if [ -x "$d/$tool" ]; then
                        warn "ثنائي آخر يفوز على $tool: $path يتقدم على $d/$tool — راجع ترتيب PATH"
                        break
                    fi
                done
                ;;
        esac
    done
    [ "$ok" -eq 1 ]
}

path_dry_run() {
    echo "== معاينة تغييرات PATH (بلا كتابة) =="
    echo "الملفات (حسب SHELL=$SHELL):"
    for f in $(path_rc_files); do
        local st kind
        st="$(path_status_file "$f")"
        kind="$(path_file_kind "$f")"
        echo ""
        echo "-- $f — الحالة: $st"
        case "$st" in
            identical) echo "   الكتلة موجودة مطابقة — لا تغيير." ;;
            different) echo "   الكتلة موجودة مختلفة — ستُستبدل في مكانها:" ;;
            *) echo "   ستُضاف هذه الكتلة في نهاية الملف:" ;;
        esac
        if [ "$st" != "identical" ]; then
            path_block_content "$kind" | sed 's/^/   /'
        fi
    done
    echo ""
    echo "للتراجع لاحقًا: bash setup.sh --remove-path"
}

path_apply_all() {
    local all_ok=1 f st
    for f in $(path_rc_files); do
        st="$(path_apply_file "$f")"
        case "$st" in
            added) pass "أُضيفت كتلة PATH إلى $f" ;;
            replaced) pass "استُبدلت كتلة PATH في $f (بلا تكرار)" ;;
            identical) pass "كتلة PATH موجودة مطابقة في $f" ;;
            *) warn "تعذّر كتابة كتلة PATH في $f"; all_ok=0 ;;
        esac
    done
    [ "$all_ok" -eq 1 ]
}

path_remove_all() {
    local f st
    for f in $(path_rc_files); do
        st="$(path_remove_file "$f")"
        case "$st" in
            removed) pass "حُذفت كتلة PATH من $f" ;;
            absent) echo "[INFO] لا كتلة PATH في $f" ;;
            *) warn "تعذّر حذف كتلة PATH من $f" ;;
        esac
    done
}

# أدوات طباعة مشتركة (قبل main() — تُستدعى من أوضاع PATH المستقلة أيضًا).
step() { echo ""; echo "== [$1/7] $2 =="; }
pass() { echo "[PASS] $1"; }
warn() { echo "[WARN] $1"; }
fail() { echo "[FAIL] $1"; }
would() { echo "[DRY-RUN] $1"; }

main() {
cd "$(dirname "$0")" || exit 1
ROOT="$PWD"

DRY_RUN=0
CHECK=0
WITH_HEAVY=""
FULL=0
NO_PATH=0
PATH_ONLY=0
PATH_DRY_RUN=0
REMOVE_PATH=0

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --check) CHECK=1 ;;
        --full) FULL=1 ;;
        --no-path) NO_PATH=1 ;;
        --path-only) PATH_ONLY=1 ;;
        --path-dry-run) PATH_DRY_RUN=1 ;;
        --remove-path) REMOVE_PATH=1 ;;
        --with)
            shift
            [ $# -gt 0 ] || { echo "خطأ: --with يحتاج قائمة (whisper,moviepy,all)" >&2; exit 2; }
            WITH_HEAVY="$1" ;;
        --with=*) WITH_HEAVY="${1#--with=}" ;;
        -h|--help) usage; exit 0 ;;
        *) echo "خطأ: وسيط غير معروف: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$PATH_ONLY" -eq 1 ] && [ "$NO_PATH" -eq 1 ]; then
    echo "خطأ: --path-only يتعارض مع --no-path" >&2
    exit 2
fi

# أوضاع PATH المستقلة (قبل أي خطوة تثبيت).
if [ "$PATH_DRY_RUN" -eq 1 ]; then
    path_dry_run
    exit 0
fi
if [ "$REMOVE_PATH" -eq 1 ]; then
    path_remove_all
    exit 0
fi
if [ "$PATH_ONLY" -eq 1 ]; then
    echo "== كتلة PATH فقط =="
    if path_apply_all && path_verify_fresh_shell; then
        echo "كتلة PATH جاهزة ومُتحقق منها في shell جديدة."
        exit 0
    else
        echo "كتلة PATH طُبقت بتحذيرات — راجع السطور أعلاه."
        exit 1
    fi
fi

[ "$FULL" -eq 1 ] && WITH_HEAVY="all"

# ما طُلب من الثقيلتين مقدمًا (يُحسب مبكرًا لفحص مساحة القرص).
HEAVY_WANT=""
case ",$WITH_HEAVY," in
    *,all,*) HEAVY_WANT="whisper moviepy" ;;
    *,whisper,*) HEAVY_WANT="$HEAVY_WANT whisper" ;;
esac
case ",$WITH_HEAVY," in
    *,all,*) : ;;
    *,moviepy,*) HEAVY_WANT="$HEAVY_WANT moviepy" ;;
esac
if [ -n "$WITH_HEAVY" ] && [ "$WITH_HEAVY" != "all" ] && [ -z "$HEAVY_WANT" ]; then
    echo "خطأ: --with يقبل whisper أو moviepy أو all (وصل: $WITH_HEAVY)" >&2
    exit 2
fi

CORE_OK=1

echo "== تثبيت studio — أمر واحد (v0.1.41) =="
echo "المجلد: $ROOT"
[ "$DRY_RUN" -eq 1 ] && echo "الوضع: جاف — عرض فقط، بلا تنفيذ."
[ "$CHECK" -eq 1 ] && echo "الوضع: فحص فقط — بلا تثبيت."

# ---------- [1/7] python3 ----------
step 1 "بايثون"
if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 غير موجود — ثبّته أولًا: sudo apt-get install -y python3 python3-venv"
    CORE_OK=0
else
    PY_VER="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null)"
    echo "python3 موجود: $PY_VER"
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        pass "python3 $PY_VER (‏3.10+‏)"
    else
        fail "python3 $PY_VER أقدم من 3.10 — حدّث بايثون أولًا"
        CORE_OK=0
    fi
    if [ "$DRY_RUN" -eq 0 ] && [ "$CHECK" -eq 0 ]; then
        if python3 -m venv --help >/dev/null 2>&1; then
            pass "إنشاء البيئات متاح (python3-venv)"
        else
            warn "python3-venv غائب — سيُثبَّت في الخطوة 2 أو يدوًا: sudo apt-get install -y python3-venv"
        fi
    fi
fi

# ---------- [2/7] حزم النظام ----------
step 2 "حزم النظام (ffmpeg وffprobe وfontconfig وخط عربي)"
SYS_MISSING=""
for t in ffmpeg ffprobe fc-list; do
    if command -v "$t" >/dev/null 2>&1; then
        pass "$t موجود"
    else
        SYS_MISSING="$SYS_MISSING $t"
    fi
done
if command -v fc-list >/dev/null 2>&1; then
    if fc-list :lang=ar 2>/dev/null | grep -q .; then
        pass "خط عربي موجود (fc-list :lang=ar)"
    else
        warn "لا خط عربي (fc-list :lang=ar فارغ) — يلزم fonts-noto-core"
        SYS_MISSING="$SYS_MISSING fonts-noto-core"
    fi
fi
APT_PKGS=""
case "$SYS_MISSING" in
    *ffmpeg*|*ffprobe*) APT_PKGS="$APT_PKGS ffmpeg" ;;
esac
case "$SYS_MISSING" in
    *fc-list*|*fonts-noto-core*) APT_PKGS="$APT_PKGS fontconfig fonts-noto-core" ;;
esac
if [ -z "$APT_PKGS" ] && [ -z "$SYS_MISSING" ]; then
    pass "كل حزم النظام الأساسية موجودة"
elif [ "$DRY_RUN" -eq 1 ]; then
    would "تثبيت حزم النظام الغائبة: sudo apt-get install -y$APT_PKGS"
elif [ "$CHECK" -eq 1 ]; then
    fail "حزم نظام غائبة:$SYS_MISSING — ثبّتها: sudo apt-get install -y$APT_PKGS"
    CORE_OK=0
else
    if [ "${STUDIO_SETUP_NO_APT:-0}" = "1" ]; then
        warn "حزم نظام غائبة:$SYS_MISSING — التثبيت التلقائي معطّل (STUDIO_SETUP_NO_APT=1)"
        echo "       ثبّتها يدويًا: sudo apt-get install -y$APT_PKGS"
    elif sudo -n true 2>/dev/null; then
        echo "تثبيت حزم النظام الغائبة عبر sudo بلا كلمة سر…"
        if sudo -n apt-get install -y $APT_PKGS >/dev/null 2>&1; then
            pass "حزم النظام اكتملت"
        else
            warn "تعذّر التثبيت التلقائي — ثبّتها يدويًا: sudo apt-get install -y$APT_PKGS"
        fi
    else
        warn "حزم نظام غائبة:$SYS_MISSING — بلا sudo بلا كلمة سر"
        echo "       ثبّتها يدويًا: sudo apt-get install -y$APT_PKGS"
    fi
fi

# ---------- [3/7] البيئة الخفيفة المشتركة ----------
step 3 "البيئة الخفيفة المشتركة (تسكن في .venv-youtube)"
# فحص مساحة القرص أولًا: تثبيت مقطوع بقرص ممتلئ يترك بيانات
# تالفة (كُشف في sandbox ‏2026-11-23: ‎/tmp ‏512M امتلأ).
NEED_MB=250
[ -n "$HEAVY_WANT" ] && NEED_MB=997
FREE_MB="$(python3 -c 'import os,sys; print(os.statvfs(".").f_bavail * os.statvfs(".").f_frsize // (1024*1024))' 2>/dev/null || echo -1)"
if [ "$DRY_RUN" -eq 0 ] && [ "$CHECK" -eq 0 ] && [ "$FREE_MB" -ge 0 ] && [ "$FREE_MB" -lt "$NEED_MB" ]; then
    fail "مساحة قرص حرة ${FREE_MB}M فقط — يلزم ~${NEED_MB}M — حرّر مساحة ثم أعد التشغيل"
    CORE_OK=0
elif [ "$DRY_RUN" -eq 1 ]; then
    would "إنشاء .venv-youtube كبيئة مشتركة وتثبيت gtts + google-api-python-client + auto-editor"
    would "إنشاء روابط رمزية: .venv-gtts و.venv-autoeditor -> .venv-youtube (إن غابت البيئات القديمة)"
    would "التحقق SHA-256 من الملفات المثبّتة (python3 -m lib.ensure_env verify --shared)"
    python3 -m lib.ensure_env check 2>/dev/null || true
elif [ "$CHECK" -eq 1 ]; then
    python3 -m lib.ensure_env check
    if [ $? -ne 0 ]; then
        fail "البيئة الخفيفة غير مكتملة — شغّل setup.sh (بلا --check)"
        CORE_OK=0
    elif ! python3 -m lib.ensure_env verify --shared; then
        fail "تحقق SHA-256 فشل — البيئة الخفيفة تالفة، أعد التثبيت"
        CORE_OK=0
    fi
else
    if python3 -m lib.ensure_env install --shared \
            && python3 -m lib.ensure_env verify --shared; then
        pass "البيئة الخفيفة المشتركة جاهزة (.venv-youtube) — وتحقّق SHA-256 ناجح"
    else
        fail "تعذّر إكمال البيئة الخفيفة أو فشل تحقق SHA-256 — راجع سطور [FAIL] أعلاه"
        CORE_OK=0
    fi
fi

# ---------- [4/7] البيئتان الثقيلتان (كسولتان افتراضيًا) ----------
step 4 "البيئتان الثقيلتان — التثبيت الكسول (whisper ‏~478M وmoviepy ‏~269M)"
if [ "$DRY_RUN" -eq 1 ]; then
    if [ -n "$HEAVY_WANT" ]; then
        would "تثبيت البيئات الثقيلة مقدمًا: $HEAVY_WANT"
    else
        would "تخطَّ الثقيلتين (كسولتان — تُثبَّتان عند أول استخدام لأمرهما)"
    fi
elif [ "$CHECK" -eq 1 ]; then
    for t in whisper moviepy; do
        if [ -x ".venv-$t/bin/python" ]; then
            mod="faster_whisper"
            [ "$t" = "moviepy" ] && mod="moviepy"
            if ".venv-$t/bin/python" -c "import $mod" 2>/dev/null; then
                pass "$t مثبّت"
            else
                echo "[LAZY] $t موجود لكن الاستيراد يفشل — يُعاد تثبيته عند أول استخدام"
            fi
        else
            echo "[LAZY] $t غير مثبّت — يُثبَّت تلقائيًا عند أول استخدام (لا يمنع التثبيت)"
        fi
    done
elif [ -n "$HEAVY_WANT" ]; then
    # shellcheck disable=SC2086
    if python3 -m lib.ensure_env install $HEAVY_WANT \
            && python3 -m lib.ensure_env verify $HEAVY_WANT; then
        pass "البيئات الثقيلة المطلوبة جاهزة: $HEAVY_WANT — وتحقّق SHA-256 ناجح"
    else
        fail "تعذّر تثبيت بعض البيئات الثقيلة أو فشل تحقق SHA-256 — راجع سطور [FAIL] أعلاه"
        CORE_OK=0
    fi
else
    echo "[LAZY] whisper وmoviepy غير مثبّتتين مقدمًا — تُثبَّتان عند"
    echo "       أول استخدام لأمرهما (python3 -m lib.ensure_env install whisper|moviepy)"
    echo "       أو مقدمًا بـ: bash setup.sh --with whisper,moviepy"
fi

# ---------- [5/7] خادم الذكاء المحلي (قراءة فقط) ----------
step 5 "خادم الذكاء المحلي (فحص فقط)"
if ! command -v omniroute >/dev/null 2>&1; then
    warn "أمر omniroute غائب — سلسلة الذكاء تعمل بساق Gemini فقط حتى يُثبَّت"
    echo "       (يُثبَّت عبر سكربت استعادة البيئة: bash ~/workspace/setup-env.sh)"
elif [ "$DRY_RUN" -eq 1 ]; then
    would "فحص خادم الذكاء على 127.0.0.1:20128 (قراءة فقط)"
elif python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:20128/api/health', timeout=2)" >/dev/null 2>&1; then
    pass "خادم الذكاء يرد على 127.0.0.1:20128"
else
    warn "خادم الذكاء متوقف — يبدأ تلقائيًا عند أول أمر studio يحتاجه"
fi

# ---------- [6/7] doctor ----------
step 6 "فحص doctor الكامل"
if [ "$DRY_RUN" -eq 1 ]; then
    would "تشغيل: python3 studio.py doctor --fix"
elif [ "$CHECK" -eq 1 ]; then
    if [ -f studio.py ]; then
        python3 studio.py doctor || CORE_OK=0
    else
        warn "studio.py غائب في هذا المجلد — فحص doctor متخطَّى"
    fi
else
    if [ -f studio.py ]; then
        if python3 studio.py doctor --fix; then
            pass "doctor اكتمل"
        else
            fail "doctor أبلغ فشلًا — أصلح سطور [FAIL] أعلاه ثم أعد تشغيل setup.sh"
            CORE_OK=0
        fi
    else
        warn "studio.py غائب في هذا المجلد — فحص doctor متخطَّى"
    fi
fi

# ---------- [7/7] كتلة PATH المعلَّمة + تحقق shell جديدة ----------
step 7 "كتلة PATH في ملفات بدء التشغيل"
if [ "$DRY_RUN" -eq 1 ]; then
    would "إضافة كتلة PATH المعلَّمة (# >>> qisas-studio >>>) إلى ملفات بدء التشغيل"
    would "التحقق من shell جديدة أن المجلدين على PATH"
elif [ "$CHECK" -eq 1 ]; then
    for f in $(path_rc_files); do
        case "$(path_status_file "$f")" in
            identical) pass "كتلة PATH موجودة في $f" ;;
            different) warn "كتلة PATH في $f مختلفة — ستُستبدل عند إعادة التثبيت" ;;
            *) warn "كتلة PATH غائبة في $f — ستُضاف عند التثبيت (أو جرّب --path-only)" ;;
        esac
    done
    path_verify_fresh_shell || true
elif [ "$NO_PATH" -eq 1 ]; then
    echo "[INFO] خطوة PATH متخطَّاة (--no-path) — أضف المجلدين يدويًا أو بـ --path-only"
else
    if ! path_apply_all; then
        warn "تعذّرت كتابة كتلة PATH — أكمل التثبيت بلا PATH دائم (جرّب --path-only لاحقًا)"
    fi
    path_verify_fresh_shell || true
fi

# ---------- ملخص ----------
echo ""
echo "== الملخص =="
if [ -d .venv-youtube ]; then
    du -sh .venv-youtube 2>/dev/null | sed 's/^/[INFO] .venv-youtube (مشتركة): /'
fi
for v in .venv-whisper .venv-moviepy; do
    if [ -d "$v" ]; then
        du -sh "$v" 2>/dev/null | sed "s|^|[INFO] $v: |"
    fi
done
if [ "$DRY_RUN" -eq 1 ]; then
    echo "وضع جاف — لم يُنفَّذ شيء."
    exit 0
fi
if [ "$CHECK" -eq 1 ]; then
    if [ "$CORE_OK" -eq 1 ]; then
        echo "الفحص: النظام جاهز."
        exit 0
    else
        echo "الفحص: شيء أساسي غائب — شغّل: bash setup.sh"
        exit 1
    fi
fi
if [ "$CORE_OK" -eq 1 ]; then
    echo "التثبيت اكتمل — النظام جاهز."
    echo "جرّب الآن:  python3 studio.py run --demo"
    echo "الثقيلتان كسولتان: تُثبَّتان عند أول استخدام، أو بـ bash setup.sh --with whisper,moviepy"
    [ "$NO_PATH" -eq 0 ] && echo "افتح shell جديدة لتسري كتلة PATH (أو: source ~/.bashrc)"
    exit 0
else
    echo "التثبيت غير مكتمل — أصلح سطور [FAIL] أعلاه ثم أعد تشغيل setup.sh."
    echo "(إعادة التشغيل آمنة: لا يعيد ما اكتمل.)"
    exit 1
fi
}

# السطر الأخير وحده يستدعي main — سكربت مقطوع التنزيل لا ينفّذ شيئًا.
main "$@"
