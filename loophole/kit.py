import math
from pathlib import Path

import numpy as np

from . import level as lvl
from .bake import LMH, LMW, PAD
from .materials import MATID, PANEL

EPS = 0.004
GAP = 0.018
CH = 0.009
DEP = 0.02
TRIM = 20
RUBBER = 21
FIXTURE = 11
LIGHT = 10



def h8(*k):
    x = 0
    for v in k:
        x = (x * 1103515245 + int(v) * 2654435761 + 12345) & 0xFFFFFFFF
    x ^= x >> 13
    x = (x * 0x5BD1E995) & 0xFFFFFFFF
    x ^= x >> 15
    return x & 255


class WB:
    def __init__(self):
        self.P = []
        self.N = []
        self.UV = []
        self.M = []
        self.A = []
        self.S = []

    def tri(self, ps, ns, uvs, m, aos, seed):
        for p, n, uv, a in zip(ps, ns, uvs, aos):
            self.P.append(p)
            self.N.append(n)
            self.UV.append(uv)
            self.M.append(m)
            self.A.append(a)
            self.S.append(seed)

    def quad(self, ps, n, lmf, m, aos=(1, 1, 1, 1), seed=0, ns=None):
        ns = ns or [n] * 4
        uvs = [lmf(p) for p in ps]
        a, b, c, d = range(4)
        self.tri([ps[a], ps[b], ps[c]], [ns[a], ns[b], ns[c]], [uvs[a], uvs[b], uvs[c]], m, [aos[a], aos[b], aos[c]],
                 seed)
        self.tri([ps[a], ps[c], ps[d]], [ns[a], ns[c], ns[d]], [uvs[a], uvs[c], uvs[d]], m, [aos[a], aos[c], aos[d]],
                 seed)

    def arrays(self):
        return (np.array(self.P, float), np.array(self.N, float), np.array(self.UV, float), np.array(self.M, float),
                np.array(self.A, float), np.array(self.S, float))


def lm_fn(r):
    du = r["u1"] - r["u0"]
    dv = r["v1"] - r["v0"]
    eu = 0.25 / max(r["tu"], 1)
    ev = 0.25 / max(r["tv"], 1)

    def f(p):
        fu = min(max((p[r["u"]] - r["u0"]) / du, eu), 1 - eu)
        fv = min(max((p[r["v"]] - r["v0"]) / dv, ev), 1 - ev)
        return [(r["ax"] + PAD + fu * r["tu"]) / LMW, (r["ay"] + PAD + fv * r["tv"]) / LMH]
    return f


def frame(r):
    ax, u, v = r["axis"], r["u"], r["v"]
    n = np.zeros(3)
    n[ax] = r["sgn"]
    eu = np.zeros(3)
    eu[u] = 1
    ev = np.zeros(3)
    ev[v] = 1
    return n, eu, ev


def pt(r, a, b, h):
    p = np.zeros(3)
    p[r["axis"]] = r["pl"] + r["sgn"] * h
    p[r["u"]] = a
    p[r["v"]] = b
    return p


def oriented(ps, n):
    e1 = ps[1] - ps[0]
    e2 = ps[2] - ps[0]
    if np.dot(np.cross(e1, e2), n) < 0:
        return ps[::-1]
    return ps


def flat_rect(wb, r, lmf, mid, h=0.0, ext=EPS, ao=1.0):
    ps = [pt(r, r["u0"] - ext, r["v0"] - ext, h), pt(r, r["u1"] + ext, r["v0"] - ext, h),
          pt(r, r["u1"] + ext, r["v1"] + ext, h), pt(r, r["u0"] - ext, r["v1"] + ext, h)]
    n, _, _ = frame(r)
    wb.quad(oriented(ps, n), list(n), lmf, mid, (ao,) * 4)


