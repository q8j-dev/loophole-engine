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
    for r in t.get("roads", []):
        H = level_road(r, X, Z, H)
    H = carve_waters(t, X, Z, H)
    return xs, zs, H


def road_nearest(r, X, Z, reach):
    pts = np.asarray(r["pts"], float)
    xs, zs = X[0], Z[:, 0]
    dx_, dz_ = xs[1] - xs[0], zs[1] - zs[0]
    d2 = np.full(X.shape, 1e18)
    idx = np.zeros(X.shape, np.int64)
    rx, rz = int(np.ceil(reach / dx_)) + 1, int(np.ceil(reach / dz_)) + 1
    for i, (px, pz) in enumerate(pts):
        cx, cz = int(round((px - xs[0]) / dx_)), int(round((pz - zs[0]) / dz_))
        x0, x1, z0, z1 = max(cx - rx, 0), min(cx + rx + 1, len(xs)), max(cz - rz, 0), min(cz + rz + 1, len(zs))
        if x0 >= x1 or z0 >= z1:
            continue
        dd = (X[z0:z1, x0:x1] - px) ** 2 + (Z[z0:z1, x0:x1] - pz) ** 2
        sub = d2[z0:z1, x0:x1]
        m = dd < sub
        sub[m] = dd[m]
        idx[z0:z1, x0:x1][m] = i
    return np.sqrt(d2), idx


def level_road(r, X, Z, H):
    pts = np.asarray(r["pts"], float)
    xs, zs = X[0], Z[:, 0]
    ix = np.clip(np.searchsorted(xs, pts[:, 0]), 0, len(xs) - 1)
    iz = np.clip(np.searchsorted(zs, pts[:, 1]), 0, len(zs) - 1)
    hc = H[iz, ix]
    k = 31
    ker = np.ones(k) / k
    pad = np.concatenate([hc[-k:], hc, hc[:k]])
    for _ in range(2):
        pad = np.convolve(pad, ker, mode="same")
    hc = pad[k:-k]
    fall = 6.0
    d, j = road_nearest(r, X, Z, r["width"] / 2 + fall)
    w = np.clip(1 - (d - r["width"] / 2 - 1.0) / fall, 0, 1)
    w = w * w * (3 - 2 * w)
    return H * (1 - w) + hc[j] * w


def seg_dist(X, Z, pts):
    pts = np.asarray(pts, float)
    d = np.full(X.shape, 1e9)
    for a, b in zip(pts, pts[1:]):
        ab = b - a
        L2 = max(float(ab @ ab), 1e-6)
        tt = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / L2, 0, 1)
        d = np.minimum(d, np.hypot(X - (a[0] + ab[0] * tt), Z - (a[1] + ab[1] * tt)))
    return d


def carve_waters(t, X, Z, H):
    H = H.copy()
    step = t["step"]
    for w in t.get("waters", []):
        if w["kind"] == "lake":
            ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
            rx = w["x"] + np.cos(ang) * w["r"] * 1.15
            rz = w["z"] + np.sin(ang) * w["r"] * 1.15
            ix = np.clip(np.round((rx - t["x0"]) / step).astype(int), 0, X.shape[1] - 1)
            iz = np.clip(np.round((rz - t["z0"]) / step).astype(int), 0, X.shape[0] - 1)
            if w.get("level") is None:
                w["y"] = float(np.percentile(H[iz, ix], 25)) - 0.2
            else:
                w["y"] = float(w["level"])
            nz = fbm(X / 6.0, Z / 6.0, w.get("seed", 3), 3)
            d = np.hypot(X - w["x"], Z - w["z"]) / (w["r"] * (0.85 + 0.35 * nz))
            prof = w["y"] - w["depth"] * (1 - np.clip((d - 0.35) / 0.65, 0, 1) ** 1.6)
            shore = w["y"] + 0.3 + (d - 1.0) * w["r"] * 0.25
            target = np.where(d < 1.0, prof, shore)
            H = np.where(d < 1.5, np.minimum(H, target), H)
        else:
            pts = np.asarray(w["pts"], float)
            d = seg_dist(X, Z, pts)
            if w.get("level") is None:
                near = d < w["width"] * 0.5 + 2.0
                w["y"] = float(np.percentile(H[near], 15)) - 0.25 if near.any() else 0.0
            else:
                w["y"] = float(w["level"])
            nz = fbm(X / 5.0, Z / 5.0, w.get("seed", 5), 3)
            hw = w["width"] * 0.5 * (0.85 + 0.3 * nz)
            prof = w["y"] - w["depth"] * (1 - np.clip(d / np.maximum(hw, 0.3), 0, 1) ** 2)
            shore = w["y"] + 0.3 + (d - hw) * 0.3
            target = np.where(d < hw, prof, shore)
            H = np.where(d < hw + 4.0, np.minimum(H, target), H)
    return H


