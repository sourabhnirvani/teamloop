"""Draw every app icon from ui/public/logo.svg (the one source), so the logo can't drift between places.

    .venv\\Scripts\\python.exe scripts\\make_icons.py

Writes the phone app's icons with the logo's hash in their names and points the manifest at them, so an
installed phone app sees a changed manifest and refreshes its icon after an update. Also writes
ui/public/app-icon.png (fixed name: the desktop app fetches it from the server after each update) and
desktop/icon.png. Rendering uses the installed Chrome through Playwright (already a dependency).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "ui" / "public"
LOGO = PUBLIC / "logo.svg"

PAGE = """<!doctype html><html><head><style>html,body{{margin:0;background:transparent}}
#c{{width:{size}px;height:{size}px;{extra}}} #c svg{{width:100%;height:100%;display:block}}</style></head>
<body><div id="c">{svg}</div></body></html>"""


async def render(svg: str, size: int, out: Path, maskable: bool = False) -> None:
    from playwright.async_api import async_playwright

    if maskable:
        # full-bleed square, the logo shrunk into the safe circle, so launchers can crop it into any shape
        bg = re.search(r'<rect width="512" height="512" rx="118" fill="url\(#tl-bg\)"/>', svg)
        assert bg, "logo.svg changed: update make_icons.py's maskable step"
        inner = svg.replace(bg.group(0), "").replace(
            '<rect width="512" height="512" rx="118" fill="url(#tl-shine)"/>', "")
        body = inner[inner.index(">", inner.index("<svg")) + 1: inner.rindex("</svg>")]
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
               + body[: body.index("</defs>") + 7]
               + '<rect width="512" height="512" fill="url(#tl-bg)"/><rect width="512" height="512" fill="url(#tl-shine)"/>'
               + '<g transform="translate(51.2 51.2) scale(.8)">' + body[body.index("</defs>") + 7:] + "</g></svg>")
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
        await page.set_content(PAGE.format(size=size, svg=svg, extra=""))
        await page.locator("#c").screenshot(path=str(out), omit_background=True)
        await browser.close()


async def main() -> None:
    svg = LOGO.read_text(encoding="utf-8")
    tag = hashlib.sha1(svg.encode()).hexdigest()[:8]
    icons = PUBLIC / "icons"
    icons.mkdir(exist_ok=True)
    for old in icons.glob("icon-*.png"):
        old.unlink()  # earlier logos
    made = {
        "any192": icons / f"icon-{tag}-192.png",
        "any512": icons / f"icon-{tag}-512.png",
        "maskable": icons / f"icon-{tag}-maskable-512.png",
    }
    await render(svg, 192, made["any192"])
    await render(svg, 512, made["any512"])
    await render(svg, 512, made["maskable"], maskable=True)
    await render(svg, 512, PUBLIC / "app-icon.png")
    await render(svg, 512, ROOT / "desktop" / "icon.png")
    await render(svg, 180, PUBLIC / "apple-touch-icon.png")

    manifest_path = PUBLIC / "manifest.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["icons"] = [
        {"src": f"/icons/{made['any192'].name}", "sizes": "192x192", "type": "image/png"},
        {"src": f"/icons/{made['any512'].name}", "sizes": "512x512", "type": "image/png"},
        {"src": f"/icons/{made['maskable'].name}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for name in ("icon-192.png", "icon-512.png", "icon-512-maskable.png"):  # the old fixed names
        (PUBLIC / name).unlink(missing_ok=True)
    print(f"icons for logo {tag}: {', '.join(p.name for p in made.values())}, app-icon.png, desktop/icon.png")


if __name__ == "__main__":
    asyncio.run(main())