def cells(a0, a1, size):
    out = []
    k = math.floor(a0 / size + 1e-6)
    while k * size < a1 - 1e-6:
        c0 = max(a0, k * size)
        c1 = min(a1, (k + 1) * size)
        if c1 - c0 > 1e-4:
            out.append((k, c0, c1))
        k += 1
    return out


def panel(wb, r, lmf, mid, a0, a1, b0, b1, seed, gap=GAP, ch=CH, dep=DEP, lip=None):
    n, eu, ev = frame(r)
    g = gap / 2
    ta0, ta1, tb0, tb1 = a0 + g + ch, a1 - g - ch, b0 + g + ch, b1 - g - ch
    sa0, sa1, sb0, sb1 = a0 + g, a1 - g, b0 + g, b1 - g
    if ta1 <= ta0 or tb1 <= tb0:
        return
    top = [pt(r, ta0, tb0, 0), pt(r, ta1, tb0, 0), pt(r, ta1, tb1, 0), pt(r, ta0, tb1, 0)]
    wb.quad(oriented(top, n), list(n), lmf, mid, (1, 1, 1, 1), seed)
    sides = [((ta0, tb0), (ta1, tb0), (sa0, sb0), (sa1, sb0), -ev),
             ((ta1, tb0), (ta1, tb1), (sa1, sb0), (sa1, sb1), eu),
             ((ta1, tb1), (ta0, tb1), (sa1, sb1), (sa0, sb1), ev),
             ((ta0, tb1), (ta0, tb0), (sa0, sb1), (sa0, sb0), -eu)]
    for (i0, i1, o0, o1, d) in sides:
        cn = n + d
        cn = cn / np.linalg.norm(cn)
        q = [pt(r, *i0, 0), pt(r, *i1, 0), pt(r, *o1, -ch), pt(r, *o0, -ch)]
        wb.quad(oriented(q, cn), list(cn), lmf, mid, (1, 1, 0.82, 0.82), seed)
        w = [pt(r, *o0, -ch), pt(r, *o1, -ch), pt(r, *o1, -dep), pt(r, *o0, -dep)]
        wb.quad(oriented(w, d), list(d), lmf, mid, (0.82, 0.82, 0.3, 0.3), seed)


OPEN = []


def is_open(r, a0, a1, b0, b1):
    for (ax, sg, p) in OPEN:
        if ax != r["axis"] or sg != r["sgn"] or abs(p[ax] - r["pl"]) > 0.05:
            continue
        if a0 <= p[r["u"]] <= a1 and b0 <= p[r["v"]] <= b1:
            return True
    return False


def recess(wb, r, lmf, a0, a1, b0, b1, depth=0.26):
    g = GAP / 2
    a0, a1, b0, b1 = a0 + g, a1 - g, b0 + g, b1 - g
    n, eu, ev = frame(r)
    back = [pt(r, a0, b0, -depth), pt(r, a1, b0, -depth), pt(r, a1, b1, -depth), pt(r, a0, b1, -depth)]
    wb.quad(oriented(back, n), list(n), lmf, 4, (0.25, 0.25, 0.25, 0.25))
    for (p0, p1, d) in (((a0, b0), (a1, b0), ev), ((a1, b0), (a1, b1), -eu), ((a1, b1), (a0, b1), -ev),
                        ((a0, b1), (a0, b0), eu)):
        q = [pt(r, *p0, -DEP), pt(r, *p1, -DEP), pt(r, *p1, -depth), pt(r, *p0, -depth)]
        wb.quad(oriented(q, d), list(d), lmf, TRIM, (0.6, 0.6, 0.3, 0.3))
    lip = 0.025
    for (p0, p1, q0, q1) in (((a0 - lip, b0 - lip), (a1 + lip, b0), None, None),
                             ((a0 - lip, b1), (a1 + lip, b1 + lip), None, None),
                             ((a0 - lip, b0), (a0, b1), None, None), ((a1, b0), (a1 + lip, b1), None, None)):
        lo = pt(r, p0[0], p0[1], -DEP)
        hi = pt(r, p1[0], p1[1], 0.006)
        box(wb, np.minimum(lo, hi), np.maximum(lo, hi), lmf, TRIM)


