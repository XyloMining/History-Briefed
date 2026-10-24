"""Frame-by-frame renderer: Ken Burns stills, dissolves, vignette, grain, optional captions, piped into FFmpeg."""
import pathlib
import subprocess

import numpy as np
from PIL import Image

from . import captions as cap
from .episode import build_spec
from .tts import synthesize
from .visuals import get_shot


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


class Shot:
    """One still with a slow push/pull and a gentle sideways drift."""

    def __init__(self, img, w, h, zoom, idx, static=False):
        self.w, self.h = w, h
        self.zoom = 0.03 if static else zoom
        bw, bh = int(w * (1 + self.zoom)), int(h * (1 + self.zoom))
        self.img = img.resize((bw, bh), Image.LANCZOS)
        self.push = idx % 2 == 0
        self.drift = (-1, 1, 0)[idx % 3] * (0.0 if static else 0.6)

    def frame(self, p):
        p = min(1.0, max(0.0, p))
        z = 1 + self.zoom * (ease(p) if self.push else 1 - ease(p))
        bw, bh = self.img.size
        cw, ch = bw / z, bh / z
        cx = bw / 2 + self.drift * (bw - cw) / 2 * (p - 0.5) * 2
        cy = bh / 2
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        return np.asarray(self.img.resize((self.w, self.h), Image.BICUBIC, box=box))


def build_timeline(cfg, spec, scenes):
    """Each scene's shots share its time equally. Returns [(start, end, shot_index)]."""
    tl, k = [], 0
    for sc, tm in zip(spec, scenes):
        n = len(sc["visuals"])
        span = (tm["end"] - tm["start"]) / n
        for j in range(n):
            tl.append((tm["start"] + j * span, tm["start"] + (j + 1) * span, k))
            k += 1
    return tl


def render_episode(cfg, ep, outdir: pathlib.Path, backend=None, voice=None, log=print):
    v = cfg["video"]
    W, H, FPS = v["width"], v["height"], v["fps"]
    outdir.mkdir(parents=True, exist_ok=True)
    spec = build_spec(cfg, ep)
    wav, scenes, used = synthesize(cfg, [s["narration"] for s in spec], outdir / "audio", backend, voice)
    total = scenes[-1]["end"] + v["tail_seconds"]
    if not v["min_seconds"] <= total <= v["max_seconds"]:
        raise RuntimeError(f"{ep['id']}: {total:.1f}s is outside {v['min_seconds']}-{v['max_seconds']}s")

    shots, k = [], 0
    for sc in spec:
        for vis in sc["visuals"]:
            img = get_shot(cfg, vis, int(W * 1.0), int(H * 1.0))
            shots.append(Shot(img, W, H, v["zoom"], k, static=vis.get("kind") == "outro"))
            k += 1
    tl = build_timeline(cfg, spec, scenes)
    grps = cap.groups(scenes, cfg["captions"]["words_per_group"])
    if cfg["captions"]["srt"]:
        cap.write_srt(outdir / "captions.srt", grps)

    cf = v["crossfade"]
    # Vignette and film grain run inside FFmpeg (fast, in C); Python only draws the picture.
    grade = f"vignette=angle=PI/{max(2.2, 4.5 - 2.0 * v['vignette']):.2f},noise=alls={max(1, int(v['grain'] * 80))}:allf=t"

    def shot_frame(i, t):
        s, e, _ = tl[i]
        return shots[i].frame((t - s) / max(e - s, 1e-3))

    out = outdir / "video.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(wav), "-vf", grade]
    music = cfg["tts"].get("music")
    if music and pathlib.Path(music).exists():
        cmd += ["-stream_loop", "-1", "-i", music, "-filter_complex",
                f"[2:a]volume={cfg['tts']['music_volume']}[m];[1:a]apad[a];[a][m]amix=inputs=2:duration=first[aout]",
                "-map", "0:v", "-map", "[aout]"]
    else:
        cmd += ["-af", "apad", "-map", "0:v", "-map", "1:a"]
    cmd += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", str(v["crf"]), "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for n in range(int(total * FPS)):
            t = n / FPS
            i = next((j for j, (s, e, _) in enumerate(tl) if t < e), len(tl) - 1)
            fr = shot_frame(i, t)
            nxt_start = tl[i][1] - cf
            if i + 1 < len(tl) and t > nxt_start:
                a = ease((t - nxt_start) / cf)
                fr = (fr.astype(np.float32) * (1 - a) + shot_frame(i + 1, t).astype(np.float32) * a).astype(np.uint8)
            img = fr
            if cfg["captions"]["burn_in"] and not spec_is_outro(tl, i, spec):
                im = cap.draw(Image.fromarray(img), grps, t, cfg)
                img = np.asarray(im)
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed: " + err[-400:])
    except BrokenPipeError:
        raise RuntimeError("ffmpeg stopped early: " + proc.stderr.read().decode()[-400:])
    log(f"rendered {out} ({total:.1f}s, voice backend: {used})")
    return {"path": out, "seconds": total, "backend": used, "scenes": scenes, "spec": spec}


def spec_is_outro(tl, i, spec):
    """True while the iconic outro image is on screen (captions would sit on top of its own text)."""
    last_shot = len(tl) - 1
    return tl[i][2] == last_shot
