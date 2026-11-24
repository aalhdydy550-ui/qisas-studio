#!/bin/bash
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
# سكربت استعادة بيئة studio بعد إعادة تشغيل الـVM — إصدار 3
# كل الأدوات تعيش في الـhome؛ هذا السكربت يعيد الروابط في /usr/local/bin
# وحزم apt المفقودة فقط. آمن عند تشغيله مرتين (idempotent).
# يُشغَّل تلقائيًا عند الإقلاع عبر خدمة studio-env-restore.service،
# ويمكن تشغيله يدويًا: bash ~/workspace/setup-env.sh
# إصلاح ذاتي (v0.1.15): السكربت نفسه يعيد تثبيت ملف خدمة systemd
# من نسخة الـhome الاحتياطية إن غاب أو اختلف (خطوة 0)، وstudio.py
# يستدعي هذا السكربت تلقائيًا عند بدء التشغيل إن غابت أداة أو غاب
# ملف الخدمة، وخطاف شل خفيف في ~/.bashrc و~/.profile يعيد تثبيت
# الخدمة عند تسجيل الدخول التفاعلي — فلا خطوة يدوية أبدًا.
# (v0.1.16): خطوة 10 تتأكد أن خادم OmniRoute شغال على loopback،
# لأن أمر `chat` يحتاجه وإلا فشل بصمت.
# (2026-11-22): قفل تسلسل flock يمنع تشغيلين متزامنين؛ وإعادة محاولة
# apt؛ وضمان إعداد بروكسي apt وبديل بروكسي من /etc/environment؛ وشبكة
# أمان fontconfig وpython3-yaml وpython3-pil في الخطوة 8.
# (جولة حماية 2026-11-22): الخطوة 11 تثبّت gitleaks (ماسح أسرار، MIT)
# عبر ~/workspace/protection/restore-gitleaks.sh إن غاب ثنائيه.
set -u

HOME_BIN="$HOME/.local/bin"
NPM_GLOBAL="$HOME/.npm-global"
MLT_HOME="$HOME/opt/mlt"
UNIT_SRC="$HOME/workspace/studio-env-restore.service"
UNIT_DST="/etc/systemd/system/studio-env-restore.service"
if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo -n"; fi
NEED_APT_UPDATE=0

# تسلسل التشغيلات المتزامنة: تشغيلان متزامنان (كرونان متداخلان، أو
# studio.py + خدمة الإقلاع) كانا يشغّلان هذا السكربت معًا فيتصارعان
# على قفل apt وعلى npm. القفل هنا انتظار حاجب حتى 240 ثانية (ضمن
# مهلة studio.py البالغة 300 ثانية)؛ ومن تجاوز المهلة يتخطى بهدوء —
# الإصلاح الآخر يكمل العمل.
# L9: قفل دليل mkdir ذري (لا مسار /tmp متوقع ولا symlink قابل للاتباع —
# ملف قفل mktemp جديد في كل تشغيل كان سيقفل inode مختلفًا فلا يمنع أحدًا).
# دليل قديم أكثر من 30 دقيقة يُعدّ متقادمًا (تشغيل مقتول) فيُزال.
SETUP_LOCKDIR="/tmp/setup-env.lock.d"
_lock_waited=0
while ! mkdir "$SETUP_LOCKDIR" 2>/dev/null; do
    if [ -d "$SETUP_LOCKDIR" ] && [ -n "$(find "$SETUP_LOCKDIR" -maxdepth 0 -mmin +30 2>/dev/null)" ]; then
        rmdir "$SETUP_LOCKDIR" 2>/dev/null && continue
    fi
    if [ "$_lock_waited" -ge 240 ]; then
        echo "setup-env: إصلاح آخر قيد التشغيل منذ أكثر من 4 دقائق — يُتخطى"
        exit 0
    fi
    sleep 5
    _lock_waited=$((_lock_waited + 5))
done
chmod 700 "$SETUP_LOCKDIR" 2>/dev/null || true
trap 'rmdir "$SETUP_LOCKDIR" 2>/dev/null' EXIT