def surface(wb, r, lmf):
    m = r["mat"]
    mid = MATID[m]
    if m not in PANEL:
        flat_rect(wb, r, lmf, mid)
        return
    ph, pv = PANEL[m]
    if r["axis"] == 1:
        su, sv = ph, ph
    elif r["u"] == 1:
        su, sv = pv, ph
    else:
        su, sv = ph, pv
    has_open = m in ("white", "metal") and r["axis"] != 1 and any(
        is_open(r, a0, a1, b0, b1) for _, a0, a1 in cells(r["u0"], r["u1"], su) for _, b0, b1 in cells(r["v0"], r["v1"], sv))
    if not has_open:
        flat_rect(wb, r, lmf, mid, -DEP, ext=DEP + EPS, ao=0.25)
    else:
        n_, _, _ = frame(r)
        for _, a0, a1 in cells(r["u0"], r["u1"], su):
            for _, b0, b1 in cells(r["v0"], r["v1"], sv):
                if is_open(r, a0, a1, b0, b1):
                    continue
                e = EPS
                ps = [pt(r, a0 - e, b0 - e, -DEP), pt(r, a1 + e, b0 - e, -DEP), pt(r, a1 + e, b1 + e, -DEP),
                      pt(r, a0 - e, b1 + e, -DEP)]
                wb.quad(oriented(ps, n_), list(n_), lmf, mid, (0.25,) * 4)
    for ka, a0, a1 in cells(r["u0"], r["u1"], su):
        for kb, b0, b1 in cells(r["v0"], r["v1"], sv):
            seed = h8(r["axis"], r["sgn"], int(round(r["pl"] * 2)), ka, kb, mid)
            if m in ("white", "metal") and r["axis"] != 1 and is_open(r, a0, a1, b0, b1):
                recess(wb, r, lmf, a0, a1, b0, b1)
            elif m == "floor":
                panel(wb, r, lmf, mid, a0, a1, b0, b1, seed, gap=0.012, ch=0.006, dep=0.012)
            elif m == "ceil":
                panel(wb, r, lmf, mid, a0, a1, b0, b1, seed, gap=0.03, ch=0.012, dep=0.05)
            else:
                panel(wb, r, lmf, mid, a0, a1, b0, b1, seed)


class RectIndex:
    def __init__(self, rects):
        self.by = {}
        for i, r in enumerate(rects):
            self.by.setdefault((r["axis"], r["sgn"], round(r["pl"], 3)), []).append(r)

    def find(self, axis, sgn, pl, p):
        best = None
        bd = 1e9
        for r in self.by.get((axis, sgn, round(pl, 3)), []):
            du = max(r["u0"] - p[r["u"]], 0, p[r["u"]] - r["u1"])
            dv = max(r["v0"] - p[r["v"]], 0, p[r["v"]] - r["v1"])
            d = du + dv
            if d < bd:
                bd = d
                best = r
        return best if bd < 0.3 else None


def box(wb, lo, hi, lmf, mid, ao_bottom=1.0, skip=()):
    lo = np.array(lo, float)
    hi = np.array(hi, float)
    for ax in range(3):
        for sg in (-1, 1):
            if (ax, sg) in skip:
                continue
            u, v = [a for a in range(3) if a != ax]
            n = np.zeros(3)
            n[ax] = sg
            ps = []
            for (cu, cv) in ((0, 0), (1, 0), (1, 1), (0, 1)):
                p = np.zeros(3)
                p[ax] = hi[ax] if sg > 0 else lo[ax]
                p[u] = hi[u] if cu else lo[u]
                p[v] = hi[v] if cv else lo[v]
                ps.append(p)
            ao = [1.0] * 4
            if ax != 1:
                ao = [ao_bottom if p[1] <= lo[1] + 1e-6 else 1.0 for p in ps]
            o = oriented(ps, n)
            if o is not ps:
                ao = ao[::-1]
            wb.quad(o, list(n), lmf, mid, ao)