def under_water(t, X, Z, H):
    m = np.zeros(X.shape, bool)
    for w in t.get("waters", []):
        if "y" not in w:
            continue
        if w["kind"] == "lake":
            near = np.hypot(X - w["x"], Z - w["z"]) < w["r"] * 1.6
        else:
            near = seg_dist(X, Z, w["pts"]) < w["width"] + 3
        m |= near & (H < w["y"] + 0.12)
    return m


def masks(t, xs2, zs2, H2, holes, res):
    X, Z = np.meshgrid(xs2, zs2)
    gx = np.gradient(H2, res, axis=1)
    gz = np.gradient(H2, res, axis=0)
    ny = 1 / np.sqrt(1 + gx * gx + gz * gz)
    dens = np.clip((ny - 0.82) / 0.1, 0, 1)
    for (hx0, hz0, hx1, hz1) in holes:
        dens[(X > hx0 - 0.5) & (X < hx1 + 0.5) & (Z > hz0 - 0.5) & (Z < hz1 + 0.5)] = 0
    pm = np.zeros_like(H2)
    for pts, w, mat in t.get("paths", []):
        pts = np.array(pts, float)
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            ab = b - a
            L2 = max(float(ab @ ab), 1e-6)
            tt = np.clip(((X - a[0]) * ab[0] + (Z - a[1]) * ab[1]) / L2, 0, 1)
            dx = X - (a[0] + ab[0] * tt)
            dz = Z - (a[1] + ab[1] * tt)
            d = np.sqrt(dx * dx + dz * dz)
            edge = fbm(X / 1.3, Z / 1.3, 77, 3) * 0.6
            pm = np.maximum(pm, np.clip((w / 2 + edge - 0.2 - d) / 0.5, 0, 1))
    rm = np.zeros_like(H2)
    km = np.zeros_like(H2)
    par = np.zeros_like(H2)
    for r in t.get("roads", []):
        hw = r["width"] / 2
        d, j = road_nearest(r, X, Z, hw + 3)
        s_ = np.asarray(r["s"], float)[j]
        dens *= np.clip((d - hw - 0.6) / 1.4, 0, 1)
        if r.get("paint", True) is False:
            continue
        rm = np.maximum(rm, np.clip((hw - d) / 0.35 + 0.5, 0, 1))
        if r.get("kerbs", True):
            band = np.clip((d - (hw - 0.95)) / 0.12, 0, 1) * np.clip((hw + 0.1 - d) / 0.12, 0, 1)
            par = np.where(band > 0, ((np.floor(s_ / 1.6) % 2) == 0).astype(float), par)
            km = np.maximum(km, band)
    for (cx, cz, cr) in t.get("clear", []):
        dens *= np.clip((np.hypot(X - cx, Z - cz) - cr) / 1.5, 0, 1)
    dens *= (1 - pm) * float(t.get("grass", 1.0))
    dens[under_water(t, X, Z, H2)] = 0
    return np.clip(dens, 0, 1), np.stack([np.where(km > 0, par, pm), rm, km], -1)


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
    def __init__(self, t, xs, zs, H, ring=220.0, ring_step=5.0):
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


def crown_transmit(P, D, dapple=True):
    from .bake import vnoise3
    from .decor_place import CROWNS
    tr = np.ones(len(P))
    for c, r in CROWNS:
        c = np.asarray(c, float)
        r = np.maximum(np.asarray(r, float), 0.2)
        o = (P - c) / r
        d = D / r
        a = np.einsum("ij,ij->i", d, d)
        b = np.einsum("ij,ij->i", o, d)
        cc = np.einsum("ij,ij->i", o, o) - 1
        h = b * b - a * cc
        hit = (h > 0) & (-b + np.sqrt(np.maximum(h, 0)) > 0)
        if not hit.any():
            continue
        idx = np.nonzero(hit)[0]
        sq = np.sqrt(h[idx])
        depth = sq / np.maximum(a[idx], 1e-6)
        t = np.exp(-depth * 2.2) * 0.6 + 0.03
        if dapple:
            te = np.maximum((-b[idx] - sq) / np.maximum(a[idx], 1e-6), 0)
            ent = P[idx] + D[idx] * te[:, None]
            nz = vnoise3(ent, 1.1, 7) * 0.65 + vnoise3(ent, 2.7, 9) * 0.35
            t = np.where(nz > 0.66, np.maximum(t, 0.7 * np.clip((nz - 0.66) * 8, 0, 1)), t)
        tr[idx] *= t
    return np.clip(tr, 0, 1)


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
            tr = crown_transmit(Po, V)
            E += (cp * vis * tr)[:, None] * col[None] / len(dirs)
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
            vis += (~occ) * crown_transmit(Po, D, dapple=False)
        vis /= k_sky
        E += sr[None] * (vis * (0.75 + 0.25 * N[:, 1]))[:, None]
        if sun is not None:
            E += (1 - vis)[:, None] * np.array(sun["col"])[None] * 0.04 + sr[None] * 0.05
    others = [L for L in lights if L["kind"] != "sun"]
    if others and grid is not None:
        Ed, _ = direct_fn(Po, N, others, grid, rng, ns=2)
        E += Ed
    return E
