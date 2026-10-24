import functools
import pathlib

from PIL import ImageFont

from .config import resolve

CANDIDATES = [
    "assets/fonts/EBGaramond-Medium.ttf", "assets/fonts/Cinzel-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/Library/Fonts/Georgia Bold.ttf", "C:/Windows/Fonts/georgiab.ttf",
]


@functools.lru_cache(maxsize=64)
def font(size, path=""):
    for c in ([path] if path else []) + CANDIDATES:
        p = resolve(c)
        if pathlib.Path(p).exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if f.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines
