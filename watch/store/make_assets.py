"""Create the Connect IQ Store images from the simulator captures in raw/.

    ../../.venv/bin/python make_assets.py

Output in out/:
  screenshot-0N-*.png   square 500×500, watch with bezel on a light background (< 150 KB)
  display-0N-*.png      display only, 280×280 (round, black outside)
  store-icon.png        500×500, no black/transparent background, no text, 10 px margin
  hero-en.png, hero-de.png   1440×720
  device-icon-amoled.png, device-icon-mip.png   128×128 (MIP in the 64-colour palette)

Requirements: Garmin Connect IQ brand guidelines (500×500 sRGB, 10 px margin, no text, no Garmin
elements), hero 1440×720, developer forum: square screenshots, at most 150 KB.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
RAW = HERE / "raw"
OUT = HERE / "out"
ORANGE = (255, 122, 47)
DEEP = (18, 24, 38)
CYAN = (0, 214, 240)
CENTER = (239, 353)          # display centre in the simulator window capture (fēnix 7X Pro)
RADIUS = 140
SHOTS = [("01-ride", "Ride"), ("02-feedback", "Acknowledgement"), ("03-actions", "Actions"),
         ("04-workout", "Workout"), ("05-connect", "Connect"),
         ("amoled-01-ride", "Ride AMOLED"), ("amoled-02-feedback", "Acknowledgement AMOLED"),
         ("amoled-03-actions", "Actions AMOLED"), ("amoled-04-workout", "Workout AMOLED")]


def font(size, bold=True):
    for name in (("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
                 "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def save_small(img, path, limit=150_000):
    """Save as PNG; reduce to a palette if needed to stay below `limit` bytes."""
    img.save(path, optimize=True)
    if path.stat().st_size > limit:
        img.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
    return path.stat().st_size


# display centre and radius in the simulator window capture, per window size (device)
DISPLAYS = {(478, 692): (239, 353, 140),     # fēnix 7X Pro, 280 px
            (713, 1009): (366, 520, 227)}    # fēnix 8 47 mm, 454 px


def find_display(raw):
    return DISPLAYS[raw.size]


def display_only(raw):
    x, y, radius = find_display(raw)
    global RADIUS
    RADIUS = radius
    box = (x - RADIUS, y - RADIUS, x + RADIUS, y + RADIUS)
    disp = raw.crop(box).convert("RGB")
    mask = Image.new("L", disp.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * RADIUS - 1, 2 * RADIUS - 1), fill=255)
    out = Image.new("RGB", disp.size, (0, 0, 0))
    out.paste(disp, (0, 0), mask)
    return out


def framed(raw, size=500):
    # watch with straps, without the simulator's menu bar and status line (height depends on the device)
    w, h = raw.size
    watch = raw.crop((8, 66, w - 12, h - 68)).convert("RGB")   # without window border and status line
    canvas = Image.new("RGB", (watch.height, watch.height), (255, 255, 255))
    canvas.paste(watch, ((canvas.width - watch.width) // 2, 0))
    return canvas.resize((size, size), Image.LANCZOS)


def arrow_mark(draw, cx, cy, r, color, width):
    """Logo mark: circle with an up arrow (like the app's launcher icon), no text."""
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=width)
    a = r * 0.55
    draw.line((cx, cy + a, cx, cy - a * 0.9), fill=color, width=width)
    draw.line((cx - a * 0.75, cy - a * 0.05, cx, cy - a * 0.9, cx + a * 0.75, cy - a * 0.05),
              fill=color, width=width, joint="curve")


