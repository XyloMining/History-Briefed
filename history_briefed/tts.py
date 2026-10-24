"""Narration. One clip per scene so timings are measured, not guessed.
Backends: kokoro (offline neural voice) or silent (timing-only, for dry runs)."""
import pathlib
import re
import subprocess
import urllib.request
import wave

import numpy as np

from .config import resolve

SR = 24000
CLAUSE = re.compile(r"(?<=[,.;:?!])\s+|(?<=\.\.\.)\s+")
MODEL_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
_K = None


def model_paths(cfg):
    d = resolve(cfg["tts"].get("model_dir", "models"))
    return d / "kokoro-v1.0.onnx", d / "voices-v1.0.bin"


def download_models(cfg):
    d = resolve(cfg["tts"].get("model_dir", "models"))
    d.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        dest = d / name
        if not dest.exists():
            print(f"downloading {name} ...")
            urllib.request.urlretrieve(url, dest)


def kokoro_ready(cfg):
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    return all(p.exists() for p in model_paths(cfg))


def _kokoro(cfg, text, voice=None):
    global _K
    from kokoro_onnx import Kokoro

    t = cfg["tts"]
    if _K is None:
        m, v = model_paths(cfg)
        _K = Kokoro(str(m), str(v))
    samples, sr = _K.create(text, voice=voice or t["voice"], speed=float(t.get("speed", 1.0)), lang=t.get("lang", "en-gb"))
    return np.asarray(samples, dtype=np.float32), sr


def _clause_audio(cfg, text, backend, voice=None):
    if backend == "kokoro":
        s, sr = _kokoro(cfg, text, voice)
        if sr != SR:
            raise RuntimeError(f"unexpected sample rate {sr}")
        return s
    wps = float(cfg["tts"]["words_per_second_fallback"])
    return np.zeros(int(max(0.4, len(text.split()) / wps) * SR), dtype=np.float32)


def scene_audio(cfg, text, backend, voice=None):
    """Synthesize clause by clause. Returns (samples, [{text,start,end}]) with times relative to the scene."""
    t = cfg["tts"]
    parts = [c for c in CLAUSE.split(text.strip()) if c]
    chunks, clauses, cur = [], [], 0.0
    for i, c in enumerate(parts):
        s = _clause_audio(cfg, c, backend, voice)
        dur = len(s) / SR
        clauses.append({"text": c, "start": cur, "end": cur + dur})
        chunks.append(s)
        cur += dur
        if i < len(parts) - 1:
            gap = t["pause_end"] if c.rstrip()[-1:] in ".?!" else t["pause_comma"]
            chunks.append(np.zeros(int(gap * SR), dtype=np.float32))
            cur += gap
    return np.concatenate(chunks), clauses


def write_wav(path, samples):
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def pick_backend(cfg):
    b = cfg["tts"]["backend"]
    if b == "auto":
        return "kokoro" if kokoro_ready(cfg) else "silent"
    if b == "kokoro" and not kokoro_ready(cfg):
        raise RuntimeError("Kokoro not ready. Run: python -m history_briefed setup")
    return b


def synthesize(cfg, narrations, workdir: pathlib.Path, backend=None, voice=None):
    """Returns (wav_path, scenes, backend); scene = {start,end,speech,clauses} on the full-track clock."""
    workdir.mkdir(parents=True, exist_ok=True)
    backend = backend or pick_backend(cfg)
    gap = np.zeros(int(float(cfg["tts"]["scene_gap"]) * SR), dtype=np.float32)
    chunks, scenes, t = [], [], 0.0
    for text in narrations:
        s, clauses = scene_audio(cfg, text, backend, voice)
        speech = len(s) / SR
        scenes.append({"start": t, "end": t + speech + len(gap) / SR, "speech": speech,
                       "clauses": [{"text": c["text"], "start": t + c["start"], "end": t + c["end"]} for c in clauses]})
        chunks += [s, gap]
        t += speech + len(gap) / SR
    raw = workdir / "narration_raw.wav"
    write_wav(raw, np.concatenate(chunks))
    out = raw
    master = cfg["tts"].get("master")
    if master and backend != "silent":
        out = workdir / "narration.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", master, "-ar", str(SR), "-ac", "1", str(out)],
                       check=True)
    return out, scenes, backend
