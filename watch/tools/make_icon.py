"""Generate the launcher icons: orange disc with a white up arrow.

40 px for MIP devices (resources/), 60 and 65 px for AMOLED devices (resources-icon60/65).

Run with the project venv (Pillow): ../.venv/bin/python tools/make_icon.py
Colours are taken from the 64-colour MIP palette (0x55 steps) so nothing gets dithered.
"""
from pathlib import Path

from PIL import Image, ImageDraw

SCALE = 8  # draw large, then downsample for smooth edges
ORANGE = (255, 85, 0, 255)
WHITE = (255, 255, 255, 255)

AMOLED_ORANGE = (255, 122, 47, 255)


def make(size, orange, folder):
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, big - 1, big - 1), fill=orange)
    s = big / 40.0
    d.polygon([(20 * s, 7 * s), (32 * s, 20 * s), (24.5 * s, 20 * s), (24.5 * s, 32 * s),
               (15.5 * s, 32 * s), (15.5 * s, 20 * s), (8 * s, 20 * s)], fill=WHITE)
    img = img.resize((size, size), Image.LANCZOS)
    out = Path(__file__).resolve().parent.parent / folder / "drawables" / "launcher_icon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)


make(40, ORANGE, "resources")
make(60, AMOLED_ORANGE, "resources-icon60")
make(65, AMOLED_ORANGE, "resources-icon65")
# Edge bike computers (16-bit LCD)
for size in (35, 36, 39, 56, 62, 68):
    make(size, AMOLED_ORANGE, f"resources-icon{size}")
