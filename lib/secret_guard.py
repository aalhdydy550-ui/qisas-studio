#!/usr/bin/env python3
"""حارس تسرّب الأسرار — جولة v0.1.37 (مقترح tinker رقم 1).

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
"""
import fnmatch
import math
import os
import re

# --- قائمة السماح الصريحة (قيم عامة معلنة) ---
ALLOWLIST_VALUES = {
    # رقم فودافون كاش للدفع اليدوي — معلن في README والصفحة.
    "01023468196",
    # معرّف صفحة فيسبوك «قصص وعبر» — عام.
    "1048148471706586",
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
_PEM_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
# سلسلة مقتبسة طويلة مختلطة الحالة والأرقام (ليست هكس خالصًا
# — بصمات SHA الأربعينية هكس خالص وتُستثنى عمدًا).
_LONG_STRING_RE = re.compile(r"['\"]([A-Za-z0-9_\-/+=]{32,})['\"]")

# قيم اختبار/أمثلة لا تُعدّ أسرارًا أبدًا.
_FIXTURE_MARKERS = (
    "test", "fake", "example", "placeholder", "your-",
    "1234567890", "xxx", "change-me", "dummy", "sample",
)


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
        findings.append({
            "file": rel_path,
            "line": lineno,
            "pattern": kind,
            "value": value[:24] + ("…" if len(value) > 24 else ""),
        })

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
    for pattern, kind in ((_HF_RE, "huggingface"),
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
    """امسح الشجرة؛ ارجع قائمة إصابات (فارغة = نظيف)."""
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
            if _is_ignored(rel, patterns):
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