def edges(c):
    air = c.air
    sx, sy, sz = air.shape
    solid = ~air
    pad = np.ones((sx + 2, sy + 2, sz + 2), bool)
    pad[1:-1, 1:-1, 1:-1] = solid
    out = []
    dirs = [np.array(d) for d in ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))]
    for i in range(sx):
        for j in range(sy):
            for k in range(sz):
                if not air[i, j, k]:
                    continue
                if not pad[i + 1, j, k + 1]:
                    continue
                for d in dirs:
                    if pad[i + 1 + d[0], j + 1, k + 1 + d[2]]:
                        out.append(("base", i, j, k, tuple(d)))
                    if not pad[i + 1 + d[0], j + 1, k + 1 + d[2]] and not pad[i + 1 + d[0], j, k + 1 + d[2]]:
                        out.append(("lip", i, j, k, tuple(d)))
    return out


def runs(items):
    groups = {}
    for kind, i, j, k, d in items:
        along = 2 if d[0] != 0 else 0
        key = (kind, d, j) + ((i, None) if along == 2 else (None, k))
        idx = k if along == 2 else i
        groups.setdefault(key, []).append(idx)
    out = []
    for key, idxs in groups.items():
        idxs = sorted(set(idxs))
        s = idxs[0]
        prev = s
        for x in idxs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            out.append((key, s, prev + 1))
            if x is not None:
                s = x
                prev = x
    return out


def trims(wb, c, ri):
    o = c.origin
    R = 1.0 / lvl.RES
    for (kind, d, j, fi, fk), a, b in runs(edges(c)):
        dx, _, dz = d
        y = o[1] + j * R
        if kind == "base":
            if dx != 0:
                x = o[0] + (fi + (1 if dx > 0 else 0)) * R
                z0, z1 = o[2] + a * R, o[2] + b * R
                wall = ri.find(0, -dx, x, np.array([x, y + 0.3, (z0 + z1) / 2]))
                if wall is None or wall["mat"] not in ("white", "metal", "dark"):
                    continue
                lmf = lm_fn(wall)
                t = 0.013
                lo = [x - dx * t if dx > 0 else x, y, z0]
                hi = [x if dx > 0 else x - dx * t, y + 0.11, z1]
                lo[0], hi[0] = min(lo[0], hi[0]), max(lo[0], hi[0])
                box(wb, lo, hi, lmf, RUBBER, ao_bottom=0.55, skip=((0, dx),))
            else:
                z = o[2] + (fk + (1 if dz > 0 else 0)) * R
                x0, x1 = o[0] + a * R, o[0] + b * R
                wall = ri.find(2, -dz, z, np.array([(x0 + x1) / 2, y + 0.3, z]))
                if wall is None or wall["mat"] not in ("white", "metal", "dark"):
                    continue
                lmf = lm_fn(wall)
                t = 0.013
                lo = [x0, y, min(z, z - dz * t)]
                hi = [x1, y + 0.11, max(z, z - dz * t)]
                box(wb, lo, hi, lmf, RUBBER, ao_bottom=0.55, skip=((2, dz),))
        else:
            w = 0.045
            t = 0.004
            if dx != 0:
                x = o[0] + (fi + (1 if dx > 0 else 0)) * R
                z0, z1 = o[2] + a * R, o[2] + b * R
                top = ri.find(1, 1, y, np.array([x - dx * 0.2, y, (z0 + z1) / 2]))
                side = ri.find(0, dx, x, np.array([x, y - 0.2, (z0 + z1) / 2]))
                if top is None or side is None:
                    continue
                box(wb, [min(x - dx * w, x + dx * t), y, z0], [max(x - dx * w, x + dx * t), y + t, z1], lm_fn(top),
                    TRIM, skip=((1, -1),))
                box(wb, [min(x, x + dx * t), y - w, z0], [max(x, x + dx * t), y, z1], lm_fn(side), TRIM,
                    skip=((0, -dx), (1, 1)))
            else:
                z = o[2] + (fk + (1 if dz > 0 else 0)) * R
                x0, x1 = o[0] + a * R, o[0] + b * R
                top = ri.find(1, 1, y, np.array([(x0 + x1) / 2, y, z - dz * 0.2]))
                side = ri.find(2, dz, z, np.array([(x0 + x1) / 2, y - 0.2, z]))
                if top is None or side is None:
                    continue
                box(wb, [x0, y, min(z - dz * w, z + dz * t)], [x1, y + t, max(z - dz * w, z + dz * t)], lm_fn(top),
                    TRIM, skip=((1, -1),))
                box(wb, [x0, y - w, min(z, z + dz * t)], [x1, y, max(z, z + dz * t)], lm_fn(side), TRIM,
                    skip=((2, -dz), (1, 1)))


