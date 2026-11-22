#!/usr/bin/env python3
"""اختبار A/B — `studio.py ab` و`studio.py ab-results`.

لفيديو واحد: يولّد هوكين مختلفين ومصغرتين مختلفتين، ويسجّل
الزوج في `runs/ab-*.json` (الفيديو، الهوك أ/ب، المصغرة أ/ب،
تاريخ النشر). وبعد نشر النسختين يقارن `ab-results` مشاهداتهما
عبر `analyze` (فيسبوك + يوتيوب).

صراحة مهمة (تُطبع مع كل أمر): فيسبوك ويوتيوب بلا اختبار A/B
أصلي للريلز/الشورتس — الأداة تولّد النسختين وتتتبع المقارنة
بين منشورين منفصلين (عنوان النشر لكل نسخة هو هوكها، فيُميَّز
المنشوران بنص الهوك في الكابشن/العنوان). أي نسخة غير منشورة
بعد تُطبع «غير منشورة بعد» — بلا أرقام مخترعة أبدًا.
"""
import json
import os
import re
import subprocess
import time

from lib import analyze
from lib import ideas as ideas_lib
from lib import thumbnail

AB_NOTE = ("تنبيه: فيسبوك ويوتيوب بلا اختبار A/B أصلي للريلز/"
           "الشورتس — هذه الأداة تولّد النسختين وتتتبع المقارنة "
           "بين منشورين منفصلين؛ انشر كل نسخة بعنوانها (هوكها) "
           "ثم قارن بـ ab-results.")

_LOCAL_HOOK_B_SUFFIX = " — النهاية هتصدمك"


