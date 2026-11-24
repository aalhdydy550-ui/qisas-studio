#!/bin/bash
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
# ensure-env.sh — حارس بيئة studio بعد إعادة تشغيل الـVM (إصلاح دائم 2026-11-21)
#
# المشكلة: بعد كل ريستارت تُمسح حزم apt في /usr (أدوات الحماية الست + قاعدة
# ClamAV) وروابط /usr/local/bin وملف خدمة systemd في /etc، بينما ينجو الـhome.
# وكان الإصلاح يدويًا (تشغيل سكربتين) أو معتمدًا على دخول تفاعلي فقط، فبقيت
# أدوات الحماية غائبة حتى بعد استعادة studio.
#
# هذا الحارس يتحقق بصمت (أقل من ثانية إن كان كل شيء سليمًا) ويصلح تلقائيًا:
#  - ملف الخدمة الغائب: يُعاد نسخه + daemon-reload + enable فورًا (سريع).
#  - خادم OmniRoute المتوقف: يُشغَّل على loopback فورًا (سريع، بلا انتظار).
#  - روابط /usr/local/bin الغائبة: تُعاد عبر setup-env.sh (كانت تُفحص
#    بـ`command -v` فقط، فيراها الحارس «موجودة» ما دام ثنائي الـhome
#    على PATH رغم غياب الرابط — عيب وُجد 2026-11-22).
#  - أي إصلاح بطيء (تثبيت أدوات apt، قاعدة ClamAV، روابط الأدوات): يُطلق
#    في الخلفية منفصلًا بلا حظر للمتصل، مع قفل flock واحد يمنع إصلاحين
#    متزامنين، وانتظار قفل apt إن كان مشغولًا.
# آمن عند الاستدعاء المتكرر (idempotent)، ولا يفشل المتصل أبدًا.
#
# الربط: ~/.bashrc و~/.profile (عند الدخول) + studio.py (عند كل تشغيل،
# بوضع --apt-only من _ensure_protection_tools) — فلا خطوة يدوية بعد أي ريستارت.
# الاستخدام:
#   bash ~/workspace/ensure-env.sh            # فحص كامل + إصلاح
#   bash ~/workspace/ensure-env.sh --apt-only # أدوات الحماية + قاعدة ClamAV فقط
#   bash ~/workspace/ensure-env.sh --dry-run  # قراءة فقط: ما الغائب وما الذي كان سيُصلح
#
# --- الحد المتبقي (بصراحة، 2026-11-22) ---
# تثبيتات apt لا يمكن جعلها دائمة على هذه الـVM بتصميمها: كل ريستارت يعيد
# /usr و/etc إلى حالة صورة النظام (يُسجَّل ذلك في /var/lib/hatch/os-intent)،
# فتُمسح الحزم المثبتة بعد الصورة (أدوات الحماية الست + ffmpeg + غيرها) ومعها
# قاعدة ClamAV وروابط /usr/local/bin وملف الخدمة. لا يوجد مسار «ثبّت مرة
# واحدة وانتهى» — الحارس هو الحل: يعيد التثبيت تلقائيًا عند أول تشغيل بعد
# الريستارت. ما ينجو بطبيعته: كل شيء في الـhome (ثنائيات، venvs، إعدادات،
# بيانات studio). وما لا يعمل أصلًا في الـVM: fail2ban وufw مثبّتان لكن
# netfilter ممنوع فيهما — يُعاد تثبيتهما ليبقى الفحص أخضر، لا ليعملا.
# انظر التفصيل في ~/workspace/ensure-env-README.md.
#
# إصلاحات 2026-11-22 (حل مشكلة التثبيت بعد إعادة التشغيل):
#  1) حلقة انتظار قفل apt كانت عمياء: `flock -n` على /var/lib/dpkg/lock
#     ينجح حتى مع قفل fcntl حصري ممسوك (وهو ما يستخدمه apt فعليًا) — أُثبت
#     حيًا. صارت تنتظر بمسبار fcntl حقيقي (python3)، وإن بقي القفل مشغولًا
#     بعد دقيقتين يُؤجَّل الإصلاح (يُسجَّل ويُعاد عند الاستدعاء التالي) بدل
#     تشغيل apt في وجه قفل فيفشل.
#  2) فحص روابط /usr/local/bin صراحةً (هدف كل رابط مقابل ثنائي الـhome).
#  3) فحص fc-list (fontconfig) ومكتبتي بايثون النظاميتين yaml/PIL — بلا
#     تغطية إصلاح قبل ذلك.
#  4) سجل الإصلاح الخلفي انتقل من /tmp (يُمسح مع الريستارت فتضيع كل
#     أدلة التشخيص) إلى ~/workspace/ensure-env-bg.log مع تدوير (آخر 500 سطر).
set -u

