import math

import numpy as np

from .materials import MATID, resolve


def vnoise(x, z, seed):
    xi = np.floor(x).astype(np.int64)
    zi = np.floor(z).astype(np.int64)
    fx = x - xi
    fz = z - zi

    def h(a, b):
        v = (a * 374761393 + b * 668265263 + seed * 1442695041) & 0xFFFFFFFF
        v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
        return (v & 0xFFFF) / 65535.0
    ux = fx * fx * (3 - 2 * fx)
    uz = fz * fz * (3 - 2 * fz)
    a, b, c, d = h(xi, zi), h(xi + 1, zi), h(xi, zi + 1), h(xi + 1, zi + 1)
    return (a * (1 - ux) + b * ux) * (1 - uz) + (c * (1 - ux) + d * ux) * uz


def fbm(x, z, seed, octaves=5):
    s = np.zeros_like(x)
    amp, tot, f = 1.0, 0.0, 1.0
    for o in range(octaves):
        s += vnoise(x * f, z * f, seed + o * 17) * amp
        tot += amp
        amp *= 0.5
        f *= 2.03
    return s / tot


def heights(t):
    xs = np.arange(t["x0"], t["x1"] + 1e-6, t["step"])
    zs = np.arange(t["z0"], t["z1"] + 1e-6, t["step"])
    X, Z = np.meshgrid(xs, zs)
    hf = t["height"]
    if hf is None:
        H = t["base"] + t["hills"] * (fbm(X / 18.0, Z / 18.0, t["seed"]) - 0.35) * 2.0
        H = np.maximum(H, t["base"] - 0.3)
    elif callable(hf):
        H = np.vectorize(lambda a, b: float(hf(a, b)))(X, Z) + t["base"]
    else:
        H = np.asarray(hf, float) + t["base"]
        if H.shape != X.shape:
            raise SystemExit(f"terrain height grid must be {X.shape[0]} rows by {X.shape[1]} columns")
    for (fx0, fz0, fx1, fz1, fy, fall) in t.get("flats", []):
        dx = np.maximum(np.maximum(fx0 - X, X - fx1), 0)
        dz = np.maximum(np.maximum(fz0 - Z, Z - fz1), 0)
        d = np.sqrt(dx * dx + dz * dz)
        w = np.clip(1 - d / max(fall, 1e-3), 0, 1)
        w = w * w * (3 - 2 * w)
        H = H * (1 - w) + fy * w
    return xs, zs, H


def mesh(t, H, xs, zs):
    nz, nx = H.shape
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X, H, Z], -1)
    gx = np.gradient(H, t["step"], axis=1)
    gz = np.gradient(H, t["step"], axis=0)
    Nv = np.stack([-gx, np.ones_like(H), -gz], -1)
    Nv /= np.linalg.norm(Nv, axis=-1, keepdims=True)
    i = np.arange(nz - 1)[:, None] * nx + np.arange(nx - 1)[None, :]
    i = i.ravel()
    tris = np.stack([np.stack([i, i + nx, i + 1], 1), np.stack([i + 1, i + nx, i + nx + 1], 1)], 1).reshape(-1, 3)
    idx = tris.ravel()
    Pf = P.reshape(-1, 3)[idx]
    Nf = Nv.reshape(-1, 3)[idx]
    mat = MATID[resolve(t["material"])]
    seeds = (np.floor(Pf[:, 0] * 0.37) * 7 + np.floor(Pf[:, 2] * 0.29) * 13) % 251
    return Pf, Nf, np.full(len(Pf), float(mat)), seeds
