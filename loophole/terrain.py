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


def mesh(t, H, xs, zs, holes=()):
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
    Pv = P.reshape(-1, 3)
    cen = Pv[tris].mean(1)
    keep = np.ones(len(tris), bool)
    for (hx0, hz0, hx1, hz1) in holes:
        keep &= ~((cen[:, 0] > hx0) & (cen[:, 0] < hx1) & (cen[:, 2] > hz0) & (cen[:, 2] < hz1))
    tris = tris[keep]
    idx = tris.ravel()
    Pf = P.reshape(-1, 3)[idx]
    Nf = Nv.reshape(-1, 3)[idx]
    mat = MATID[resolve(t["material"])]
    seeds = (np.floor(Pf[:, 0] * 0.37) * 7 + np.floor(Pf[:, 2] * 0.29) * 13) % 251
    return Pf, Nf, np.full(len(Pf), float(mat)), seeds


class Field:
    def __init__(self, t, xs, zs, H, ring=220.0, ring_step=8.0):
        self.t = t
        self.xs, self.zs, self.H = xs, zs, H
        self.x0, self.x1, self.z0, self.z1 = xs[0], xs[-1], zs[0], zs[-1]
        self.step = t["step"]
        self.ring = ring
        self.ring_step = ring_step
        self.base = float(np.median(H))
        self.seed = t["seed"]

    def inner(self, x, z):
        fx = np.clip((x - self.x0) / self.step, 0, len(self.xs) - 1.001)
        fz = np.clip((z - self.z0) / self.step, 0, len(self.zs) - 1.001)
        ix = np.floor(fx).astype(int)
        iz = np.floor(fz).astype(int)
        tx = fx - ix
        tz = fz - iz
        H = self.H
        return (H[iz, ix] * (1 - tx) + H[iz, ix + 1] * tx) * (1 - tz) + (H[iz + 1, ix] * (1 - tx) + H[iz + 1, ix + 1] * tx) * tz

    def height(self, x, z):
        x = np.asarray(x, float)
        z = np.asarray(z, float)
        dx = np.maximum(np.maximum(self.x0 - x, x - self.x1), 0)
        dz = np.maximum(np.maximum(self.z0 - z, z - self.z1), 0)
        d = np.sqrt(dx * dx + dz * dz)
        out = self.inner(x, z)
        m = d > 0
        if m.any():
            xm, zm, dm = x[m], z[m], d[m]
            ramp = np.clip(dm / 90.0, 0, 1)
            mount = (fbm(xm / 70.0, zm / 70.0, self.seed + 91, 5) - 0.3) * 70.0 * ramp ** 1.3 + dm * 0.12
            out[m] = out[m] + np.maximum(mount, -2.0) + (fbm(xm / 14.0, zm / 14.0, self.seed + 5, 3) - 0.5) * 3.0 * np.clip(dm / 20, 0, 1)
        return out

    def ring_mesh(self):
        R = self.ring
        st = self.ring_step
        xs = np.arange(self.x0 - R, self.x1 + R + 1e-6, st)
        zs = np.arange(self.z0 - R, self.z1 + R + 1e-6, st)
        X, Z = np.meshgrid(xs, zs)
        Hh = self.height(X, Z)
        inside = (X > self.x0 + st) & (X < self.x1 - st) & (Z > self.z0 + st) & (Z < self.z1 - st)
        Hh = np.where(inside, Hh - 1.5, Hh - 0.08)
        gx = np.gradient(Hh, st, axis=1)
        gz = np.gradient(Hh, st, axis=0)
        Nv = np.stack([-gx, np.ones_like(Hh), -gz], -1)
        Nv /= np.linalg.norm(Nv, axis=-1, keepdims=True)
        P = np.stack([X, Hh, Z], -1)
        nz, nx = Hh.shape
        i = (np.arange(nz - 1)[:, None] * nx + np.arange(nx - 1)[None, :]).ravel()
        tris = np.stack([np.stack([i, i + nx, i + 1], 1), np.stack([i + 1, i + nx, i + nx + 1], 1)], 1).reshape(-1, 3)
        keep = ~inside.ravel()[tris].all(1)
        idx = tris[keep].ravel()
        return P.reshape(-1, 3)[idx], Nv.reshape(-1, 3)[idx]

    def occluded(self, P, D, tmax=300.0, t0=0.3):
        n = len(P)
        hit = np.zeros(n, bool)
        act = np.arange(n)
        t = t0
        while len(act) and t < tmax:
            Q = P[act] + D[act] * t
            h = self.height(Q[:, 0], Q[:, 2])
            s = Q[:, 1] < h
            hit[act[s]] = True
            keep = ~s & (Q[:, 1] < h + 120)
            act = act[keep]
            t += 0.5 + t * 0.06
        return hit