def fixture(wb, ri, cx, cy, cz, hu, hv):
    pl = cy + 0.006
    r = ri.find(1, -1, pl, np.array([cx, pl, cz]))
    lmf = lm_fn(r) if r else (lambda p: [0.0, 0.0])
    f = 0.06
    d = 0.045
    lip = 0.012
    x0, x1, z0, z1 = cx - hu - f, cx + hu + f, cz - hv - f, cz + hv + f
    box(wb, [x0, pl - d, z0], [x1, pl, z1], lmf, TRIM, skip=((1, 1), (1, -1)))
    y = pl - d
    rings = [(x0, z0, x1, z1), (cx - hu, cz - hv, cx + hu, cz + hv)]
    (ax0, az0, ax1, az1), (bx0, bz0, bx1, bz1) = rings
    dn = [0.0, -1.0, 0.0]
    for q in ([[ax0, y, az0], [ax1, y, az0], [bx1, y, bz0], [bx0, y, bz0]],
              [[ax1, y, az0], [ax1, y, az1], [bx1, y, bz1], [bx1, y, bz0]],
              [[ax1, y, az1], [ax0, y, az1], [bx0, y, bz1], [bx1, y, bz1]],
              [[ax0, y, az1], [ax0, y, az0], [bx0, y, bz0], [bx0, y, bz1]]):
        ps = [np.array(p) for p in q]
        wb.quad(oriented(ps, np.array(dn)), dn, lmf, TRIM, (1, 1, 1, 1))
    yi = y + lip
    for (p0, p1, nn) in (((bx0, bz0), (bx1, bz0), [0, 0, 1]), ((bx1, bz0), (bx1, bz1), [-1, 0, 0]),
                         ((bx1, bz1), (bx0, bz1), [0, 0, -1]), ((bx0, bz1), (bx0, bz0), [1, 0, 0])):
        ps = [np.array([p0[0], y, p0[1]]), np.array([p1[0], y, p1[1]]), np.array([p1[0], yi, p1[1]]),
              np.array([p0[0], yi, p0[1]])]
        wb.quad(oriented(ps, np.array(nn, float)), nn, lmf, FIXTURE, (1, 1, 0.7, 0.7))
    ps = [np.array(p) for p in ([bx0, yi, bz0], [bx1, yi, bz0], [bx1, yi, bz1], [bx0, yi, bz1])]
    wb.quad(oriented(ps, np.array(dn)), dn, lmf, LIGHT)


BEAM = 22
PAINT = 23
STRIPE = 24
GLASS = 25
GLYPHS = Path(__file__).resolve().parent / "data" / "glyphs.npz"