HOME_DIR="$HOME"
WORKSPACE="$HOME_DIR/workspace"
UNIT_SRC="$WORKSPACE/studio-env-restore.service"
UNIT_DST="/etc/systemd/system/studio-env-restore.service"
SETUP_ENV="$WORKSPACE/setup-env.sh"
RESTORE_TOOLS="$WORKSPACE/restore-system-tools.sh"
UPDATE_DB="$WORKSPACE/update-clamav-db.sh"
PROTECT_DIR="$WORKSPACE/protection"
GITLEAKS_BIN="$PROTECT_DIR/bin/gitleaks"
RESTORE_GITLEAKS="$PROTECT_DIR/restore-gitleaks.sh"
PROTECT_SCRIPTS=(integrity.py perm-audit.py clamav-scan.sh)
BASELINE_FILE="$PROTECT_DIR/baseline.json"
LOG_FILE="$WORKSPACE/ensure-env.log"
BG_LOG="$WORKSPACE/ensure-env-bg.log"
APT_LOCKS=(/var/lib/dpkg/lock /var/lib/dpkg/lock-frontend)

DRY_RUN=0
APT_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        --apt-only) APT_ONLY=1 ;;
    esac
done

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo -n"; fi

log() { # log <msg> — يسجل في ملف الـhome فقط عند اتخاذ إجراء فعلي
    if [ "$DRY_RUN" -eq 0 ]; then
        printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG_FILE"
    fi
}

say() { # say <msg> — للتجربة فقط
    if [ "$DRY_RUN" -eq 1 ]; then printf '%s\n' "$*"; fi
}

# تدوير السجلات (آخر 500 سطر) إن تجاوزت 1000 سطر — حتى لا تنمو بلا حد.
for _log in "$LOG_FILE" "$BG_LOG"; do
    if [ -f "$_log" ] && [ "$(wc -l < "$_log")" -gt 1000 ]; then
        # L9: تدوير عبر mktemp — ملف .tmp متوقع في نفس المجلد كان قابلًا
        # للاستبدال برابط رمزي قبل الكتابة.
        _tmp="$(mktemp "$(dirname "$_log")/.$(basename "$_log").XXXXXX")" \
            && tail -n 500 "$_log" > "$_tmp" && mv "$_tmp" "$_log"
    fi
done
#  5) فحوصات أدوات الحماية المنزلية (جولة حماية 2026-11-22): gitleaks
#     (ثنائي في ~/workspace/protection/bin) + سكربتات الحماية الثلاثة
#     + أساس السلامة baseline.json — تُفحص في كل استدعاء؛ غياب gitleaks
#     يُصلح خلفيًا عبر restore-gitleaks.sh، وغياب سكربت أو أساس يُسجَّل
#     تحذيرًا فقط (لا يمكن توليدهما تلقائيًا من العدم).
# ترحيل لمرة واحدة: سجل الخلفية القديم في /tmp (قبل 2026-11-22) إلى موضعه
# الجديد في الـworkspace إن وُجد ولم يكن الجديد موجودًا بعد.
if [ ! -f "$BG_LOG" ] && [ -f /tmp/ensure-env-bg.log ] && [ ! -L /tmp/ensure-env-bg.log ]; then
    cp /tmp/ensure-env-bg.log "$BG_LOG" 2>/dev/null || true
