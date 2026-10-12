"""TeamLoop's logo: a black badge with a bold white S, a blue-violet drop at the top right, and a grain of white
speckles rising from the bottom right. Writes ui/public/logo.svg, the one source make_icons.py draws every icon from.

    .venv\\Scripts\\python.exe scripts\\make_logo.py && .venv\\Scripts\\python.exe scripts\\make_icons.py

The grain is generated (seeded, so the logo is the same every run) and embedded as an image, so the SVG looks the same
in every browser and at every size; the S and the drop are vector paths.
"""

from __future__ import annotations

import base64
import io
import math
import random
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "public" / "logo.svg"
BG = "#0b0b10"
SIZE = 512


def grain(seed: int = 12) -> str:
    """White speckles thickening toward the bottom right, clustered like a stipple (base64 WebP, 512x512)."""
    rnd = random.Random(seed)
    coarse = Image.new("L", (150, 150))
    coarse.putdata([rnd.randint(0, 255) for _ in range(150 * 150)])
    coarse = coarse.resize((SIZE, SIZE), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.7))
    fine = Image.new("L", (SIZE, SIZE))
    fine.putdata([rnd.randint(0, 255) for _ in range(SIZE * SIZE)])
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    px, cp, fp = out.load(), coarse.load(), fine.load()
    for y in range(SIZE):
        for x in range(SIZE):
            # how far into the bottom-right corner: 0 at the middle, 1 at the corner
            d = ((x - 300) * 0.8 + (y - 300)) / 250
            if d <= 0:
                continue
            density = min(1.0, d) ** 1.7 * 0.62  # never solid: speckles all the way to the edge
            noise = (cp[x, y] * 0.55 + fp[x, y] * 0.45) / 255
            if noise < density:
                px[x, y] = (255, 255, 255, 255)
    buf = io.BytesIO()
    out.save(buf, "WEBP", lossless=True, method=6)
    return base64.b64encode(buf.getvalue()).decode()


def drop(cx: float, cy: float, r: float) -> str:
    """A round dot with one square corner pointing down-left, toward the S."""
    return (f"M{cx} {cy - r} A{r} {r} 0 0 1 {cx + r} {cy} A{r} {r} 0 0 1 {cx} {cy + r} "
            f"L{cx - r} {cy + r} L{cx - r} {cy} A{r} {r} 0 0 1 {cx} {cy - r} Z")


def s_path() -> str:
    """A bold geometric S: two stacked bowls drawn as one thick stroke."""
    def pt(cx, cy, rx, ry, deg):
        a = math.radians(deg)
        return f"{cx + rx * math.cos(a):.1f} {cy + ry * math.sin(a):.1f}"
    top = (256, 196, 74, 58)
    bot = (256, 312, 80, 58)
    return (f"M{pt(*top, -28)} "
            f"A{top[2]} {top[3]} 0 1 0 {pt(*top, 90)} "
            f"A{bot[2]} {bot[3]} 0 1 1 {pt(*bot, 152)}")


def main() -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" data-bg="{BG}">
  <!-- TeamLoop: S on a black badge, a blue-violet drop, and grain rising from the bottom right -->
  <defs>
    <linearGradient id="tl-drop" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#4f86ff"/>
      <stop offset="1" stop-color="#7b5cff"/>
    </linearGradient>
    <clipPath id="tl-round"><circle cx="256" cy="256" r="256"/></clipPath>
  </defs>
  <circle cx="256" cy="256" r="256" fill="{BG}"/>
  <image width="512" height="512" clip-path="url(#tl-round)" href="data:image/webp;base64,{grain()}"/>
  <path d="{s_path()}" fill="none" stroke="#ffffff" stroke-width="66" stroke-linecap="butt" stroke-linejoin="round"/>
  <path d="{drop(372, 132, 24)}" fill="url(#tl-drop)"/>
</svg>
'''
    OUT.write_text(svg, encoding="utf-8")
    print(f"logo.svg {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
