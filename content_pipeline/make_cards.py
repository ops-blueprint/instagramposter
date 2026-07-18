#!/usr/bin/env python3
"""Render fact dicts (from fetch_facts.py) into branded fact-card images.

Uses only local Pillow rendering + macOS system fonts. No paid APIs.
Output size: 1080x1350 (4:5), the aspect ratio Facebook's feed favors.
"""
import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
W, H = 1080, 1350

# Bundled fonts (not OS system fonts) so rendering is identical on macOS and on
# GitHub Actions' Ubuntu runners. Anton and Ubuntu are free, open-license (OFL/UFL).
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_BOLD = FONT_DIR / "Ubuntu-Bold.ttf"
FONT_BLACK = FONT_DIR / "Anton-Regular.ttf"
FONT_REGULAR = FONT_DIR / "Ubuntu-Regular.ttf"

# Palette per region so the feed doesn't look monotonous, but stays consistent as a brand
PALETTE = {
    "USA":       {"bg": (17, 24, 39), "accent": (239, 68, 68)},
    "UK":        {"bg": (15, 23, 42), "accent": (59, 130, 246)},
    "Australia": {"bg": (10, 30, 40), "accent": (250, 204, 21)},
    "Europe":    {"bg": (24, 20, 40), "accent": (168, 85, 247)},
    "World":     {"bg": (20, 20, 20), "accent": (34, 197, 94)},
    "Trending":  {"bg": (28, 22, 12), "accent": (245, 158, 11)},
    "Viral":     {"bg": (30, 12, 18), "accent": (244, 63, 94)},
}


def fit_text(draw, text, font_path, max_width, max_height, start_size=64, min_size=32):
    size = start_size
    while size >= min_size:
        font = ImageFont.truetype(str(font_path), size)
        avg_char_w = font.getlength("n")
        wrap_width = max(10, int(max_width / max(avg_char_w, 1)))
        lines = textwrap.wrap(text, width=wrap_width)
        line_height = font.getbbox("Ag")[3] + 14
        total_height = line_height * len(lines)
        if total_height <= max_height:
            return font, lines, line_height
        size -= 2
    font = ImageFont.truetype(str(font_path), min_size)
    wrap_width = max(10, int(max_width / max(font.getlength("n"), 1)))
    lines = textwrap.wrap(text, width=wrap_width)
    line_height = font.getbbox("Ag")[3] + 14
    return font, lines, line_height


