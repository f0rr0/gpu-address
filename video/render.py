# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow==11.3.0"]
# ///
"""Render the silent launch cut: uv run video/render.py (requires ffmpeg)."""

import hashlib
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/launch-video"
OUT.mkdir(parents=True, exist_ok=True)
W, H, FPS, SECONDS = 1920, 1080, 30, 20
BG, INK, MUTED = "#111111", "#ededed", "#a3a3a3"
COLORS = {"street_address": "#a3c9a8", "city": "#91b9d8", "state": "#dfbc82", "postcode": "#b5a0d6"}
NAMES = {
    "street_address": "STREET ADDRESS",
    "city": "CITY",
    "state": "STATE",
    "postcode": "ZIP CODE",
}
FONTS = {}
for family, file in [
    ("instrumentserif", "InstrumentSerif-Regular.ttf"),
    ("geistmono", "GeistMono[wght].ttf"),
]:
    path = OUT / file
    if not path.exists():
        urllib.request.urlretrieve(
            f"https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/{urllib.parse.quote(file)}",
            path,
        )
        urllib.request.urlretrieve(
            f"https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/OFL.txt",
            OUT / f"{family}-OFL.txt",
        )
    FONTS[family] = str(path)

FONT_CACHE = {}


def font(size, serif=False):
    key = (size, serif)
    if key not in FONT_CACHE:
        FONT_CACHE[key] = ImageFont.truetype(
            FONTS["instrumentserif" if serif else "geistmono"], size
        )
    return FONT_CACHE[key]


evidence = json.loads(Path(__file__).with_name("cases.json").read_text())
assert (
    hashlib.sha256((ROOT / "packages/core/model.bin").read_bytes()).hexdigest()
    == evidence["modelSha256"]
), "Reverify examples when the model changes"
CASES = evidence["cases"]
evaluation_dir = ROOT / "apps/website/public/evaluation-us-v1"
evaluation = json.loads((evaluation_dir / "results.json").read_text())
browser = json.loads((evaluation_dir / "browser-parity.json").read_text())
assert evaluation["model_sha256"] == evidence["modelSha256"]
METRICS = [
    (
        f"{evaluation['sizes']['gpu']['bytes'] / 1000:.1f}",
        "kB (Brotli)",
        "MODEL WEIGHTS",
        "Brotli quality 11",
    ),
    (
        f"{browser['models']['candidate']['warm']['medianMs']:.1f}",
        "ms",
        "WARM MEDIAN",
        "Chrome 153 / M1 Pro",
    ),
    (
        f"{evaluation['nad']['models']['gpu']['percent']:.1f}",
        "%",
        "WHOLE-ADDRESS MATCH",
        "828 / 842 NAD addresses",
    ),
]
for case in CASES:
    assert "," not in case["text"]
    assert " ".join(p["raw"] for p in case["components"]) == case["text"]
    assert [p["label"] for p in case["components"]] == list(COLORS)


def ease(t):
    t = max(0, min(1, t))
    return 1 - (1 - t) ** 3


def text(d, xy, value, size=28, color=INK, serif=False):
    d.text(xy, value, font=font(size, serif), fill=color, anchor="lt")


def centered(d, y, value, size, color=INK, serif=False):
    text(d, ((W - d.textlength(value, font=font(size, serif))) / 2, y), value, size, color, serif)


def logo(d, x, y, size):
    # Same checkerboard mark as apps/website/app/icon.svg.
    unit = size / 8
    for row in range(1, 7):
        for col in range(1, 7):
            if (row + col) % 2 == 0:
                d.rectangle(
                    (
                        x + col * unit,
                        y + row * unit,
                        x + (col + 1) * unit - 1,
                        y + (row + 1) * unit - 1,
                    ),
                    fill="#e5e5e5",
                )


