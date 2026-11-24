#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""تنظيف الصوت الخام بقص الصمت عبر Auto-Editor (خطوة اختيارية).

يستخدم ثنائي Auto-Editor في بيئة المشروع الخاصة
(`.venv-autoeditor/bin/auto-editor`، الإصدار 29.3.1) أو أي
`auto-editor` على PATH. يقص الصمت الطويل في بداية/نهاية/وسط
الصوت الخام قبل التجميع — سريع جدًا (ملف 10 ثوانٍ في ~0.1 ث).

قاعدة صارمة: لا يُستخدم أبدًا على السرد النهائي
(`narration/` و`narration-male/`) لأن وقفات الصمت فيه مقصودة
دراميًا وتُبنى عليها الكتابة المتزامنة (ASS). محاولة تمرير
ملف سرد نهائي تُرفض إلا مع `--force` الصريح.
"""
import os
import shutil
import subprocess
import time


class AutoEditError(Exception):
    """خطأ في تنظيف الصوت (رسالته عربية جاهزة للعرض)."""


FINAL_NARRATION_DIRS = ("narration", "narration-male")


def is_final_narration_path(path):
    """هل هذا مسار سرد نهائي؟ (أي مكوّن من مكوناته مجلد سرد)."""
    parts = os.path.normpath(str(path)).split(os.sep)
    return any(p in FINAL_NARRATION_DIRS for p in parts)


def find_auto_editor(studio_dir=None):
    """ابحث عن ثنائي auto-editor: بيئة المشروع أولًا ثم PATH."""
    here = studio_dir or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    venv_bin = os.path.join(here, ".venv-autoeditor", "bin", "auto-editor")
    if os.path.isfile(venv_bin):
        return venv_bin
    on_path = shutil.which("auto-editor")
    if on_path:
        return on_path
    raise AutoEditError(
        "ثنائي auto-editor غير موجود — ثبّته في بيئة المشروع:\n"
        "  python3 -m venv .venv-autoeditor && "
        ".venv-autoeditor/bin/pip install auto-editor")


def build_command(editor_bin, input_path, output_path,
                  threshold=0.02, margin=0.2):
    """ابنِ أمر auto-editor (دالة نقية — للاختبار)."""
    return [editor_bin, input_path,
            "--edit", "audio:threshold=%s" % threshold,
            "--margin", "%ss" % margin,
            "--output", output_path, "--no-open"]


def clean_audio(input_path, output_path, threshold=0.02, margin=0.2,
                force=False, studio_dir=None, timeout=300):
    """قص صمت الصوت الخام. يرجع قاموس النتيجة.

    يرفع AutoEditError عند: ملف دخل مفقود، عتبة/هامش خارج النطاق،
    سرد نهائي بلا --force، ثنائي مفقود، أو فشل auto-editor.
    """
    if not os.path.isfile(input_path):
        raise AutoEditError("ملف الصوت غير موجود: %s" % input_path)
    if not (0.0 < float(threshold) < 1.0):
        raise AutoEditError("العتبة (threshold) يجب أن تكون بين 0 و1: %s"
                            % threshold)
    if float(margin) < 0:
        raise AutoEditError("الهامش (margin) لا يمكن أن يكون سالبًا: %s"
                            % margin)
    if not force and is_final_narration_path(input_path):
        raise AutoEditError(
            "هذا ملف سرد نهائي — وقفات الصمت فيه مقصودة دراميًا "
            "والكتابة المتزامنة مبنية عليها. التنظيف مرفوض هنا؛ "
            "استخدم --force فقط إن كنت متأكدًا مما تفعل.")
    editor_bin = find_auto_editor(studio_dir)
    cmd = build_command(editor_bin, input_path, output_path,
                        threshold, margin)
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AutoEditError("انتهت مهلة تنظيف الصوت (%d ثانية)" % timeout)
    except OSError as e:
        raise AutoEditError("تعذر تشغيل auto-editor: %s" % e)
    if result.returncode != 0:
        tail = ((result.stderr or "") + (result.stdout or ""))[-1200:]
        raise AutoEditError("فشل auto-editor (رمز الخروج %d):\n%s"
                            % (result.returncode, tail))
    if not os.path.isfile(output_path):
        raise AutoEditError("انتهى auto-editor دون إنشاء ملف الخرج: %s"
                            % output_path)
    return {"output": output_path,
            "seconds": round(time.time() - t0, 1),
            "size_bytes": os.path.getsize(output_path)}
