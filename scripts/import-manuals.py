#!/usr/bin/env python3
"""
Import Cognate block manuals from `code/manuals/<slug>/` into the website.

The source manuals (authored via `tools/manuals/build_manual.py` in the code
repo) are print-first: narrow A4 layout, absolute file:// logo paths, and no
site chrome. For the website we want:

  * the site-wide nav, matching all other pages;
  * a breadcrumb: Blocks / <Block name> / Manual;
  * a readable body column inside the site-width container;
  * a prominent Download PDF link;
  * screen-tuned CSS for the `.param`, `.page-overview`, `.spec` blocks the
    source markup uses.

The source HTML stays canonical in `code/manuals/` (used for PDF export).
This script extracts the semantic content and reformats it. Re-running is
safe: everything under `public/blocks/<slug>/manual/` is recreated.

Usage:
  python3 import-manuals.py all
  python3 import-manuals.py cognate-bitcrush
  python3 import-manuals.py bitcrush chord   # short names work
"""

from __future__ import annotations
import argparse
import html as htmllib
import re
import shutil
import sys
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJ_ROOT / "code" / "manuals"
TARGET_ROOT = PROJ_ROOT / "website" / "public" / "blocks"

ALL_SLUGS = [
    "cognate-bitcrush",
    "cognate-chord",
    "cognate-hologram",
    "cognate-kinetic",
    "cognate-metro",
    "cognate-pultrick",
    "cognate-ringmod",
]


def block_title(slug: str) -> str:
    return "Cognate " + slug.split("-", 1)[1].capitalize()


def normalise_slug(s: str) -> str:
    s = s.strip().lower()
    return s if s.startswith("cognate-") else f"cognate-{s}"


def extract_parts(source_html: str):
    """Pull the useful pieces out of the print manual."""
    # Body inner
    m = re.search(r'<body class="web">(.*?)</body>', source_html, re.S)
    if not m:
        raise ValueError("Couldn't find <body class=\"web\"> in source manual")
    body = m.group(1)

    # Strip any site-strip header we previously injected on import
    body = re.sub(r'<header class="site-strip".*?</header>\s*', "", body, flags=re.S)

    # Release info from .cover
    release = {}
    rm = re.search(
        r'<div class="release">\s*<strong>([^<]+)</strong>\s*<br>\s*([^<]+?)\s*</div>',
        body,
    )
    if rm:
        release["version"] = rm.group(1).strip()
        release["date"] = rm.group(2).strip()

    # Remove the cover div (logo + release) — we rebuild our own header
    body = re.sub(r'<div class="cover">.*?</div>\s*</div>\s*', "", body, count=1, flags=re.S)

    # Title-block: tagline is the plugin category
    tb = re.search(
        r'<div class="title-block">.*?<h1>([^<]+)</h1>\s*<p class="tagline">([^<]+)</p>.*?</div>\s*</div>',
        body,
        flags=re.S,
    )
    title = tb.group(1).strip() if tb else ""
    tagline = tb.group(2).strip() if tb else ""
    # Remove the title-block — we rebuild it above the body
    body = re.sub(r'<div class="title-block">.*?</div>\s*</div>\s*', "", body, count=1, flags=re.S)

    # Footer note
    body = re.sub(r'<div class="footer-note">.*?</div>\s*', "", body, flags=re.S)

    return {
        "release": release,
        "title": htmllib.unescape(title),
        "tagline": htmllib.unescape(tagline),
        "body": body.strip(),
    }


