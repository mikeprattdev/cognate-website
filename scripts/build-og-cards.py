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
        gd.line([(x, 0), (x, img.height)], fill=(255, 255, 255, 21), width=line_w)
    for y in range(0, img.height, step):
        gd.line([(0, y), (img.width, y)], fill=(255, 255, 255, 21), width=line_w)
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    cx, cy = int(img.width * 0.25), int(img.height * 0.55)
    max_r = 480 * SS
    for r in range(max_r, 0, -6):
        alpha = max(0, int(176 * (1 - r / max_r) ** 1.4))
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


def build_site_card() -> Image.Image:
    """Generic site-wide OG card: primary Cognate logo, tagline, Anagram photo."""
    W, H = CARD_W * SS, CARD_H * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    draw_background(draw, W, H)
    draw_grid_overlay(img)

    # Soften the grid in the centre: a radial black overlay (20% → 0%) that
    # fades away before reaching the edges, so grid stays crisp at corners.
    grid_softener = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gs_mask = Image.new("L", (W, H), 0)
    gsm = ImageDraw.Draw(gs_mask)
    cx, cy = W // 2, H // 2
    max_r = int(min(W, H) * 0.55)
    for r in range(max_r, 0, -4):
        alpha = max(0, int(51 * (1 - r / max_r) ** 1.2))
        gsm.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)
    grid_softener.putalpha(gs_mask)
    img.alpha_composite(grid_softener)

    draw_orange_glow(img)

    # Photo panel — right column
    panel_x = int(W * 0.56)
    panel_y = 60 * SS
    panel_w = W - panel_x - 60 * SS
    panel_h = H - 120 * SS

    panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
    pmask = Image.new("L", (panel_w, panel_h), 0)
    ImageDraw.Draw(pmask).rounded_rectangle(
        (0, 0, panel_w, panel_h), radius=20 * SS, fill=255)

    # Dark fill for the panel (slightly lighter than card bg so the photo sits on
    # a distinct rounded plate).
    fill = Image.new("RGBA", (panel_w, panel_h), (14, 20, 30, 255))
    fill.putalpha(pmask)
    panel.alpha_composite(fill)

    anagram_path = SITE / "images" / "anagram-34.png"
    if anagram_path.exists():
        src = Image.open(anagram_path).convert("RGBA")
        # Crop through the photo's blank border by zooming past contain-fit.
        scale = min(panel_w / src.width, panel_h / src.height) * 1.43
        new_w = int(src.width * scale)
        new_h = int(src.height * scale)
        new = src.resize((new_w, new_h), Image.LANCZOS)
        # Centred, shifted up by 20px (in final pixels) so we have room below for the blocks.
        px = (panel_w - new_w) // 2
        py = (panel_h - new_h) // 2 - 20 * SS
        panel.alpha_composite(new, (px, py))

    # Row of 7 block silhouettes overlapping across the lower half of the panel.
    block_pngs = [SITE / b["block_img"] for b in BLOCKS]
    block_pngs = [p for p in block_pngs if p.exists()]
    if block_pngs:
        block_size = 128 * SS
        overlap = int(block_size * 0.45)          # positive = images overlap
        step = block_size - overlap
        n = len(block_pngs)
        row_w = block_size + (n - 1) * step
        row_x = (panel_w - row_w) // 2
        row_y = panel_h - block_size - 38 * SS
        for i, bp in enumerate(block_pngs):
            bi = Image.open(bp).convert("RGBA")
            bi.thumbnail((block_size, block_size), Image.LANCZOS)
            # Subtle shadow so they read as stacked plates.
            sh = Image.new("RGBA", (bi.width + 24 * SS, bi.height + 24 * SS), (0, 0, 0, 0))
            ImageDraw.Draw(sh).rounded_rectangle(
                (10 * SS, 16 * SS, sh.width - 10 * SS, sh.height - 6 * SS),
                radius=18 * SS, fill=(0, 0, 0, 180))
            sh = sh.filter(ImageFilter.GaussianBlur(10 * SS))
            panel.alpha_composite(sh, (row_x + i * step - 12 * SS, row_y - 12 * SS))
            panel.alpha_composite(bi, (row_x + i * step, row_y))

    # Re-apply the rounded mask to clip any over-hanging pixels.
    panel.putalpha(pmask)

    # Softer outer drop shadow — more diffuse, lower opacity.
    shadow = Image.new("RGBA", (panel_w + 80 * SS, panel_h + 80 * SS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((40 * SS, 48 * SS, shadow.width - 40 * SS, shadow.height - 32 * SS),
                         radius=20 * SS, fill=(0, 0, 0, 130))
    shadow = shadow.filter(ImageFilter.GaussianBlur(36 * SS))
    img.alpha_composite(shadow, (panel_x - 40 * SS, panel_y - 24 * SS))
    img.alpha_composite(panel, (panel_x, panel_y))

    # Darker gradient under the text column so the grid and any residual
    # photo halo don't reduce contrast. Fades left → right.
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scrim_draw = ImageDraw.Draw(scrim)
    scrim_w = int(W * 0.58)
    for x in range(scrim_w):
        t = x / scrim_w
        alpha = int(180 * (1 - t) ** 1.6)
        if alpha > 0:
            scrim_draw.line([(x, 0), (x, H)], fill=(6, 9, 14, alpha))
    img.alpha_composite(scrim)

    fonts_bold = [FONTS_DIR / "grift-bold.ttf",
                  Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")]
    fonts_medium = [FONTS_DIR / "grift-medium.ttf",
                    Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
    fonts_regular = [FONTS_DIR / "grift-regular.ttf",
                     Path("/System/Library/Fonts/Supplemental/Arial.ttf")]

    f_title = load_font(fonts_bold, 72 * SS)
    f_tag = load_font(fonts_medium, 24 * SS)
    f_site = load_font(fonts_regular, 22 * SS)

    text_x = 60 * SS
    text_w = panel_x - text_x - 40 * SS  # leave a clear gap before the photo panel

    # Primary logo at top, left-aligned
    logo_path = SITE / "images" / "CognateAudioPrimary-Colour White Text @5x.png"
    logo_bottom = 60 * SS
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        target_h = 84 * SS
        ratio = target_h / logo.height
        logo = logo.resize((int(logo.width * ratio), target_h), Image.LANCZOS)
        img.alpha_composite(logo, (text_x, 60 * SS))
        logo_bottom = 60 * SS + logo.height

    # Heading
    y = logo_bottom + 48 * SS
    draw.text((text_x, y), "Blocks.", font=f_title, fill=TEXT_MAIN)
    bb = draw.textbbox((text_x, y), "Blocks.", font=f_title)
    unlocked_x = bb[2] + 20 * SS
    if unlocked_x + 320 * SS < text_x + text_w:
        draw.text((unlocked_x, y), "Unlocked.", font=f_title, fill=ORANGE)
        y += 92 * SS
    else:
        y += 84 * SS
        draw.text((text_x, y), "Unlocked.", font=f_title, fill=ORANGE)
        y += 84 * SS

    # Paragraph — two fixed lines
    y += 10 * SS
    for line in [
        "Creative, useful blocks for Darkglass Anagram.",
        "Built by bassists, for bassists.",
    ]:
        draw.text((text_x, y), line, font=f_tag, fill=TEXT_SUB)
        y += 34 * SS

    # Site URL aligned with everything else
    draw.text((text_x, H - 80 * SS), "cognate.audio", font=f_site, fill=TEXT_SUB)

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
    # Site-wide card
    site_card = build_site_card()
    site_out = SITE / "og.png"
    site_card.save(site_out, optimize=True)
    print(f"  wrote {site_out.relative_to(PROJ)}")
    count += 1
    print(f"Generated {count} og cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