def beams(wb, c, ri):
    x0, y0, z0, x1, y1, z1 = c.main_box
    W, D = x1 - x0, z1 - z0
    along_x = W <= D
    span0, span1 = (x0, x1) if along_x else (z0, z1)
    o0, o1 = (z0, z1) if along_x else (x0, x1)
    n = max(1, int(round((o1 - o0) / 4.0)))
    for k in range(1, n):
        o = o0 + k * (o1 - o0) / n
        r = ri.find(1, -1, y1, np.array([(x0 + x1) / 2 if along_x else o, y1, o if along_x else (z0 + z1) / 2]))
        if r is None:
            continue
        lmf = lm_fn(r)
        yb = y1 - 0.34
        parts = [(yb, yb + 0.026, 0.11), (yb + 0.026, y1 - 0.026, 0.009), (y1 - 0.026, y1 + 0.02, 0.11)]
        for (ya, yc, hw) in parts:
            if along_x:
                box(wb, [span0, ya, o - hw], [span1, yc, o + hw], lmf, BEAM, ao_bottom=1.0)
            else:
                box(wb, [o - hw, ya, span0], [o + hw, yc, span1], lmf, BEAM, ao_bottom=1.0)
        m = int((span1 - span0) / 1.2)
        for j in range(1, m + 1):
            t = span0 + j * (span1 - span0) / (m + 1)
            for side in (-1, 1):
                if along_x:
                    box(wb, [t - 0.006, yb + 0.026, o + side * 0.009], [t + 0.006, y1 - 0.026, o + side * 0.1],
                        lmf, BEAM)
                else:
                    box(wb, [o + side * 0.009, yb + 0.026, t - 0.006], [o + side * 0.1, y1 - 0.026, t + 0.006],
                        lmf, BEAM)


def wall_frame(n):
    n = np.array(n, float)
    up = np.array([0.0, 1.0, 0.0])
    right = np.cross(-n, up)
    return right, up


def sign(wb, c, ri):
    if not GLYPHS.exists():
        return
    items = []
    items += [((x, y, z, n, h), t) for (x, y, z, n, h, t) in getattr(c, "signs", [])]
    for sg, text in items:
        sign_one(wb, ri, sg, text)


def sign_one(wb, ri, sg, text):
    x, y, z, n, hgt = sg
    g = np.load(GLYPHS)
    n = np.array(n, float)
    right, up = wall_frame(n)
    ax = int(np.argmax(np.abs(n)))
    base = np.array([x, y, z], float)
    wall = ri.find(ax, int(np.sign(n[ax])), base[ax], base + up * 0.5)
    if wall is None:
        return
    lmf = lm_fn(wall)
    cap = g["w0"][3] - g["w0"][2]
    sc = hgt / cap
    widths = [(g["w" + ch][1] - g["w" + ch][0]) * sc for ch in text]
    gap = 0.12 * hgt
    total = sum(widths) + gap * (len(text) - 1)
    cur = -total / 2
    if wall["mat"] in ("metal", "dark"):
        pw = total / 2 + 0.22 * hgt
        y0b, y1b = -0.32 * hgt, 1.18 * hgt
        q = [base + right * -pw + up * y0b + n * 0.0015, base + right * pw + up * y0b + n * 0.0015,
             base + right * pw + up * y1b + n * 0.0015, base + right * -pw + up * y1b + n * 0.0015]
        wb.quad(oriented(q, n), list(n), lmf, 16)
    for ch, w in zip(text, widths):
        tris = g["g" + ch]
        x0g = g["w" + ch][0]
        for t in tris:
            ps = []
            for (gx, gy) in t:
                p = base + right * (cur + (gx - x0g) * sc) + up * (gy - g["w0"][2]) * sc + n * 0.003
                ps.append(p)
            e1 = ps[1] - ps[0]
            e2 = ps[2] - ps[0]
            if np.dot(np.cross(e1, e2), n) < 0:
                ps = [ps[0], ps[2], ps[1]]
            wb.tri(ps, [list(n)] * 3, [lmf(p) for p in ps], PAINT, [1, 1, 1], 0)
        cur += w + gap
    bar_y = -0.16 * hgt
    q = [base + right * (-total / 2) + up * bar_y + n * 0.003, base + right * (total / 2) + up * bar_y + n * 0.003,
         base + right * (total / 2) + up * (bar_y + 0.05 * hgt) + n * 0.003,
         base + right * (-total / 2) + up * (bar_y + 0.05 * hgt) + n * 0.003]
    wb.quad(oriented(q, n), list(n), lmf, STRIPE)