def frame(t):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    if t < 2.5:
        lift = 35 * (1 - ease(t / 0.5))
        logo(d, 845, 185 + lift, 230)
        centered(d, 446 + lift, "gpu-postal", 160, serif=True)
        centered(d, 665, "US addresses. On your GPU.", 32, COLORS["street_address"])
    elif t < 14.5:
        index = 0 if t < 8.5 else 1
        local = t - (2.5 if index == 0 else 8.5)
        case = CASES[index]
        text(d, (120, 165), case["name"], 106, serif=True)
        raw = case["text"]
        visible = min(len(raw), int(local * 95))
        text(d, (126, 346), raw[:visible], 43)
        x = 126
        for i, part in enumerate(case["components"]):
            # Each verified input span lights up, then its component arrives.
            p = ease((local - 0.65 - i * 0.12) / 0.3)
            width = d.textlength(part["raw"], font=font(43))
            if p > 0:
                d.line((x, 408, x + width * p, 408), fill=COLORS[part["label"]], width=3)
                cx, cy = 126 + (i % 2) * 850, 524 + (i // 2) * 174 + 22 * (1 - p)
                layer = Image.new("RGB", (800, 144), BG)
                ld = ImageDraw.Draw(layer)
                ld.rounded_rectangle(
                    (0, 0, 798, 142), radius=5, fill="#191919", outline="#333333", width=2
                )
                ld.rectangle((0, 0, 4, 142), fill=COLORS[part["label"]])
                text(ld, (28, 24), NAMES[part["label"]], 21, COLORS[part["label"]])
                text(ld, (28, 72), part["raw"], 32)
                im.paste(Image.blend(Image.new("RGB", layer.size, BG), layer, p), (cx, int(cy)))
            x += width + d.textlength(" ", font=font(43))
    elif t < 17.5:
        centered(d, 224, "Small enough to bring along.", 100, serif=True)
        for i, (value, unit, label, detail) in enumerate(METRICS):
            p = ease((t - 14.5 - 0.2 - i * 0.18) / 0.5)
            metric = Image.new("RGB", (540, 340), BG)
            md = ImageDraw.Draw(metric)
            text(md, (0, 0), value, 140, COLORS["street_address"], serif=True)
            text(md, (0, 157), unit, 28)
            text(md, (0, 233), label, 23, MUTED)
            text(md, (0, 279), detail, 22, MUTED)
            if p > 0:
                im.paste(metric.crop((0, 0, int(540 * p), 340)), (140 + i * 570, 421))
        centered(d, 825, "NAD evaluation: training overlap unknown", 23, MUTED)
    else:
        brand = Image.new("RGB", (W, 160), BG)
        brand_draw = ImageDraw.Draw(brand)
        logo(brand_draw, 0, 0, 116)
        text(brand_draw, (143, 14), "gpu-postal", 104, serif=True)
        brand = brand.crop(ImageChops.difference(brand, Image.new("RGB", brand.size, BG)).getbbox())
        im.paste(brand, ((W - brand.width) // 2, 234))
        centered(d, 492, "npm install gpu-postal@experimental", 39)
        centered(d, 636, "gpu-postal.f0rr0.dev", 36, COLORS["street_address"])
    # Fade scenes, but keep the creator credit visible throughout.
    distance = min(abs(t - b) for b in [0, 2.5, 8.5, 14.5, 17.5, 20])
    im = Image.blend(Image.new("RGB", (W, H), BG), im, ease(distance / 0.16))
    centered(ImageDraw.Draw(im), 1014, "built by f0rr0.dev", 24, MUTED)
    return im


if __name__ == "__main__":
    closing = frame(19).crop((0, 200, W, 400))
    bounds = ImageChops.difference(closing, Image.new("RGB", closing.size, BG)).getbbox()
    assert abs((bounds[0] + bounds[2]) / 2 - W / 2) <= 1, "Closing brand must be centered"
    footer = frame(0).crop((0, 990, W, H)).tobytes()
    assert all(
        frame(t).crop((0, 990, W, H)).tobytes() == footer
        for t in [1, 2.5, 6, 8.5, 12, 14.5, 16, 17.5, 19]
    ), "Footer must persist through every scene and transition"
    for second in [1, 6, 12, 16, 19]:
        frame(second).save(OUT / f"v5-frame-{second:02}.png")
    assert frame(14.6).crop((140, 421, 680, 761)).getpixel((10, 10)) == (17, 17, 17)
    assert (
        frame(14.9).crop((1280, 421, 1820, 761)).tobytes()
        != frame(16).crop((1280, 421, 1820, 761)).tobytes()
    ), "Metrics must reveal in sequence"
    destination = OUT / "gpu-postal-launch-v5.mp4"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for n in range(SECONDS * FPS):
            proc.stdin.write(frame(n / FPS).tobytes())
        proc.stdin.close()
        assert proc.wait() == 0, "ffmpeg failed"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    print(destination)
