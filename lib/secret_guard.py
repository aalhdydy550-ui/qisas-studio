#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""حارس تسرّب الأسرار — جولة v0.1.37 (مقترح tinker رقم 1)،
موسَّع في جولة الأنماط W8 (مسح semsec §3 و§4 — نمط فقط،
أُعيد تنفيذه بايثون بالمكتبة القياسية من الصفر دون نقل كود).

يمسح شجرة studio بحثًا عن أنماط أسرار (مفاتيح API، توكنات،
كلمات مرور، مفاتيح PEM) قبل أي رفع مستقبلي. قاعدتان:
1. الملفات المغطاة بـ .gitignore لا تُفحص (ملفات الأسرار
   الحقيقية على القرص — youtube-token.json وclient_secrets.json
   و.env — مستثناة لأنها لا تُرفع أصلًا، بشرط بقائها في
   .gitignore — وهذا ما يتحقق منه check_gitignore).
2. قائمة سماح صريحة وموثقة لقيم عامة معلنة: رقم فودافون
   كاش ومعرّف الصفحة (يظهران في README والصفحة العامة).

أي إصابة خارج هاتين القاعدتين تفشل المجموعة — لا تُسكَت
بإضافة استثناء جديد دون توثيق سببه هنا.

كواشف صيغة المزود (W8): كل مزود يُكتشف ببادئته الدقيقة
وطوله ومجموعة محارفه — مقتصرًا على المزودين الذين يستخدمهم
الاستوديو فعلًا (Google/Gemini وGroq وOpenRouter وHuggingFace
وOpenAI وAnthropic وElevenLabs وGitHub) + كشف عام لملفات
.env الملتزَمة (أي ملف .env غير مغطى بـ .gitignore) وللمفاتيح
الخاصة (RSA/EC/OpenSSH/PKCS#8/المشفّرة). الفاحص يعمل كفحص
ما قبل الدفع — لا داخل خط الفيديو.

قالب كل إصابة (W8): {"file", "line", "pattern", "value",
"id", "severity", "fix"} — معرّف ثابت (SG-…) وخطورة
("critical" لمفتاح مزود/مفتاح خاص/ملف .env ملتزَم، و"high"
للإسناد العام والتوكن الحامل والسلسلة الطويلة) ورسالة إصلاح
تقول ما الخطأ وكيف يُصلَح. القيمة تُقتطع إلى 24 حرفًا —
لا تظهر قيمة كاملة أبدًا في أي تقرير.

استثناء بنيوي موثق (W8): رموز الأخطاء بصيغة
STUDIO-<العائلة>-<رقم من 3 خانات> معرّفات عامة ثابتة
موثقة في docs/ERRORS-RUNBOOK.md وليست أسرارًا — مفاتيح
مثل facebook_token تحملها كقيم في lib/errors.py،
وإنتروبياها العالية توقع كاشف الإسناد فيها خطأً؛
فهي مستثناة بنمطها (لا بقيمها) في _ERROR_CODE_RE أدناه.

مفاتيح كتابة فقط (جولة v0.1.63، بند 13 — عقد ع12، §7):
المفاتيح تُكتب ولا تُقرأ أبدًا — لا دالة عامة في هذه الوحدة
ترجع قيمة مفتاح؛ وسرد المفاتيح يعرض الأسماء والوجود فقط،
والتشخيص يقنّع القيم. حفظ مفتاح يجري اختبارًا واحدًا صغيرًا
(قابل للحقن عبر `tester` — والافتراضي تحقق صيغة فقط بلا
شبكة؛ والتحقق الحي من المزوّد يحقنه المتصل)؛ والمفتاح الذي
يرفضه الاختبار لا يُحفظ. التدوير يكتب الجديد بعد نجاح
اختباره فقط والقديم يبقى حتى ينجح الجديد. الرموز تُقرأ من
ملف عبر `read_token_file` (مسار `--token-file`) أبدًا من
سطر الأوامر. مخزن المفاتيح `keys.json` تحت مجلد الحالة
نفسه `~/.qisas-studio` (أو `QISAS_KEYS_DIR` في الاختبارات)،
المجلد 0700 والملف 0600 وكتابة ذرية على نمط `lib/license.py`.
"""
import fnmatch
import json
import math
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

# --- قائمة السماح الصريحة (قيم عامة معلنة) ---
# مفاتيح وهمية بصيغ صحيحة للوثائق/الاختبارات (W8): كلها
# حروف مكررة واحدة يستحيل أن يصدرها أي مزود كمفتاح حقيقي،
# وموثقة هنا لتبقى الأمثلة في الاختبارات دون أن تُكتشف —
# لا تُحذف دون استبدال الأمثلة التي تعتمد عليها.
_FAKE_GOOGLE_KEY = "AIza" + "A" * 35
_FAKE_GROQ_KEY = "gsk_" + "A" * 48
_FAKE_OPENROUTER_KEY = "sk-or-v1-" + "a" * 64
_FAKE_OPENAI_KEY = "sk-" + "A" * 48
_FAKE_ANTHROPIC_KEY = "sk-ant-api03-" + "A" * 93
_FAKE_ELEVENLABS_KEY = "sk_" + "a" * 48

ALLOWLIST_VALUES = {
    # رقم فودافون كاش للدفع اليدوي — معلن في README والصفحة.
    "01023468196",
    # معرّف صفحة فيسبوك «قصص وعبر» — عام.
    "1048148471706586",
    # مفاتيح وهمية بصيغ صحيحة — أمثلة للوثائق/الاختبارات فقط.
    _FAKE_GOOGLE_KEY,
    _FAKE_GROQ_KEY,
    _FAKE_OPENROUTER_KEY,
    _FAKE_OPENAI_KEY,
    _FAKE_ANTHROPIC_KEY,
    _FAKE_ELEVENLABS_KEY,
}

# --- إدخالات .gitignore المطلوبة لملفات الأسرار ---
# (جولة الحماية المرحلة 2: الأنماط العريضة الثلاثة تمنع فجوات
# الأسماء — ملف مثل `backup.env` أو `mytoken.json` أو `id_rsa`
# يجب أن يبقى خارج الرفع حتى لو لم يطابق الاسم الدقيق.)
REQUIRED_GITIGNORE = (
    "config.yaml",
    "youtube-token.json",
    "client_secrets",
    ".env",
    "*.env*",
    "*token*",
    "id_rsa*",
)

# مجلدات تُستثنى من المسح دائمًا (مخرجات/نسخ احتياطية/بيانات).
SKIP_DIRS = {
    ".git", "runs", "backups", "client-orders", "__pycache__",
    "node_modules", ".venv", ".venv-youtube", ".venv-3.11",
    ".venv-3.9", ".venv-kaggle",
}

# امتدادات ثنائية لا تُقرأ كنص.
SKIP_EXTENSIONS = {
    ".mp4", ".wav", ".mp3", ".jpg", ".jpeg", ".png", ".gif",
    ".zip", ".pyc", ".onnx", ".bin", ".cube", ".pdf", ".apk",
    ".deb", ".ico", ".woff", ".woff2", ".ttf",
}

_MAX_FILE_BYTES = 1_000_000

# مفاتيح الإسناد: مفتاح سري + قيمة طويلة عالية الإنتروبيا.
_SECRET_KEYS = (
    "api_key", "apikey", "api-key", "secret", "token", "password",
    "passwd", "client_secret", "refresh_token", "access_token",
    "auth", "bearer", "private_key", "hf_token", "github_token",
    "openai_api_key", "anthropic_api_key", "gemini_api_key",
    "webhook_secret", "session_key", "encryption_key",
)
_ASSIGN_RE = re.compile(
    r"(?i)(?:['\"])?(%s)['\"]?\s*[:=]\s*['\"]?([^\s'\",;]{16,})" %
    "|".join(re.escape(k) for k in _SECRET_KEYS))
_BEARER_RE = re.compile(r"Bearer\s+([A-Za-z0-9_\-\.]{20,})")
_HF_RE = re.compile(r"hf_[A-Za-z0-9]{20,}")
_GITHUB_RE = re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}")
_GITHUB_PAT_RE = re.compile(r"github_pat_[A-Za-z0-9_]{22,}")
_AWS_RE = re.compile(r"AKIA[0-9A-Z]{16}")
# كواشف صيغة المزود (W8 — بادئة + طول + مجموعة محارف، من
# الصيغ العامة المعروفة لكل مزود، لا من أي مستودع قواعد):
# Google/Gemini: ‏AIza + ‏35 حرفًا (39 إجمالًا).
_GOOGLE_RE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
# Groq: ‏gsk_ + ‏48 حرفًا على الأقل.
_GROQ_RE = re.compile(r"gsk_[A-Za-z0-9]{48,}")
# OpenRouter: ‏sk-or-v1- + ‏64 حرفًا.
_OPENROUTER_RE = re.compile(r"sk-or-v1-[A-Za-z0-9]{64}")
# OpenAI: ‏sk- + ‏48 حرفًا على الأقل (مع sk-proj- وsk-svcacct-)؛
# والاستثناء السالب يمنع ازدواج العدّ مع OpenRouter وAnthropic
# (بادئتاهما تبدآن بـ sk- أيضًا).
_OPENAI_RE = re.compile(
    r"sk-(?!or-v1-|ant-api03-)(?:proj-|svcacct-)?[A-Za-z0-9_\-]{48,}")
# Anthropic: ‏sk-ant-api03- + ‏93 حرفًا على الأقل (قد تليها ‎-AA).
_ANTHROPIC_RE = re.compile(r"sk-ant-api03-[A-Za-z0-9_\-]{93,}")
# ElevenLabs: ‏sk_ + ‏48 حرف هكس — والنفي الخلفي يمنع
# ازدواج العدّ مع Groq (‏gsk_ + ‏48 حرفًا: حرف g قبل sk_
# يجعلها مفتاح Groq لا ElevenLabs).
_ELEVENLABS_RE = re.compile(r"(?<![A-Za-z0-9])sk_[0-9a-fA-F]{48}")
# مفاتيح خاصة: RSA وEC وOpenSSH وPKCS#8 (بلا بادئة نوع)
# والمشفّرة — العلامة مركّبة ديناميكيًا عند الإبلاغ حتى لا
# يطابق الحارس سطره هو.
_PEM_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED |DSA )?PRIVATE KEY-----")
# سلسلة مقتبسة طويلة مختلطة الحالة والأرقام (ليست هكس خالصًا
# — بصمات SHA الأربعينية هكس خالص وتُستثنى عمدًا).
_LONG_STRING_RE = re.compile(r"['\"]([A-Za-z0-9_\-/+=]{32,})['\"]")

# ملفات .env: الاسم نفسه أو ‎.env.<بيئة>‎ (مثل ‎.env.local‎)؛
# والقوالب المقصودة الالتزام (‎.env.example‎ وأخواتها) ليست
# ملفات أسرار — يُفحص محتواها سطرًا سطرًا كأي ملف، لكن اسمها
# وحده لا يُبلَّغ.
_DOTENV_EXAMPLE_SUFFIXES = (".example", ".sample", ".template", ".dist")


def _is_dotenv_file(name):
    """هل اسم الملف ملف ‎.env‎ حقيقي (لا قالب مثال)؟"""
    if name == ".env":
        return True
    if not name.startswith(".env."):
        return False
    return not any(name.endswith(s)
                   for s in _DOTENV_EXAMPLE_SUFFIXES)


# قالب الإصابات (W8): النمط ← (المعرّف، الخطورة، رسالة الإصلاح).
_FINDING_META = {
    "google": ("SG-GOOGLE-001", "critical",
               "أزل مفتاح Google/Gemini من الملف ودوّره (ألغِه من "
               "Google Cloud وأنشئ بديلًا)؛ وضع البديل في ملف .env "
               "مغطى بـ .gitignore أو في مدير أسرار، ولا تلتزم به أبدًا."),
    "groq": ("SG-GROQ-001", "critical",
             "أزل مفتاح Groq من الملف ودوّره (ألغِه من لوحة Groq "
             "وأنشئ بديلًا)؛ وضع البديل في ملف .env مغطى بـ "
             ".gitignore أو في مدير أسرار، ولا تلتزم به أبدًا."),
    "openrouter": ("SG-OPENROUTER-001", "critical",
                   "أزل مفتاح OpenRouter من الملف ودوّره (ألغِه من "
                   "لوحة OpenRouter وأنشئ بديلًا)؛ وضع البديل في "
                   "ملف .env مغطى بـ .gitignore أو في مدير أسرار، "
                   "ولا تلتزم به أبدًا."),
    "openai": ("SG-OPENAI-001", "critical",
               "أزل مفتاح OpenAI من الملف ودوّره (ألغِه من لوحة "
               "OpenAI وأنشئ بديلًا)؛ وضع البديل في ملف .env مغطى "
               "بـ .gitignore أو في مدير أسرار، ولا تلتزم به أبدًا."),
    "anthropic": ("SG-ANTHROPIC-001", "critical",
                  "أزل مفتاح Anthropic من الملف ودوّره (ألغِه من "
                  "لوحة Anthropic وأنشئ بديلًا)؛ وضع البديل في ملف "
                  ".env مغطى بـ .gitignore أو في مدير أسرار، ولا "
                  "تلتزم به أبدًا."),
    "elevenlabs": ("SG-ELEVENLABS-001", "critical",
                   "أزل مفتاح ElevenLabs من الملف ودوّره (ألغِه من "
                   "لوحة ElevenLabs وأنشئ بديلًا)؛ وضع البديل في "
                   "ملف .env مغطى بـ .gitignore أو في مدير أسرار، "
                   "ولا تلتزم به أبدًا."),
    "huggingface": ("SG-HF-001", "critical",
                    "أزل توكن HuggingFace من الملف ودوّره (ألغِه من "
                    "إعدادات HuggingFace وأنشئ بديلًا)؛ وضع البديل "
                    "في ملف .env مغطى بـ .gitignore أو في مدير "
                    "أسرار، ولا تلتزم به أبدًا."),
    "github": ("SG-GITHUB-001", "critical",
               "أزل توكن GitHub من الملف ودوّره (ألغِه من إعدادات "
               "GitHub وأنشئ بديلًا)؛ وضع البديل في ملف .env مغطى "
               "بـ .gitignore أو في مدير أسرار، ولا تلتزم به أبدًا."),
    "github_pat": ("SG-GITHUB-002", "critical",
                   "أزل توكن GitHub الدقيق (fine-grained) من الملف "
                   "ودوّره (ألغِه من إعدادات GitHub وأنشئ بديلًا)؛ "
                   "وضع البديل في ملف .env مغطى بـ .gitignore أو "
                   "في مدير أسرار، ولا تلتزم به أبدًا."),
    "aws": ("SG-AWS-001", "critical",
            "أزل مفتاح AWS من الملف وعطّل مفتاح الوصول المرتبط به "
            "من لوحة AWS وأنشئ بديلًا؛ وضع البديل في ملف .env "
            "مغطى بـ .gitignore أو في مدير أسرار."),
    "pem": ("SG-PEM-001", "critical",
            "أزل المفتاح الخاص من الملف نهائيًا (واحذفه من تاريخ "
            "git إن التُزم) وأنشئ مفتاحًا جديدًا — مفتاح خاص مسرّب "
            "لا يُصلَح بالحذف وحده."),
    "dotenv_file": ("SG-DOTENV-001", "critical",
                    "أضف الملف إلى .gitignore واحذفه من التتبع "
                    "(git rm --cached) ودوّر كل أسراره؛ وإن كان "
                    "قالبًا مقصودًا فأعد تسميته ‎.env.example‎ بقيم "
                    "وهمية فقط."),
    "assignment": ("SG-ASSIGN-001", "high",
                   "أزل القيمة السرية من الكود وانقلها إلى ملف .env "
                   "مغطى بـ .gitignore (أو مدير أسرار)؛ وإن تسرّبت "
                   "في التزام سابق فدوّرها."),
    "bearer": ("SG-BEARER-001", "high",
               "أزل التوكن الحامل من الكود وانقله إلى ملف .env مغطى "
               "بـ .gitignore (أو مدير أسرار)؛ وإن تسرّب فدوّره."),
    "long_string": ("SG-LONGSTR-001", "high",
                    "إن كانت القيمة سرًا حقيقيًا فأزلها ودوّرها "
                    "وانقلها إلى .env مغطى بـ .gitignore؛ وإن كانت "
                    "بصمة أو معرّفًا عامًا فأضفها إلى "
                    "ALLOWLIST_VALUES في lib/secret_guard.py مع "
                    "توثيق سببها."),
}


def _make_finding(rel_path, lineno, kind, value):
    """ابنِ إصابة بالقالب الكامل (معرّف + خطورة + إصلاح)."""
    fid, severity, fix = _FINDING_META.get(
        kind, ("SG-UNKNOWN-001", "high",
               "أزل القيمة من الكود وراجع سبب الإبلاغ عنها."))
    return {"file": rel_path,
            "line": lineno,
            "pattern": kind,
            "value": value[:24] + ("…" if len(value) > 24 else ""),
            "id": fid,
            "severity": severity,
            "fix": fix}

# قيم اختبار/أمثلة لا تُعدّ أسرارًا أبدًا.
_FIXTURE_MARKERS = (
    "test", "fake", "example", "placeholder", "your-",
    "1234567890", "xxx", "change-me", "dummy", "sample",
)

# رموز أخطاء عامة موثقة (انظر docstring): ليست أسرارًا.
_ERROR_CODE_RE = re.compile(r"^STUDIO-[A-Z]+-[0-9]{3}$")


def _entropy(text):
    """إنتروبيا شانون للحروف (بت/حرف)."""
    if not text:
        return 0.0
    counts = {}
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(text)
    return -sum((c / total) * math.log2(c / total)
                for c in counts.values())


def _is_path_like(value):
    """قيمة تبدو مسار ملف لا سرًا (~/... أو /... أو تنتهي بامتداد)."""
    if value.startswith(("~", "/", "./", "../")):
        return True
    if value.endswith((".json", ".yaml", ".yml", ".txt", ".md",
                       ".py", ".sh", ".mp4", ".wav")):
        return True
    return False


def _is_fixture(value):
    low = value.lower()
    return any(m in low for m in _FIXTURE_MARKERS)


def _is_hex_only(value):
    return all(c in "0123456789abcdef" for c in value.lower())


def _load_gitignore_patterns(root):
    patterns = []
    path = os.path.join(root, ".gitignore")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    except OSError:
        pass
    return patterns


def _is_ignored(rel_path, patterns):
    """هل يطابق المسار النسبي أي نمط في .gitignore (تقريب fnmatch)."""
    name = os.path.basename(rel_path)
    for pat in patterns:
        p = pat.lstrip("/").rstrip("/")
        if fnmatch.fnmatch(rel_path, p) or fnmatch.fnmatch(name, p):
            return True
        if fnmatch.fnmatch(rel_path, p + "/*"):
            return True
        if "/" not in p and fnmatch.fnmatch(rel_path, "*/" + p):
            return True
    return False


def _check_line(line, rel_path, lineno, findings):
    """افحص سطرًا واحدًا بكل الأنماط؛ أضف الإصابات إلى findings."""
    def add(kind, value):
        if value in ALLOWLIST_VALUES:
            return
        if _is_fixture(value):
            return
        if _ERROR_CODE_RE.match(value):
            return
        findings.append(_make_finding(rel_path, lineno, kind, value))

    m = _ASSIGN_RE.search(line)
    if m:
        value = m.group(2)
        # استدعاء دالة (load_token(...)/expanduser(...)) لا سر.
        if ("(" in value) or (")" in value):
            value = ""
        if (len(value) >= 16 and _entropy(value) >= 3.5
                and not _is_path_like(value)):
            add("assignment", value)
    m = _BEARER_RE.search(line)
    if m and _entropy(m.group(1)) >= 3.5:
        add("bearer", m.group(1))
    for pattern, kind in ((_GOOGLE_RE, "google"),
                          (_GROQ_RE, "groq"),
                          (_OPENROUTER_RE, "openrouter"),
                          (_ANTHROPIC_RE, "anthropic"),
                          (_OPENAI_RE, "openai"),
                          (_ELEVENLABS_RE, "elevenlabs"),
                          (_HF_RE, "huggingface"),
                          (_GITHUB_RE, "github"),
                          (_GITHUB_PAT_RE, "github_pat"),
                          (_AWS_RE, "aws")):
        m = pattern.search(line)
        if m:
            add(kind, m.group(0))
    if _PEM_RE.search(line):
        # العلامة مركّبة ديناميكيًا حتى لا يطابق الحارس سطره هو.
        add("pem", "-----BEGIN " + "PRIVATE KEY-----")
    m = _LONG_STRING_RE.search(line)
    if m:
        value = m.group(1)
        if (len(value) >= 32 and _entropy(value) >= 4.5
                and not _is_hex_only(value)
                and not _is_path_like(value)
                and not value.startswith(("http://", "https://"))):
            add("long_string", value)


def scan_tree(root):
    """امسح الشجرة؛ ارجع قائمة إصابات (فارغة = نظيف).

    ملف ‎.env‎ غير مغطى بـ .gitignore يُبلَّغ عنه بذاته
    (SG-DOTENV-001) لأنه سيُلتزَم بما فيه من أسرار — أما
    المغطى بـ .gitignore فيُتخطى كاملًا (قاعدة الملف 1)،
    وقوالب ‎.env.example‎ وأخواتها لا يُبلَّغ عن اسمها.
    كل إصابة تحمل قالب «معرّف + خطورة + رسالة إصلاح».
    """
    root = os.path.abspath(root)
    patterns = _load_gitignore_patterns(root)
    findings = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            if os.path.splitext(name)[1].lower() in SKIP_EXTENSIONS:
                continue
            ignored = _is_ignored(rel, patterns)
            if _is_dotenv_file(name) and not ignored:
                findings.append(
                    _make_finding(rel, 1, "dotenv_file", name))
            if ignored:
                continue
            try:
                if os.path.getsize(path) > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            try:
                with open(path, encoding="utf-8", errors="strict") as fh:
                    lines = fh.readlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, 1):
                _check_line(line, rel, i, findings)
    return findings


def to_sarif(findings):
    """صدّر الإصابات بصيغة SARIF 2.1.0 (جولة الأنماط W8 — أولوية دنيا).

    مخرجات منظمة قابلة للقراءة الآلية (تُرفع إلى GitHub عبر
    upload-sarif مثلًا). الرسائل تحمل النمط والمعرّف ورسالة
    الإصلاح فقط — لا قيمة سرية كاملة ولا مبتورة.
    """
    rules = {}
    results = []
    for f in findings:
        fid = f["id"]
        if fid not in rules:
            rules[fid] = {
                "id": fid,
                "name": f["pattern"],
                "shortDescription": {"text": f["fix"]},
                "defaultConfiguration": {
                    "level": ("error" if f["severity"] == "critical"
                              else "warning")},
            }
        results.append({
            "ruleId": fid,
            "level": ("error" if f["severity"] == "critical"
                      else "warning"),
            "message": {"text": "%s في %s:%d — %s" % (
                f["pattern"], f["file"], f["line"], f["fix"])},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f["file"]},
                    "region": {"startLine": f["line"]},
                },
            }],
        })
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {
                "name": "secret-guard",
                "informationUri": "https://github.com/aalhdydy550-ui/"
                                  "qisas-studio",
                "rules": list(rules.values()),
            }},
                "results": results}]}


def check_gitignore(root):
    """تحقق أن .gitignore يغطي ملفات الأسرار؛ ارجع النواقص."""
    path = os.path.join(root, ".gitignore")
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return list(REQUIRED_GITIGNORE)
    return [entry for entry in REQUIRED_GITIGNORE
            if entry not in content]


# ------------------------------------------------------------------
# مفاتيح كتابة فقط — جولة v0.1.63، بند 13 (عقد ع12)
# ------------------------------------------------------------------

KEYS_DIR_ENV = "QISAS_KEYS_DIR"
DEFAULT_KEYS_DIR = os.path.join("~", ".qisas-studio")
KEYS_FILENAME = "keys.json"

CAIRO_TZ = ZoneInfo("Africa/Cairo")

# المزودون الذين يستخدمهم الاستوديو فعلًا (نفس قائمة كواشف
# الصيغة أعلاه) — اسم المزوّد ← نمط صيغة مفتاحه للتحقق
# الأولي من الصيغة (بلا شبكة).
_PROVIDER_FORMAT_RES = {
    "gemini": _GOOGLE_RE,
    "google": _GOOGLE_RE,
    "groq": _GROQ_RE,
    "openrouter": _OPENROUTER_RE,
    "openai": _OPENAI_RE,
    "anthropic": _ANTHROPIC_RE,
    "elevenlabs": _ELEVENLABS_RE,
    "huggingface": _HF_RE,
    "github": _GITHUB_RE,
}

KNOWN_PROVIDERS = tuple(sorted(_PROVIDER_FORMAT_RES))

_KEY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class KeyTestError(Exception):
    """رفض الاختبار مفتاحًا (رسالته عربية) — والمفتاح لم يُحفظ."""


class KeyStoreError(Exception):
    """خطأ في مخزن المفاتيح أو ملف التوكن (رسالته عربية)."""


def keys_dir():
    """مجلد مخزن المفاتيح: QISAS_KEYS_DIR أو ~/.qisas-studio."""
    override = os.environ.get(KEYS_DIR_ENV, "").strip()
    if override:
        return os.path.expanduser(override)
    return os.path.expanduser(DEFAULT_KEYS_DIR)


def keys_path(directory=None):
    """المسار الكامل لملف مخزن المفاتيح keys.json."""
    return os.path.join(directory or keys_dir(), KEYS_FILENAME)


def _now_cairo_iso():
    """الآن بتوقيت القاهرة بصيغة ISO (لأختام المخزن)."""
    return datetime.now(tz=CAIRO_TZ).isoformat(timespec="seconds")


def _validate_key_name(name):
    """تحقق من اسم مفتاح؛ ValueError على اسم فارغ أو غير صالح."""
    if not isinstance(name, str) or not _KEY_NAME_RE.match(name):
        raise ValueError(
            "اسم المفتاح غير صالح: %r — الاسم حروف وأرقام و«-» "
            "و«_» فقط، ويبدأ بحرف أو رقم (حتى 64 حرفًا)"
            % (name,))


def _infer_provider(value):
    """خمّن المزوّد من صيغة القيمة، أو None إن لم تطابق أحدًا."""
    for provider, pattern in _PROVIDER_FORMAT_RES.items():
        if pattern.search(value):
            return provider
    return None


def _format_tester(provider, value):
    """الاختبار الافتراضي: تحقق صيغة فقط (بلا أي شبكة).

    يرجع (True/False، رسالة عربية). مزوّد غير معروف تُقبل
    قيمته إن كانت غير فارغة (لا صيغة معروفة تُقاس عليها) —
    والتحقق الحي من أي مزوّد يمرَّر عبر `tester` في
    `test_key`/`set_key`/`rotate_key`.
    """
    pattern = _PROVIDER_FORMAT_RES.get(provider)
    if pattern is None:
        return True, ("لا صيغة معروفة لمزوّد «%s» — قُبلت القيمة "
                      "بعد تحقق الصيغة العامة فقط (بلا استدعاء "
                      "شبكة)" % provider)
    if pattern.search(value):
        return True, ("صيغة المفتاح مطابقة لصيغة مزوّد «%s» "
                      "(فحص صيغة فقط — بلا استدعاء شبكة)"
                      % provider)
    return False, ("صيغة المفتاح غير مطابقة لصيغة مزوّد «%s» — "
                   "تحقق من المفتاح وأعد المحاولة" % provider)


def test_key(provider, value, tester=None):
    """اختبر مفتاحًا بلا حفظه؛ ارجع (نجح؟، رسالة عربية).

    tester قابل اختياري `tester(provider, value) -> bool` —
    استدعاء واحد صغير يحقنه المتصل (التحقق الحي من المزوّد،
    أو محاكاة المزوّد في الاختبارات). بلا tester يُستخدم
    تحقق الصيغة فقط. tester يرفض (False) أو يرمي يعني
    الفشل — ولا يُحفظ شيء هنا أبدًا.
    """
    if not isinstance(value, str) or not value.strip():
        return False, "المفتاح فارغ — ضع مفتاحًا غير فارغ"
    value = value.strip()
    if tester is None:
        return _format_tester(provider, value)
    try:
        ok = bool(tester(provider, value))
    except Exception as exc:  # أي عطل في الاختبار = رفض.
        return False, "رفض المزوّد المفتاح (%s): %s" % (provider, exc)
    if ok:
        return True, "قبل المزوّد المفتاح (%s)" % provider
    return False, "رفض المزوّد المفتاح (%s) — لم يُحفظ" % provider


def read_token_file(path):
    """اقرأ رمزًا/مفتاحًا من ملف (مسار `--token-file`).

    الرموز تُمرَّر عبر ملف أبدًا عبر سطر الأوامر — هذه الدالة
    هي المسار المصرّح به وحده لقراءة قيمة من القرص. ترفع
    KeyStoreError عند ملف غائب أو فارغ. القيمة تُرجع مقصوصة
    الأطراف (سطر جديد أخير وما يشبهه ليس جزءًا من المفتاح).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            value = fh.read().strip()
    except OSError:
        raise KeyStoreError(
            "ملف التوكن غير موجود أو لا يُقرأ: %s — مرّر مسار ملف "
            "يحمل التوكن عبر --token-file" % (path,))
    if not value:
        raise KeyStoreError(
            "ملف التوكن فارغ: %s — ضع التوكن في الملف وأعد المحاولة"
            % (path,))
    return value


def _load_store(directory=None):
    """اقرأ مخزن المفاتيح (داخلية)؛ ارجع {"keys": {...}}.

    ملف غائب = مخزن فارغ. JSON تالف أو بنية غير قاموس =
    KeyStoreError (لا يُسكت بإسقاط مفاتيح محفوظة).
    """
    path = keys_path(directory)
    if not os.path.isfile(path):
        return {"keys": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        raise KeyStoreError(
            "ملف مخزن المفاتيح تالف: %s — لا يُكتب فوقه حتى "
            "يُراجَع يدويًا (حتى لا تُفقد مفاتيح محفوظة)" % path)
    if not isinstance(data, dict) or not isinstance(
            data.get("keys", {}), dict):
        raise KeyStoreError(
            "بنية ملف مخزن المفاتيح غير صالحة: %s" % path)
    return {"keys": dict(data["keys"])}


def _save_store(store, directory=None):
    """احفظ المخزن ذريًا (ملف مؤقت + os.replace) بصلاحية 600،
    ومجلد المخزن 700. ترجع نسخة من المخزن المحفوظ."""
    directory = directory or keys_dir()
    os.makedirs(directory, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    path = keys_path(directory)
    tmp = path + ".tmp"
    payload = {"keys": store["keys"]}
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)
    return {"keys": dict(store["keys"])}


def _resolve_provider(name, value, provider):
    """حدّد المزوّد: صريح، أو اسم معروف، أو تخمين من الصيغة،
    أو «custom»."""
    if provider:
        return provider
    if name in _PROVIDER_FORMAT_RES:
        return name
    return _infer_provider(value) or "custom"


def set_key(name, value, provider=None, tester=None,
            directory=None):
    """احفظ مفتاحًا بعد اختبار واحد ناجح — ولا تحفظ غيره.

    يجري `test_key` أولًا؛ والمفتاح الذي يرفضه الاختبار لا
    يُحفظ (KeyTestError) ويبقى المخزن كما هو. حفظ اسم موجود
    يستبدل قيمته بعد الاختبار ويحافظ على تاريخ إضافته.
    ترجع إدخال السرد للمفتاح (اسم + مزوّد + وجود — بلا قيمة).
    """
    _validate_key_name(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("قيمة المفتاح فارغة — ضع مفتاحًا غير فارغ")
    value = value.strip()
    provider = _resolve_provider(name, value, provider)
    ok, message = test_key(provider, value, tester=tester)
    if not ok:
        raise KeyTestError(message)
    store = _load_store(directory)
    now = _now_cairo_iso()
    previous = store["keys"].get(name)
    entry = {"provider": provider,
             "value": value,
             "added_at": (previous.get("added_at") if previous
                          else now),
             "updated_at": now}
    if previous and previous.get("rotated_at"):
        entry["rotated_at"] = previous["rotated_at"]
    store["keys"][name] = entry
    _save_store(store, directory)
    return {"name": name, "provider": provider, "present": True,
            "added_at": entry["added_at"],
            "rotated_at": entry.get("rotated_at")}


def rotate_key(name, new_value, tester=None, directory=None):
    """دوّر مفتاحًا: اختبر الجديد أولًا، واكتبه فقط بعد نجاحه.

    القديم يبقى في المخزن حتى ينجح اختبار الجديد (فشل
    الاختبار = KeyTestError والمخزن بلا أي تغيير). اسم غائب
    = KeyStoreError. ترجع إدخال السرد للمفتاح (بلا قيمة).
    """
    _validate_key_name(name)
    if not isinstance(new_value, str) or not new_value.strip():
        raise ValueError("قيمة المفتاح الجديد فارغة — ضع مفتاحًا "
                         "غير فارغ")
    new_value = new_value.strip()
    store = _load_store(directory)
    previous = store["keys"].get(name)
    if previous is None:
        raise KeyStoreError(
            "لا يوجد مفتاح محفوظ باسم «%s» حتى يُدوَّر — أضفه أولًا"
            " عبر keys set" % name)
    provider = previous.get("provider") or "custom"
    ok, message = test_key(provider, new_value, tester=tester)
    if not ok:
        raise KeyTestError(message)
    now = _now_cairo_iso()
    store["keys"][name] = {"provider": provider,
                           "value": new_value,
                           "added_at": previous.get("added_at") or now,
                           "updated_at": now,
                           "rotated_at": now}
    _save_store(store, directory)
    return {"name": name, "provider": provider, "present": True,
            "added_at": store["keys"][name]["added_at"],
            "rotated_at": now}


def list_keys(directory=None):
    """اسرد المفاتيح: الأسماء والمزوّدون والوجود فقط.

    لا ترجع أي قيمة سرية أبدًا — كل إدخال {"name"،
    "provider"، "present": True، "added_at"، "rotated_at"}.
    مرتبة بالاسم.
    """
    store = _load_store(directory)
    entries = []
    for name in sorted(store["keys"]):
        entry = store["keys"][name]
        entries.append({"name": name,
                        "provider": entry.get("provider") or "custom",
                        "present": True,
                        "added_at": entry.get("added_at"),
                        "rotated_at": entry.get("rotated_at")})
    return entries


def has_key(name, directory=None):
    """هل يوجد مفتاح محفوظ بهذا الاسم؟ (وجود فقط — بلا قيمة)."""
    _validate_key_name(name)
    store = _load_store(directory)
    return name in store["keys"]


def mask_secret(value, visible=4):
    """قنّع قيمة سرية للتشخيص: أول N + «…» + آخر N.

    لا ترجع القيمة الكاملة أبدًا؛ وقيمة أقصر من 2N تُستبدل
    بنجوم بطولها. قيمة فارغة ترجع "".
    """
    if not value:
        return ""
    if len(value) <= 2 * visible:
        return "*" * len(value)
    return "%s…%s" % (value[:visible], value[-visible:])


def redact_text(text):
    """احجب قيمًا بصيغ مزودين معروفة داخل نص (للتشخيص/المخرجات).

    كل مطابقة تُستبدل بصيغتها المقنّعة عبر `mask_secret` —
    فلا تظهر قيمة كاملة في أي مخرج. نص بلا مطابقات يُرجع
    كما هو.
    """
    if not text:
        return ""
    redacted = text
    for pattern in (_GOOGLE_RE, _GROQ_RE, _OPENROUTER_RE,
                    _ANTHROPIC_RE, _OPENAI_RE, _ELEVENLABS_RE,
                    _HF_RE, _GITHUB_RE, _GITHUB_PAT_RE, _AWS_RE):
        redacted = pattern.sub(
            lambda m: mask_secret(m.group(0)), redacted)
    redacted = _BEARER_RE.sub(
        lambda m: "Bearer " + mask_secret(m.group(1)), redacted)
    return redacted


def diagnose_keys(directory=None):
    """أسطر تشخيص عربية عن المفاتيح المحفوظة — مقنّعة دائمًا.

    كل سطر يحمل الاسم والمزوّد والوجود والقيمة المقنّعة فقط؛
    ولا سطر يحمل قيمة كاملة أبدًا. ترجع قائمة أسطر.
    """
    store = _load_store(directory)
    lines = ["تشخيص المفاتيح: %d مفتاحًا محفوظًا "
             "(القيم مقنّعة ولا تُعرض كاملة أبدًا)"
             % len(store["keys"])]
    for name in sorted(store["keys"]):
        entry = store["keys"][name]
        lines.append("• %s (%s): موجود — %s"
                     % (name, entry.get("provider") or "custom",
                        mask_secret(entry.get("value") or "")))
    for provider in KNOWN_PROVIDERS:
        if provider not in store["keys"]:
            lines.append("• %s: غير موجود" % provider)
    return lines


__all__ = ["ALLOWLIST_VALUES", "REQUIRED_GITIGNORE", "SKIP_DIRS",
           "SKIP_EXTENSIONS", "scan_tree", "to_sarif",
           "check_gitignore", "KEYS_DIR_ENV", "KEYS_FILENAME",
           "KNOWN_PROVIDERS", "KeyTestError", "KeyStoreError",
           "keys_dir", "keys_path", "test_key", "read_token_file",
           "set_key", "rotate_key", "list_keys", "has_key",
           "mask_secret", "redact_text", "diagnose_keys"]
