#!/usr/bin/env python3
# Copyright 2026 aalhdydy550-ui (https://github.com/aalhdydy550-ui)
# Licensed under the PolyForm Noncommercial License 1.0.0 — see LICENSE.
# Commercial use requires a separate licence — see LICENSE-COMMERCIAL-TEMPLATE.md.
"""Generate a 720x1280 quote card in the «قصص وعبر» golden style.

Usage:
  python3 make_quote_cards.py --kind عبرة --text "النص" --out card.png [--source "المصدر"]
Arabic shaping is handled by Pillow's raqm layout (direction='rtl').
"""
import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 720, 1280
FONT_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
BADGE = Path(__file__).resolve().parent / "assets" / "qisas-logo-badge.png"

DARK = (74, 52, 16, 255)        # dark brown text
GOLD_DARK = (122, 86, 20, 255)  # dark gold lines
GOLD_MID = (176, 138, 58, 255)


def gold_background():
    """Vertical gold gradient with a soft central glow."""
    img = Image.new("RGB", (W, H))
    px = img.load()
    top = (138, 104, 34)
    mid = (245, 227, 176)
    bot = (122, 92, 34)
    for y in range(H):
        if y < H // 2:
            t = y / (H // 2)
            c = tuple(int(top[i] + (mid[i] - top[i]) * t) for i in range(3))
        else:
            t = (y - H // 2) / (H // 2)
            c = tuple(int(mid[i] + (bot[i] - mid[i]) * t) for i in range(3))
        for x in range(W):
            px[x, y] = c
    # soft radial glow in the centre
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-220, 220, W + 220, 1060), fill=48)
    img = Image.composite(
        Image.new("RGB", (W, H), (255, 244, 205)), img, glow)
    return img.convert("RGBA")


def wrap_text(draw, text, font, max_width):
    """Wrap Arabic text by words so each line fits max_width."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font, direction="rtl", language="ar") <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_card(kind, text, out_path, source=""):
    # Noto Naskh lacks the em/en dash glyphs; normalise them to a hyphen.
    text = text.replace("—", "-").replace("–", "-")
    source = source.replace("—", "-").replace("–", "-")
    img = gold_background()
    d = ImageDraw.Draw(img)
    # double border frame
    d.rectangle((34, 34, W - 34, H - 34), outline=GOLD_DARK, width=4)
    d.rectangle((48, 48, W - 48, H - 48), outline=GOLD_MID, width=2)
    # logo badge, top centre
    if BADGE.exists():
        badge = Image.open(BADGE).convert("RGBA").resize((150, 150), Image.LANCZOS)
        img.paste(badge, ((W - 150) // 2, 84), badge)
        d = ImageDraw.Draw(img)
    # kind title
    title_font = ImageFont.truetype(FONT_BOLD, 66)
    ty = 260
    d.text((W // 2, ty), kind, font=title_font, fill=DARK,
           anchor="ma", direction="rtl", language="ar")
    # ornament divider
    dy = ty + 108
    d.line((W // 2 - 90, dy, W // 2 + 90, dy), fill=GOLD_DARK, width=3)
    d.ellipse((W // 2 - 7, dy - 7, W // 2 + 7, dy + 7), fill=GOLD_DARK)
    # main text, centred block
    body_font = ImageFont.truetype(FONT_BOLD, 54)
    lines = wrap_text(d, text, body_font, 580)
    line_h = 84
    block_h = line_h * len(lines)
    y0 = 480 + max(0, (360 - block_h) // 2)
    for i, line in enumerate(lines):
        d.text((W // 2, y0 + i * line_h), line, font=body_font, fill=DARK,
               anchor="ma", direction="rtl", language="ar")
    # source line (e.g. verse reference)
    if source:
        src_font = ImageFont.truetype(FONT_REG, 38)
        d.text((W // 2, y0 + block_h + 30), source, font=src_font, fill=GOLD_DARK,
               anchor="ma", direction="rtl", language="ar")
    # page name, bottom
    foot_font = ImageFont.truetype(FONT_BOLD, 40)
    d.text((W // 2, H - 150), "قصص وعبر", font=foot_font, fill=DARK,
           anchor="ma", direction="rtl", language="ar")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=95)
    print(f"saved {out} ({len(lines)} lines)")
    return out


def main():
    ap = argparse.ArgumentParser(description="بطاقة اقتباس ذهبية 720×1280")
    ap.add_argument("--kind", required=True, help="عبرة / حكمة / موعظة")
    ap.add_argument("--text", required=True, help="نص البطاقة")
    ap.add_argument("--out", required=True, help="مسار الصورة الناتجة")
    ap.add_argument("--source", default="", help="سطر مصدر صغير تحت النص")
    a = ap.parse_args()
    make_card(a.kind, a.text, a.out, a.source)


if __name__ == "__main__":
    sys.exit(main())