def draw_gradient(img, top_color, bottom_color):
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def make_card(fact, out_path, page_handle="@YourPage"):
    colors = PALETTE.get(fact["region"], PALETTE["World"])
    bg = colors["bg"]
    accent = colors["accent"]
    top = tuple(min(255, c + 20) for c in bg)
    bottom = tuple(max(0, c - 15) for c in bg)

    img = Image.new("RGB", (W, H), bg)
    draw_gradient(img, top, bottom)
    draw = ImageDraw.Draw(img)

    margin = 80

    # accent bar top
    draw.rectangle([0, 0, W, 14], fill=accent)

    # Eyebrow: region + suffix (plain text only -- emoji glyphs render as tofu
    # boxes with our bundled fonts, so region is spelled out instead of using flags)
    eyebrow_suffix = fact.get("eyebrow_suffix", "ON THIS DAY")
    eyebrow_font = ImageFont.truetype(str(FONT_BOLD), 40)
    eyebrow = f"{fact['region'].upper()} · {eyebrow_suffix}"
    draw.text((margin, 90), eyebrow, font=eyebrow_font, fill=accent)

    has_year = bool(fact.get("year"))
    if has_year:
        # Year, big
        year_font = ImageFont.truetype(str(FONT_BLACK), 130)
        draw.text((margin, 150), str(fact["year"]), font=year_font, fill=(255, 255, 255))
        # divider
        draw.rectangle([margin, 330, margin + 120, 336], fill=accent)
        area_top = 400
    else:
        # No year (general facts) -- skip that block, divider sits right under the eyebrow
        draw.rectangle([margin, 170, margin + 120, 176], fill=accent)
        area_top = 240

    # Fact body text, auto-fit and vertically centered in the space below the divider
    area_bottom = H - 160
    body_font, lines, line_height = fit_text(
        draw, fact["text"], FONT_REGULAR,
        max_width=W - 2 * margin, max_height=area_bottom - area_top, start_size=72, min_size=34
    )
    block_height = line_height * len(lines)
    y = area_top + max(0, (area_bottom - area_top - block_height) // 2)
    for line in lines:
        draw.text((margin, y), line, font=body_font, fill=(240, 240, 240))
        y += line_height

    # Footer: page handle + call to action
    footer_font = ImageFont.truetype(str(FONT_BOLD), 34)
    cta_font = ImageFont.truetype(str(FONT_REGULAR), 30)
    draw.rectangle([0, H - 130, W, H], fill=(0, 0, 0))
    draw.text((margin, H - 100), page_handle, font=footer_font, fill=accent)
    draw.text((margin, H - 55), "Follow for daily facts", font=cta_font, fill=(220, 220, 220))

    img.save(out_path, quality=95)
    return out_path


REEL_W, REEL_H = 1080, 1920


def make_card_vertical(fact, out_path, page_handle="@YourPage"):
    """9:16 version for Reels. Keeps text clear of where Facebook's own Reels UI
    (caption, follow button, like/comment/share icons) overlays the bottom/right
    edges when actually played back in the app."""
    colors = PALETTE.get(fact["region"], PALETTE["World"])
    bg = colors["bg"]
    accent = colors["accent"]
    top = tuple(min(255, c + 20) for c in bg)
    bottom = tuple(max(0, c - 15) for c in bg)

    img = Image.new("RGB", (REEL_W, REEL_H), bg)
    draw_gradient_custom(img, top, bottom, REEL_W, REEL_H)
    draw = ImageDraw.Draw(img)

    margin = 90
    safe_right = REEL_W - 160

    draw.rectangle([0, 0, REEL_W, 16], fill=accent)

    eyebrow_suffix = fact.get("eyebrow_suffix", "ON THIS DAY")
    eyebrow_font = ImageFont.truetype(str(FONT_BOLD), 44)
    eyebrow = f"{fact['region'].upper()} · {eyebrow_suffix}"
    draw.text((margin, 140), eyebrow, font=eyebrow_font, fill=accent)

    has_year = bool(fact.get("year"))
    if has_year:
        year_font = ImageFont.truetype(str(FONT_BLACK), 170)
        draw.text((margin, 220), str(fact["year"]), font=year_font, fill=(255, 255, 255))
        draw.rectangle([margin, 430, margin + 150, 438], fill=accent)
        area_top = 500
    else:
        draw.rectangle([margin, 220, margin + 150, 228], fill=accent)
        area_top = 300

    area_bottom = 1380
    body_font, lines, line_height = fit_text(
        draw, fact["text"], FONT_REGULAR,
        max_width=safe_right - margin, max_height=area_bottom - area_top, start_size=64, min_size=34
    )
    block_height = line_height * len(lines)
    y = area_top + max(0, (area_bottom - area_top - block_height) // 2)
    for line in lines:
        draw.text((margin, y), line, font=body_font, fill=(240, 240, 240))
        y += line_height

    # Handle placed above the zone where Facebook's own Reels caption/UI usually sits
    footer_font = ImageFont.truetype(str(FONT_BOLD), 38)
    cta_font = ImageFont.truetype(str(FONT_REGULAR), 32)
    draw.text((margin, 1500), page_handle, font=footer_font, fill=accent)
    draw.text((margin, 1550), "Follow for daily facts", font=cta_font, fill=(220, 220, 220))

    img.save(out_path, quality=95)
    return out_path


def draw_gradient_custom(img, top_color, bottom_color, w, h):
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def main():
    parser = argparse.ArgumentParser(description="Render fact cards from a facts JSON file")
    parser.add_argument("--facts", default=str(BASE_DIR / "facts_today.json"))
    parser.add_argument("--out-dir", default=str(BASE_DIR / "output"))
    parser.add_argument("--handle", default="@YourPage", help="Text shown in the footer of each card")
    args = parser.parse_args()

    facts = json.loads(Path(args.facts).read_text())
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for i, fact in enumerate(facts, start=1):
        out_path = out_dir / f"fact_{i}.png"
        make_card(fact, out_path, page_handle=args.handle)
        paths.append(str(out_path))
        print(f"Wrote {out_path}")

    return paths


if __name__ == "__main__":
    main()
