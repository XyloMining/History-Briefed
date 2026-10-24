"""Episode files (episodes/*.json) -> validated specs the renderer consumes."""
import json
import re

from .config import ROOT

REQUIRED = ("id", "order", "title", "hook", "scenes", "description", "tags", "thumbnail")


class EpisodeError(ValueError):
    pass


def load_all():
    eps = []
    for p in sorted((ROOT / "episodes").glob("*.json")):
        ep = json.loads(p.read_text(encoding="utf-8"))
        ep["_file"] = p.name
        validate(ep)
        eps.append(ep)
    eps.sort(key=lambda e: e["order"])
    ids = [e["id"] for e in eps]
    if len(ids) != len(set(ids)):
        raise EpisodeError("duplicate episode ids")
    return eps


def validate(ep):
    miss = [k for k in REQUIRED if k not in ep]
    if miss:
        raise EpisodeError(f"{ep.get('_file')}: missing {miss}")
    if len(ep["scenes"]) < 3:
        raise EpisodeError(f"{ep['id']}: needs at least 3 scenes after the hook")
    for i, sc in enumerate(ep["scenes"]):
        if not sc.get("narration") or not sc.get("visuals"):
            raise EpisodeError(f"{ep['id']} scene {i}: narration and visuals are required")
    if len(ep["tags"]) < 5:
        raise EpisodeError(f"{ep['id']}: add at least 5 tags")
    if "#Shorts" not in ep["title"] and "#Shorts" not in ep["description"]:
        raise EpisodeError(f"{ep['id']}: include #Shorts in the title or description")


def find(eps, ident):
    for e in eps:
        if e["id"] == ident or e["id"].startswith(ident) or str(e["order"]) == ident:
            return e
    raise EpisodeError(f"no episode matching {ident!r}")


def build_spec(cfg, ep):
    """Flatten hook + scenes + fixed outro into the ordered scene list."""
    spec = [{"narration": ep["hook"]["narration"], "visuals": ep["hook"]["visuals"], "kind": "hook"}]
    spec += [{"narration": s["narration"], "visuals": s["visuals"], "kind": "body"} for s in ep["scenes"]]
    o = cfg["outro"]
    spec.append({"narration": o["subscribe_line"], "visuals": [dict(ep.get("outro_visual") or ep["scenes"][-1]["visuals"][-1])],
                 "kind": "cta"})
    spec.append({"narration": o["brand_line"], "visuals": [{"kind": "outro"}], "kind": "outro"})
    return spec


def words(text):
    return re.findall(r"[A-Za-z0-9'’]+", text)
