#!/usr/bin/env python3
"""Generate a profile picture for @curseorcure3, matching the dark-facts brand.

Free, local, Pillow-only -- reuses the same bundled fonts as the post cards.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(__file__).resolve().parent.parent / "content_pipeline" / "fonts"
FONT_BLACK = FONT_DIR / "Anton-Regular.ttf"
FONT_BOLD = FONT_DIR / "Ubuntu-Bold.ttf"

BG_TOP = (20, 8, 10)
BG_BOTTOM = (5, 2, 3)
ACCENT_RED = (200, 30, 40)
ACCENT_GOLD = (196, 154, 74)


def vertical_gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h), top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def make_profile_pic(out_path, size=1080):
    img = vertical_gradient(size, size, BG_TOP, BG_BOTTOM)
    draw = ImageDraw.Draw(img)

    # Outer ring, split red/gold to represent "curse or cure"
    margin = 40
    ring_width = 34
    box = [margin, margin, size - margin, size - margin]
    draw.arc(box, start=-90, end=90, fill=ACCENT_RED, width=ring_width)
    draw.arc(box, start=90, end=270, fill=ACCENT_GOLD, width=ring_width)

    # Central monogram
    mono_font = ImageFont.truetype(str(FONT_BLACK), 340)
    text = "C"
    bbox = draw.textbbox((0, 0), text, font=mono_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1] - 60), text, font=mono_font, fill=(240, 240, 240))

    # Tagline
    tag_font = ImageFont.truetype(str(FONT_BOLD), 58)
    tagline = "DARK FACTS"
    bbox2 = draw.textbbox((0, 0), tagline, font=tag_font)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((size - tw2) / 2, size / 2 + 170), tagline, font=tag_font, fill=(210, 210, 210))

    img.save(out_path, quality=95)
    print(f"Wrote {out_path} ({size}x{size})")


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent
    make_profile_pic(out_dir / "profile_pic.png")