fi

apt_lock_held() { # apt_lock_held — هل قفل apt مشغول الآن؟ (0=مشغول، 1=حر)
    # مسبار fcntl حقيقي: apt/dpkg يقفلان بـfcntl (POSIX)، لا بـflock —
    # وflock على نفس الملف لا يرى قفل fcntl إطلاقًا (أُثبت حيًا 2026-11-22).
    local f
    for f in "${APT_LOCKS[@]}"; do
        [ -e "$f" ] || continue
        if command -v python3 >/dev/null 2>&1; then
            if python3 -c 'import fcntl, sys
try:
    fh = open(sys.argv[1], "r+")
except OSError:
    fh = open(sys.argv[1], "r")
try:
    fcntl.lockf(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(0)
sys.exit(1)' "$f" 2>/dev/null; then
                return 0
            fi
        elif command -v fuser >/dev/null 2>&1; then
            if fuser -s "$f" 2>/dev/null; then return 0; fi
        fi
    done
    return 1
}

# H2: عنوان ربط خادم OmniRoute الفعلي من /proc/net/tcp[6] — فحص ما بعد
# الإقلاع (كما يفعل studio.py). يعيد 127.0.0.1 أو ::1 أو عنوانًا آخر أو
# فارغًا إن لم يكن الخادم يستمع.
omniroute_bind_address() {
    local f line local_addr addr port ip
    for f in /proc/net/tcp /proc/net/tcp6; do
        [ -r "$f" ] || continue
        while read -r line; do
            set -- $line
            [ "$#" -ge 4 ] || continue
            local_addr="$2"
            addr="${local_addr%:*}"; port="${local_addr##*:}"
            # Skip the /proc header line (local_address) and any non-hex
            # port before the base-16 arithmetic — it would abort the
            # expansion with "value too great for base".
            case "$port" in *[!0-9A-Fa-f]*) continue ;; esac
            [ "$((16#$port))" -eq 20128 ] 2>/dev/null || continue
            [ "$4" = "0A" ] || continue
            if [ "$f" = /proc/net/tcp ]; then
                ip="$((16#${addr:6:2})).$((16#${addr:4:2})).$((16#${addr:2:2})).$((16#${addr:0:2}))"
            elif [ "$addr" = "00000000000000000000000001000000" ]; then
                ip="::1"
            else
                ip="[$addr]"
            fi
            echo "$ip"
            return 0
        done < "$f"
    done
    echo ""
}

HOME_TOOLS=(ffmpeg melt yt-dlp omniroute ollama piper zstd)
APT_TOOLS=(lynis clamscan rkhunter chkrootkit fail2ban-client ufw)
# روابط /usr/local/bin المتوقعة: الأداة -> هدفها في الـhome.
# (ffmpeg ثنائي apt في /usr/bin فلا رابط له هنا.)
LINK_TOOLS=(melt yt-dlp omniroute ollama piper zstd)

link_target() { # link_target <tool> — الهدف المتوقع لرابط الأداة
    case "$1" in
        # melt: نسخة apt أولًا (عيب 2026-11-22: نسخة ~/opt/mlt
        # المنزلية مكسورة بعد الريستارت — مكتبات نظامها ممسوحة)؛
        # والمنزلية بديل فقط إن غابت apt.
        melt) if [ -x /usr/bin/melt ]; then echo "/usr/bin/melt"; else echo "$HOME_DIR/opt/mlt/bin/melt"; fi ;;
        yt-dlp) echo "$HOME_DIR/.local/bin/yt-dlp" ;;
        omniroute) echo "$HOME_DIR/.npm-global/bin/omniroute" ;;
        ollama) echo "$HOME_DIR/opt/ollama/bin/ollama" ;;
        piper) echo "$HOME_DIR/.local/bin/piper" ;;
        zstd) echo "$HOME_DIR/.local/bin/zstd" ;;
    esac
}

