import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .fonts import font, wrap
from .visuals import get_shot


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_thumbnail(cfg, ep, path):
    W, H = cfg["video"]["width"], cfg["video"]["height"]
    t = ep["thumbnail"]
    im = get_shot(cfg, {"kind": "image", "prompt": t["prompt"]}, W, H).convert("RGB")
    arr = np.asarray(im, dtype=np.float32)
    y = np.linspace(0, 1, H)[:, None, None]
    arr = arr * (0.55 + 0.45 * (1 - y) ** 0.5) * 0.9           # darken toward the bottom for text
    im = Image.fromarray(np.clip(arr, 0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.6))
    d = ImageDraw.Draw(im)
    colour = hex_rgb(cfg["thumbnail"]["color"])
    size = 190
    while size > 70:
        f = font(size, cfg["thumbnail"].get("font_path", ""))
        lines = wrap(t["text"].upper(), f, W - 140)
        if len(lines) <= 3 and max(f.getlength(l) for l in lines) <= W - 140:
            break
        size -= 10
    block = len(lines) * int(size * 1.08)
    y0 = int(H * 0.70) - block // 2
    for i, line in enumerate(lines):
        for dx, dy in ((4, 4), (-2, 3), (3, -2)):
            d.text((W // 2 + dx, y0 + i * int(size * 1.08) + dy), line, font=f, fill=(0, 0, 0), anchor="mt")
        d.text((W // 2, y0 + i * int(size * 1.08)), line, font=f, fill=colour, anchor="mt")
    d.line([(W // 2 - 160, y0 + block + 30), (W // 2 + 160, y0 + block + 30)], fill=colour, width=4)
    im.save(path)
    return path
