import math

import numpy as np

from .materials import MATID


class G:
    def __init__(self):
        self.P, self.N, self.M, self.S = [], [], [], []
        self.occ = []

    def quad(self, a, b, c, d, mat, seed=0):
        a, b, c, d = (np.asarray(v, float) for v in (a, b, c, d))
        n = np.cross(b - a, c - a)
        ln = np.linalg.norm(n)
        if ln < 1e-9:
            return
        n /= ln
        for tri in ((a, b, c), (a, c, d)):
            self.P += list(tri)
            self.N += [n] * 3
            self.M += [MATID[mat]] * 3
            self.S += [seed] * 3

    def tri(self, a, b, c, mat, seed=0, center=None):
        a, b, c = (np.asarray(v, float) for v in (a, b, c))
        n = np.cross(b - a, c - a)
        if center is not None and np.dot(n, (a + b + c) / 3 - np.asarray(center, float)) < 0:
            b, c = c, b
            n = -n
        ln = np.linalg.norm(n)
        if ln < 1e-9:
            return
        n /= ln
        self.P += [a, b, c]
        self.N += [n] * 3
        self.M += [MATID[mat]] * 3
        self.S += [seed] * 3

    def box(self, lo, hi, mat, seed=0, skip=()):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        faces = {"+z": ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)),
                 "-z": ((x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)),
                 "+x": ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)),
                 "-x": ((x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)),
                 "+y": ((x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)),
                 "-y": ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))}
        for k, f in faces.items():
            if k not in skip:
                self.quad(*f, mat, seed)

    def obox(self, c, ax, ay, az, hx, hy, hz, mat, seed=0):
        c = np.asarray(c, float)
        ax, ay, az = (np.asarray(v, float) for v in (ax, ay, az))
        pts = {}
        for sx in (-1, 1):
            for sy in (-1, 1):
                for sz in (-1, 1):
                    pts[(sx, sy, sz)] = c + ax * hx * sx + ay * hy * sy + az * hz * sz
        for (a, b, cc, d) in (((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),
                              ((1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)),
                              ((1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)),
                              ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)),
                              ((-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)),
                              ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1))):
            self.quad(pts[a], pts[b], pts[cc], pts[d], mat, seed)

    def arrays(self):
        if not self.P:
            z = np.zeros((0, 3))
            return z, z, np.zeros(0), np.zeros(0)
        return (np.array(self.P, float), np.array(self.N, float), np.array(self.M, float), np.array(self.S, float))


