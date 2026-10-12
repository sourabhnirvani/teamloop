"""TeamLoop's logo: a black badge with a clean white S, a blue drop at the top right, and a grain of white speckles
rising from the bottom right. Writes ui/public/logo.svg, the one source make_icons.py draws every icon from.

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

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ui" / "public" / "logo.svg"
BG = "#000000"
BLUE = "#1783ff"
SIZE = 512
STROKE = 42  # one even line weight, like a geometric sans


def _noise(rnd: random.Random, cells: int, blur: float):
    """Random values on a cells x cells grid, smoothly upscaled to the full size and spread evenly over 0-255
    (so a threshold of t keeps about t/255 of the pixels; bigger cells = bigger specks)."""
    img = Image.new("L", (cells, cells))
    img.putdata([rnd.randint(0, 255) for _ in range(cells * cells)])
    img = img.resize((SIZE, SIZE), Image.BICUBIC)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return ImageOps.equalize(img).load()


def grain(seed: int = 7) -> str:
    """A wormy white speckle, thickest along the bottom-right rim and thinning out toward the middle (base64 WebP)."""
    rnd = random.Random(seed)
    clumps = _noise(rnd, 16, 6)     # where the speckle bunches up
    worms = _noise(rnd, 190, 0.9)   # the worms themselves: thresholded near the middle they join into a maze
    out = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    px = out.load()
    c = SIZE / 2
    for y in range(SIZE):
        for x in range(SIZE):
            # how far toward the bottom right (leaning down): 0 on a wavy line through the lower middle, 1 at the rim
            clump = clumps[x, y] / 255
            d = ((x - c) * 0.55 + (y - c) * 0.84 - 74 + (clump - 0.5) * 60) / 182
            if d <= 0:
                continue
            r = math.hypot(x - c, y - c) / c
            if r > 1:
                continue
            # at most about half white, so it stays a maze of worms and holes and never goes solid
            density = min(1.0, d) ** 0.9 * (0.34 + 0.18 * r ** 4) * (0.75 + 0.5 * clump)
            # soft edge on each worm, so it doesn't look pixelated at large sizes; dimmer away from the rim
            a = ((density * 255 - worms[x, y]) / 28 + 0.5) * min(1.0, d * 4)
            if a > 0:
                px[x, y] = (255, 255, 255, int(min(1.0, a) * (150 + 95 * min(1.0, d))))
    buf = io.BytesIO()
    out.save(buf, "WEBP", lossless=True, method=6)
    return base64.b64encode(buf.getvalue()).decode()


def drop(cx: float, cy: float, r: float) -> str:
    """A round dot with one square corner pointing down-left, toward the S."""
    return (f"M{cx} {cy - r} A{r} {r} 0 0 1 {cx + r} {cy} A{r} {r} 0 0 1 {cx} {cy + r} "
            f"L{cx - r} {cy + r} L{cx - r} {cy} A{r} {r} 0 0 1 {cx} {cy - r} Z")


def s_path() -> str:
    """The S's centre line: a top bowl opening right, a diagonal spine, a bottom bowl opening left (stroked at STROKE).
    The letter is about 220 tall and centred in the badge, the size of the K in the reference badge."""
    return ("M327 195 "
            "C318 176 294 166 259 166 "
            "C218 166 193 185 193 212 "
            "C193 236 211 246 240 252 "
            "L272 259 "
            "C305 266 327 280 327 308 "
            "C327 335 299 346 257 346 "
            "C216 346 190 334 181 311")


def main() -> None:
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" data-bg="{BG}">
  <!-- TeamLoop: S on a black badge, a blue drop, and grain rising from the bottom right -->
  <defs><clipPath id="tl-round"><circle cx="256" cy="256" r="256"/></clipPath></defs>
  <circle cx="256" cy="256" r="256" fill="{BG}"/>
  <image width="512" height="512" clip-path="url(#tl-round)" href="data:image/webp;base64,{grain()}"/>
  <path d="{s_path()}" fill="none" stroke="#ffffff" stroke-width="{STROKE}" stroke-linecap="butt"/>
  <path d="{drop(400, 122, 24)}" fill="{BLUE}"/>
</svg>
'''
    OUT.write_text(svg, encoding="utf-8")
    print(f"logo.svg {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
