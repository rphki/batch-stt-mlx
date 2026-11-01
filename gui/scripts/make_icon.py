"""Render the app icon (waveform + double chevron) into gui/icons/.

Usage: python gui/scripts/make_icon.py   (any Python with Pillow)
The PNGs are committed, so this only needs to run when the design changes.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ORANGE = (255, 145, 77)
GRAY = (115, 115, 115)
SIZES = [16, 32, 64, 128, 256, 512, 1024]
S = 4  # supersampling
N = 1024 * S
OUT = Path(__file__).resolve().parent.parent / "icons"


def r(v):
    return int(v * S)


def render():
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))

    # macOS grid: 824x824 tile, soft shadow
    shadow = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [r(100), r(112), r(924), r(936)], r(185), fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(r(14)))
    img.alpha_composite(shadow)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([r(100), r(100), r(924), r(924)], r(185),
                        fill=(255, 255, 255, 255))

    # waveform (orange) + double chevron (gray), centred as one group
    w, gap, cy, rad = 52, 26, 512, 12
    heights = [140, 300, 210, 370, 170]
    ch, t, step, sep = 100, 60, 122, 70
    total = len(heights) * w + (len(heights) - 1) * gap + sep + step + ch + t / 2 ** 0.5
    x = 512 - total / 2
    for h in heights:
        d.rounded_rectangle([r(x), r(cy - h / 2), r(x + w), r(cy + h / 2)],
                            r(rad), fill=ORANGE)
        x += w + gap
    x0 = x - gap + sep

    # chevrons drawn into a mask, corners softened by blur + threshold
    mask = Image.new("L", (N, N), 0)
    md = ImageDraw.Draw(mask)
    q = t / 2 / 2 ** 0.5  # half stroke, projected on each axis
    for dx in (0, step):
        ax = x0 + dx + ch  # apex of the centre line
        pts = [(ax - ch + q, cy - ch - q), (ax + 2 * q, cy), (ax - ch + q, cy + ch + q),
               (ax - ch - q, cy + ch - q), (ax - 2 * q, cy), (ax - ch - q, cy - ch + q)]
        md.polygon([(r(a), r(b)) for a, b in pts], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(r(7))).point(lambda v: 255 if v > 128 else 0)
    img.paste(Image.new("RGBA", (N, N), GRAY + (255,)), (0, 0), mask)
    return img


def main():
    OUT.mkdir(exist_ok=True)
    img = render()
    for size in SIZES:
        img.resize((size, size), Image.LANCZOS).save(OUT / f"whisper_batch-{size}.png")


if __name__ == "__main__":
    main()