def opening_frame(g, b, side, at, w, h, bottom, kind, frame_mat, sill_mat):
    x0, z0, x1, z1, y, t = b["x0"], b["z0"], b["x1"], b["z1"], b["y"], b["t"]
    fw, fd = 0.09, 0.07
    yb = y + bottom
    yt = yb + h
    if side in ("-z", "+z"):
        out = -1 if side == "-z" else 1
        zf = z0 if side == "-z" else z1
        u0, u1 = at - w / 2, at + w / 2

        def P(u, yy, d):
            return (u, yy, zf + out * d)
        rng = ((u0 - fw, u0), (u1, u1 + fw))
        for (a, c) in rng:
            g.box(np.minimum(P(a, yb, -0.02), P(c, yt, fd)), np.maximum(P(a, yb, -0.02), P(c, yt, fd)), frame_mat)
        g.box(np.minimum(P(u0 - fw, yt, -0.02), P(u1 + fw, yt + fw, fd)), np.maximum(P(u0 - fw, yt, -0.02), P(u1 + fw, yt + fw, fd)), frame_mat)
        if kind == "window":
            g.box(np.minimum(P(u0 - fw - 0.06, yb - 0.08, -0.04), P(u1 + fw + 0.06, yb, fd + 0.1)),
                  np.maximum(P(u0 - fw - 0.06, yb - 0.08, -0.04), P(u1 + fw + 0.06, yb, fd + 0.1)), sill_mat)
            g.box(np.minimum(P(u0, yb, -t + 0.02), P(u1, yb + 0.02, 0.0)), np.maximum(P(u0, yb, -t + 0.02), P(u1, yb + 0.02, 0.0)), frame_mat)
            mid = (u0 + u1) / 2
            g.box(np.minimum(P(mid - 0.03, yb, -t / 2 - 0.03), P(mid + 0.03, yt, -t / 2 + 0.03)),
                  np.maximum(P(mid - 0.03, yb, -t / 2 - 0.03), P(mid + 0.03, yt, -t / 2 + 0.03)), frame_mat)
            ym = yb + h * 0.55
            g.box(np.minimum(P(u0, ym - 0.03, -t / 2 - 0.03), P(u1, ym + 0.03, -t / 2 + 0.03)),
                  np.maximum(P(u0, ym - 0.03, -t / 2 - 0.03), P(u1, ym + 0.03, -t / 2 + 0.03)), frame_mat)
            zg = zf + out * (-t / 2)
            g.quad((u0, yb, zg), (u1, yb, zg), (u1, yt, zg), (u0, yt, zg), "windowglass")
            g.quad((u1, yb, zg), (u0, yb, zg), (u0, yt, zg), (u1, yt, zg), "windowglass")
    else:
        out = -1 if side == "-x" else 1
        xf = x0 if side == "-x" else x1
        u0, u1 = at - w / 2, at + w / 2

        def P(u, yy, d):
            return (xf + out * d, yy, u)
        for (a, c) in ((u0 - fw, u0), (u1, u1 + fw)):
            g.box(np.minimum(P(a, yb, -0.02), P(c, yt, fd)), np.maximum(P(a, yb, -0.02), P(c, yt, fd)), frame_mat)
        g.box(np.minimum(P(u0 - fw, yt, -0.02), P(u1 + fw, yt + fw, fd)), np.maximum(P(u0 - fw, yt, -0.02), P(u1 + fw, yt + fw, fd)), frame_mat)
        if kind == "window":
            g.box(np.minimum(P(u0 - fw - 0.06, yb - 0.08, -0.04), P(u1 + fw + 0.06, yb, fd + 0.1)),
                  np.maximum(P(u0 - fw - 0.06, yb - 0.08, -0.04), P(u1 + fw + 0.06, yb, fd + 0.1)), sill_mat)
            mid = (u0 + u1) / 2
            g.box(np.minimum(P(mid - 0.03, yb, -t / 2 - 0.03), P(mid + 0.03, yt, -t / 2 + 0.03)),
                  np.maximum(P(mid - 0.03, yb, -t / 2 - 0.03), P(mid + 0.03, yt, -t / 2 + 0.03)), frame_mat)
            ym = yb + h * 0.55
            g.box(np.minimum(P(u0, ym - 0.03, -t / 2 - 0.03), P(u1, ym + 0.03, -t / 2 + 0.03)),
                  np.maximum(P(u0, ym - 0.03, -t / 2 - 0.03), P(u1, ym + 0.03, -t / 2 + 0.03)), frame_mat)
            xg = xf + out * (-t / 2)
            g.quad((xg, yb, u1), (xg, yb, u0), (xg, yt, u0), (xg, yt, u1), "windowglass")
            g.quad((xg, yb, u0), (xg, yb, u1), (xg, yt, u1), (xg, yt, u0), "windowglass")


