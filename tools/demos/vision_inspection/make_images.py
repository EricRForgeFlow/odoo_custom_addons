"""Synthetic images of printed circuit boards, with defects at known places.

    uv run --no-project --with pillow python make_images.py

Writes images/<name>.jpg and images/samples.json: for each image, the detections a
vision model would send (label, confidence, box relative to the image). The boards
are drawn here, so the demo needs no dataset and no camera, and has no licence to
respect.
"""

import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "images")
W, H = 960, 640
BOARD = (22, 92, 58)
TRACE = (44, 132, 84)
PAD = (205, 170, 90)
CHIP = (28, 28, 30)
SILK = (225, 232, 225)

# name, defects (label, confidence), seed. Confidences mimic a model's output:
# low ones send the inspection to review.
SAMPLES = [
    ("board_ok_1", [], 1),
    ("board_ok_2", [], 2),
    ("board_ok_3", [], 3),
    ("board_missing", [("missing", 0.94)], 4),
    ("board_scratch_minor", [("scratch", 0.88)], 5),
    ("board_scratch_unsure", [("scratch", 0.61)], 6),
    ("board_bent", [("bent", 0.91)], 7),
    ("board_two_scratches", [("scratch", 0.9), ("scratch", 0.83)], 8),
    ("board_missing_bent", [("missing", 0.96), ("bent", 0.72)], 9),
    ("board_ok_4", [], 10),
    ("board_scratch_faint", [("scratch", 0.42)], 11),
    ("board_bent_unsure", [("bent", 0.58)], 12),
    ("board_live_fail", [("missing", 0.93), ("scratch", 0.86), ("bent", 0.31)], 13),
    ("board_live_review", [("scratch", 0.64)], 14),
]

CHIPS = [(120, 150, 170, 110), (420, 120, 200, 140), (690, 330, 150, 150)]


def chip(draw, x, y, w, h, present=True, bent_pin=None):
    """A chip with pins on its top and bottom edges; returns the box of the bent pin."""
    pins = max(4, w // 22)
    bent_box = None
    for i in range(pins):
        px = x + 12 + i * (w - 24) / (pins - 1) - 4
        for top in (True, False):
            py = y - 16 if top else y + h
            draw.rectangle([px, py, px + 8, py + 16], fill=PAD)
            if bent_pin == (i, top):
                tip = py - 18 if top else py + 34
                draw.line([px + 4, py + (0 if top else 16), px + 26, tip], fill=(232, 205, 120), width=7)
                bent_box = (px - 6, min(py, tip) - 6, px + 36, max(py + 16, tip) + 6)
    if present:
        draw.rectangle([x, y, x + w, y + h], fill=CHIP)
        draw.ellipse([x + 10, y + 10, x + 22, y + 22], fill=(70, 70, 74))
        draw.text((x + w / 2 - 18, y + h / 2 - 6), f"U{x % 7 + 1}", fill=(150, 150, 150))
    else:
        draw.rectangle([x + 6, y + 6, x + w - 6, y + h - 6], outline=SILK, width=2)
    return bent_box


def board(seed, defects):
    rng = random.Random(seed)
    image = Image.new("RGB", (W, H), (58, 60, 64))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([30, 30, W - 30, H - 30], radius=26, fill=BOARD)
    for hx, hy in ((60, 60), (W - 60, 60), (60, H - 60), (W - 60, H - 60)):
        draw.ellipse([hx - 14, hy - 14, hx + 14, hy + 14], fill=PAD)
        draw.ellipse([hx - 7, hy - 7, hx + 7, hy + 7], fill=(58, 60, 64))
    for _ in range(26):
        x, y = rng.randrange(80, W - 80), rng.randrange(80, H - 80)
        points = [(x, y)]
        for _ in range(3):
            if rng.random() < 0.5:
                x = min(W - 70, max(70, x + rng.choice((-1, 1)) * rng.randrange(40, 200)))
            else:
                y = min(H - 70, max(70, y + rng.choice((-1, 1)) * rng.randrange(40, 160)))
            points.append((x, y))
        draw.line(points, fill=TRACE, width=4, joint="curve")
    for _ in range(14):
        x, y = rng.randrange(90, W - 120), rng.randrange(330, H - 90)
        if rng.random() < 0.5:
            draw.rectangle([x, y, x + 34, y + 14], fill=(130, 100, 60))
            draw.rectangle([x, y, x + 7, y + 14], fill=PAD)
            draw.rectangle([x + 27, y, x + 34, y + 14], fill=PAD)
        else:
            draw.ellipse([x, y, x + 26, y + 26], fill=(70, 90, 150))
            draw.ellipse([x + 7, y + 7, x + 19, y + 19], fill=(150, 165, 200))
    labels = [label for label, _ in defects]
    boxes = {}
    missing_chip = 1 if "missing" in labels else None
    bent_chip = 2 if "bent" in labels else None
    for index, (x, y, w, h) in enumerate(CHIPS):
        bent = (rng.randrange(1, 4), rng.random() < 0.5) if index == bent_chip else None
        bent_box = chip(draw, x, y, w, h, present=index != missing_chip, bent_pin=bent)
        if index == missing_chip:
            boxes.setdefault("missing", []).append((x - 8, y - 22, x + w + 8, y + h + 22))
        if bent_box:
            boxes.setdefault("bent", []).append(bent_box)
    draw.rectangle([W - 210, 90, W - 70, 150], outline=SILK, width=2)
    draw.text((W - 196, 112), "FF-PCB-001  REV B", fill=SILK)
    for _ in range(labels.count("scratch")):
        x, y = rng.randrange(120, W - 340), rng.randrange(260, H - 140)
        points = [(x, y)]
        for _ in range(5):
            x += rng.randrange(30, 55)
            y += rng.randrange(-14, 16)
            points.append((x, y))
        draw.line(points, fill=(196, 214, 200), width=3)
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        boxes.setdefault("scratch", []).append((min(xs) - 10, min(ys) - 12, max(xs) + 10, max(ys) + 12))
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    detections = []
    used = {}
    for label, confidence in defects:
        x0, y0, x1, y1 = boxes[label][used.get(label, 0)]
        used[label] = used.get(label, 0) + 1
        detections.append({
            "label": label,
            "confidence": confidence,
            "bbox": {
                "x": round(x0 / W, 4),
                "y": round(y0 / H, 4),
                "w": round((x1 - x0) / W, 4),
                "h": round((y1 - y0) / H, 4),
            },
        })
    return image, detections


def main():
    os.makedirs(OUT, exist_ok=True)
    samples = {}
    for name, defects, seed in SAMPLES:
        image, detections = board(seed, defects)
        image.save(os.path.join(OUT, f"{name}.jpg"), quality=88)
        samples[name] = detections
    with open(os.path.join(OUT, "samples.json"), "w") as handle:
        json.dump(samples, handle, indent=1)
    print(f"{len(samples)} boards in {OUT}")


if __name__ == "__main__":
    main()
