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
"""
import fnmatch
import math
import os
import re

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