def datum(wb, c, rects):
    yd = c.main_box[1] + 1.05
    for r in rects:
        if r["axis"] == 1 or r["mat"] not in ("white", "metal"):
            continue
        vy = "u" if r["u"] == 1 else "v"
        lo, hi = (r["u0"], r["u1"]) if vy == "u" else (r["v0"], r["v1"])
        if not (lo <= yd - 0.01 and hi >= yd + 0.06):
            continue
        n, _, _ = frame(r)
        lmf = lm_fn(r)
        if vy == "u":
            a0, a1 = yd, yd + 0.045
            ps = [pt(r, a0, r["v0"], 0.0025), pt(r, a1, r["v0"], 0.0025), pt(r, a1, r["v1"], 0.0025),
                  pt(r, a0, r["v1"], 0.0025)]
        else:
            b0, b1 = yd, yd + 0.045
            ps = [pt(r, r["u0"], b0, 0.0025), pt(r, r["u1"], b0, 0.0025), pt(r, r["u1"], b1, 0.0025),
                  pt(r, r["u0"], b1, 0.0025)]
        wb.quad(oriented(ps, n), list(n), lmf, STRIPE)


def windows(wb, c, ri):
    for (x0, y0, z0, x1, y1, z1, f) in c.windows:
        n = np.array(f, float)
        ax = int(np.argmax(np.abs(n)))
        s = n[ax]
        pl = [x0, y0, z0][ax]
        mid = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
        wall = ri.find(ax, int(s), pl, mid)
        if wall is None:
            continue
        lmf = lm_fn(wall)
        lo = np.array([x0, y0, z0], float)
        hi = np.array([x1, y1, z1], float)
        hz = 2 if ax == 0 else 0
        fw = 0.09
        dep = 0.06
        lo2 = lo.copy()
        hi2 = hi.copy()
        lo2[ax] = min(pl, pl + s * dep)
        hi2[ax] = max(pl, pl + s * dep)
        for (a, b) in (((lo2[hz] - fw, lo2[1] - fw), (hi2[hz] + fw, lo2[1])),
                       ((lo2[hz] - fw, hi2[1]), (hi2[hz] + fw, hi2[1] + fw)),
                       ((lo2[hz] - fw, lo2[1]), (lo2[hz], hi2[1])),
                       ((hi2[hz], lo2[1]), (hi2[hz] + fw, hi2[1]))):
            bl = lo2.copy()
            bh = hi2.copy()
            bl[hz], bl[1] = a
            bh[hz], bh[1] = b
            box(wb, bl, bh, lmf, TRIM, skip=((ax, -int(s)),))
        sill_l = lo2.copy()
        sill_h = hi2.copy()
        sill_l[1] = lo[1] - fw - 0.03
        sill_h[1] = lo[1] - fw
        sill_l[hz] -= fw + 0.05
        sill_h[hz] += fw + 0.05
        sill_l[ax] = min(pl, pl + s * (dep + 0.05))
        sill_h[ax] = max(pl, pl + s * (dep + 0.05))
        box(wb, sill_l, sill_h, lmf, TRIM, skip=((ax, -int(s)),))
        gp = pl + s * 0.008
        corners = []
        for (cu, cv) in ((0, 0), (1, 0), (1, 1), (0, 1)):
            p = np.zeros(3)
            p[ax] = gp
            p[hz] = lo[hz] if cu == 0 else hi[hz]
            p[1] = lo[1] if cv == 0 else hi[1]
            corners.append(p)
        if ax == 0:
            us = [-s * p[2] for p in corners]
        else:
            us = [s * p[0] for p in corners]
        umin, umax = min(us), max(us)
        width = hi[hz] - lo[hz]
        height = hi[1] - lo[1]
        seed = int(np.clip(round(width / height * 32), 1, 255))
        uvs = [[(u - umin) / (umax - umin), (p[1] - lo[1]) / height] for u, p in zip(us, corners)]
        order = [0, 1, 2, 3]
        e1 = corners[1] - corners[0]
        e2 = corners[2] - corners[0]
        if np.dot(np.cross(e1, e2), n) < 0:
            order = [3, 2, 1, 0]
        P = [corners[i] for i in order]
        U = [uvs[i] for i in order]
        gm = 19 if getattr(c, "lit_windows", False) else GLASS
        wb.tri([P[0], P[1], P[2]], [list(n)] * 3, [U[0], U[1], U[2]], gm, [1, 1, 1], seed)
        wb.tri([P[0], P[2], P[3]], [list(n)] * 3, [U[0], U[2], U[3]], gm, [1, 1, 1], seed)


