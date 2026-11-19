import argparse
import math
from pathlib import Path

import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parents[1] / "loophole" / "data" / "glyphs.npz"


class FlatPen(BasePen):
    def __init__(self, gs, step):
        super().__init__(gs)
        self.contours = []
        self.cur = []
        self.step = step

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, a, b, c):
        p0 = self.cur[-1]
        n = max(2, int(math.dist(p0, c) / self.step))
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((u ** 3 * p0[0] + 3 * u * u * t * a[0] + 3 * u * t * t * b[0] + t ** 3 * c[0],
                             u ** 3 * p0[1] + 3 * u * u * t * a[1] + 3 * u * t * t * b[1] + t ** 3 * c[1]))

    def _qCurveToOne(self, a, b):
        p0 = self.cur[-1]
        n = max(2, int(math.dist(p0, b) / self.step))
        for i in range(1, n + 1):
            t = i / n
            u = 1 - t
            self.cur.append((u * u * p0[0] + 2 * u * t * a[0] + t * t * b[0], u * u * p0[1] + 2 * u * t * a[1] + t * t * b[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = []

    _endPath = _closePath


def triangulate(contours):
    edges = []
    for c in contours:
        for i in range(len(c)):
            (x0, y0), (x1, y1) = c[i], c[(i + 1) % len(c)]
            if abs(y1 - y0) > 1e-9:
                edges.append((x0, y0, x1, y1, 1 if y1 > y0 else -1))
    ys = sorted(set(round(p[1], 6) for c in contours for p in c))
    tris = []

    def xat(e, y):
        x0, y0, x1, y1, _ = e
        return x0 + (x1 - x0) * (y - y0) / (y1 - y0)

    for ya, yb in zip(ys, ys[1:]):
        if yb - ya < 1e-7:
            continue
        ym = (ya + yb) / 2
        act = [e for e in edges if min(e[1], e[3]) <= ym <= max(e[1], e[3])]
        act.sort(key=lambda e: xat(e, ym))
        w = 0
        left = None
        for e in act:
            nw = w + e[4]
            if w == 0 and nw != 0:
                left = e
            elif w != 0 and nw == 0:
                la, lb, ra, rb = xat(left, ya), xat(left, yb), xat(e, ya), xat(e, yb)
                if ra - la > 1e-7:
                    tris.append([(la, ya), (ra, ya), (rb, yb)])
                if rb - lb > 1e-7:
                    tris.append([(la, ya), (rb, yb), (lb, yb)])
            w = nw
    return np.array(tris, np.float32).reshape(-1, 3, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    a = ap.parse_args()
    f = TTFont(a.font)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    cap = float(f["OS/2"].sCapHeight)
    out = {}
    for code in range(32, 127):
        name = cmap.get(code)
        if name is None:
            continue
        pen = FlatPen(gs, cap * 0.04)
        gs[name].draw(pen)
        cs = [[(x / cap, y / cap) for x, y in c] for c in pen.contours]
        out[f"g{code}"] = triangulate(cs)
        out[f"w{code}"] = np.array([0.0, gs[name].width / cap, 0.0, 1.0], np.float32)
    np.savez_compressed(OUT, **out)
    print("glyphs", len(out) // 2, sum(len(v) for k, v in out.items() if k[0] == "g"), "triangles")


if __name__ == "__main__":
    main()
