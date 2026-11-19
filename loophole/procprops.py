import math
from functools import lru_cache

import numpy as np

from .materials import MATID


class B:
    def __init__(self):
        self.P = []
        self.N = []
        self.M = []
        self.S = []

    def tri(self, a, b, c, na, nb, nc, mat, seed):
        self.P += [a, b, c]
        self.N += [na, nb, nc]
        self.M += [MATID[mat]] * 3
        self.S += [seed] * 3

    def quad(self, a, b, c, d, n, mat, seed=0):
        self.tri(a, b, c, n, n, n, mat, seed)
        self.tri(a, c, d, n, n, n, mat, seed)

    def box(self, lo, hi, mat, seed=0, skip_bottom=False):
        lo = np.asarray(lo, float)
        hi = np.asarray(hi, float)
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        f = [((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), (0, 0, 1)),
             ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (0, 0, -1)),
             ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (1, 0, 0)),
             ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0), (-1, 0, 0)),
             ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (0, 1, 0)),
             ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), (0, -1, 0))]
        for i, (a, b, c, d, n) in enumerate(f):
            if skip_bottom and i == 5:
                continue
            self.quad(a, b, c, d, n, mat, seed)

    def cyl(self, base, r0, r1, h, mat, segs=12, seed=0, caps=True, axis=(0, 1, 0)):
        base = np.asarray(base, float)
        ax = np.asarray(axis, float)
        ax /= np.linalg.norm(ax)
        t = np.cross(ax, [0, 0, 1.0] if abs(ax[1]) > 0.9 else [0, 1.0, 0])
        t /= np.linalg.norm(t)
        b = np.cross(ax, t)
        top = base + ax * h
        slope = (r0 - r1) / max(h, 1e-6)
        for k in range(segs):
            a0 = 2 * math.pi * k / segs
            a1 = 2 * math.pi * (k + 1) / segs
            d0 = t * math.cos(a0) + b * math.sin(a0)
            d1 = t * math.cos(a1) + b * math.sin(a1)
            n0 = d0 + ax * slope
            n1 = d1 + ax * slope
            n0 /= np.linalg.norm(n0)
            n1 /= np.linalg.norm(n1)
            p00, p01 = base + d0 * r0, base + d1 * r0
            p10, p11 = top + d0 * r1, top + d1 * r1
            self.tri(p00, p01, p11, n0, n1, n1, mat, seed)
            self.tri(p00, p11, p10, n0, n1, n0, mat, seed)
            if caps:
                if r1 > 0:
                    self.tri(top, p10, p11, ax, ax, ax, mat, seed)
                self.tri(base, p01, p00, -ax, -ax, -ax, mat, seed)

    def blob(self, c, r, mat, seed=0, sub=2, rough=0.22, squash=(1, 1, 1)):
        rng = np.random.default_rng(seed + 1)
        V, F = icosphere(sub)
        ph = rng.random(3) * 10
        disp = 1 + rough * (np.sin(V[:, 0] * 3.1 + ph[0]) * np.sin(V[:, 1] * 2.7 + ph[1]) * np.sin(V[:, 2] * 3.7 + ph[2])
                            + 0.5 * np.sin(V[:, 0] * 7.3 + V[:, 2] * 5.1 + ph[1]))
        P = V * disp[:, None] * r * np.asarray(squash, float) + np.asarray(c, float)
        N = np.zeros_like(P)
        for f in F:
            a, b_, cc = P[f]
            n = np.cross(b_ - a, cc - a)
            N[f] += n
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        for f in F:
            self.tri(P[f[0]], P[f[1]], P[f[2]], N[f[0]], N[f[1]], N[f[2]], mat, seed % 251)

    def arrays(self):
        return (np.array(self.P, float).reshape(-1, 3), np.array(self.N, float).reshape(-1, 3),
                np.array(self.M, float), np.array(self.S, float))


