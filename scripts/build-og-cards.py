#!/usr/bin/env python3
"""
Generate Open Graph social-share cards (1200×630) for each block page.

Produces `public/blocks/<slug>/og.png` ready to be referenced by
`<meta property="og:image" …>`. Re-run after adding/renaming blocks.

Run with the Python 3.11 that has Pillow installed:
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
    website/scripts/build-og-cards.py
"""

from __future__ import annotations
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    sys.exit(
        "Pillow is not available on this Python. Run with the Python 3.11 that "
        "has Pillow installed, e.g.\n"
        "  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 "
        "website/scripts/build-og-cards.py"
    )

PROJ = Path(__file__).resolve().parents[2]
SITE = PROJ / "website" / "public"
FONTS_DIR = PROJ / "marketing" / "Cognate Audio Design System" / "fonts"

# Brand colours matching the site's rich-cta
BG_TOP = (16, 22, 32)       # #101620
BG_MID = (31, 41, 55)       # #1F2937
BG_BOT = (42, 24, 19)       # #2A1813
ORANGE = (242, 105, 74)     # #F2694A
ORANGE_WARM = (247, 164, 145)  # #F7A491
TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (201, 206, 214)  # #C9CED6
TEXT_EYEBROW = (247, 164, 145)

CARD_W, CARD_H = 1200, 630
# Render at 2× then downsample for clean anti-aliasing — fixes font hinting
# artefacts at small sizes (e.g. the grift eyebrow/tagline text).
SS = 2

BLOCKS = [
    dict(
        slug="cognate-bitcrush",
        name="Cognate Bitcrush",
        category="Overdrive & Distortion",
        tagline="A gritty, lo-fi sculptor for bass.",
        block_img="images/cognate-bitcrush block image 800x800.png",
    ),
    dict(
        slug="cognate-chord",
        name="Cognate Chord",
        category="Utilities",
        tagline="A chord reference and practice companion.",
        block_img="images/cognate-chord block image 800x800.png",
    ),
    dict(
        slug="cognate-hologram",
        name="Cognate Hologram",
        category="Modulation & Pitch",
        tagline="Bass stereo spatialiser for Anagram.",
        block_img="images/cognate-hologram block image 800x800.png",
    ),
    dict(
        slug="cognate-kinetic",
        name="Cognate Kinetic",
        category="EQs, Filters & Dynamics",
        tagline="A bass-first envelope filter.",
        block_img="images/cognate-kinetic block image 800x800.png",
    ),
    dict(
        slug="cognate-metro",
        name="Cognate Metro",
        category="Utilities — Free",
        tagline="Free metronome for Darkglass Anagram.",
        block_img="images/cognate-metro block image 800x800.png",
    ),
    dict(
        slug="cognate-pultrick",
        name="Cognate Pultrick",
        category="EQs, Filters & Dynamics",
        tagline="The Pultec trick, in your Anagram.",
        block_img="images/cognate-pultrick block image 800x800.png",
    ),
    dict(
        slug="cognate-ringmod",
        name="Cognate Ringmod",
        category="Modulation & Pitch",
        tagline="Musical ring modulation for bass.",
        block_img="images/cognate-ringmod block image 800x800.png",
    ),
]


