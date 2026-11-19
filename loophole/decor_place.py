from functools import lru_cache
from pathlib import Path

import numpy as np

KIT = Path(__file__).resolve().parent / "data" / "kit"
from .library import FOLIAGE

SOLID = {"catwalk", "column", "crate", "barrel", "machine", "fan", "pipe", "elbow", "valve", "tray", "beam", "duct",
         "panel", "table", "chair", "bookshelf", "sofa", "bed", "woodbarrel", "woodcrate", "bench", "firepit",
         "boulder", "rock", "stump", "armchair", "nightstand", "cabinet", "toolcart", "streetlamp"}


LAYOUT = {"layout": {}, "PW": 256, "PH": 256}


def set_layout(lay):
    LAYOUT.clear()
    LAYOUT.update(lay)
    module.cache_clear()


KINDS = sorted(p.stem[4:] for p in KIT.glob("kit_*.npz"))
EXTRA = {}


def refresh():
    KINDS[:] = sorted(set(p.stem[4:] for p in KIT.glob("kit_*.npz")) | set(EXTRA))
    raw.cache_clear()
    module.cache_clear()


def mesh_path(name):
    return EXTRA.get(name, KIT / f"kit_{name}.npz")


@lru_cache(None)
def raw(name):
    d = np.load(mesh_path(name))
    out = {k: d[k] for k in d.files}
    return out


@lru_cache(None)
def module(name):
    lay = LAYOUT
    d = raw(name)
    if name not in lay["layout"]:
        raise KeyError(f"prop '{name}' was not packed into the decor atlas")
    x, y, s = lay["layout"][name]
    uv = d["uv"].astype(float)
    uv = np.stack([(x + np.clip(uv[:, 0], 0, 1) * s) / lay["PW"], (y + np.clip(uv[:, 1], 0, 1) * s) / lay["PH"]], 1)
    return d["pos"].astype(float), d["nrm"].astype(float), uv, d["tan"].astype(float)


def vflags(name):
    d = raw(name)
    n = len(d["pos"])
    flag = np.asarray(d["flag"], float) if "flag" in d else np.where(d["tan"][:, 3] < 0, 2.0, 1.0)
    sway = np.asarray(d["sway"], float) if "sway" in d else np.zeros(n)
    return flag, sway


def basis(fwd, up):
    f = np.asarray(fwd, float)
    f = f / np.linalg.norm(f)
    u = np.asarray(up, float)
    u = u - f * np.dot(u, f)
    n = np.linalg.norm(u)
    if n < 1e-6:
        u = np.array([0.0, 1.0, 0.0]) if abs(f[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = u - f * np.dot(u, f)
    u = u / np.linalg.norm(u)
    s = np.cross(f, u)
    return np.stack([f, u, s], 1)


def instance(name, pos, fwd=(1, 0, 0), up=(0, 1, 0), scale=(1, 1, 1)):
    P, N, UV, T = module(name)
    R = basis(fwd, up)
    sc = np.asarray(scale, float)
    wp = (P * sc) @ R.T + np.asarray(pos, float)
    nn = (N / sc) @ R.T
    nn = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
    tt = (T[:, :3] / sc) @ R.T
    raw = tt / np.maximum(np.linalg.norm(tt, axis=1, keepdims=True), 1e-9)
    tt = (T[:, :3] * sc) @ R.T
    tt = tt - nn * np.sum(tt * nn, 1, keepdims=True)
    tt = tt / np.maximum(np.linalg.norm(tt, axis=1, keepdims=True), 1e-9)
    sign = T[:, 3] * (np.sign(np.linalg.det(R * sc[None, :])) or 1.0)
    instance.raw = raw
    return wp, nn, UV, tt, sign


CROWNS = []


def build(c):
    CROWNS.clear()
    Ps, Ns, Ms, As, Ss, boxes, Fl = [], [], [], [], [], [], []
    for k, it in enumerate(getattr(c, "decor", [])):
        name, pos, fwd, up, scale = it
        P, N, UV, T, sg = instance(name, pos, fwd, up, scale)
        fl, sw = vflags(name)
        T = np.where((fl > 4.5)[:, None], instance.raw, T)
        Ps.append(P)
        Ns.append(N)
        Ms.append(np.concatenate([UV, T, sg[:, None]], 1))
        As.append(np.where(fl > 4.5, sw, 1.0))
        Fl.append(fl)
        Ss.append(np.full(len(P), (k * 37) % 251))
        if name in FOLIAGE:
            fl_ = vflags(name)[0]
            sel = fl_ < 4.5
            if sel.any() and name in ("oak", "birch", "pine"):
                lo, hi = P[sel].min(0), P[sel].max(0)
                c_ = (lo + hi) / 2
                r_ = 0.16 * float(np.mean(scale[::2]))
                boxes.append((c_[0] - r_, lo[1], c_[2] - r_, c_[0] + r_, lo[1] + (hi[1] - lo[1]) * 0.6, c_[2] + r_))
            lf = ~sel
            if lf.any():
                lo, hi = P[lf].min(0), P[lf].max(0)
                CROWNS.append(((lo + hi) / 2, (hi - lo) / 2 * 0.85))
        elif name in SOLID:
            lo = P.min(0)
            hi = P.max(0)
            sh = np.minimum(0.1, (hi - lo) * 0.18) + (0.0 if name in ("catwalk", "tray") else 0.02)
            boxes.append(tuple(lo + sh) + tuple(hi - sh))
    Ms = [np.concatenate([m, np.zeros((len(m), 1)), f[:, None]], 1) for m, f in zip(Ms, Fl)]
    ex = getattr(c, "extra", None)
    if ex is not None and len(ex[0]):
        P, N, M, S = ex[0], ex[1], ex[2], ex[3]
        Ps.append(P)
        Ns.append(N)
        m = np.zeros((len(P), 8))
        m[:, 6] = 1.0
        m[:, 7] = M
        Ms.append(m)
        As.append(np.ones(len(P)))
        Ss.append(S)
    if not Ps:
        z = np.zeros((0, 3))
        return z, z, np.zeros((0, 8)), np.zeros(0), np.zeros(0), boxes
    return (np.concatenate(Ps), np.concatenate(Ns), np.concatenate(Ms), np.concatenate(As), np.concatenate(Ss),
            boxes)


def footprints(c):
    out = []
    for it in getattr(c, "decor", []):
        name, pos, fwd, up, scale = it
        P = instance(name, pos, fwd, up, scale)[0]
        out.append((P.min(0), P.max(0)))
    return out
