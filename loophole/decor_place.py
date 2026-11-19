from functools import lru_cache
from pathlib import Path

import numpy as np

KIT = Path(__file__).resolve().parent / "data" / "kit"
SOLID = {"catwalk", "column", "crate", "barrel", "machine", "fan", "pipe", "elbow", "valve", "tray", "beam", "duct",
         "panel"}


@lru_cache(None)
def _layout():
    import json
    return json.loads((Path(__file__).resolve().parent / "data" / "atlas" / "decor.json").read_text())


KINDS = sorted(p.stem[4:] for p in KIT.glob("kit_*.npz"))


@lru_cache(None)
def module(name):
    lay = _layout()
    d = np.load(KIT / f"kit_{name}.npz")
    x, y, s = lay["layout"][name]
    uv = d["uv"].astype(float)
    uv = np.stack([(x + np.clip(uv[:, 0], 0, 1) * s) / lay["PW"], (y + np.clip(uv[:, 1], 0, 1) * s) / lay["PH"]], 1)
    return d["pos"].astype(float), d["nrm"].astype(float), uv, d["tan"].astype(float)


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
    tt = (T[:, :3] * sc) @ R.T
    tt = tt - nn * np.sum(tt * nn, 1, keepdims=True)
    tt = tt / np.maximum(np.linalg.norm(tt, axis=1, keepdims=True), 1e-9)
    sign = T[:, 3] * (np.sign(np.linalg.det(R * sc[None, :])) or 1.0)
    return wp, nn, UV, tt, sign


def build(c):
    Ps, Ns, Ms, As, Ss, boxes = [], [], [], [], [], []
    for k, it in enumerate(getattr(c, "decor", [])):
        name, pos, fwd, up, scale = it
        P, N, UV, T, sg = instance(name, pos, fwd, up, scale)
        Ps.append(P)
        Ns.append(N)
        Ms.append(np.concatenate([UV, T, sg[:, None]], 1))
        As.append(np.ones(len(P)))
        Ss.append(np.full(len(P), (k * 37) % 251))
        if name in SOLID:
            lo = P.min(0)
            hi = P.max(0)
            sh = np.minimum(0.1, (hi - lo) * 0.18) + (0.0 if name in ("catwalk", "tray") else 0.02)
            boxes.append(tuple(lo + sh) + tuple(hi - sh))
    Ms = [np.concatenate([m, np.zeros((len(m), 2))], 1) for m in Ms]
    from . import procprops
    for (kind, pos, yaw, scale, seed) in getattr(c, "procs", []):
        P, N, M, S = procprops.instance(kind, pos, yaw, scale, seed)
        Ps.append(P)
        Ns.append(N)
        extra = np.zeros((len(P), 8))
        extra[:, 6] = 1.0
        extra[:, 7] = M
        Ms.append(extra)
        As.append(np.ones(len(P)))
        Ss.append(S)
        boxes += procprops.occluders(kind, pos, yaw, scale, seed)
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