def _norm(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def suggest_hooks(title, chat_fn=None):
    """اقترح هوكين مختلفين للعنوان: النموذج أولًا، وبديل محلي
    (العنوان نفسه + صيغة سؤال) عند غياب الشبكة. يرجع
    (هوك أ، هوك ب، المصدر)."""
    title = _norm(title)
    if chat_fn is not None:
        prompt = (
            "لصفحة فيسبوك «قصص وعبر» باللهجة المصرية: اقترح هوكين "
            "مختلفين لفيديو قصة بعنوان «%s». كل هوك جملة واحدة "
            "صادمة تُقال في أول ثانيتين ولا تبدأ برقم أبدًا. اكتب "
            "الهوكين في سطرين فقط، سطر لكل هوك، بلا أي نص آخر."
            % title)
        try:
            text = chat_fn(prompt)
            lines = [l.strip() for l in text.splitlines()
                     if l.strip()]
            hooks = [l for l in lines
                     if ideas_lib.valid_hook(l)]
            if len(hooks) >= 2 and hooks[0] != hooks[1]:
                return hooks[0], hooks[1], "omniroute"
        except Exception:
            pass
    return title, title + _LOCAL_HOOK_B_SUFFIX, "local"


def create_ab(video, hook_a, hook_b, out_dir, title=None,
              thumbnail_fn=None, duration_fn=None):
    """ولّد مصغرتين (أ عند 35% من المدة، ب عند 65%) وسجّل
    الزوج في ab-<وقت>.json داخل out_dir. يرجع السجل.
    thumbnail_fn(video, hook, out, at_seconds) -> مسار؛
    duration_fn(video) -> المدة بالثواني."""
    video = os.path.abspath(os.path.expanduser(video))
    if not os.path.isfile(video):
        raise ValueError("ملف الفيديو غير موجود: %s" % video)
    hook_a, hook_b = _norm(hook_a), _norm(hook_b)
    if not hook_a or not hook_b:
        raise ValueError("الهوكان مطلوبان (أ و ب)")
    # نفس قواعد الأسلوب في ideas: بلا رقم في البداية وبلا وسوم
    # ASS و≤140 حرفًا — الهوك يُستخدم عنوان نشر أيضًا، فوسم
    # مثل {\fs200} كان يظهر في الكابشن/العنوان حرفيًا.
    if not ideas_lib.valid_hook(hook_a) \
            or not ideas_lib.valid_hook(hook_b):
        raise ValueError("الهوك يجب أن يكون جملة واحدة صادمة "
                         "بلا رقم في البداية وبلا وسوم (≤140 حرفًا)")
    if hook_a == hook_b:
        raise ValueError("الهوكان متطابقان — اختبار A/B يحتاج "
                         "هوكين مختلفين")
    duration_fn = duration_fn or thumbnail.video_duration
    thumbnail_fn = thumbnail_fn or thumbnail.make_thumbnail
    duration = duration_fn(video)
    ts = time.strftime("%Y%m%d-%H%M%S")
    ab_dir = os.path.join(out_dir, "ab-%s" % ts)
    os.makedirs(ab_dir, exist_ok=True)
    thumb_a = os.path.join(ab_dir, "thumb-a.jpg")
    thumb_b = os.path.join(ab_dir, "thumb-b.jpg")
    thumbnail_fn(video, hook_a, thumb_a,
                 at_seconds=round(duration * 0.35, 1))
    thumbnail_fn(video, hook_b, thumb_b,
                 at_seconds=round(duration * 0.65, 1))
    record = {
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "video": video,
        "title": title or "",
        "duration": round(duration, 1),
        "hook_a": hook_a,
        "hook_b": hook_b,
        "thumb_a": thumb_a,
        "thumb_b": thumb_b,
        "publish_title_a": hook_a,
        "publish_title_b": hook_b,
        "note": AB_NOTE,
    }
    record_path = os.path.join(ab_dir, "ab-%s.json" % ts)
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    record["record_path"] = record_path
    return record


def fetch_fb_posts(facebook_bin, page_id, limit=10, run=None):
    """آخر منشورات الصفحة (حتى limit) كمقاييس موحّدة عبر
    analyze._fb_entry_metrics. يرجع (قائمة، ملاحظة)."""
    runner = run or (lambda cmd, **kw: subprocess.run(
        cmd, capture_output=True, text=True, timeout=120, **kw))
    try:
        proc = runner([facebook_bin, "pages", "posts", "list",
                       "--page-id", str(page_id),
                       "--limit", str(limit)])
    except FileNotFoundError:
        return [], "facebook-cli غير متاح"
    except subprocess.TimeoutExpired:
        return [], "انتهت مهلة قراءة منشورات فيسبوك"
    if proc.returncode != 0:
        return [], ("فشل قراءة منشورات فيسبوك (رمز الخروج %d)"
                    % proc.returncode)
    try:
        data = json.loads(proc.stdout or "")
    except ValueError:
        return [], "مخرجات facebook-cli ليست JSON صالحًا"
    entries = []
    for raw in (data.get("results") or []):
        try:
            entries.append(analyze._fb_entry_metrics(raw))
        except Exception:
            continue
    return entries, None


def fetch_yt_uploads(channel_id, limit=10, run=None):
    """آخر فيديوهات القناة (حتى limit): {title, views,
    video_id}. يرجع (قائمة، ملاحظة)."""
    if not channel_id:
        return [], "معرّف قناة يوتيوب غير مضبوط"
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{10,}", channel_id):
        return [], "معرّف قناة يوتيوب غير صالح: %s" % channel_id
    import urllib.parse
    playlist_url = ("https://www.youtube.com/playlist?"
                    + urllib.parse.urlencode(
                        {"list": "UU" + channel_id[2:]}))
    try:
        playlist = analyze._run_ytdlp(
            ["--flat-playlist", "-J", playlist_url], run=run)
    except (analyze.AnalyzeError, FileNotFoundError) as e:
        return [], "تعذرت قراءة قائمة رفع يوتيوب: %s" % e
    except subprocess.TimeoutExpired:
        return [], "انتهت مهلة قراءة قائمة رفع يوتيوب"
    out = []
    for entry in (playlist.get("entries") or [])[:limit]:
        out.append({"title": entry.get("title") or "",
                    "views": entry.get("view_count"),
                    "video_id": entry.get("id") or ""})
    return out, None


def match_variant(entries, needle, text_key):
    """أول منشور يحتوي نص الهوك (بعد الطي). None إن لم يوجد."""
    needle = _norm(needle)
    if not needle:
        return None
    for entry in entries:
        if needle in _norm(entry.get(text_key) or ""):
            return entry
    return None


def compare_ab(record, fb_entries, yt_entries):
    """قارن النسختين: مشاهدات كل نسخة على كل منصة + المجموع +
    الفائز. نسخة غير موجودة في القوائم = غير منشورة بعد."""
    result = {"record": record["record_path"]
              if "record_path" in record else None,
              "variants": {}, "winner": None, "decisive": False}
    fb_a = match_variant(fb_entries, record["hook_a"], "caption")
    fb_b = match_variant(fb_entries, record["hook_b"], "caption")
    yt_a = match_variant(yt_entries, record["hook_a"], "title")
    yt_b = match_variant(yt_entries, record["hook_b"], "title")
    if fb_a is not None and fb_a is fb_b:
        fb_b = None
    if yt_a is not None and yt_a is yt_b:
        yt_b = None
    for key, fb, yt in (("a", fb_a, yt_a), ("b", fb_b, yt_b)):
        fb_views = fb.get("views") if fb else None
        yt_views = yt.get("views") if yt else None
        total = sum(v for v in (fb_views, yt_views)
                    if isinstance(v, (int, float)))
        result["variants"][key] = {
            "hook": record["hook_a" if key == "a" else "hook_b"],
            "facebook_views": fb_views,
            "youtube_views": yt_views,
            "total_views": total if (fb_views is not None
                                     or yt_views is not None) else None,
            "published": fb is not None or yt is not None,
        }
    a = result["variants"]["a"]
    b = result["variants"]["b"]
    if a["published"] and b["published"] \
            and a["total_views"] is not None \
            and b["total_views"] is not None:
        result["decisive"] = True
        if a["total_views"] > b["total_views"]:
            result["winner"] = "a"
        elif b["total_views"] > a["total_views"]:
            result["winner"] = "b"
        else:
            result["winner"] = "tie"
    return result


def format_comparison(record, comparison):
    """نص عربي لنتيجة المقارنة."""
    lines = ["== نتيجة اختبار A/B ==",
             "الفيديو: %s" % record["video"],
             "أ: %s" % record["hook_a"],
             "ب: %s" % record["hook_b"],
             ""]
    for key, label in (("a", "أ"), ("b", "ب")):
        v = comparison["variants"][key]
        if not v["published"]:
            lines.append("نسخة %s: غير منشورة بعد — انشرها بعنوان "
                         "هوكها ثم أعد ab-results" % label)
            continue
        lines.append("نسخة %s: فيسبوك %s — يوتيوب %s — المجموع %s"
                     % (label,
                        analyze.format_value(v["facebook_views"]),
                        analyze.format_value(v["youtube_views"]),
                        analyze.format_value(v["total_views"])))
    lines.append("")
    if not comparison["decisive"]:
        lines.append("النتيجة: غير حاسمة بعد — انشر النسختين "
                     "وانتظر مشاهداتهما.")
    elif comparison["winner"] == "tie":
        lines.append("النتيجة: تعادل — الهوكان متساويان حتى الآن.")
    else:
        win = comparison["winner"]
        lines.append("الفائز حتى الآن: نسخة %s (%s)"
                     % ("أ" if win == "a" else "ب",
                        comparison["variants"][win]["hook"]))
    lines.append("")
    lines.append(AB_NOTE)
    return "\n".join(lines) + "\n"
