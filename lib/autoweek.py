#!/usr/bin/env python3
"""الأسبوع التلقائي — `long-video --auto-week`: اختيار قصص الأسبوع.

يقرأ قصص الأسبوع من ملف الطابور: الأسطر المؤرخة في أقسام
«المنشور» و«المجدول» و«المخطط له» (عنوان عريض + تاريخ
`YYYY-MM-DD HH:MM`) الواقعة في نافذة الأيام السبعة الأخيرة
(افتراضيًا) والتي حلّ موعدها فعلًا (لا مواعيد مستقبلية).
«الأفضل» هنا = قصص الأسبوع المنشورة بالترتيب الزمني — لا ترتيب
بالمشاهدات (يحتاج Analytics API، غير متاح؛ انظر `analyze`).

كل قصة تُحوَّل إلى مصدر فصل لـlong-video:
1. مشروع OpenMontage جاهز (عبر خريطة KNOWN_PROJECTS أو مجلد
   مشروع بنفس slug القصة) → فصل `story`/`project`.
2. مجلد فصل مُعدّ تحت `runs/*/chapters/<slug>` (title.txt +
   سرد + صور) → فصل `chapter-dir`.
3. بلا مصدر → تُتخطى مع السبب.

أقل من قصتين صالحتين = خطأ واضح يسمّي كل قصة وما ينقصها.
"""
import datetime
import glob
import os
import re

DATED_SECTIONS = ("المنشور", "المجدول", "المخطط له")
DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})")
ENTRY_RE = re.compile(
    r"^\s*(?:\d+\.|-)\s+"
    r"(?:\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+)?\*\*(.+?)\*\*")

# كلمة مميزة من العنوان → slug الأصول (مشروع OpenMontage أو مجلد فصل).
TITLE_SLUGS = {
    "العنزة": "anza",
    "النجار": "najjar",
    "حماتي": "hamati",
    "عائشة": "aisha",
    "منقشة": "manqasha",
    "حذاء": "hizaa",
    "أبو حنيفة": "abu-hanifa",
    "الأصمعي": "asmai",
    "صنائع المعروف": "sanaea",
    "عجائب الصدقة": "ajaib-sadaqa",
}


class AutoWeekError(Exception):
    """خطأ في اختيار قصص الأسبوع (رسالته عربية)."""


def _slug_for_title(title):
    for keyword, slug in TITLE_SLUGS.items():
        if keyword in title:
            return slug
    return None


