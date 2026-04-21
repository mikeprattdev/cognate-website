#!/usr/bin/env python3
"""
Build the "Suggested Settings" section on each block page from
website/blocks/<slug>/presets/presets.json.

Idempotent: delimits the generated section with <!-- PRESETS:START --> and
<!-- PRESETS:END --> marker comments. Running it again replaces the section
cleanly. If there are no presets for a block, the section is emptied.

Audio: if `<id>.m4a` exists alongside the page images, it is rendered as an
<audio controls> under the images on the card, and passed into the shared
lightbox via `window.openLightbox(images, name, desc, audio)`.

presets.json schema (array):
  [
    {
      "id":          "01-slam",
      "name":        "Slam",
      "description": "Punchy, compressed bass grit.",
      "pages":       2
    }
  ]

Images per preset live at:
  website/blocks/<slug>/presets/<id>-page1.png
  website/blocks/<slug>/presets/<id>-page2.png   (optional)
  website/blocks/<slug>/presets/<id>.m4a         (optional)
"""

from __future__ import annotations
import html as htmllib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "public"
BLOCKS_DIR = ROOT / "blocks"

START = "<!-- PRESETS:START -->"
END = "<!-- PRESETS:END -->"


def block_title(slug: str) -> str:
    # "cognate-pultrick" -> "Cognate Pultrick"
    return "Cognate " + slug.split("-", 1)[1].capitalize()


def esc(s: str) -> str:
    return htmllib.escape(s, quote=True)


def render_section(slug: str, presets: list[dict], block_dir: Path) -> str:
    if not presets:
        return f"{START}\n{END}"

    name = block_title(slug)
    cards = []
    for p in presets:
        pid = p["id"]
        pages = int(p.get("pages", 1))
        images = [f"presets/{pid}-page{i}.png" for i in range(1, pages + 1)]
        audio_rel = f"presets/{pid}.m4a"
        audio_file = block_dir / audio_rel
        audio_src = audio_rel if audio_file.exists() else ""

        thumbs = "\n".join(
            f'                        <img src="{src}" alt="{esc(p["name"])} page {i+1}" '
            f'class="w-full rounded-lg border border-gray-200 transition-transform duration-300 group-hover:scale-[1.01]">'
            for i, src in enumerate(images)
        )
        desc = p.get("description", "").strip()
        desc_html = (
            f'                <p class="text-sm text-gray-600 mb-4">{esc(desc)}</p>\n'
            if desc
            else ""
        )
        audio_html = (
            f'''                <audio controls preload="none" class="w-full mt-3" onclick="event.stopPropagation()">
                    <source src="{audio_src}" type="audio/mp4">
                </audio>
'''
            if audio_src
            else ""
        )
        onclick_js = (
            f"window.openLightbox({json.dumps(images)}, "
            f"{json.dumps(p['name'])}, {json.dumps(desc)}, "
            f"{json.dumps(audio_src)})"
        )
        # Attribute is wrapped in single quotes; escape any apostrophes
        # (common in descriptions) so they don't terminate the attribute.
        onclick = onclick_js.replace("'", "&#39;")
        cards.append(
            f'''            <button type="button" onclick='{onclick}' class="group text-left bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md hover:border-gray-300 transition-all cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cognate-orange">
                <h3 class="text-lg font-semibold mb-1">{esc(p["name"])}</h3>
{desc_html}                <div class="grid grid-cols-1 gap-3 mt-2">
{thumbs}
                </div>
{audio_html}                <div class="mt-3 inline-flex items-center gap-1 text-xs text-gray-500 group-hover:text-cognate-orange transition-colors">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m-3-3h6"/></svg>
                    Click to enlarge
                </div>
            </button>'''
        )

    cards_html = "\n".join(cards)
    return (
        f"{START}\n"
        f'    <section class="py-16 px-6">\n'
        f'        <div class="max-w-6xl mx-auto">\n'
        f'            <h2 class="text-2xl md:text-3xl font-bold mb-2">Suggested Settings</h2>\n'
        f'            <p class="text-gray-600 mb-10">Starting points to explore {name}. Click a preset to see full-size settings.</p>\n'
        f'            <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-8">\n'
        f"{cards_html}\n"
        f"            </div>\n"
        f"        </div>\n"
        f"    </section>\n"
        f"    {END}"
    )


def load_presets(block_dir: Path) -> list[dict]:
    f = block_dir / "presets" / "presets.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError as e:
        print(f"  [!] {f}: {e}", file=sys.stderr)
        return []


def patch_block_page(block_dir: Path, section: str) -> bool:
    page = block_dir / "index.html"
    if not page.exists():
        print(f"  [!] no block page at {page}")
        return False
    html = page.read_text()

    if START in html and END in html:
        before = html.split(START)[0]
        after = html.split(END, 1)[1]
        new_html = before + section + after
    else:
        anchor = "<!-- Related Blocks -->"
        if anchor not in html:
            print(f"  [!] {block_dir.name}: cannot find '{anchor}' insertion anchor")
            return False
        new_html = html.replace(anchor, f"{section}\n\n    {anchor}", 1)

    if new_html == html:
        return False
    page.write_text(new_html)
    return True


def main() -> int:
    block_dirs = sorted(
        d for d in BLOCKS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("cognate-")
    )
    any_change = False
    for block_dir in block_dirs:
        slug = block_dir.name
        presets = load_presets(block_dir)
        section = render_section(slug, presets, block_dir)
        changed = patch_block_page(block_dir, section)
        status = "updated" if changed else "unchanged"
        count = len(presets)
        print(f"  {slug}: {count} preset{'s' if count != 1 else ''} — {status}")
        any_change = any_change or changed
    if not any_change:
        print("No block pages changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
