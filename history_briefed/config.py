import os
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def load_config(path=None):
    load_env()
    p = pathlib.Path(path) if path else ROOT / "config.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def resolve(path):
    p = pathlib.Path(path)
    return p if p.is_absolute() else ROOT / p
