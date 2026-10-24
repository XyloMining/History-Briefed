"""Shots: AI stills (Gemini) with a cached, offline-safe placeholder fallback; text cards for dates and figures."""
import hashlib
import os
import random
import time

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from .config import resolve
from .fonts import font, wrap

GOLD = (201, 168, 106)


def cover(im, w, h):
    return ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS, centering=(0.5, 0.5))


def provider(cfg):
    p = cfg["visuals"]["provider"]
    if p == "auto":
        return "gemini" if os.environ.get("GEMINI_API_KEY") else "placeholder"
    return p


def _gemini(cfg, prompt):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    last = None
    for attempt in range(4):
        try:
            try:
                conf = types.GenerateContentConfig(response_modalities=["IMAGE"],
                                                   image_config=types.ImageConfig(aspect_ratio="9:16"))
            except Exception:  # older SDKs have no image_config; the prompt already asks for 9:16
                conf = types.GenerateContentConfig(response_modalities=["IMAGE"])
            r = client.models.generate_content(model=cfg["visuals"]["gemini_model"], contents=[prompt], config=conf)
            for part in r.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    import io

                    return Image.open(io.BytesIO(part.inline_data.data))
            raise RuntimeError("no image returned")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Gemini image failed: {str(last)[:200]}")


def _placeholder(w, h, seed, label=""):
    rnd = random.Random(seed)
    base = Image.linear_gradient("L").resize((w, h))
    im = ImageOps.colorize(base, (22 + rnd.randint(0, 14), 30 + rnd.randint(0, 18), 52 + rnd.randint(0, 24)), (3, 5, 10)).convert("RGB")
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(glow)
    cx, cy, r = rnd.randint(w // 4, 3 * w // 4), rnd.randint(h // 4, h // 2), rnd.randint(260, 460)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(150, 105, 45))
    im = Image.blend(im, Image.composite(glow, im, glow.convert("L").filter(ImageFilter.GaussianBlur(200))), 0.5)
    im = Image.composite(glow.filter(ImageFilter.GaussianBlur(220)), im, Image.new("L", (w, h), 70))
    if label:
        d = ImageDraw.Draw(im)
        f = font(44)
        for i, line in enumerate(wrap(label, f, w - 200)[:4]):
            d.text((w // 2, h // 2 + i * 56), line, font=f, fill=(110, 120, 140), anchor="mm")
    return im


def _card(w, h, text, sub=""):
    im = ImageOps.colorize(Image.linear_gradient("L").resize((w, h)), (16, 20, 34), (3, 4, 9)).convert("RGB")
    d = ImageDraw.Draw(im)
    size = 280
    while size > 80:
        f = font(size)
        if max(f.getlength(l) for l in wrap(text, f, w - 160)) <= w - 160 and len(wrap(text, f, w - 160)) <= 3:
            break
        size -= 12
    lines = wrap(text, f, w - 160)
    y = h // 2 - (len(lines) * int(size * 1.1)) // 2
    for i, line in enumerate(lines):
        d.text((w // 2, y + i * int(size * 1.1)), line, font=f, fill=GOLD, anchor="mt")
    if sub:
        d.text((w // 2, h // 2 + len(lines) * int(size * 0.62) + 40), sub, font=font(52), fill=(185, 190, 205), anchor="mt")
    return im


def get_shot(cfg, shot, w, h):
    """Return a PIL image (w x h) for one visual spec."""
    kind = shot.get("kind", "image")
    if kind == "outro":
        return cover(Image.open(resolve(cfg["outro"]["image"])), w, h)
    if kind == "card":
        return _card(w, h, shot["text"], shot.get("sub", ""))
    prompt = f"{shot['prompt']} {cfg['visuals']['style_prefix']}".strip()
    key = hashlib.sha1((prompt + cfg["visuals"]["gemini_model"]).encode()).hexdigest()[:16]
    cdir = resolve(cfg["visuals"]["cache_dir"])
    cdir.mkdir(parents=True, exist_ok=True)
    cached = cdir / f"{key}.png"
    if cached.exists():
        return cover(Image.open(cached), w, h)
    if provider(cfg) == "gemini":
        im = _gemini(cfg, prompt)
        im.convert("RGB").save(cached)
        return cover(im, w, h)
    return _placeholder(w, h, int(key, 16), shot["prompt"][:90])