# بديل البروكسي: curl وnpm يحتاجان البروكسي، ومتغيرات البيئة قد تغيب
# في سياق خدمة systemd أو كرون. /etc/environment يحفظ البروكسي بلا
# بيانات اعتماد (يقبل الاتصال المحلي بلا مصادقة — أُثبت حيًا 2026-11-22).
if [ -z "${http_proxy:-}" ] && [ -f /etc/environment ]; then
    _env_proxy=$(sed -n 's/^\(export \)\?http_proxy=//p' /etc/environment 2>/dev/null | head -1)
    [ -n "$_env_proxy" ] || _env_proxy=$(sed -n 's/^\(export \)\?HTTP_PROXY=//p' /etc/environment 2>/dev/null | head -1)
    # L9: أزل زوج علامات اقتباس محيطة واحدًا فقط — tr -d '"' كان يحذف كل
    # علامة اقتباس داخل القيمة فيفسد كلمة سر فيها علامة اقتباس.
    case "$_env_proxy" in
        \"*) _env_proxy="${_env_proxy#\"}"; _env_proxy="${_env_proxy%\"}" ;;
        \'*) _env_proxy="${_env_proxy#\'}"; _env_proxy="${_env_proxy%\'}" ;;
    esac
    if [ -n "$_env_proxy" ]; then
        export http_proxy="$_env_proxy" https_proxy="$_env_proxy"
        export HTTP_PROXY="$_env_proxy" HTTPS_PROXY="$_env_proxy"
    fi
    unset _env_proxy
fi

link() { $SUDO ln -sf "$1" "/usr/local/bin/$2"; }

ensure_apt_proxy() { # إعداد بروكسي apt (في /etc فيُمسح مع الريستارت)
    local cfg="/etc/apt/apt.conf.d/80hatch-egress-proxy"
    if [ ! -f "$cfg" ] || ! grep -q "hatch-egress-proxy:3128" "$cfg" 2>/dev/null; then
        printf 'Acquire::http::Proxy "http://hatch-egress-proxy:3128";\nAcquire::https::Proxy "http://hatch-egress-proxy:3128";\n' \
            | $SUDO tee "$cfg" >/dev/null 2>&1 || true
    fi
}

apt_install() { # apt_install pkg... (إعادة حتى 3 مرات عند فشل القفل/الشبكة)
    local attempt=1
    while [ "$attempt" -le 3 ]; do
        if [ "$NEED_APT_UPDATE" -eq 0 ]; then
            ensure_apt_proxy
            $SUDO apt-get update -qq && NEED_APT_UPDATE=1
        fi
        if $SUDO apt-get install -y "$@"; then return 0; fi
        echo "apt_install: فشلت المحاولة $attempt/3 ($*) — إعادة بعد $((attempt * 10)) ثوانٍ" >&2
        sleep $((attempt * 10))
        attempt=$((attempt + 1))
    done
    return 1
}

# M7: تحقق من SHA256 منشور قبل استخدام أي ثنائي منزَّل — ملف المجاميع
# يُنزَّل مع الثنائي نفسه عبر TLS نفسه (يحمي من تنزيل مبتور/تالف، لا من
# خادم مخترق — وهذا هو المقصود بـ"SHA256 منشور"). أي فشل يحذف الثنائي
# فلا يُستخدم ولا يُربط، ويُعاد التنزيل عند التشغيل التالي.
verify_sha256() { # verify_sha256 <file> <sums-url> <basename-in-sums>
    local file="$1" sums_url="$2" name="$3" sums expected actual
    sums="$(mktemp)"
    if ! curl --fail --proto =https --max-redirs 3 --max-time 60 -sL -o "$sums" "$sums_url"; then
        echo "sha256    : تحذير — تعذّر تنزيل ملف المجاميع ($sums_url)؛ يُحذف الثنائي" >&2
        rm -f "$sums" "$file"
        return 1
    fi
    expected="$(awk -v n="$name" '$2 == n || $2 == "./" n {print $1; exit}' "$sums" 2>/dev/null)"
    rm -f "$sums"
    if [ -z "$expected" ]; then
        echo "sha256    : تحذير — لا توجد بصمة منشورة لـ$name؛ يُحذف الثنائي" >&2
        rm -f "$file"
        return 1
    fi
    actual="$(sha256sum "$file" 2>/dev/null | awk '{print $1}')"
    if [ "$actual" != "$expected" ]; then
        echo "sha256    : خطأ — بصمة $name لا تطابق المنشور؛ يُحذف الثنائي" >&2
        rm -f "$file"
        return 1
    fi
    return 0
}

# H2: عنوان ربط خادم OmniRoute الفعلي من /proc/net/tcp[6] (كما في
# ensure-env.sh وstudio.py).
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

echo "== 0) ملف خدمة systemd (إصلاح ذاتي من نسخة الـhome) =="
if [ -f "$UNIT_SRC" ]; then
    if [ ! -f "$UNIT_DST" ] || ! cmp -s "$UNIT_SRC" "$UNIT_DST"; then
        if $SUDO cp "$UNIT_SRC" "$UNIT_DST" 2>/dev/null; then
            $SUDO systemctl daemon-reload 2>/dev/null || true
            $SUDO systemctl enable studio-env-restore.service >/dev/null 2>&1 || true
            echo "unit     : أُعيد تثبيت ملف الخدمة من النسخة الاحتياطية"
        else
            echo "unit     : تحذير — تعذّر نسخ ملف الخدمة إلى /etc (بلا صلاحية؟)"
        fi
    else
        echo "unit     : موجود ومطابق للنسخة الاحتياطية"
    fi
else
    echo "unit     : تحذير — النسخة الاحتياطية غائبة ($UNIT_SRC)"
fi

echo "== 1) PATH في ~/.bashrc و~/.profile =="
for f in ~/.bashrc ~/.profile; do
    grep -q 'npm-global/bin' "$f" 2>/dev/null || \
        echo 'export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"' >> "$f"
done
export PATH="$HOME_BIN:$NPM_GLOBAL/bin:$PATH"

echo "== 2) yt-dlp (ثنائي مستقل في ~/.local/bin) =="
if [ ! -x "$HOME_BIN/yt-dlp" ]; then
    # M7: --fail وhttps فقط و3 إعادة توجيه كحد أقصى ومهلة 60ث + تحقق SHA256
    if curl --fail --proto =https --max-redirs 3 --max-time 60 -L -o "$HOME_BIN/yt-dlp" \
            https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
        && verify_sha256 "$HOME_BIN/yt-dlp" \
            https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS \
            yt-dlp; then
        chmod +x "$HOME_BIN/yt-dlp"
    else
        echo "yt-dlp   : خطأ — فشل التنزيل أو التحقق؛ سيُعاد عند التشغيل التالي" >&2
    fi
fi
[ -x "$HOME_BIN/yt-dlp" ] && link "$HOME_BIN/yt-dlp" yt-dlp

echo "== 3) zstd (ثنائي مستقل في ~/.local/bin من حزمة .deb) =="
if [ ! -x "$HOME_BIN/zstd" ]; then
    tmpd="$(mktemp -d)"
    if (cd "$tmpd" && apt-get download zstd >/dev/null 2>&1 \
         && dpkg-deb -x zstd_*.deb "$tmpd/x" >/dev/null 2>&1 \
         && cp "$tmpd/x/usr/bin/zstd" "$HOME_BIN/zstd"); then
        chmod +x "$HOME_BIN/zstd"
    else
        apt_install zstd
        cp /usr/bin/zstd "$HOME_BIN/zstd" 2>/dev/null || true
    fi
    rm -rf "$tmpd"
fi
link "$HOME_BIN/zstd" zstd

echo "== 4) OmniRoute (npm ببادئة ~/.npm-global — الإعداد في ~/.omniroute ينجو) =="
npm config set prefix "$NPM_GLOBAL" 2>/dev/null
if [ ! -x "$NPM_GLOBAL/bin/omniroute" ]; then
    # M7: إصدار مثبّت — المثبَّت والمختبَر 3.8.54؛ الرفع يكون بقرار صريح.
    npm install -g omniroute@3.8.54
fi
link "$NPM_GLOBAL/bin/omniroute" omniroute

echo "== 5) Ollama (ثنائي في ~/opt/ollama — الموديل في ~/.ollama ينجو) =="
if [ ! -x "$HOME/opt/ollama/bin/ollama" ] && [ ! -x "$HOME/opt/ollama/ollama" ]; then
    command -v zstd >/dev/null 2>&1 || apt_install zstd
    # M7: --fail وhttps فقط و3 إعادة توجيه كحد أقصى ومهلة 60ث + تحقق SHA256
    if curl --fail --proto =https --max-redirs 3 --max-time 60 -L -o "$HOME/opt/ollama.tar.zst" \
            "https://ollama.com/download/ollama-linux-amd64.tar.zst" \
        && verify_sha256 "$HOME/opt/ollama.tar.zst" \
            https://github.com/ollama/ollama/releases/latest/download/sha256sum.txt \
            ollama-linux-amd64.tar.zst; then
        mkdir -p "$HOME/opt/ollama"
        tar --zstd -xf "$HOME/opt/ollama.tar.zst" -C "$HOME/opt/ollama"
    else
        echo "ollama   : خطأ — فشل التنزيل أو التحقق؛ سيُعاد عند التشغيل التالي" >&2
        rm -f "$HOME/opt/ollama.tar.zst"
    fi
fi
if [ -x "$HOME/opt/ollama/bin/ollama" ]; then
    link "$HOME/opt/ollama/bin/ollama" ollama
elif [ -x "$HOME/opt/ollama/ollama" ]; then
    link "$HOME/opt/ollama/ollama" ollama
fi

echo "== 6) piper (ثنائي + موديل في الـhome) =="
if [ -x "$HOME_BIN/piper" ]; then
    link "$HOME_BIN/piper" piper
else
    echo "piper    : غير موجود (ثبّته من https://github.com/rhasspy/piper)"
fi

echo "== 7) melt (MLT 7.22.0 — يُفضَّل تثبيت apt؛ المنزلي بديل) =="
# عيب 2026-11-22: نسخة ~/opt/mlt المنزلية تربط مكتبات نظام
# (libavformat.so.60 وlibQt5Network.so.5 وlibexif.so.12…)
# تُمسح مع إعادة تشغيل الـVM، فتفشل كل وحدات MLT عند التحميل:
# لا صور qimage ولا نصوص dynamictext ولا مستهلك avformat،
# فيريندر melt «99%» من إطارات فارغة ثم يعلق بلا ملف خرج.
# تثبيت apt يجلب الاعتماديات كاملة، فيُقدَّم أولًا.
melt_ok() { # نسخة apt موجودة وتحمّل وحداتها بلا أخطاء dlopen
    [ -x /usr/bin/melt ] || return 1
    _melt_out="$(/usr/bin/melt -version 2>&1)" || return 1
    case "$_melt_out" in
        *'failed to dlopen'*) return 1 ;;
    esac
    return 0
}
if melt_ok; then
    link /usr/bin/melt melt
    echo "melt     : apt (/usr/bin/melt) — يعمل"
else
    apt_install melt || true
    if melt_ok; then
        link /usr/bin/melt melt
        echo "melt     : apt (/usr/bin/melt) — ثُبّت الآن"
    else
        write_melt_wrapper() {
            mkdir -p "$MLT_HOME/bin"
            cat > "$MLT_HOME/bin/melt" <<'WRAPPER_EOF'
#!/bin/bash
# melt منزلي — نسخة MLT 7.22.0 مستخرجة من حزم .deb إلى ~/opt/mlt (تنجو من إعادة تشغيل الـVM).
export LD_LIBRARY_PATH="/home/hatch/opt/mlt/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export MLT_REPOSITORY="/home/hatch/opt/mlt/usr/lib/x86_64-linux-gnu/mlt-7"
export MLT_DATA="/home/hatch/opt/mlt/usr/share/mlt-7"
exec /home/hatch/opt/mlt/usr/bin/melt "$@"
WRAPPER_EOF
            chmod +x "$MLT_HOME/bin/melt"
        }
        if [ ! -x "$MLT_HOME/usr/bin/melt" ]; then
            tmpd="$(mktemp -d)"
            if (cd "$tmpd" && apt-get download melt libmlt7 libmlt++7 libmlt-data libsdl2-2.0-0 >/dev/null 2>&1); then
                for d in "$tmpd"/*.deb; do dpkg-deb -x "$d" "$MLT_HOME" >/dev/null 2>&1; done
            fi
            rm -rf "$tmpd"
            if [ ! -x "$MLT_HOME/usr/bin/melt" ]; then
                echo "تعذّر استخراج melt المنزلي وتثبيت apt — خلفية MLT معطلة"
            fi
        fi
        if [ -x "$MLT_HOME/usr/bin/melt" ]; then
            [ -x "$MLT_HOME/bin/melt" ] || write_melt_wrapper
            link "$MLT_HOME/bin/melt" melt
        fi
    fi
fi

echo "== 8) حزم apt المساندة (xvfb وmesa-vulkan-drivers وffmpeg وfontconfig وpython3-yaml وpython3-pil — شبكة أمان) =="
command -v xvfb-run >/dev/null 2>&1 || apt_install xvfb
dpkg -s mesa-vulkan-drivers >/dev/null 2>&1 || apt_install mesa-vulkan-drivers
command -v ffmpeg >/dev/null 2>&1 || apt_install ffmpeg
command -v fc-list >/dev/null 2>&1 || apt_install fontconfig
python3 -c "import yaml" 2>/dev/null || apt_install python3-yaml
python3 -c "import PIL" 2>/dev/null || apt_install python3-pil

echo "== 9) تحقق =="
for t in yt-dlp omniroute melt ollama ffmpeg zstd; do
    printf "%-10s: " "$t"
    if command -v "$t" >/dev/null 2>&1; then
        "$t" --version 2>&1 | head -1
    else
        echo "غير موجود"
    fi
done
if [ -x "$HOME_BIN/piper" ]; then
    echo "piper    : موجود في ~/.local/bin"
else
    echo "piper    : غير موجود (ثبّته من https://github.com/rhasspy/piper)"
fi

echo "== 10) خادم OmniRoute (أمر chat يحتاجه — loopback فقط) =="
# عيب 2026-11-21: `omniroute chat` مجرد عميل HTTP للخادم على
# localhost:20128؛ وإن كان الخادم متوقفًا يفشل بصمت (exit 1 بلا رسالة).
# الخادم يُشغَّل على 127.0.0.1 فقط فلا ينكشف على الشبكة.
if command -v omniroute >/dev/null 2>&1; then
    if curl -sf --max-time 2 http://127.0.0.1:20128/api/health >/dev/null 2>&1; then
        echo "omniroute  : الخادم شغال على 127.0.0.1:20128"
    else
        # H2: المتغير الفعّال HOSTNAME (الحزمة تتجاهل OMNIROUTE_SERVER_HOST).
        REQUIRE_API_KEY=true HOSTNAME=127.0.0.1 OMNIROUTE_SERVER_HOST=127.0.0.1 omniroute serve --no-open --daemon --port 20128 >/dev/null 2>&1 || true
        # إصلاح 2026-11-21 (اختبار اختراق): REQUIRE_API_KEY=true إلزامي —
        # الافتراضي في حزمة omniroute هو false، وبدونه تقبل
        # /v1/chat/completions طلبات بلا مفتاح. القيمة في ~/.omniroute/.env
        # أيضًا (تُحمَّل أولًا وتغلب على افتراضي الحزمة).
        # إصلاح 2026-11-21: إقلاع الخادم يستغرق أكثر من 5 ثوانٍ أحيانًا
        # (لوحظ بعد ريستارت VM: الخادم قام بعد انتهاء مهلة الـ5 ثوانٍ
        # فأبلغ السكربت تحذيرًا كاذبًا) — نفحص الصحة حتى 30 ثانية.
        for i in $(seq 1 30); do
            if curl -sf --max-time 2 http://127.0.0.1:20128/api/health >/dev/null 2>&1; then break; fi
            sleep 1
        done
        if curl -sf --max-time 2 http://127.0.0.1:20128/api/health >/dev/null 2>&1; then
            # H2: أكّد الربط الفعلي بعد الإقلاع — صحة HTTP وحدها لا تثبت
            # أن الخادم على loopback فقط.
            _bind="$(omniroute_bind_address)"
            if [ "$_bind" = "127.0.0.1" ]; then
                echo "omniroute  : الخادم شُغّل على 127.0.0.1:20128 (الربط مؤكد: $_bind)"
            elif [ -n "$_bind" ]; then
                echo "omniroute  : تحذير — الخادم شُغّل لكنه يربط $_bind وليس loopback فقط!"
            else
                echo "omniroute  : الخادم شُغّل على 127.0.0.1:20128 (تعذّر تأكيد الربط)"
            fi
        else
            echo "omniroute  : تحذير — الخادم لم يرد (سيحاول studio تشغيله)"
        fi
    fi
fi
echo "== 11) gitleaks (ماسح أسرار — ثنائي في ~/workspace/protection/bin، MIT) =="
if [ -x "$HOME/workspace/protection/bin/gitleaks" ]; then
    echo "gitleaks : موجود ($("$HOME/workspace/protection/bin/gitleaks" version 2>/dev/null))"
elif [ -x "$HOME/workspace/protection/restore-gitleaks.sh" ]; then
    /bin/bash "$HOME/workspace/protection/restore-gitleaks.sh" \
        || echo "gitleaks : تحذير — فشل التثبيت؛ سيُعاد عند التشغيل التالي"
else
    echo "gitleaks : تحذير — سكربت الاستعادة غائب؛ ثبّته يدويًا من https://github.com/gitleaks/gitleaks"
fi

echo "تم — إن ظهر أي 'غير موجود' أعد تشغيل السكربت أو ثبّت الأداة يدويًا."