missing_home=()
missing_links=()
missing_apt=()
db_missing=0
unit_missing=0
server_down=0
py_missing=0
fclist_missing=0

if [ "$APT_ONLY" -eq 0 ]; then
    # 1) ملف الخدمة
    if [ ! -f "$UNIT_DST" ] || ! cmp -s "$UNIT_SRC" "$UNIT_DST" 2>/dev/null; then
        unit_missing=1
    fi
    # 2) روابط أدوات الـhome + وجود الأدوات نفسها
    for t in "${HOME_TOOLS[@]}"; do
        command -v "$t" >/dev/null 2>&1 || missing_home+=("$t")
    done
    for t in "${LINK_TOOLS[@]}"; do
        if [ ! -L "/usr/local/bin/$t" ] \
            || [ "$(readlink "/usr/local/bin/$t" 2>/dev/null)" != "$(link_target "$t")" ]; then
            missing_links+=("$t")
        fi
    done
    # 2ب) fc-list (fontconfig — حزمة apt تُمسح مع الريستارت)
    command -v fc-list >/dev/null 2>&1 || fclist_missing=1
    # 2ج) مكتبتا بايثون النظاميتان PyYAML وPillow (حزمتا apt)
    python3 -c "import yaml, PIL" 2>/dev/null || py_missing=1
    # 5) خادم OmniRoute (فقط إن كان الثنائي موجودًا)
    if command -v omniroute >/dev/null 2>&1; then
        curl -sf --max-time 2 http://127.0.0.1:20128/api/health >/dev/null 2>&1 \
            || server_down=1
    fi
fi

# 3) أدوات حماية apt
for t in "${APT_TOOLS[@]}"; do
    command -v "$t" >/dev/null 2>&1 || missing_apt+=("$t")