def roof(g, b):
    x0, z0, x1, z1 = b["x0"], b["z0"], b["x1"], b["z1"]
    top = b["top"]
    kind = b["roof_shape"]
    ov = 0.45
    if kind == "flat":
        h = 0.55
        for (lo, hi) in (((x0, top, z0), (x1, top + h, z0 + 0.25)), ((x0, top, z1 - 0.25), (x1, top + h, z1)),
                         ((x0, top, z0), (x0 + 0.25, top + h, z1)), ((x1 - 0.25, top, z0), (x1, top + h, z1))):
            g.box(lo, hi, b["walls"], skip=("-y",))
        for (lo, hi) in (((x0 - 0.05, top + h, z0 - 0.05), (x1 + 0.05, top + h + 0.08, z0 + 0.3)),
                         ((x0 - 0.05, top + h, z1 - 0.3), (x1 + 0.05, top + h + 0.08, z1 + 0.05)),
                         ((x0 - 0.05, top + h, z0 - 0.05), (x0 + 0.3, top + h + 0.08, z1 + 0.05)),
                         ((x1 - 0.3, top + h, z0 - 0.05), (x1 + 0.05, top + h + 0.08, z1 + 0.05))):
            g.box(lo, hi, "concrete")
        return
    along_x = (x1 - x0) >= (z1 - z0)
    pitch = math.radians(b["pitch"])
    if along_x:
        half = (z1 - z0) / 2
        rise = math.tan(pitch) * half
        zc = (z0 + z1) / 2
        ridge = top + rise
        ctr = ((x0 + x1) / 2, top, zc)
        for x in (x0, x1):
            g.tri((x, top, z0), (x, top, z1), (x, ridge, zc), b["walls"], center=ctr)
        for sgn in (-1, 1):
            ze = zc + sgn * (half + ov)
            ye = top - math.tan(pitch) * ov
            slope = np.array([0, ridge - ye, zc - ze])
            L = np.linalg.norm(slope)
            ay = slope / L
            ax = np.array([1.0, 0, 0])
            az = np.cross(ax, ay) * sgn
            c = np.array([(x0 + x1) / 2, (ridge + ye) / 2, (zc + ze) / 2]) + az * 0.08
            g.obox(c, ax, ay, az, (x1 - x0) / 2 + ov, L / 2, 0.08, b["roof"])
            g.obox(np.array([(x0 + x1) / 2, ye - 0.06, ze]), ax, np.array([0, 1.0, 0]), np.array([0, 0, 1.0]),
                   (x1 - x0) / 2 + ov, 0.12, 0.03, "wood")
        g.obox(np.array([(x0 + x1) / 2, ridge + 0.12, zc]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]),
               np.array([0, 0, 1.0]), (x1 - x0) / 2 + ov, 0.08, 0.14, b["roof"])
        g.occ.append((x0, top, z0, x1, top + rise * 0.6, z1))
    else:
        half = (x1 - x0) / 2
        rise = math.tan(pitch) * half
        xc = (x0 + x1) / 2
        ridge = top + rise
        ctr = (xc, top, (z0 + z1) / 2)
        g.tri((x0, top, z0), (x1, top, z0), (xc, ridge, z0), b["walls"], center=ctr)
        g.tri((x1, top, z1), (x0, top, z1), (xc, ridge, z1), b["walls"], center=ctr)
        for sgn in (-1, 1):
            xe = xc + sgn * (half + ov)
            ye = top - math.tan(pitch) * ov
            slope = np.array([xc - xe, ridge - ye, 0])
            L = np.linalg.norm(slope)
            ay = slope / L
            az = np.array([0, 0, 1.0])
            ax = np.cross(ay, az) * sgn
            c = np.array([(xc + xe) / 2, (ridge + ye) / 2, (z0 + z1) / 2]) + ax * 0.08
            g.obox(c, ax, ay, az, 0.08, L / 2, (z1 - z0) / 2 + ov, b["roof"])
            g.obox(np.array([xe, ye - 0.06, (z0 + z1) / 2]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]),
                   np.array([0, 0, 1.0]), 0.03, 0.12, (z1 - z0) / 2 + ov, "wood")
        g.obox(np.array([xc, ridge + 0.12, (z0 + z1) / 2]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]),
               np.array([0, 0, 1.0]), 0.14, 0.08, (z1 - z0) / 2 + ov, b["roof"])
        g.occ.append((x0, top, z0, x1, top + rise * 0.6, z1))


def geometry(buildings):
    g = G()
    for b in buildings:
        x0, z0, x1, z1, y = b["x0"], b["z0"], b["x1"], b["z1"], b["y"]
        pl = 0.05
        doors = [(s_, at, w) for (s_, at, w, h, bot, k) in b["openings"] if k == "door"]
        for side in ("-z", "+z", "-x", "+x"):
            a0, a1 = (x0 - pl, x1 + pl) if side in ("-z", "+z") else (z0 - pl, z1 + pl)
            cuts = sorted((at - w / 2 - 0.09, at + w / 2 + 0.09) for (s_, at, w) in doors if s_ == side)
            spans = []
            cur = a0
            for c0, c1 in cuts:
                if c0 > cur:
                    spans.append((cur, c0))
                cur = max(cur, c1)
            if cur < a1:
                spans.append((cur, a1))
            for u0, u1 in spans:
                if side == "-z":
                    g.box((u0, y - 0.25, z0 - pl), (u1, y + 0.45, z0 + 0.01), b["plinth"], skip=("-y",))
                elif side == "+z":
                    g.box((u0, y - 0.25, z1 - 0.01), (u1, y + 0.45, z1 + pl), b["plinth"], skip=("-y",))
                elif side == "-x":
                    g.box((x0 - pl, y - 0.25, u0), (x0 + 0.01, y + 0.45, u1), b["plinth"], skip=("-y",))
                else:
                    g.box((x1 - 0.01, y - 0.25, u0), (x1 + pl, y + 0.45, u1), b["plinth"], skip=("-y",))
        for (side, at, w, h, bottom, kind) in b["openings"]:
            opening_frame(g, b, side, at, w, h, bottom, kind, b["trim"], b["sill"])
        yc = y + b["height"]
        t = b["t"]
        for (lo, hi) in (((x0 + t, yc - 0.12, z0 + t), (x1 - t, yc, z0 + t + 0.06)),
                         ((x0 + t, yc - 0.12, z1 - t - 0.06), (x1 - t, yc, z1 - t)),
                         ((x0 + t, yc - 0.12, z0 + t), (x0 + t + 0.06, yc, z1 - t)),
                         ((x1 - t - 0.06, yc - 0.12, z0 + t), (x1 - t, yc, z1 - t))):
            g.box(lo, hi, b["trim"])
        if b["roof_shape"]:
            roof(g, b)
    P, N, M, S = g.arrays()
    return P, N, M, S, g.occ