def hazard_ring(wb, c, ri):
    for ring in getattr(c, "rings", []):
        ring_one(wb, ri, *ring)


def ring_one(wb, ri, bx, by, bz):
    r = ri.find(1, 1, by, np.array([bx, by, bz]))
    if r is None:
        return
    lmf = lm_fn(r)
    n = 64
    up = [0.0, 1.0, 0.0]
    for k in range(n):
        a0 = 2 * math.pi * k / n
        a1 = 2 * math.pi * (k + 1) / n
        ps = []
        for (rr, a) in ((1.08, a0), (1.08, a1), (1.24, a1), (1.24, a0)):
            ps.append(np.array([bx + rr * math.cos(a), by + 0.0025, bz + rr * math.sin(a)]))
        wb.quad(oriented(ps, np.array(up)), up, lmf, 27)


def build(c, meta, dirr=None):
    OPEN.clear()
    OPEN.extend(getattr(c, "open_panels", []))
    wb = WB()
    rects = meta["rects"]
    ri = RectIndex(rects)
    for r in rects:
        surface(wb, r, lm_fn(r))
    trims(wb, c, ri)
    for (cx, cy, cz, hu, hv) in meta["panels"]:
        fixture(wb, ri, cx, cy, cz, hu, hv)
    if getattr(c, "beams", True):
        beams(wb, c, ri)
    sign(wb, c, ri)
    if getattr(c, "stripe", True):
        datum(wb, c, rects)
    windows(wb, c, ri)
    hazard_ring(wb, c, ri)
    P, N, UV, Mt, A, S = wb.arrays()
    irr = np.zeros((len(P), 3))
    flag = np.zeros(len(P))
    from . import decor_place
    DP, DN, DM, DA, DS, _ = decor_place.build(c)
    if len(DP):
        di = np.asarray(dirr) if dirr is not None else np.zeros((len(DP), 3))
        if len(di) != len(DP):
            di = np.zeros((len(DP), 3))
        n0 = len(P)
        P = np.concatenate([P, DP])
        N = np.concatenate([N, DN])
        UV = np.concatenate([UV, DM[:, 0:2]])
        Mt = np.concatenate([Mt, np.full(len(DP), 40.0)])
        A = np.concatenate([A, DA])
        S = np.concatenate([S, DS])
        irr = np.concatenate([irr, di])
        flag = np.concatenate([flag, np.where(DM[:, 5] < 0, 2.0, 1.0)])
        tan = np.zeros((len(P), 3))
        tan[n0:] = DM[:, 2:5]
        return P, N, UV, Mt, A, S, irr, flag, tan
    return P, N, UV, Mt, A, S, irr, flag, np.zeros((len(P), 3))
