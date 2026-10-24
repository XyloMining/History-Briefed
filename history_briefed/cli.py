import argparse
import json


import shutil


from . import schedule
from .config import ROOT, load_config, resolve
from .episode import EpisodeError, build_spec, find, load_all, words
from .render import render_episode
from .thumbnail import make_thumbnail
from . import tts, visuals

OUT = ROOT / "build"


def cmd_setup(cfg, a):
    tts.download_models(cfg)
    print("Kokoro model ready.")


def cmd_doctor(cfg, a):
    ok = True

    def line(label, good, note=""):
        nonlocal ok
        ok &= bool(good)
        print(f"[{'ok' if good else '!!'}] {label} {note}")

    line("ffmpeg", shutil.which("ffmpeg"))
    line("ffprobe", shutil.which("ffprobe"))
    line("Kokoro voice", tts.kokoro_ready(cfg), "(run: python -m history_briefed setup)" if not tts.kokoro_ready(cfg) else "")
    line("visual provider", True, f"-> {visuals.provider(cfg)}" + ("" if visuals.provider(cfg) == "gemini" else "  (placeholders only; set GEMINI_API_KEY)"))
    line("outro image (vertical)", resolve(cfg["outro"]["image"]).exists(), cfg["outro"]["image"])
    try:
        eps = load_all()
        line("episodes", True, f"{len(eps)} valid")
    except EpisodeError as e:
        line("episodes", False, str(e))
    return 0 if ok else 1


def cmd_list(cfg, a):
    eps = load_all()
    for ep, slot in zip(eps, schedule.slots(cfg, len(eps))):
        n = sum(len(words(s["narration"])) for s in build_spec(cfg, ep))
        est = n / float(cfg["tts"]["words_per_second_fallback"])
        print(f"{ep['order']:>2}  {slot:%a %d %b %Y %H:%M}  ~{est:4.0f}s  {ep['id']:<28} {ep['title']}")


def build_one(cfg, ep, a):
    out = OUT / ep["id"]
    backend = "silent" if a.silent else None
    if a.placeholder:
        cfg["visuals"]["provider"] = "placeholder"
    r = render_episode(cfg, ep, out, backend=backend, voice=a.voice)
    make_thumbnail(cfg, ep, out / "thumbnail.png")
    meta = {"id": ep["id"], "title": ep["title"], "description": ep["description"], "tags": ep["tags"],
            "seconds": round(r["seconds"], 1), "voice_backend": r["backend"]}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def cmd_build(cfg, a):
    eps = load_all()
    chosen = eps if a.all else [find(eps, i) for i in a.ids]
    if not chosen:
        print("Nothing to build. Use: build --all  or  build <id> ...")
        return 1
    for ep in chosen:
        print(f"== {ep['id']}")
        build_one(cfg, ep, a)
    cmd_queue(cfg, a)
    return 0


def cmd_queue(cfg, a):
    """Write build/queue.json: everything Buffer needs, with the slot for each built episode."""
    eps = load_all()
    base = cfg["publish"]["raw_base"].rstrip("/")
    q = []
    for ep, slot in zip(eps, schedule.slots(cfg, len(eps))):
        meta = OUT / ep["id"] / "meta.json"
        if not meta.exists():
            continue
        m = json.loads(meta.read_text())
        q.append({"order": ep["order"], "id": ep["id"], "title": m["title"], "description": m["description"],
                  "tags": m["tags"], "seconds": m["seconds"], "scheduled_local": slot.isoformat(),
                  "scheduled_utc": schedule.iso_utc(slot), "video_url": f"{base}/{ep['id']}/video.mp4",
                  "thumbnail": f"{base}/{ep['id']}/thumbnail.png", "captions": f"{base}/{ep['id']}/captions.srt"})
    OUT.mkdir(exist_ok=True)
    (OUT / "queue.json").write_text(json.dumps(q, indent=2), encoding="utf-8")
    print(f"queue.json: {len(q)} built episode(s)")


def cmd_publish(cfg, a):
    """Copy finished renders into videos/ (the public folder Buffer pulls from)."""
    dest = ROOT / "videos"
    n = 0
    for d in sorted(OUT.glob("*/video.mp4")):
        t = dest / d.parent.name
        t.mkdir(parents=True, exist_ok=True)
        for f in ("video.mp4", "thumbnail.png", "captions.srt", "meta.json"):
            if (d.parent / f).exists():
                shutil.copy2(d.parent / f, t / f)
        n += 1
    shutil.copy2(OUT / "queue.json", dest / "queue.json") if (OUT / "queue.json").exists() else None
    print(f"copied {n} episode(s) to videos/")


def cmd_compare_voices(cfg, a):
    if not tts.kokoro_ready(cfg):
        print("Kokoro isn't set up. Run: python -m history_briefed setup")
        return 1
    line = "In nineteen sixteen, the world had no summer. Here is the story, briefed."
    out = OUT / "voice_samples"
    out.mkdir(parents=True, exist_ok=True)
    for v in a.voices:
        s, _ = tts.scene_audio(cfg, line, "kokoro", voice=v)
        tts.write_wav(out / f"{v}.wav", s)
        print("wrote", out / f"{v}.wav")
    print("Listen against assets/voiceover_reference.wav, then set tts.voice in config.yaml.")


def cmd_smoke(cfg, a):
    """Offline sanity render: placeholder visuals + silent timing track, first episode."""
    a.silent, a.placeholder, a.voice = True, True, None
    cfg["video"]["fps"] = 12  # quick preview; real builds use video.fps
    ep = load_all()[0]
    meta = build_one(cfg, ep, a)
    print(json.dumps(meta, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="history_briefed")
    p.add_argument("--config")
    sp = p.add_subparsers(dest="cmd", required=True)
    sp.add_parser("setup")
    sp.add_parser("doctor")
    sp.add_parser("list")
    sp.add_parser("queue")
    sp.add_parser("publish")
    sp.add_parser("smoke")
    b = sp.add_parser("build")
    b.add_argument("ids", nargs="*")
    b.add_argument("--all", action="store_true")
    b.add_argument("--silent", action="store_true", help="timing-only narration (dry run)")
    b.add_argument("--placeholder", action="store_true", help="skip image generation")
    b.add_argument("--voice")
    c = sp.add_parser("compare-voices")
    c.add_argument("voices", nargs="*", default=["bm_george", "bm_lewis", "bm_daniel", "bm_fable", "am_michael", "am_adam"])
    a = p.parse_args(argv)
    cfg = load_config(a.config)
    fn = {"setup": cmd_setup, "doctor": cmd_doctor, "list": cmd_list, "build": cmd_build, "queue": cmd_queue,
          "publish": cmd_publish, "compare-voices": cmd_compare_voices, "smoke": cmd_smoke}[a.cmd]
    try:
        return fn(cfg, a) or 0
    except (EpisodeError, RuntimeError) as e:
        print("error:", e)
        return 1
