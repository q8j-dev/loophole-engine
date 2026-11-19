import json
import math

import numpy as np

from .bake import LMH, LMW, PAD
from .materials import MATID

EPS = 0.004


class Mesh:
    def __init__(self, keys):
        self.keys = keys
        self.data = {k: [] for k in keys}
        self.ntri = 0

    def tri(self, verts):
        for k, size in self.keys.items():
            for v in verts:
                val = v[k]
                if size == 1:
                    self.data[k].append(float(val))
                else:
                    self.data[k].extend(float(x) for x in val)
        self.ntri += 1

    def quad(self, a, b, c, d):
        self.tri([a, b, c])
        self.tri([a, c, d])

    def items(self, prec=4):
        out = {}
        for k, arr in self.data.items():
            out[k] = [round(x, prec) for x in arr]
        first = json.dumps(out, separators=(",", ":"))
        return [first] + ["{}"] * (self.ntri - 1)


WKEYS = {"aPos": 3, "aNrm": 3, "aLM": 2, "aMat": 1}


def V(p, n, lm, m):
    return {"aPos": p, "aNrm": n, "aLM": lm, "aMat": m}


def world_mesh(meta):
    m = Mesh(WKEYS)
    for r in meta["rects"]:
        ax, u, v = r["axis"], r["u"], r["v"]
        n = [0.0, 0.0, 0.0]
        n[ax] = float(r["sgn"])
        mid = MATID[r["mat"]]
        corners = []
        for (cu, cv) in ((0, 0), (1, 0), (1, 1), (0, 1)):
            uu = r["u0"] - EPS + cu * (r["u1"] - r["u0"] + 2 * EPS)
            vv = r["v0"] - EPS + cv * (r["v1"] - r["v0"] + 2 * EPS)
            p = [0.0, 0.0, 0.0]
            p[ax] = r["pl"]
            p[u] = uu
            p[v] = vv
            lx = (r["ax"] + PAD + (uu - r["u0"]) / (r["u1"] - r["u0"]) * r["tu"]) / LMW
            ly = (r["ay"] + PAD + (vv - r["v0"]) / (r["v1"] - r["v0"]) * r["tv"]) / LMH
            corners.append(V(p, n, [lx, ly], mid))
        m.quad(*corners)
    for (cx, cy, cz, hu, hv) in meta["panels"]:
        dn = [0.0, -1.0, 0.0]
        for (y, e, mid) in ((cy + 0.003, 0.07, 11), (cy, 0.0, 10)):
            a = V([cx - hu - e, y, cz - hv - e], dn, [0, 0], mid)
            b = V([cx + hu + e, y, cz - hv - e], dn, [0, 0], mid)
            c = V([cx + hu + e, y, cz + hv + e], dn, [0, 0], mid)
            d = V([cx - hu - e, y, cz + hv + e], dn, [0, 0], mid)
            m.quad(a, b, c, d)
    return m


def portal_disc(seg=56):
    m = Mesh({"aPos": 3})
    for i in range(seg):
        a0 = 2 * math.pi * i / seg
        a1 = 2 * math.pi * (i + 1) / seg
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        m.tri([{"aPos": [0, 0, 0]}, {"aPos": [c0, s0, 0]}, {"aPos": [c1, s1, 0]}])
        R = 1.22
        m.quad({"aPos": [c0, s0, 0]}, {"aPos": [c1, s1, 0]}, {"aPos": [c1 * R, s1 * R, 0]}, {"aPos": [c0 * R, s0 * R, 0]})
    return m


def quad_mesh():
    m = Mesh({"aPos": 3})
    m.quad({"aPos": [-1, -1, 0]}, {"aPos": [1, -1, 0]}, {"aPos": [1, 1, 0]}, {"aPos": [-1, 1, 0]})
    return m


def text_quads(n=96):
    m = Mesh({"aSlot": 1, "aCorner": 2})
    for i in range(n):
        m.quad(*[{"aSlot": i, "aCorner": c} for c in ([0, 0], [1, 0], [1, 1], [0, 1])])
    return m


def particles(n, seed):
    rng = np.random.default_rng(seed)
    m = Mesh({"aSeed": 4, "aCorner": 2})
    for _ in range(n):
        s = list(rng.random(4))
        cs = [{"aSeed": s, "aCorner": c} for c in ([-1, -1], [1, -1], [1, 1], [-1, 1])]
        m.quad(*cs)
    return m


def grass_cards(n, seed, cell=28.0):
    rng = np.random.default_rng(seed)
    m = Mesh({"aSeed": 4, "aCorner": 3})
    g = int(math.ceil(math.sqrt(n)))
    for i in range(n):
        gx, gz = (i % g + rng.random()) / g, (i // g + rng.random()) / g
        s = [gx, gz, float(rng.random()), float(rng.random())]
        for q in range(2):
            cs = [{"aSeed": s, "aCorner": [x, y, q]} for x, y in ((-1, 0), (1, 0), (1, 1), (-1, 1))]
            m.quad(*cs)
    return m