def parse_dated_stories(queue_path):
    """اقرأ القصص المؤرخة من أقسام المنشور/المجدول/المخطط له.

    يرجع قائمة {"title", "date"} (datetime) مرتبة زمنيًا — تاريخ
    كل قصة هو أول تاريخ `YYYY-MM-DD HH:MM` في مدخلها.
    """
    if not os.path.isfile(queue_path):
        raise AutoWeekError("ملف الطابور غير موجود: %s" % queue_path)
    with open(queue_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    stories = []
    section = None
    current = None

    def flush():
        nonlocal current
        if current is not None:
            stories.append(current)
        current = None

    for line in lines:
        if line.startswith("## "):
            flush()
            heading = line.strip()
            section = heading if any(s in heading for s in DATED_SECTIONS) \
                else None
            continue
        if section is None:
            continue
        m = ENTRY_RE.match(line.strip())
        if m:
            flush()
            current = {"title": m.group(1).strip(), "text": line,
                       "section": section}
            continue
        if current is not None:
            current["text"] += "\n" + line
    flush()
    out = []
    for s in stories:
        dm = DATE_RE.search(s["text"])
        if not dm:
            continue
        year, month, day, hour, minute = (int(x) for x in dm.groups())
        try:
            date = datetime.datetime(year, month, day, hour, minute)
        except ValueError:
            continue
        out.append({"title": s["title"], "date": date,
                    "section": s["section"]})
    out.sort(key=lambda s: s["date"])
    return out


def _chapter_dir_for_slug(runs_dir, slug, title):
    """ابحث عن مجلد فصل جاهز لـslug تحت runs/*/chapters/.

    يطابق اسم المجلد (= slug) أو محتوى title.txt (فيه الكلمة
    المميزة من العنوان). يرجع المسار أو None.
    """
    keyword = None
    for k in TITLE_SLUGS:
        if k in title:
            keyword = k
            break
    for path in sorted(glob.glob(os.path.join(runs_dir, "*", "chapters",
                                               "*"))):
        if not os.path.isdir(path):
            continue
        if os.path.basename(path) == slug:
            return path
        title_path = os.path.join(path, "title.txt")
        if keyword and os.path.isfile(title_path):
            try:
                with open(title_path, encoding="utf-8") as f:
                    if keyword in f.read():
                        return path
            except OSError:
                continue
    return None


def resolve_chapter_source(cfg, title, known_projects):
    """حوّل عنوان قصة إلى مصدر فصل long-video أو (None, السبب).

    known_projects: خريطة KNOWN_PROJECTS (رقم → (slug, مشروع)).
    يرجع (kind, value) حيث kind في (story, project, chapter-dir).
    """
    slug = _slug_for_title(title)
    if not slug:
        return None, ("لا مصدر فصل معروف لهذه القصة — جهّز مشروع "
                      "OpenMontage أو مجلد فصل أولًا")
    known_slugs = {s for (_, (s, _)) in known_projects.items()}
    projects_dir = (cfg.get("openmontage") or {}).get("projects_dir")
    if slug in known_slugs:
        return "story", slug
    if projects_dir and os.path.isdir(os.path.join(
            os.path.expanduser(projects_dir), slug)):
        return "project", slug
    runs_dir = (cfg.get("paths") or {}).get("runs_dir")
    if runs_dir:
        chapter_dir = _chapter_dir_for_slug(
            os.path.expanduser(runs_dir), slug, title)
        if chapter_dir:
            return "chapter-dir", chapter_dir
    return None, ("بلا مصدر فصل — لا مشروع OpenMontage باسم %s ولا "
                  "مجلد فصل تحت runs/*/chapters/" % slug)


def pick_week_stories(queue_path, cfg, known_projects, since=None,
                      today=None):
    """اختر قصص الأسبوع الصالحة كفصول.

    since: بداية النافذة (date) — افتراضيًا: اليوم − 6 أيام.
    today: نهاية النافذة (datetime) — افتراضيًا: الآن.
    يرجع (usable, skipped): usable قائمة {"title","date","type",
    "source"}، وskipped قائمة {"title","date","reason"}.
    يرفع AutoWeekError إن قلّ الصالح عن قصتين، مسميًا النواقص.
    """
    now = today if today is not None else datetime.datetime.now()
    if isinstance(now, datetime.datetime):
        now_date = now.date()
    else:
        # today قد يكون date — حوّله إلى نهاية اليوم للمقارنة.
        now_date = now
        now = datetime.datetime.combine(now, datetime.time.max)
    if since is None:
        since = now_date - datetime.timedelta(days=6)
    elif isinstance(since, datetime.datetime):
        since = since.date()
    dated = parse_dated_stories(queue_path)
    usable, skipped = [], []
    seen_titles = set()
    for s in dated:
        if s["date"].date() < since or s["date"] > now:
            continue
        if s["title"] in seen_titles:
            skipped.append({"title": s["title"], "date": s["date"],
                            "reason": "عنوان مكرر — أُخذت النسخة الأولى"})
            continue
        kind, value = resolve_chapter_source(cfg, s["title"],
                                             known_projects)
        if kind:
            seen_titles.add(s["title"])
            usable.append({"title": s["title"], "date": s["date"],
                           "type": kind, "source": value})
        else:
            skipped.append({"title": s["title"], "date": s["date"],
                            "reason": value})
    if len(usable) < 2:
        lines = ["قصص الأسبوع الصالحة كفصول: %d (المطلوب 2 على الأقل)"
                 % len(usable)]
        for u in usable:
            lines.append("  جاهزة: %s (%s)"
                         % (u["title"], u["date"].strftime("%Y-%m-%d")))
        for s in skipped:
            lines.append("  ناقصة: %s (%s) — %s"
                         % (s["title"],
                            s["date"].strftime("%Y-%m-%d"), s["reason"]))
        if not usable and not skipped:
            lines.append("  لا قصص مؤرخة في النافذة (%s إلى %s)"
                         % (since, now.strftime("%Y-%m-%d")))
        raise AutoWeekError("\n".join(lines))
    return usable, skipped