MANUAL_CSS = """
    /* Manual-specific CSS, scoped to .manual-content. */
    .manual-content { color: #1f2937; line-height: 1.65; font-size: 17px; }
    .manual-content h2 { font-size: 24px; font-weight: 700; margin: 48px 0 14px; letter-spacing: -0.01em; color: #111827; border-top: 1px solid #F3F4F6; padding-top: 24px; }
    .manual-content h2:first-of-type { border-top: none; padding-top: 0; margin-top: 32px; }
    .manual-content h3 { font-size: 19px; font-weight: 600; margin: 0 0 8px; color: #111827; }
    .manual-content p { margin: 0 0 14px; }
    .manual-content ul, .manual-content ol { margin: 0 0 14px; padding-left: 22px; }
    .manual-content li { margin: 4px 0; }
    .manual-content table { width: 100%; margin: 0 0 20px; border-collapse: collapse; font-size: 15px; }
    .manual-content thead { display: none; }
    .manual-content th, .manual-content td { padding: 8px 12px; border-bottom: 1px solid #F3F4F6; text-align: left; vertical-align: top; }
    .manual-content td:first-child { width: 160px; color: #6B7280; }
    .manual-content code { background: #F3F4F6; padding: 1px 6px; border-radius: 4px; font-size: 0.95em; }
    .manual-content strong { color: #111827; }

    .page-overview { display: inline-block; margin: 8px 16px 12px 0; vertical-align: top; }
    .page-overview img { max-width: 320px; width: 100%; border: 1px solid #E5E7EB; border-radius: 12px; display: block; }
    .page-overview .caption { font-size: 13px; color: #6B7280; margin-top: 6px; text-align: center; }

    .param { display: grid; grid-template-columns: 88px 1fr; gap: 20px; align-items: start; padding: 18px 0; border-bottom: 1px solid #F3F4F6; }
    .param:last-of-type { border-bottom: none; }
    .param .img { position: relative; }
    .param .img img { width: 88px; height: 88px; object-fit: contain; border: 1px solid #E5E7EB; border-radius: 12px; background: #fff; padding: 6px; }
    .param .body h3 { margin-top: 0; }
    .param .body .spec { list-style: none; padding: 0; margin: 0 0 10px; font-size: 14px; color: #4B5563; }
    .param .body .spec li { margin: 2px 0; }
    @media (max-width: 640px) {
        .param { grid-template-columns: 64px 1fr; gap: 14px; }
        .param .img img { width: 64px; height: 64px; }
    }
"""


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} Manual — Cognate Audio</title>
    <meta name="description" content="User manual for {title} — parameters, use cases, and how it fits into your Darkglass Anagram.">
    <link rel="icon" type="image/png" href="../../../images/favicon.png">
    <link rel="canonical" href="https://cognate.audio/blocks/{slug}/manual/">
    <link rel="apple-touch-icon" sizes="180x180" href="/images/favicon.png">
    <meta name="theme-color" content="#F2694A">
    <meta property="og:type" content="article">
    <meta property="og:site_name" content="Cognate Audio">
    <meta property="og:title" content="{title} Manual — Cognate Audio">
    <meta property="og:description" content="User manual for {title}.">
    <meta property="og:url" content="https://cognate.audio/blocks/{slug}/manual/">
    <meta property="og:image" content="https://cognate.audio/blocks/{slug}/manual/images/block.png">
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{ 'cognate-orange': '#F2694A', 'cognate-dark': '#48515B', 'cognate-red': '#DF3610' }},
                    fontFamily: {{ sans: ['Inter', 'system-ui', 'sans-serif'] }},
                }}
            }}
        }}
    </script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>{manual_css}</style>
