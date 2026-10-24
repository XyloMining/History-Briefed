"""Caption groups from measured clause timings; optional burn-in and an .srt for YouTube."""
from PIL import ImageDraw

from .fonts import font


def groups(scenes, n=4):
    out = []
    for sc in scenes:
        timed = []
        for c in sc["clauses"]:
            toks = c["text"].split()
            total = sum(max(2, len(t)) for t in toks)
            t = c["start"]
            for w in toks:
                d = (c["end"] - c["start"]) * max(2, len(w)) / total
                timed.append((w, t, t + d))
                t += d
        out += [timed[i:i + n] for i in range(0, len(timed), n)]
    return out


def _ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(path, grps):
    lines = []
    for i, g in enumerate(grps, 1):
        lines += [str(i), f"{_ts(g[0][1])} --> {_ts(g[-1][2])}", " ".join(w for w, _, _ in g), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def draw(img, grps, t, cfg):
    cur = None
    for g in grps:
        if g[0][1] - 0.04 <= t:
            cur = g
    if not cur or t > cur[-1][2] + 0.25:
        return img
    c = cfg["captions"]
    f = font(c["font_size"])
    sp = f.getlength(" ")
    total = sum(f.getlength(w) for w, _, _ in cur) + sp * (len(cur) - 1)
    x = (img.width - total) / 2
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([x - 30, c["y"] - 16, x + total + 30, c["y"] + c["font_size"] + 30], 26, fill=(0, 0, 0, 150))
    for w, a, b in cur:
        d.text((x, c["y"]), w, font=f, fill=(201, 168, 106, 255) if a <= t < b else (245, 245, 245, 255))
        x += f.getlength(w) + sp
    return img