done
# 4) قاعدة بيانات ClamAV — فحص كل نمط على حدة: glob بلا مطابقات يبقى
# نصًا حرفيًا في bash، فيفشل `ls نمط1 نمط2` إن لم يطابق أحدهما (عيب
# وُجد 2026-11-21: قاعدة موجودة بصيغة .cvd فقط قُرئت «غائبة» لأن
# ‎*.cld بلا مطابقات فأفشل ls كله).
db_missing=1
for db in /var/lib/clamav/*.cvd /var/lib/clamav/*.cld; do
    [ -e "$db" ] && { db_missing=0; break; }
done
# 4ب) أدوات الحماية المنزلية (جولة حماية 2026-11-22) — فحص سريع بلا شبكة:
# الثنائي في الـhome فينجو من الريستارت أصلًا؛ الفحص هنا يكشف الحذف
# العرضي أو التلف فقط.
gitleaks_missing=0
if [ ! -x "$GITLEAKS_BIN" ] || ! "$GITLEAKS_BIN" version >/dev/null 2>&1; then
    gitleaks_missing=1
fi
missing_protect_scripts=()
for _ps in "${PROTECT_SCRIPTS[@]}"; do
    # وجود الملف يكفي: الـ.py يُستدعى عبر python3 والـ.sh عبر bash.
    [ -f "$PROTECT_DIR/$_ps" ] || missing_protect_scripts+=("$_ps")
done
baseline_missing=0
[ -f "$BASELINE_FILE" ] || baseline_missing=1

if [ "$DRY_RUN" -eq 1 ]; then
    say "unit: $([ "$unit_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "home-tools missing: ${missing_home[*]:-none}"
    say "links missing: ${missing_links[*]:-none}"
    say "fc-list: $([ "$fclist_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "python-libs yaml/PIL: $([ "$py_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "apt-tools missing: ${missing_apt[*]:-none}"
    say "clamav-db: $([ "$db_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "gitleaks: $([ "$gitleaks_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "protect-scripts missing: ${missing_protect_scripts[*]:-none}"
    say "integrity-baseline: $([ "$baseline_missing" -eq 1 ] && echo MISSING || echo OK)"
    say "server: $([ "$server_down" -eq 1 ] && echo DOWN || echo OK)"
    [ "$unit_missing" -eq 1 ] && say "WOULD: restore unit file (sync)"
    { [ "${#missing_home[@]}" -gt 0 ] || [ "${#missing_links[@]}" -gt 0 ] \
        || [ "$fclist_missing" -eq 1 ] || [ "$py_missing" -eq 1 ]; } \
        && say "WOULD: run setup-env.sh (background)"
    [ "${#missing_apt[@]}" -gt 0 ] && say "WOULD: run restore-system-tools.sh (background)"
    [ "$db_missing" -eq 1 ] && [ "${#missing_apt[@]}" -eq 0 ] \
        && say "WOULD: run update-clamav-db.sh (background)"
    [ "$gitleaks_missing" -eq 1 ] && say "WOULD: run restore-gitleaks.sh (background)"
    [ "$server_down" -eq 1 ] && say "WOULD: start omniroute server (sync, loopback)"
    exit 0
fi

# --- إصلاح سريع متزامن: ملف الخدمة ---
if [ "$unit_missing" -eq 1 ] && [ -f "$UNIT_SRC" ]; then
    if $SUDO cp "$UNIT_SRC" "$UNIT_DST" 2>/dev/null; then
        $SUDO systemctl daemon-reload 2>/dev/null || true
        $SUDO systemctl enable studio-env-restore.service >/dev/null 2>&1 || true
        log "unit: أُعيد ملف الخدمة إلى /etc + enable"
    else
        log "unit: تحذير — تعذّر نسخ ملف الخدمة إلى /etc"
    fi
fi

# --- إصلاح سريع متزامن: خادم OmniRoute المتوقف ---
if [ "$server_down" -eq 1 ]; then
    # نفس أمر الإقلاع في setup-env.sh خطوة 10: loopback فقط + مفتاح إلزامي.
    # H2: المتغير الفعّال HOSTNAME (الحزمة تتجاهل OMNIROUTE_SERVER_HOST).
    REQUIRE_API_KEY=true HOSTNAME=127.0.0.1 OMNIROUTE_SERVER_HOST=127.0.0.1 \
        omniroute serve --no-open --daemon --port 20128 >/dev/null 2>&1 || true
    # H2: انتظر الصحة ثم أكّد الربط الفعلي — إقلاع ناجح على 0.0.0.0 كان
    # سيُسجَّل «أُعيد التشغيل» بلا أي تحذير.
    for i in $(seq 1 30); do
        curl -sf --max-time 2 http://127.0.0.1:20128/api/health >/dev/null 2>&1 && break
        sleep 1
    done
    _bind="$(omniroute_bind_address)"
    if [ "$_bind" = "127.0.0.1" ]; then
        log "server: أُعيد تشغيل خادم OmniRoute على 127.0.0.1:20128 (الربط مؤكد: $_bind)"
    elif [ -n "$_bind" ]; then
        log "server: تحذير — خادم OmniRoute يربط $_bind وليس loopback فقط!"
    else
        log "server: أُعيد تشغيل خادم OmniRoute (تعذّر تأكيد الربط — الخادم لا يرد؟)"
    fi
fi

# --- تحذيرات متزامنة: سكربت حماية أو أساس سلامة غائب (لا إصلاح تلقائي) ---
if [ "${#missing_protect_scripts[@]}" -gt 0 ]; then
    log "protect: تحذير — سكربتات حماية غائبة: ${missing_protect_scripts[*]} (لا تُولَّد تلقائيًا)"
fi
if [ "$baseline_missing" -eq 1 ]; then
    log "protect: تحذير — أساس السلامة baseline.json غائب؛ أعد بناءه بـ integrity.py update على شجرة سليمة معروفة"
fi

# --- إصلاحات بطيئة في الخلفية (مرة واحدة تحت قفل واحد) ---
NEED=()
{ [ "${#missing_home[@]}" -gt 0 ] || [ "${#missing_links[@]}" -gt 0 ] \
    || [ "$fclist_missing" -eq 1 ] || [ "$py_missing" -eq 1 ]; } \
    && [ -f "$SETUP_ENV" ] && NEED+=("$SETUP_ENV")
[ "${#missing_apt[@]}" -gt 0 ] && [ -f "$RESTORE_TOOLS" ] && NEED+=("$RESTORE_TOOLS")
if [ "$db_missing" -eq 1 ] && [ "${#missing_apt[@]}" -eq 0 ] \
    && [ -f "$UPDATE_DB" ]; then
    NEED+=("$UPDATE_DB")  # restore-system-tools.sh يحدّث القاعدة أصلًا إن شُغّل
fi
[ "$gitleaks_missing" -eq 1 ] && [ -f "$RESTORE_GITLEAKS" ] && NEED+=("$RESTORE_GITLEAKS")

if [ "${#NEED[@]}" -gt 0 ]; then
    (
        _repair_lockdir="/tmp/ensure-env.lock.d"
        if ! mkdir "$_repair_lockdir" 2>/dev/null; then
            if [ -d "$_repair_lockdir" ] && [ -n "$(find "$_repair_lockdir" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
                rmdir "$_repair_lockdir" 2>/dev/null
                mkdir "$_repair_lockdir" 2>/dev/null || exit 0
            else
                exit 0
            fi
        fi
        chmod 700 "$_repair_lockdir" 2>/dev/null || true
        trap 'rmdir "$_repair_lockdir" 2>/dev/null' EXIT
        # السجل يُكتب هنا (بعد الفوز بالقفل) حتى لا يتكرر إن استُدعي الحارس مرتين
        log "repair: إطلاق إصلاح خلفي: ${NEED[*]} (أدوات home غائبة: ${missing_home[*]:-لا} | روابط غائبة: ${missing_links[*]:-لا} | fc-list: $([ "$fclist_missing" -eq 1 ] && echo غائب || echo موجود) | مكتبات بايثون: $([ "$py_missing" -eq 1 ] && echo غائبة || echo موجودة) | أدوات apt غائبة: ${missing_apt[*]:-لا} | قاعدة ClamAV: $([ "$db_missing" -eq 1 ] && echo غائبة || echo موجودة) | gitleaks: $([ "$gitleaks_missing" -eq 1 ] && echo غائب || echo موجود))"
        # انتظر قفل apt إن كان مشغولًا بإصلاح آخر (حتى دقيقتين) —
        # بمسبار fcntl حقيقي لا بـflock (انظر apt_lock_held). وإن بقي
        # مشغولًا بعد المهلة يُؤجَّل الإصلاح كله لهذه المرة (الاستدعاء
        # التالي يعيد المحاولة) بدل تشغيل apt في وجه قفل فيفشل.
        _waited=0
        while apt_lock_held && [ "$_waited" -lt 24 ]; do
            sleep 5
            _waited=$((_waited + 1))
        done
        if apt_lock_held; then
            log "repair: تأجيل — قفل apt ما زال مشغولًا بعد دقيقتين؛ سيُعاد الإصلاح عند الاستدعاء التالي"
            exit 0
        fi
        {
            echo "=== $(date '+%F %T') ensure-env background repair ==="
            for s in "${NEED[@]}"; do
                echo "--- $s ---"
                /bin/bash "$s" >> "$BG_LOG" 2>&1
                echo "--- exit $? ---"
            done
            echo "=== $(date '+%F %T') done ==="
        } >> "$BG_LOG" 2>&1
        # تدوير سجل الخلفية بعد كل إصلاح (آخر 500 سطر) — عبر mktemp (L9).
        if [ -f "$BG_LOG" ] && [ "$(wc -l < "$BG_LOG")" -gt 1000 ]; then
            _tmp="$(mktemp "$(dirname "$BG_LOG")/.$(basename "$BG_LOG").XXXXXX")" \
                && tail -n 500 "$BG_LOG" > "$_tmp" && mv "$_tmp" "$BG_LOG"
        fi
    ) &
    disown 2>/dev/null || true
fi

exit 0