</head>
<body class="bg-white text-gray-900 font-sans">
    <!-- Navigation -->
    <nav class="fixed top-0 left-0 right-0 bg-white/95 backdrop-blur-sm border-b border-gray-100 z-50">
        <div class="max-w-6xl mx-auto px-6 py-3">
            <div class="flex items-center justify-between">
                <a href="../../../" class="flex items-center gap-3">
                    <img src="../../../images/CognateAudioPrimary-Colour.png" alt="Cognate Audio" class="h-10">
                </a>
                <div class="hidden md:flex items-center gap-8">
                    <a href="../../../" class="text-gray-600 hover:text-cognate-orange transition-colors">Home</a>
                    <a href="../../../blocks" class="text-gray-900 font-medium hover:text-cognate-orange transition-colors">Blocks</a>
                    <a href="../../../support" class="text-gray-600 hover:text-cognate-orange transition-colors">Support</a>
                    <a href="../../../about" class="text-gray-600 hover:text-cognate-orange transition-colors">About</a>
                    <a href="../../../contact" class="text-gray-600 hover:text-cognate-orange transition-colors">Contact</a>
                </div>
                <button id="mobile-menu-btn" class="md:hidden p-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                    </svg>
                </button>
            </div>
            <div id="mobile-menu" class="hidden md:hidden pt-4 pb-2">
                <a href="../../../" class="block py-2 text-gray-600">Home</a>
                <a href="../../../blocks" class="block py-2 text-gray-900 font-medium">Blocks</a>
                <a href="../../../support" class="block py-2 text-gray-600">Support</a>
                <a href="../../../about" class="block py-2 text-gray-600">About</a>
                <a href="../../../contact" class="block py-2 text-gray-600">Contact</a>
            </div>
        </div>
    </nav>

    <!-- Breadcrumb -->
    <div class="pt-24 px-6">
        <div class="max-w-6xl mx-auto">
            <nav class="text-sm text-gray-500">
                <a href="../../../blocks" class="hover:text-cognate-orange">Blocks</a>
                <span class="mx-2">/</span>
                <a href="../" class="hover:text-cognate-orange">{title}</a>
                <span class="mx-2">/</span>
                <span class="text-gray-900">Manual</span>
            </nav>
        </div>
    </div>

    <!-- Header -->
    <section class="py-10 px-6">
        <div class="max-w-6xl mx-auto">
            <div class="flex flex-col md:flex-row items-start gap-8">
                <div class="w-40 shrink-0">
                    <img loading="eager" decoding="async" src="images/block.png" alt="{title}" class="w-full rounded-2xl shadow-sm border border-gray-100">
                </div>
                <div class="flex-1">
                    <p class="text-sm font-medium text-cognate-orange uppercase tracking-wide mb-2">{tagline}</p>
                    <h1 class="text-3xl md:text-4xl font-bold mb-3">{title} <span class="text-gray-400 font-normal">Manual</span></h1>
                    <p class="text-gray-600 mb-6">{release_line}</p>
                    <div class="flex flex-wrap gap-3">
                        <a href="cognate-{short}.pdf" class="inline-flex items-center gap-2 bg-cognate-orange text-white px-5 py-2.5 rounded-full font-medium hover:bg-orange-600 transition-colors">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                            Download PDF
                        </a>
                        <a href="../" class="inline-flex items-center gap-2 text-gray-700 hover:text-cognate-orange px-5 py-2.5 rounded-full font-medium">
                            Back to {title}
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Content -->
    <section class="pb-24 px-6">
        <div class="max-w-6xl mx-auto">
            <div class="manual-content max-w-3xl">
{body}
            </div>
        </div>
    </section>

    <!-- NEWSLETTER:START -->
    <style>
    .newsletter {{ background: #F9FAFB; border-top: 1px solid #F3F4F6; padding: 56px 24px; }}
    .newsletter-inner {{ max-width: 1152px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 32px; align-items: center; justify-content: space-between; }}
    .newsletter-text h3 {{ font-size: 22px; font-weight: 700; margin: 0 0 6px; color: #111827; letter-spacing: -0.01em; }}
    .newsletter-text p {{ color: #4B5563; margin: 0; font-size: 15px; max-width: 540px; line-height: 1.55; }}
    .newsletter-form {{ display: flex; gap: 8px; flex: 0 0 auto; flex-wrap: wrap; }}
    .newsletter-form input[type="email"] {{ padding: 12px 18px; border: 1px solid #E5E7EB; border-radius: 9999px; font: inherit; min-width: 280px; outline: none; transition: border-color 150ms, box-shadow 150ms; background: #fff; color: #111827; }}
    .newsletter-form input[type="email"]:focus {{ border-color: #F2694A; box-shadow: 0 0 0 3px rgba(242,105,74,0.15); }}
    .newsletter-form button {{ background: #F2694A; color: #fff; padding: 12px 24px; border-radius: 9999px; border: none; font-weight: 600; cursor: pointer; font: inherit; transition: background 150ms; }}
    .newsletter-form button:hover {{ background: #E55A3C; }}
    .newsletter-form button:disabled {{ opacity: 0.6; cursor: not-allowed; }}
    .newsletter-status {{ flex: 1 0 100%; font-size: 14px; min-height: 18px; color: #4B5563; }}
    .newsletter-status.ok {{ color: #15803D; }}
    .newsletter-status.err {{ color: #B91C1C; }}
    .newsletter-form.submitted input[type="email"], .newsletter-form.submitted button {{ display: none; }}
    .newsletter-form.submitted .newsletter-status {{ flex: 0 0 auto; min-height: auto; font-size: 16px; font-weight: 500; }}
    @media (max-width: 720px) {{ .newsletter-form {{ width: 100%; }} .newsletter-form input[type="email"] {{ min-width: 0; flex: 1; }} }}
    </style>
    <section class="newsletter">
        <div class="newsletter-inner">
            <div class="newsletter-text">
                <h3>Join the newsletter</h3>
                <p>Get notified when we ship new blocks, share settings, or post something useful. No flood, no fluff. Unsubscribe any time.</p>
            </div>
            <form id="newsletter-form" action="/api/subscribe" method="POST" class="newsletter-form">
                <input type="email" name="email" placeholder="you@example.com" required aria-label="Email address">
                <input type="text" name="_gotcha" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0;">
                <button id="newsletter-submit" type="submit">Subscribe</button>
                <div class="newsletter-status" role="status" aria-live="polite"></div>
            </form>
        </div>
    </section>
    <script>
    (function() {{
        var f = document.getElementById("newsletter-form");
        if (!f) return;
        var status = f.querySelector(".newsletter-status");
        var btn = document.getElementById("newsletter-submit");
        f.addEventListener("submit", function(e) {{
            e.preventDefault();
            btn.disabled = true;
            status.textContent = "Subscribing…";
            status.className = "newsletter-status";
            fetch(f.action, {{ method: "POST", headers: {{ "Accept": "application/json" }}, body: new FormData(f) }})
                .then(function(r) {{ return r.json().then(function(j) {{ return {{ ok: r.ok, body: j }}; }}); }})
                .then(function(res) {{
                    if (res.ok && res.body.ok) {{
                        status.textContent = res.body.duplicate
                            ? "You’re already on the list — thanks!"
                            : "Thanks — check your inbox for a welcome message.";
                        status.className = "newsletter-status ok";
                        f.classList.add("submitted");
                    }} else {{
                        status.textContent = (res.body && res.body.error) || "Something went wrong. Please try again.";
                        status.className = "newsletter-status err";
                    }}
                }})
                .catch(function() {{
                    status.textContent = "Network error. Please try again.";
                    status.className = "newsletter-status err";
                }})
                .then(function() {{ btn.disabled = false; }});
        }});
    }})();
    </script>
    <!-- NEWSLETTER:END -->

    <!-- Footer -->
    <footer class="py-12 px-6 border-t border-gray-100">
        <div class="max-w-6xl mx-auto text-center text-sm text-gray-500">
            <a href="../../../" class="inline-flex items-center gap-2 text-gray-600 hover:text-cognate-orange">
                <img src="../../../images/logo-symbol.png" alt="" class="h-5">
                Cognate Audio
            </a>
        </div>
    </footer>

    <script>
        document.getElementById('mobile-menu-btn').addEventListener('click', function() {{
            document.getElementById('mobile-menu').classList.toggle('hidden');
        }});
    </script>
</body>
</html>
"""


def import_one(slug: str) -> bool:
    source = SOURCE_DIR / slug / f"{slug}.html"
    if not source.exists():
        print(f"  [skip] {slug}: no source at {source}")
        return False

    html = source.read_text()
    parts = extract_parts(html)
    target_dir = TARGET_ROOT / slug / "manual"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Images — copy the whole images/ subfolder fresh
    src_images = SOURCE_DIR / slug / "images"
    tgt_images = target_dir / "images"
    if tgt_images.exists():
        shutil.rmtree(tgt_images)
    if src_images.exists():
        shutil.copytree(src_images, tgt_images)

    # PDF + MD — copy alongside for download
    for suffix in (".pdf", ".md"):
        src_file = SOURCE_DIR / slug / f"{slug}{suffix}"
        if src_file.exists():
            shutil.copy2(src_file, target_dir / f"{slug}{suffix}")

    # Render page
    short = slug.split("-", 1)[1]
    release = parts["release"]
    release_line = ""
    if release:
        release_line = f"Version {release.get('version','')}"
        if release.get("date"):
            release_line += f" · {release['date']}"
    title = parts["title"] or block_title(slug)
    page = TEMPLATE.format(
        slug=slug,
        short=short,
        title=title,
        tagline=parts["tagline"] or "Block for Darkglass Anagram",
        release_line=release_line,
        body=parts["body"],
        manual_css=MANUAL_CSS,
    )
    (target_dir / "index.html").write_text(page)
    print(f"  [ok]   {slug}: manual regenerated")
    return True


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("targets", nargs="+", help="'all', or one or more slugs")
    args = p.parse_args(argv)

    slugs: list[str]
    if args.targets == ["all"]:
        slugs = list(ALL_SLUGS)
    else:
        slugs = [normalise_slug(t) for t in args.targets]
        bad = [s for s in slugs if s not in ALL_SLUGS]
        if bad:
            print(f"Unknown block(s): {', '.join(bad)}. Valid: {', '.join(ALL_SLUGS)}", file=sys.stderr)
            return 2

    any_ok = False
    for slug in slugs:
        if import_one(slug):
            any_ok = True
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
