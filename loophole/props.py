import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent / "data" / "props"

BUILTIN = {
    "cube": dict(file="cube", region="cube", glow=(1.0, 0.45, 0.12)),
    "door": dict(file="door", region="door", glow=(0.8, 0.1, 0.06)),
    "button": dict(file="btnb", region="btnb", glow=(1.6, 0.16, 0.1), top="btnt"),
    "device": dict(file="device", region="device", glow=(0.2, 0.7, 1.0)),
    "arms": dict(file="arms", region="arms", glow=(0.0, 0.0, 0.0)),
    "player": dict(file="player", region="player", glow=(0.3, 0.6, 1.0)),
}


@lru_cache(None)
def meta():
    return json.loads((DATA / "props.json").read_text())


def region(name):
    x, y, s, t = meta()["regions"][name]
    return x, y, s, round(t, 2)


@lru_cache(None)
def mesh(name):
    d = np.load(DATA / f"{name}.npz")
    out = dict(pos=d["pos"].astype(float), nrm=d["nrm"].astype(float), uv=d["uv"].astype(float))
    if "bone" in d:
        out["bone"] = d["bone"].astype(float)
    return out


def has_lod(name):
    return (DATA / f"{name}_lod.npz").exists()


def atlas_bytes():
    return (DATA / "patlas.jpg").read_bytes()


def atlas_size():
    m = meta()
    return m["W"], m["H"]