def sun_dirs(sd, k, rng, n, spread=0.012):
    up = np.array([0.0, 1.0, 0.0]) if abs(sd[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    tu = np.cross(up, sd)
    tu /= np.linalg.norm(tu)
    tv = np.cross(sd, tu)
    out = []
    for s_ in range(k * k):
        a = ((s_ % k + rng.random(n)) / k * 2 - 1) * spread
        b = ((s_ // k + rng.random(n)) / k * 2 - 1) * spread
        V = sd[None] + tu[None] * a[:, None] + tv[None] * b[:, None]
        out.append(V / np.linalg.norm(V, axis=1, keepdims=True))
    return out


def light_points(P, N, field, grid, sun, sky_rad, lights, direct_fn, rng, k_sky=20):
    n = len(P)
    E = np.zeros((n, 3))
    Po = P + N * 0.06
    if sun is not None:
        sd = np.array(sun["d"], float)
        sd /= np.linalg.norm(sd)
        col = np.array(sun["col"], float)
        dirs = sun_dirs(sd, 2, rng, n)
        for V in dirs:
            cp = np.clip(np.einsum("ij,ij->i", V, N), 0, None)
            ok = cp > 0
            vis = np.zeros(n, bool)
            idx = np.nonzero(ok)[0]
            if len(idx):
                occ = field.occluded(Po[idx], V[idx])
                if grid is not None:
                    occ |= grid.occluded(Po[idx], V[idx], np.full(len(idx), 60.0))
                vis[idx[~occ]] = True
            E += (cp * vis)[:, None] * col[None] / len(dirs)
    if sky_rad is not None:
        sr = np.array(sky_rad, float)
        u1 = rng.random((n, k_sky))
        u2 = rng.random((n, k_sky))
        r = np.sqrt(u1)
        ph = 2 * np.pi * u2
        T1 = np.cross(N, np.array([1.0, 0, 0]))
        T1 /= np.maximum(np.linalg.norm(T1, axis=1, keepdims=True), 1e-6)
        T2 = np.cross(N, T1)
        vis = np.zeros(n)
        for j in range(k_sky):
            D = (r[:, j, None] * np.cos(ph[:, j, None]) * T1 + r[:, j, None] * np.sin(ph[:, j, None]) * T2
                 + np.sqrt(1 - u1[:, j, None]) * N)
            occ = field.occluded(Po, D, tmax=60.0, t0=0.2)
            if grid is not None:
                occ |= grid.occluded(Po, D, np.full(n, 18.0))
            vis += ~occ
        vis /= k_sky
        E += sr[None] * (vis * (0.75 + 0.25 * N[:, 1]))[:, None]
        if sun is not None:
            E += (1 - vis)[:, None] * np.array(sun["col"])[None] * 0.06 + sr[None] * 0.08
    others = [L for L in lights if L["kind"] != "sun"]
    if others and grid is not None:
        Ed, _ = direct_fn(Po, N, others, grid, rng, ns=2)
        E += Ed
    return E