def store_icon(size=500, pad=10):
    img = Image.new("RGB", (size, size), ORANGE)
    d = ImageDraw.Draw(img)
    # soft gradient for depth; the motif keeps the 10 px margin (radius 30 % of the edge)
    for i in range(size):
        t = i / size
        c = tuple(int(ORANGE[k] * (1 - 0.18 * t) + 40 * 0.18 * t) for k in range(3))
        d.line((0, i, size, i), fill=c)
    arrow_mark(d, size // 2, size // 2, int(size * 0.3), (255, 255, 255), max(6, size // 22))
    return img


def device_icon(size=128, mip=False):
    if mip:
        bg, fg = (255, 170, 0), (255, 255, 255)   # both in the 64-colour palette (0x55 steps)
        img = Image.new("RGB", (size, size), (0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, size - 5, size - 5), fill=bg)
        arrow_mark(d, size // 2, size // 2, int(size * 0.3), fg, 8)
        return img.quantize(palette=_mip_palette(), dither=Image.Dither.NONE).convert("RGB")
    img = Image.new("RGB", (size, size), (0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, size - 5, size - 5), fill=ORANGE)
    arrow_mark(d, size // 2, size // 2, int(size * 0.3), (255, 255, 255), 7)
    return img


def _mip_palette():
    pal = Image.new("P", (1, 1))
    levels = [0, 0x55, 0xAA, 0xFF]
    colors = [c for r in levels for g in levels for b in levels for c in (r, g, b)]
    pal.putpalette(colors + [0] * (768 - len(colors)))
    return pal


def hero(lang):
    w, h = 1440, 720
    img = Image.new("RGB", (w, h), DEEP)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line((0, y, w, y), fill=(int(18 + 20 * t), int(24 + 14 * t), int(38 + 30 * t)))
    # subtle orange glow on the right
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((820, -180, 1640, 640), fill=(120, 50, 20))
    img = Image.blend(img, glow.filter(ImageFilter.GaussianBlur(120)), 0.35)
    d = ImageDraw.Draw(img)
    title = "ZWindoor"
    sub = {"en": "Turn, Ride On and fire\npower-ups from the buttons\nof your Garmin watch.",
           "de": "Abbiegen, Ride On und\nPower-ups mit den Tasten\ndeiner Garmin-Uhr."}[lang]
    d.text((90, 230), title, font=font(96), fill=(255, 255, 255))
    d.multiline_text((94, 380), sub, font=font(34, bold=False), fill=(214, 220, 230), spacing=14)
    d.rectangle((94, 352, 214, 358), fill=ORANGE)
    for (cx, cy, r), name in (((1010, 350, 200), "amoled-01-ride"), ((1290, 450, 140), "01-ride")):
        disp = display_only(Image.open(RAW / f"{name}.png")).resize((2 * r, 2 * r), Image.LANCZOS)
        ring = ImageDraw.Draw(img)
        ring.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=(52, 54, 60))
        ring.ellipse((cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), fill=(20, 20, 22))
        mask = Image.new("L", disp.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
        img.paste(disp, (cx - r, cy - r), mask)
    return img


def edge_square(raw, size=500):
    """Edge device capture (simulator window with the device, portrait) centred on a white square."""
    img = raw.convert("RGBA")
    img = img.crop((0, 0, img.width, img.height - 8))   # without the window edge at the bottom
    side = max(img.size) + 40
    canvas = Image.new("RGB", (side, side), (255, 255, 255))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas.resize((size, size), Image.LANCZOS)


EDGE_SHOTS = ["edge1040-dev-01-ride", "edge1040-dev-03-actions"]


def main():
    OUT.mkdir(exist_ok=True)
    for name in EDGE_SHOTS:
        n = save_small(edge_square(Image.open(RAW / f"{name}.png")), OUT / f"screenshot-{name.replace('-dev', '')}.png")
        print(f"{name}: screenshot {n // 1024} KB")
    for name, _label in SHOTS:
        raw = Image.open(RAW / f"{name}.png")
        n1 = save_small(framed(raw), OUT / f"screenshot-{name}.png")
        n2 = save_small(display_only(raw), OUT / f"display-{name}.png")
        print(f"{name}: screenshot {n1 // 1024} KB, display {n2 // 1024} KB")
    print("store-icon", save_small(store_icon(), OUT / "store-icon.png", 300_000) // 1024, "KB")
    for lang in ("en", "de"):
        print("hero", lang, save_small(hero(lang), OUT / f"hero-{lang}.png", 2_000_000) // 1024, "KB")
    device_icon().save(OUT / "device-icon-amoled.png")
    device_icon(mip=True).save(OUT / "device-icon-mip.png")
    print("device icons ok")


if __name__ == "__main__":
    main()