def load_font(path_candidates: list[Path], size: int) -> ImageFont.FreeTypeFont:
    for p in path_candidates:
        if p.exists():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def draw_background(draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    # Diagonal 3-stop gradient similar to the site's rich-cta
    import math
    # Pre-draw top-to-bottom gradient then overlay orange ember in corner
    for y in range(h):
        t = y / (h - 1)
        if t < 0.7:
            lt = t / 0.7
            c = tuple(int(BG_TOP[i] + (BG_MID[i] - BG_TOP[i]) * lt) for i in range(3))
        else:
            lt = (t - 0.7) / 0.3
            c = tuple(int(BG_MID[i] + (BG_BOT[i] - BG_MID[i]) * lt) for i in range(3))
        draw.line([(0, y), (w, y)], fill=c)


def draw_grid_overlay(img: Image.Image) -> None:
    # 32px grid (in final-output pixels), masked with a radial falloff
    # behind the block image. Line width + step are multiplied by SS so
    # the grid survives the LANCZOS downsample instead of getting blurred
    # into invisibility.
    grid = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    step = 32 * SS
    line_w = 1 * SS
    for x in range(0, img.width, step):
        gd.line([(x, 0), (x, img.height)], fill=(255, 255, 255, 26), width=line_w)
    for y in range(0, img.height, step):
        gd.line([(0, y), (img.width, y)], fill=(255, 255, 255, 26), width=line_w)
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    cx, cy = int(img.width * 0.25), int(img.height * 0.55)
    max_r = 480 * SS
    for r in range(max_r, 0, -6):
        alpha = max(0, int(220 * (1 - r / max_r) ** 1.4))
        md.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    grid.putalpha(mask)
    img.alpha_composite(grid)


def draw_orange_glow(img: Image.Image) -> None:
    # Soft orange ember in the top-right corner
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy, r = img.width + 80, -40, 520
    for rr in range(r, 0, -6):
        alpha = max(0, int(110 * (1 - rr / r) ** 2))
        gd.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                   fill=(ORANGE[0], ORANGE[1], ORANGE[2], alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(glow)


def text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    l, t, r, b = draw.textbbox((0, 0), text, font=font)
    return r - l, b - t


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: int,
              draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        tw, _ = text_size(draw, trial, font)
        if tw <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build_card(block: dict) -> Image.Image:
    W, H = CARD_W * SS, CARD_H * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    draw_background(draw, W, H)
    draw_grid_overlay(img)
    draw_orange_glow(img)

    # Block image on the left
    block_img_path = SITE / block["block_img"]
    if block_img_path.exists():
        bi = Image.open(block_img_path).convert("RGBA")
        target = 460 * SS
        bi.thumbnail((target, target), Image.LANCZOS)
        pad_x = 80 * SS
        pad_y = (H - bi.height) // 2
        # Soft drop shadow
        shadow = Image.new("RGBA", (bi.width + 40 * SS, bi.height + 40 * SS), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rounded_rectangle((16 * SS, 24 * SS, shadow.width - 16 * SS, shadow.height - 8 * SS),
                             radius=28 * SS, fill=(0, 0, 0, 180))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18 * SS))
        img.alpha_composite(shadow, (pad_x - 20 * SS, pad_y - 16 * SS))
        img.alpha_composite(bi, (pad_x, pad_y))

    # Right-hand text column
    text_x = 620 * SS
    text_w = W - text_x - 80 * SS

    fonts_candidates_bold = [FONTS_DIR / "grift-bold.ttf",
                             Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")]
    fonts_candidates_medium = [FONTS_DIR / "grift-medium.ttf",
                               Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
    fonts_candidates_regular = [FONTS_DIR / "grift-regular.ttf",
                                Path("/System/Library/Fonts/Supplemental/Arial.ttf")]

    f_eyebrow = load_font(fonts_candidates_bold, 24 * SS)
    f_title = load_font(fonts_candidates_bold, 64 * SS)
    f_tag = load_font(fonts_candidates_medium, 28 * SS)
    f_site = load_font(fonts_candidates_regular, 22 * SS)

    y = 100 * SS
    draw.text((text_x, y), block["category"].upper(),
              font=f_eyebrow, fill=TEXT_EYEBROW)
    y += 46 * SS

    for line in wrap_text(block["name"], f_title, text_w, draw):
        draw.text((text_x, y), line, font=f_title, fill=TEXT_MAIN)
        y += 74 * SS

    y += 6 * SS
    for line in wrap_text(block["tagline"], f_tag, text_w, draw):
        draw.text((text_x, y), line, font=f_tag, fill=TEXT_SUB)
        y += 38 * SS

    draw.text((text_x, H - 80 * SS), "cognate.audio",
              font=f_site, fill=TEXT_SUB)
    draw.ellipse((text_x - 28 * SS, H - 75 * SS, text_x - 14 * SS, H - 61 * SS), fill=ORANGE)

    logo_path = SITE / "images" / "logo-symbol.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((80 * SS, 80 * SS), Image.LANCZOS)
        img.alpha_composite(logo, (W - logo.width - 60 * SS, 60 * SS))

    # Downsample the 2× canvas with LANCZOS — this smooths grift's thin
    # strokes at small sizes and eliminates the font-hinting artefacts.
    return img.resize((CARD_W, CARD_H), Image.LANCZOS).convert("RGB")


def main() -> int:
    out_dir_base = SITE / "blocks"
    count = 0
    for block in BLOCKS:
        card = build_card(block)
        out_dir = out_dir_base / block["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "og.png"
        card.save(out_path, optimize=True)
        print(f"  wrote {out_path.relative_to(PROJ)}")
        count += 1
    print(f"Generated {count} og cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