@lru_cache(None)
def icosphere(sub):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t), (t, 0, -1),
         (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    for _ in range(sub):
        cache = {}
        nf = []

        def mid(i, j):
            k = (min(i, j), max(i, j))
            if k not in cache:
                m = V[i] + V[j]
                V.append(m / np.linalg.norm(m))
                cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = nf
    return np.array(V), np.array(F)


def tree(b, s):
    rng = np.random.default_rng(s)
    h = 2.6 + rng.random() * 0.8
    b.cyl((0, 0, 0), 0.2, 0.12, h, "bark", segs=10, seed=s)
    b.cyl((0, h * 0.55, 0), 0.08, 0.03, 1.0, "bark", segs=6, seed=s, axis=(0.7, 0.7, 0.1))
    for i in range(6):
        a = i * 1.05 + rng.random()
        rr = 0.75 + rng.random() * 0.5
        c = (math.cos(a) * 0.7 * (i > 0), h + 0.2 + rng.random() * 0.7 + (0.6 if i == 0 else 0), math.sin(a) * 0.7 * (i > 0))
        b.blob(c, rr * 1.15, "leaves", seed=s * 7 + i, sub=2, rough=0.28)


def pine(b, s):
    rng = np.random.default_rng(s)
    h = 5.0 + rng.random() * 1.5
    b.cyl((0, 0, 0), 0.18, 0.06, h * 0.9, "bark", segs=8, seed=s)
    n = 4
    for i in range(n):
        y = 1.0 + i * (h - 1.6) / n
        r = 1.6 * (1 - i / (n + 0.6))
        b.cyl((0, y, 0), r, 0.0, 1.9 - i * 0.15, "leaves", segs=9, seed=s * 5 + i, caps=True)


def bush(b, s):
    rng = np.random.default_rng(s)
    for i in range(3):
        a = i * 2.1 + rng.random()
        b.blob((math.cos(a) * 0.35, 0.45 + rng.random() * 0.15, math.sin(a) * 0.35), 0.5 + rng.random() * 0.2, "leaves",
               seed=s * 3 + i, sub=2, rough=0.3)


def rock(b, s, r=0.7):
    b.blob((0, r * 0.35, 0), r, "rock", seed=s, sub=2, rough=0.3, squash=(1.2, 0.7, 1.0))


def boulder(b, s):
    rock(b, s, 1.6)


def table(b, s):
    b.box((-0.8, 0.72, -0.45), (0.8, 0.78, 0.45), "wood", s)
    for x in (-0.72, 0.72):
        for z in (-0.37, 0.37):
            b.box((x - 0.04, 0, z - 0.04), (x + 0.04, 0.72, z + 0.04), "wood", s)


def chair(b, s):
    b.box((-0.23, 0.44, -0.23), (0.23, 0.48, 0.23), "wood", s)
    for x in (-0.2, 0.2):
        for z in (-0.2, 0.2):
            b.box((x - 0.025, 0, z - 0.025), (x + 0.025, 0.44, z + 0.025), "wood", s)
    b.box((-0.23, 0.48, 0.19), (0.23, 0.95, 0.23), "wood", s)


def shelf(b, s):
    rng = np.random.default_rng(s)
    W, H, D = 1.0, 1.9, 0.35
    b.box((-W / 2, 0, -D / 2), (-W / 2 + 0.03, H, D / 2), "wood", s)
    b.box((W / 2 - 0.03, 0, -D / 2), (W / 2, H, D / 2), "wood", s)
    b.box((-W / 2, 0, D / 2 - 0.02), (W / 2, H, D / 2), "wood", s)
    for k in range(5):
        y = k * (H - 0.03) / 4
        b.box((-W / 2, y, -D / 2), (W / 2, y + 0.03, D / 2), "wood", s)
        if k < 4:
            x = -W / 2 + 0.05
            while x < W / 2 - 0.12:
                w = 0.03 + rng.random() * 0.04
                hh = 0.2 + rng.random() * 0.15
                b.box((x, y + 0.03, -D / 2 + 0.04), (x + w, y + 0.03 + hh, D / 2 - 0.04), "fabric", int(rng.integers(0, 250)))
                x += w + 0.004


def bed(b, s):
    b.box((-0.75, 0, -1.05), (0.75, 0.35, 1.05), "wood", s)
    b.box((-0.72, 0.35, -1.0), (0.72, 0.55, 1.0), "fabric", 40)
    b.box((-0.6, 0.55, -0.95), (0.6, 0.68, -0.6), "fabric", 200)
    b.box((-0.75, 0, -1.1), (0.75, 1.0, -1.02), "wood", s)


def sofa(b, s):
    b.box((-1.0, 0.1, -0.4), (1.0, 0.45, 0.4), "fabric", s)
    b.box((-1.0, 0.45, 0.22), (1.0, 0.9, 0.42), "fabric", s)
    b.box((-1.1, 0.1, -0.4), (-0.92, 0.65, 0.42), "fabric", s)
    b.box((0.92, 0.1, -0.4), (1.1, 0.65, 0.42), "fabric", s)
    b.box((-1.05, 0, -0.35), (1.05, 0.1, 0.38), "wood", s)


def bench(b, s):
    for z in (-0.15, 0.0, 0.15):
        b.box((-0.9, 0.45, z - 0.06), (0.9, 0.48, z + 0.06), "wood", s)
    for x in (-0.75, 0.75):
        b.box((x - 0.03, 0, -0.2), (x + 0.03, 0.45, 0.2), "metal", s)


def woodcrate(b, s):
    b.box((-0.45, 0, -0.45), (0.45, 0.9, 0.45), "planks", s)
    for y in (0.02, 0.83):
        for (a, c) in (((-0.47, -0.47), (0.47, -0.43)), ((-0.47, 0.43), (0.47, 0.47)), ((-0.47, -0.47), (-0.43, 0.47)),
                       ((0.43, -0.47), (0.47, 0.47))):
            b.box((a[0], y, a[1]), (c[0], y + 0.06, c[1]), "wood", s)


def chest(b, s):
    b.box((-0.45, 0, -0.3), (0.45, 0.45, 0.3), "wood", s)
    b.cyl((-0.45, 0.45, 0), 0.3, 0.3, 0.9, "wood", segs=10, seed=s, axis=(1, 0, 0))
    for x in (-0.36, 0.36):
        b.box((x - 0.03, 0, -0.32), (x + 0.03, 0.47, 0.32), "gold", s)
    b.box((-0.06, 0.32, -0.33), (0.06, 0.46, -0.3), "gold", s)


def fence(b, s):
    for x in (-1.0, 1.0):
        b.box((x - 0.06, 0, -0.06), (x + 0.06, 1.1, 0.06), "wood", s)
    for y in (0.35, 0.8):
        b.box((-1.05, y, -0.03), (1.05, y + 0.1, 0.03), "planks", s)


def pillar(b, s):
    b.box((-0.45, 0, -0.45), (0.45, 0.3, 0.45), "stone", s)
    b.cyl((0, 0.3, 0), 0.32, 0.3, 3.4, "stone", segs=14, seed=s)
    b.box((-0.45, 3.7, -0.45), (0.45, 4.0, 0.45), "stone", s)


def torch(b, s):
    b.box((-0.06, -0.1, -0.06), (0.06, 0.1, 0.0), "metal", s)
    b.cyl((0, -0.25, 0.05), 0.03, 0.04, 0.45, "wood", segs=6, seed=s, axis=(0, 0.95, 0.3))
    b.blob((0, 0.32, 0.18), 0.09, "flame", seed=s, sub=1, rough=0.3, squash=(1, 1.7, 1))


def lantern(b, s):
    b.box((-0.12, 0, -0.12), (0.12, 0.03, 0.12), "metal", s)
    b.box((-0.12, 0.33, -0.12), (0.12, 0.36, 0.12), "metal", s)
    for x in (-0.11, 0.11):
        for z in (-0.11, 0.11):
            b.box((x - 0.01, 0.03, z - 0.01), (x + 0.01, 0.33, z + 0.01), "metal", s)
    b.blob((0, 0.15, 0), 0.06, "flame", seed=s, sub=1, rough=0.25, squash=(1, 1.6, 1))
    b.cyl((0, 0.36, 0), 0.04, 0.02, 0.12, "metal", segs=6, seed=s)


def lamppost(b, s):
    b.cyl((0, 0, 0), 0.12, 0.06, 3.6, "dark", segs=10, seed=s)
    b.box((-0.06, 3.5, -0.06), (0.06, 3.6, 0.7), "dark", s)
    b.box((-0.18, 3.38, 0.5), (0.18, 3.5, 0.9), "dark", s)
    b.box((-0.15, 3.36, 0.53), (0.15, 3.38, 0.87), "light", s)


def potplant(b, s):
    b.cyl((0, 0, 0), 0.2, 0.26, 0.4, "roof", segs=12, seed=s)
    b.blob((0, 0.65, 0), 0.38, "leaves", seed=s, sub=2, rough=0.35)


KINDS = {"tree": tree, "pine": pine, "bush": bush, "rock": rock, "boulder": boulder, "table": table, "chair": chair,
         "bookshelf": shelf, "bed": bed, "sofa": sofa, "bench": bench, "woodcrate": woodcrate, "chest": chest,
         "fence": fence, "pillar": pillar, "torch": torch, "lantern": lantern, "lamppost": lamppost,
         "potplant": potplant}
LIGHTS = {"torch": ((0, 0.34, 0.2), "orange", 4.0), "lantern": ((0, 0.16, 0), "amber", 3.0),
          "lamppost": ((0, 3.3, 0.7), "warm", 18.0)}
SOLID = {"tree", "pine", "rock", "boulder", "table", "bookshelf", "bed", "sofa", "bench", "woodcrate", "chest",
         "fence", "pillar", "lamppost", "potplant"}
TRUNK = {"tree": 0.25, "pine": 0.22, "lamppost": 0.15}


@lru_cache(None)
def mesh(kind, seed=1):
    b = B()
    KINDS[kind](b, seed)
    return b.arrays()


def instance(kind, pos, yaw=0.0, scale=1.0, seed=1):
    P, N, M, S = mesh(kind, seed)
    a = math.radians(yaw)
    R = np.array([[math.cos(a), 0, -math.sin(a)], [0, 1, 0], [math.sin(a), 0, math.cos(a)]])
    sc = np.asarray(scale if not isinstance(scale, (int, float)) else (scale,) * 3, float)
    return (P * sc) @ R.T + np.asarray(pos, float), (N / sc) @ R.T, M, S


def collider(kind, pos, yaw=0.0, scale=1.0, seed=1):
    P, _, _, _ = instance(kind, pos, yaw, scale, seed)
    lo, hi = P.min(0), P.max(0)
    if kind in TRUNK:
        r = TRUNK[kind] * (scale if isinstance(scale, (int, float)) else scale[0])
        c = np.asarray(pos, float)
        return np.array([c[0] - r, c[1], c[2] - r]), np.array([c[0] + r, hi[1], c[2] + r])
    return lo, hi


def occluders(kind, pos, yaw=0.0, scale=1.0, seed=1):
    P, _, M, _ = instance(kind, pos, yaw, scale, seed)
    out = []
    leaf = M == MATID["leaves"]
    for sel, shrink in ((~leaf, 0.08), (leaf, 0.25)):
        if sel.any():
            lo, hi = P[sel].min(0), P[sel].max(0)
            d = (hi - lo) * shrink
            out.append(tuple(lo + d) + tuple(hi - d))
    return out
