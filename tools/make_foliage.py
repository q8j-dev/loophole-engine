import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
KIT = ROOT / "loophole" / "data" / "kit"
sys.path.insert(0, str(HERE))
from lh_tiles import save_tile

TILE = 1024


def load_alpha(path):
    im = Image.open(path)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        arr = np.asarray(im).astype(np.float64)
        arr = arr / max(float(arr.max()), 1.0) * 255.0
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "L")
    return im.convert("L")


def load_rgba(src, diff, alpha):
    d = Image.open(src / diff).convert("RGB")
    a = load_alpha(src / alpha).resize(d.size)
    im = d.copy()
    im.putalpha(a)
    return im


def isolate(im, seed):
    al = np.asarray(im)[..., 3]
    m = Image.fromarray(((al > 40) * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))
    sx, sy = seed
    if m.getpixel((sx, sy)) == 0:
        return im
    ImageDraw.floodfill(m, (sx, sy), 128)
    keep = np.asarray(m) == 128
    arr = np.asarray(im).copy()
    arr[..., 3] = np.where(keep, arr[..., 3], 0)
    return Image.fromarray(arr, "RGBA")


def sprites(rgba, min_area=900, region=None, max_fill=0.62, max_frac=0.2):
    a = np.asarray(rgba)[..., 3] > 128
    H, W = a.shape
    lab = np.zeros((H, W), np.int32)
    out = []
    seen = np.zeros_like(a)
    step = 4
    for y in range(0, H, step):
        for x in range(0, W, step):
            if a[y, x] and not seen[y, x]:
                stack = [(y, x)]
                ys, xs = [], []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    ys.append(cy)
                    xs.append(cx)
                    for ny, nx in ((cy + step, cx), (cy - step, cx), (cy, cx + step), (cy, cx - step)):
                        if 0 <= ny < H and 0 <= nx < W and a[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(ys) * step * step >= min_area:
                    box = (max(min(xs) - 4, 0), max(min(ys) - 4, 0), min(max(xs) + 5, W), min(max(ys) + 5, H))
                    bw, bh = box[2] - box[0], box[3] - box[1]
                    fill = len(ys) * step * step / max(bw * bh, 1)
                    cy = (box[1] + box[3]) / 2 / H
                    if fill > max_fill or bw * bh > max_frac * W * H:
                        continue
                    if region is not None and not (region[0] <= cy <= region[1]):
                        continue
                    out.append(isolate(rgba.crop(box), (x - box[0], y - box[1])))
    return out


def cluster_card(leaves, size, seed, twig=(70, 52, 34), n=90, spread=0.9, leaf_scale=0.17):
    rng = np.random.default_rng(seed)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(canvas)
    base = np.array([size * 0.5, size * 0.98])
    tip = np.array([size * 0.5 + rng.uniform(-0.08, 0.08) * size, size * 0.06])
    pts = [base + (tip - base) * t + np.array([math.sin(t * 3.1) * size * 0.04, 0]) for t in np.linspace(0, 1, 12)]
    for i in range(len(pts) - 1):
        w = int(max(2, size * 0.018 * (1 - i / 12)))
        dr.line([tuple(pts[i]), tuple(pts[i + 1])], fill=twig + (255,), width=w)
    for k in range(n):
        t = rng.uniform(0.05, 1.0) ** 0.8
        p = base + (tip - base) * t
        side = 1 if k % 2 else -1
        ang = side * rng.uniform(20, 80) + rng.uniform(-15, 15)
        lf = leaves[int(rng.integers(0, len(leaves)))]
        sc = leaf_scale * size / max(lf.size) * rng.uniform(0.75, 1.15) * (0.7 + 0.3 * t)
        im = lf.resize((max(4, int(lf.size[0] * sc)), max(4, int(lf.size[1] * sc))), Image.LANCZOS)
        im = im.rotate(ang + 180 * (rng.random() < 0.15), expand=True, resample=Image.BICUBIC)
        shade = rng.uniform(0.85, 1.25)
        r, g, b, a = im.split()
        im = Image.merge("RGBA", (r.point(lambda v: v * shade), g.point(lambda v: v * shade), b.point(lambda v: v * shade * 0.95), a))
        w_ = spread * 0.5 * math.sin(math.pi * min(t * 1.1, 1.0)) + 0.05
        off = np.array([side * rng.uniform(0.0, w_) * size, rng.uniform(-0.05, 0.05) * size])
        q = p + off - np.array(im.size) / 2
        canvas.alpha_composite(im, (int(q[0]), int(q[1])))
    return canvas


def round_cluster(leaves, size, seed, n=55, leaf_scale=0.2, twig=(64, 48, 32)):
    rng = np.random.default_rng(seed)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    dr = ImageDraw.Draw(canvas)
    c = np.array([size / 2, size / 2])
    for k in range(7):
        a = rng.uniform(0, 2 * math.pi)
        e = c + np.array([math.cos(a), math.sin(a)]) * size * rng.uniform(0.25, 0.4)
        dr.line([tuple(c + rng.normal(0, size * 0.03, 2)), tuple(e)], fill=twig + (255,), width=max(2, size // 160))
    order = sorted(range(n), key=lambda i: rng.random())
    for k in order:
        r = (rng.uniform(0.0, 1.0) ** 0.55) * size * 0.4
        a = rng.uniform(0, 2 * math.pi)
        p = c + np.array([math.cos(a), math.sin(a)]) * r
        lf = leaves[int(rng.integers(0, len(leaves)))]
        sc = leaf_scale * size / max(lf.size) * rng.uniform(0.8, 1.2)
        im = lf.resize((max(4, int(lf.size[0] * sc)), max(4, int(lf.size[1] * sc))), Image.LANCZOS)
        ang = -math.degrees(a) - 90 + rng.uniform(-35, 35)
        im = im.rotate(ang, expand=True, resample=Image.BICUBIC)
        arr = np.asarray(im).astype(np.float32)
        depth = 0.78 + 0.22 * min(1.0, r / (size * 0.4))
        tint = np.array([rng.uniform(0.85, 1.12), rng.uniform(0.9, 1.08), rng.uniform(0.75, 1.0)]) * rng.uniform(0.8, 1.15)
        arr[..., :3] = np.clip(arr[..., :3] * tint * depth, 0, 255)
        im = Image.fromarray(arr.astype(np.uint8), "RGBA")
        q = p - np.array(im.size) / 2
        canvas.alpha_composite(im, (int(q[0]), int(q[1])))
    return canvas


def needle_card(twigs, size, seed):
    rng = np.random.default_rng(seed)
    h = size // 2
    canvas = Image.new("RGBA", (size, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(canvas)
    dr.line([(2, h // 2), (int(size * 0.7), h // 2)], fill=(58, 44, 30, 255), width=max(2, h // 60))
    for k in range(18):
        tw = twigs[int(rng.integers(0, len(twigs)))]
        x = rng.uniform(0.02, 0.9) * size
        span = h * (0.95 - 0.5 * x / size)
        sc = span / max(tw.size)
        im = tw.resize((max(4, int(tw.size[0] * sc)), max(4, int(tw.size[1] * sc))), Image.LANCZOS)
        side = 1 if k % 2 else -1
        im = im.rotate(side * rng.uniform(35, 75) - 90 * 0 + 180 * (side < 0), expand=True, resample=Image.BICUBIC)
        y = h / 2 - im.size[1] / 2 + side * im.size[1] * 0.25
        canvas.alpha_composite(im, (int(min(max(x - im.size[0] / 2, 0), size - im.size[0])), int(min(max(y, 0), h - im.size[1]))))
    return canvas


def rgba_to_maps(im, rough=0.6, nrm=None):
    a = np.asarray(im, np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3]
    m = al > 0.3
    rgb = dilate(rgb, m, 64)
    if m.any():
        mean = rgb[m].mean(0)
        grown = dilate(np.where(m[..., None], rgb, 0.0), m, 64)
        filled = np.abs(grown).sum(-1) > 1e-6
        rgb = np.where(filled[..., None], rgb, mean)
    lin = rgb ** 2.2
    alb = np.sqrt(lin)
    n = np.zeros_like(rgb)
    n[..., 0] = 0.5
    n[..., 1] = 0.5
    n[..., 2] = 1.0
    if nrm is not None:
        n = dilate(nrm, m)
    rm = np.stack([np.full(al.shape, rough), np.zeros_like(al), al], -1)
    return alb, n, rm


def dilate(a, mask, iters=24):
    a = a.copy()
    m = mask.copy()
    for _ in range(iters):
        pm = np.pad(m, 1)
        cnt = pm[:-2, 1:-1].astype(np.float32) + pm[2:, 1:-1] + pm[1:-1, :-2] + pm[1:-1, 2:]
        grow = (~m) & (cnt > 0)
        if not grow.any():
            break
        pa = np.pad(a * m[..., None], ((1, 1), (1, 1), (0, 0)))
        s = pa[:-2, 1:-1] + pa[2:, 1:-1] + pa[1:-1, :-2] + pa[1:-1, 2:]
        a = np.where(grow[..., None], s / np.maximum(cnt, 1)[..., None], a)
        m |= grow
    return a


def bark_strip(path, w, h, reps=3, tint=(1.0, 1.0, 1.0)):
    b = Image.open(path).convert("RGB").resize((w, h // reps), Image.LANCZOS)
    out = Image.new("RGB", (w, h))
    for k in range(reps):
        out.paste(b, (0, k * (h // reps)))
    a = (np.asarray(out, np.float32) / 255.0) * np.array(tint)
    return a


class Mesh:
    def __init__(self):
        self.P, self.N, self.UV, self.F, self.S, self.CN = [], [], [], [], [], []

    def tri(self, ps, ns, uvs, flag, sway, cn=None):
        for p, n, uv, s in zip(ps, ns, uvs, sway):
            self.P.append(p)
            self.N.append(n)
            self.UV.append(uv)
            self.F.append(flag)
            self.S.append(s)
            self.CN.append(n if cn is None else cn)

    def tube(self, path, radii, u0, u1, v0, v1, segs=8, sway=None, flag=1.0, vreps=1.0):
        path = np.asarray(path, float)
        n = len(path)
        frames = []
        up = np.array([1.0, 0.0, 0.0])
        for i in range(n):
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
            t /= np.linalg.norm(t)
            a = np.cross(t, up)
            if np.linalg.norm(a) < 1e-3:
                a = np.cross(t, np.array([0.0, 0.0, 1.0]))
            a /= np.linalg.norm(a)
            b = np.cross(t, a)
            frames.append((a, b))
            up = a
        L = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
        Lt = max(L[-1], 1e-6)
        rings = []
        for i in range(n):
            a, b = frames[i]
            ring = []
            for k in range(segs + 1):
                ang = 2 * math.pi * k / segs
                d = a * math.cos(ang) + b * math.sin(ang)
                ring.append((path[i] + d * radii[i], d, (u0 + (u1 - u0) * k / segs, v0 + (v1 - v0) * (L[i] / Lt))))
            rings.append(ring)
        sw = sway if sway is not None else [0.0] * n
        for i in range(n - 1):
            for k in range(segs):
                a, b, c, d = rings[i][k], rings[i][k + 1], rings[i + 1][k + 1], rings[i + 1][k]
                self.tri([a[0], b[0], c[0]], [a[1], b[1], c[1]], [a[2], b[2], c[2]], flag, [sw[i], sw[i], sw[i + 1]])
                self.tri([a[0], c[0], d[0]], [a[1], c[1], d[1]], [a[2], c[2], d[2]], flag, [sw[i], sw[i + 1], sw[i + 1]])

    def card(self, center, right, up, w, h, uv_rect, normal, sway=1.0, bend=0.0, billboard=False, rows=3):
        r = np.asarray(right, float) * w / 2
        u = np.asarray(up, float) * h
        c = np.asarray(center, float)
        nrm = np.asarray(normal, float)
        nrm = nrm / np.linalg.norm(nrm)
        cn = np.cross(np.asarray(right, float), np.asarray(up, float))
        cn = cn / max(np.linalg.norm(cn), 1e-9)
        x0, y0, x1, y1 = uv_rect
        grid = []
        for j in range(rows + 1):
            t = j / rows
            row = []
            for i in range(2):
                p = c + r * (i * 2 - 1) + u * t + np.array([0, -bend * t * t * h, 0])
                row.append((p, (x0 + (x1 - x0) * i, y1 + (y0 - y1) * t), sway * (0.4 + 0.6 * t)))
            grid.append(row)
        if billboard:
            mid = c + u * 0.5
            hw = w / 2
            corners = [(mid, (x0, y1), sway * 0.7, np.array([-hw, -h / 2, 0]) / 2.5),
                       (mid, (x1, y1), sway * 0.7, np.array([hw, -h / 2, 0]) / 2.5),
                       (mid, (x1, y0), sway, np.array([hw, h / 2, 0]) / 2.5),
                       (mid, (x0, y0), sway, np.array([-hw, h / 2, 0]) / 2.5)]
            a, b, cc, d = corners
            for tri in ((a, b, cc), (a, cc, d)):
                for p_, uv_, s_, o_ in tri:
                    self.P.append(p_)
                    self.N.append(nrm)
                    self.UV.append(uv_)
                    self.F.append(6.0)
                    self.S.append(s_)
                    self.CN.append(o_)
            return
        for j in range(rows):
            a, b, cc, d = grid[j][0], grid[j][1], grid[j + 1][1], grid[j + 1][0]
            self.tri([a[0], b[0], cc[0]], [nrm] * 3, [a[1], b[1], cc[1]], 5.0, [a[2], b[2], cc[2]], cn)
            self.tri([a[0], cc[0], d[0]], [nrm] * 3, [a[1], cc[1], d[1]], 5.0, [a[2], cc[2], d[2]], cn)

    def save(self, name):
        P = np.array(self.P, np.float32)
        N = np.array(self.N, np.float32)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-6)
        UV = np.array(self.UV, np.float32)
        T = np.zeros((len(P), 4), np.float32)
        for i in range(0, len(P), 3):
            p0, p1, p2 = P[i:i + 3]
            u0, u1, u2 = UV[i:i + 3]
            e1, e2 = p1 - p0, p2 - p0
            d1, d2 = u1 - u0, u2 - u0
            den = d1[0] * d2[1] - d2[0] * d1[1]
            tg = (e1 * d2[1] - e2 * d1[1]) / den if abs(den) > 1e-9 else np.array([1.0, 0, 0])
            for k in range(3):
                t = tg - N[i + k] * np.dot(tg, N[i + k])
                t /= max(np.linalg.norm(t), 1e-6)
                T[i + k, :3] = t
                T[i + k, 3] = 1.0
                if self.F[i + k] > 4.5:
                    T[i + k, :3] = self.CN[i + k]
        np.savez_compressed(KIT / f"kit_{name}.npz", pos=P, nrm=N, uv=UV, tan=T, flag=np.array(self.F, np.float32),
                            sway=np.array(self.S, np.float32))
        return len(P) // 3


def tangent_frame(n, rng):
    n = np.asarray(n, float)
    a = np.array([0.0, 1.0, 0.0]) if abs(n[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    r = np.cross(a, n)
    r /= np.linalg.norm(r)
    return r, np.cross(n, r)


def branch_path(start, direction, length, steps, droop, rng, curl=0.15):
    p = np.asarray(start, float)
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    out = [p.copy()]
    for i in range(steps):
        d = d + np.array([0, -droop, 0]) / steps + rng.normal(0, curl, 3) / steps
        d /= np.linalg.norm(d)
        p = p + d * length / steps
        out.append(p.copy())
    return out


def broadleaf(name, seed, src, bark, height=6.5, crown=2.8, clusters=330, tint=(1, 1, 1), leaf_tint=1.0):
    rng = np.random.default_rng(seed)
    leaves = sprites(load_rgba(src, "island_tree_01__leaves_diff.jpg", "island_tree_01__leaves_alpha.png"))
    cards = [round_cluster(leaves, 512, seed * 7 + k, n=80, leaf_scale=0.15) for k in range(2)]
    tile = np.zeros((TILE, TILE, 3), np.float32)
    ntile = np.zeros_like(tile)
    ntile[..., :2] = 0.5
    ntile[..., 2] = 1.0
    rtile = np.zeros_like(tile)
    bark_a = bark_strip(bark["diff"], TILE // 2, TILE, 3, tint)
    bark_n = bark_strip(bark["nor"], TILE // 2, TILE, 3)
    tile[:, :TILE // 2] = np.sqrt(bark_a ** 2.2)
    ntile[:, :TILE // 2] = bark_n
    rtile[:, :TILE // 2, 0] = 0.85
    for k, cimg in enumerate(cards):
        al, nm, rm = rgba_to_maps(cimg, 0.55)
        al = al * leaf_tint * np.array([0.78, 0.9, 0.66])
        tile[k * 512:(k + 1) * 512, TILE // 2:] = al
        ntile[k * 512:(k + 1) * 512, TILE // 2:] = nm
        rtile[k * 512:(k + 1) * 512, TILE // 2:] = rm
    m = Mesh()
    trunk_top = height * 0.62
    tp = [np.array([0.0, 0.0, 0.0])]
    d = np.array([rng.normal(0, 0.08), 1.0, rng.normal(0, 0.08)])
    for i in range(1, 9):
        d = d + rng.normal(0, 0.06, 3)
        d[1] = max(d[1], 0.7)
        d /= np.linalg.norm(d)
        tp.append(tp[-1] + d * trunk_top / 8)
    r0 = 0.22 * height / 6.5
    radii = [r0 * (1.35 if i == 0 else 1.0) * (1 - 0.55 * i / 8) for i in range(9)]
    m.tube(tp, radii, 0.0, 0.5, 0.0, 1.0, segs=8, sway=[0.0] * 9)
    crown_c = tp[-1] + np.array([0, crown * 0.55, 0])
    tips = []
    nb = int(rng.integers(6, 9))
    for b in range(nb):
        t = rng.uniform(0.45, 1.0)
        i = int(t * 8)
        st = tp[i]
        ang = 2 * math.pi * b / nb + rng.uniform(-0.3, 0.3)
        out = np.array([math.cos(ang), rng.uniform(0.55, 1.1), math.sin(ang)])
        L = crown * rng.uniform(0.75, 1.05)
        path = branch_path(st, out, L, 5, 0.25, rng)
        rr = [radii[i] * 0.55 * (1 - 0.8 * k / 5) for k in range(6)]
        m.tube(path, rr, 0.0, 0.5, 0.0, 0.35, segs=5, sway=[0.05 + 0.12 * k / 5 for k in range(6)])
        for k in (2, 3, 4, 5):
            tips.append(path[k])
            if k in (3, 5):
                sub = branch_path(path[k], out + rng.normal(0, 0.5, 3), L * 0.4, 3, 0.2, rng)
                m.tube(sub, [rr[k] * 0.6 * (1 - j / 3) + 0.004 for j in range(4)], 0.0, 0.5, 0.0, 0.15, segs=3,
                       sway=[0.2, 0.3, 0.4, 0.5])
                tips += sub[1:]
    tips.append(tp[-1])
    nclump = max(10, clusters // 22)
    clumps = []
    for ci in range(nclump):
        if ci % 2 == 0:
            cc = tips[int(rng.integers(0, len(tips)))] + rng.normal(0, crown * 0.1, 3)
        else:
            dvec = rng.normal(0, 1, 3)
            dvec[1] = abs(dvec[1]) * 0.8 + 0.1
            dvec /= np.linalg.norm(dvec)
            cc = crown_c + dvec * crown * np.array([0.85, 0.65, 0.85]) * rng.uniform(0.5, 0.9)
        clumps.append((cc, crown * rng.uniform(0.26, 0.38)))
    for c in range(clusters):
        cc, cr = clumps[int(rng.integers(0, nclump))]
        dvec = rng.normal(0, 1, 3)
        dvec /= np.linalg.norm(dvec)
        base = cc + dvec * cr * rng.uniform(0.35, 1.0) ** 0.5
        sn = (base - crown_c) / (crown * np.array([1.0, 0.8, 1.0]))
        nrm_s = sn / max(np.linalg.norm(sn), 1e-6) + np.array([0, 0.12, 0])
        nrm_s /= np.linalg.norm(nrm_s)
        fn = (base - cc) / cr * 0.6 + nrm_s * 0.6
        fn /= np.linalg.norm(fn)
        k = int(rng.integers(0, 2))
        rect = (0.5, k * 0.5, 1.0, (k + 1) * 0.5)
        w = rng.uniform(1.45, 1.95) * crown / 2.6
        tr, tu = tangent_frame(fn, rng)
        for q, tilt in enumerate((0.0, rng.choice([0.9, -0.9]))):
            ca = rng.uniform(0, 2 * math.pi)
            r0 = tr * math.cos(ca) + tu * math.sin(ca)
            u0 = np.cross(fn, r0)
            upv = u0 * math.cos(tilt) + fn * math.sin(tilt)
            upv /= np.linalg.norm(upv)
            m.card(base - upv * w * 0.5, r0, upv, w, w, rect, nrm_s, sway=1.0, bend=0.0, billboard=True)
    save_tile(ROOT / "loophole" / "data" / "tiles", name, tile, ntile, rtile)
    return m.save(name)


def frond_strand(fronds, w, h, seed):
    rng = np.random.default_rng(seed)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(canvas)
    pts = [(w / 2 + math.sin(t * 2.4 + seed) * w * 0.06, t * h) for t in np.linspace(0, 1, 16)]
    for a, b in zip(pts, pts[1:]):
        dr.line([a, b], fill=(96, 92, 58, 255), width=max(2, w // 90))
    y = 0.0
    while y < h * 0.95:
        fr = fronds[int(rng.integers(0, len(fronds)))]
        sc = w * rng.uniform(0.75, 1.0) / max(fr.size)
        im = fr.resize((max(4, int(fr.size[0] * sc)), max(4, int(fr.size[1] * sc))), Image.LANCZOS)
        if im.size[0] > im.size[1]:
            im = im.rotate(-90 + rng.uniform(-12, 12), expand=True, resample=Image.BICUBIC)
        arr = np.asarray(im).astype(np.float32)
        arr[..., :3] = np.clip(arr[..., :3] * rng.uniform(0.85, 1.15), 0, 255)
        im = Image.fromarray(arr.astype(np.uint8), "RGBA")
        x = int(w / 2 - im.size[0] / 2 + rng.normal(0, w * 0.05))
        canvas.alpha_composite(im, (min(max(x, 0), w - im.size[0]) if im.size[0] < w else 0, int(y)))
        y += im.size[1] * rng.uniform(0.35, 0.55)
    return canvas


def willow(name, seed, src, bark, height=7.0, crown=3.6, strands=300):
    rng = np.random.default_rng(seed)
    fronds = sorted(sprites(load_rgba(src, "jacaranda_tree__leaves_diff.jpg", "jacaranda_tree__leaves_alpha.png"),
                            20000, max_fill=0.8, max_frac=0.5), key=lambda s: -s.size[0] * s.size[1])[:3]
    tile = np.zeros((TILE, TILE, 3), np.float32)
    ntile = np.zeros_like(tile)
    ntile[..., :2] = 0.5
    ntile[..., 2] = 1.0
    rtile = np.zeros_like(tile)
    bark_a = bark_strip(bark["diff"], TILE // 2, TILE, 3, (0.95, 0.9, 0.82))
    bark_n = bark_strip(bark["nor"], TILE // 2, TILE, 3)
    tile[:, :TILE // 2] = np.sqrt(bark_a ** 2.2)
    ntile[:, :TILE // 2] = bark_n
    rtile[:, :TILE // 2, 0] = 0.85
    for k in range(2):
        st = frond_strand(fronds, 256, 1024, seed * 5 + k)
        a_ = np.asarray(st).copy()
        st = Image.fromarray(a_, "RGBA")
        al, nm, rm = rgba_to_maps(st, 0.6)
        al = al * np.array([0.82, 0.98, 0.62])
        tile[:, TILE // 2 + k * 256:TILE // 2 + (k + 1) * 256] = al
        ntile[:, TILE // 2 + k * 256:TILE // 2 + (k + 1) * 256] = nm
        rtile[:, TILE // 2 + k * 256:TILE // 2 + (k + 1) * 256] = rm
    m = Mesh()
    tp = [np.array([0.0, 0.0, 0.0])]
    d = np.array([rng.normal(0, 0.1), 1.0, rng.normal(0, 0.1)])
    for i in range(1, 7):
        d = d + rng.normal(0, 0.07, 3)
        d[1] = max(d[1], 0.7)
        d /= np.linalg.norm(d)
        tp.append(tp[-1] + d * height * 0.45 / 6)
    r0 = 0.3 * height / 7
    m.tube(tp, [r0 * (1.4 if i == 0 else 1.0) * (1 - 0.4 * i / 6) for i in range(7)], 0.0, 0.5, 0.0, 1.0, segs=8,
           sway=[0.0] * 7)
    tips = []
    for b in range(7):
        ang = 2 * math.pi * b / 7 + rng.uniform(-0.3, 0.3)
        out = np.array([math.cos(ang), rng.uniform(1.1, 1.6), math.sin(ang)])
        path = branch_path(tp[-1], out, crown * rng.uniform(0.9, 1.2), 6, 1.4, rng, curl=0.1)
        m.tube(path, [r0 * 0.55 * (1 - 0.8 * k / 6) + 0.01 for k in range(7)], 0.0, 0.5, 0.0, 0.3, segs=4,
               sway=[0.05 + 0.15 * k / 6 for k in range(7)])
        tips += path[2:]
    for s_ in range(strands):
        tip = tips[int(rng.integers(0, len(tips)))] + rng.normal(0, crown * 0.04, 3)
        top = s_ % 3 == 0
        L = (rng.uniform(0.8, 1.5) if top else rng.uniform(0.4, 0.85) * (tip[1] - 0.4))
        L = max(L, 0.9)
        k = int(rng.integers(0, 2))
        rect = (0.5 + k * 0.25, 0.0, 0.75 + k * 0.25, 1.0)
        out = tip - tp[-1]
        out[1] = 0
        out /= max(np.linalg.norm(out), 1e-6)
        upv = np.array([0, 1.0, 0]) if not top else np.array([0, 1.0, 0]) - out * 0.55
        upv = upv / np.linalg.norm(upv)
        for q in range(2):
            a = rng.uniform(0, math.pi)
            right = np.array([math.cos(a), 0, math.sin(a)])
            right -= upv * np.dot(right, upv)
            right /= np.linalg.norm(right)
            m.card(tip - upv * L, right, upv, L * 0.17, L, rect, out * 0.7 + np.array([0, 0.5, 0]), sway=1.0, rows=2)
    save_tile(ROOT / "loophole" / "data" / "tiles", name, tile, ntile, rtile)
    return m.save(name)


def pine(name, seed, src, height=8.0, whorls=14, bare=0.18, width=0.3, shape=1.0, droop=0.25, gap=0.22, tint=(0.46, 0.6, 0.42)):
    rng = np.random.default_rng(seed)
    tw = load_rgba(src, "pine_tree_01__twig_diff.jpg", "pine_tree_01__twig_alpha.png")
    twigs = sorted(sprites(tw, 4000, max_fill=0.5, max_frac=0.12), key=lambda s: -s.size[0] * s.size[1])[:2]
    twigs = [t if t.size[1] >= t.size[0] else t.rotate(90, expand=True) for t in twigs]
    tile = np.zeros((TILE, TILE, 3), np.float32)
    ntile = np.zeros_like(tile)
    ntile[..., :2] = 0.5
    ntile[..., 2] = 1.0
    rtile = np.zeros_like(tile)
    bark_a = bark_strip(src / "pine_tree_01__bark_diff.jpg", TILE // 2, TILE, 3)
    bark_n = bark_strip(src / "pine_tree_01__bark_nor_gl.jpg", TILE // 2, TILE, 3)
    tile[:, :TILE // 2] = np.sqrt(bark_a ** 2.2)
    ntile[:, :TILE // 2] = bark_n
    rtile[:, :TILE // 2, 0] = 0.9
    for k in range(4):
        card = needle_card(twigs, 512, seed * 11 + k)
        al, nm, rm = rgba_to_maps(card, 0.65)
        al = al * np.array(tint)
        tile[k * 256:(k + 1) * 256, TILE // 2:] = al
        ntile[k * 256:(k + 1) * 256, TILE // 2:] = nm
        rtile[k * 256:(k + 1) * 256, TILE // 2:] = rm
    m = Mesh()
    lean = np.array([rng.normal(0, 0.06), 0, rng.normal(0, 0.06)]) * height
    def axis(y):
        f = y / height
        return np.array([0.0, y, 0.0]) + lean * f * f
    tp = [axis(y) + np.array([rng.normal(0, 0.03), 0, rng.normal(0, 0.03)]) * (y > 0) for y in np.linspace(0, height, 10)]
    m.tube(tp, [0.22 * (1 - 0.85 * i / 9) + 0.02 for i in range(10)], 0.0, 0.5, 0.0, 1.0, segs=7,
           sway=[0.03 * i / 9 for i in range(10)])
    ys = []
    y = height * bare
    while y < height * 0.95:
        ys.append(y)
        y += height * (0.95 - bare) / whorls * rng.uniform(0.6, 1.5)
    for wi, y in enumerate(ys):
        t = (y - height * bare) / (height * (0.95 - bare))
        L0 = ((1 - t) ** shape * height * width + 0.3) * rng.uniform(0.8, 1.15)
        nb = int(rng.integers(5, 9))
        off = rng.uniform(0, 2 * math.pi)
        st = axis(y)
        for b in range(nb):
            if rng.random() < gap:
                continue
            L = L0 * rng.uniform(0.6, 1.25)
            ang = off + 2 * math.pi * (b + rng.uniform(-0.3, 0.3)) / nb
            dr = droop * (0.4 + 0.8 * (1 - t)) + rng.normal(0, 0.08)
            d = np.array([math.cos(ang), -dr + 0.15 * t, math.sin(ang)])
            d /= np.linalg.norm(d)
            side = np.cross(np.array([0.0, 1.0, 0.0]), d)
            side /= np.linalg.norm(side)
            vert = np.cross(d, side)
            m.tube([st, st + d * L * 0.55], [0.035 * (1 - t * 0.6), 0.01], 0.0, 0.5, 0.0, 0.2, segs=3,
                   sway=[0.05, 0.5])
            k = int(rng.integers(0, 4))
            rect = (0.5, k * 0.25, 1.0, (k + 1) * 0.25)
            h = L * 0.62
            nrm = d * 0.6 + np.array([0, 0.7, 0])
            for upv in (side * 0.94 + vert * 0.34, vert * 0.9 + side * 0.3, side * 0.7 - vert * 0.7):
                upv = upv / np.linalg.norm(upv)
                m.card(st + d * L * 0.5 - upv * h * 0.5, d, upv, L, h, rect, nrm, sway=0.6 + 0.4 * (1 - t), rows=1)
    top = axis(height * 0.97)
    for q in range(3):
        ang = q * math.pi / 3
        right = np.array([math.cos(ang), 0, math.sin(ang)])
        m.card(top - np.array([0, height * 0.1, 0]), np.array([0, 1.0, 0]), right, height * 0.16, 0.5,
               (0.5, 0.0, 1.0, 0.25), np.array([0, 1.0, 0]), sway=1.0)
    save_tile(ROOT / "loophole" / "data" / "tiles", name, tile, ntile, rtile)
    return m.save(name)


def flower_cell(base, seed):
    rng = np.random.default_rng(seed)
    cell = base.copy()
    W, H = cell.size
    dr = ImageDraw.Draw(cell)
    cols = [(236, 232, 214), (246, 206, 62), (176, 120, 214), (226, 96, 120), (250, 250, 245)]
    for k in range(14):
        x = rng.uniform(0.12, 0.88) * W
        top = rng.uniform(0.18, 0.55) * H
        dr.line([(x, H * 0.98), (x + rng.normal(0, W * 0.02), top)], fill=(78, 104, 46, 255), width=max(2, W // 160))
        col = cols[int(rng.integers(0, len(cols)))]
        r = W * rng.uniform(0.018, 0.03)
        for p in range(5):
            a = p * 2 * math.pi / 5 + rng.uniform(0, 1)
            cx, cy = x + math.cos(a) * r, top + math.sin(a) * r
            dr.ellipse([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], fill=col + (255,))
        dr.ellipse([x - r * 0.5, top - r * 0.5, x + r * 0.5, top + r * 0.5], fill=(214, 168, 40, 255))
    return cell


def clump(name, seed, src, diff, alpha, picks, size=0.9, cards=4, count=1, spread=0.0, rough=0.7, tint=(1, 1, 1),
          region=None, flowers=False):
    rng = np.random.default_rng(seed)
    im = load_rgba(src, diff, alpha)
    sp = sprites(im, 6000, region=region)
    sp = sorted(sp, key=lambda s: -s.size[0] * s.size[1])
    if picks:
        sp = [s for s in sp if s.size[0] > s.size[1] * 0.6][:picks]
    tile = np.zeros((TILE // 2, TILE // 2, 3), np.float32)
    ntile = np.zeros_like(tile)
    ntile[..., :2] = 0.5
    ntile[..., 2] = 1.0
    rtile = np.zeros_like(tile)
    n = min(4, len(sp))
    cw = TILE // 2 // 2
    rects = []
    for k in range(n):
        s = sp[k]
        sc = min(cw / s.size[0], cw / s.size[1])
        r = s.resize((max(1, int(s.size[0] * sc)), max(1, int(s.size[1] * sc))), Image.LANCZOS)
        cell = Image.new("RGBA", (cw, cw), (0, 0, 0, 0))
        cell.alpha_composite(r, ((cw - r.size[0]) // 2, cw - r.size[1]))
        if flowers and k == n - 1:
            cell = flower_cell(cell, seed * 31)
        al, nm, rm = rgba_to_maps(cell, rough)
        x, y = (k % 2) * cw, (k // 2) * cw
        tile[y:y + cw, x:x + cw] = al * np.array(tint)
        ntile[y:y + cw, x:x + cw] = nm
        rtile[y:y + cw, x:x + cw] = rm
        rects.append((x / (TILE / 2), y / (TILE / 2), (x + cw) / (TILE / 2), (y + cw) / (TILE / 2)))
    m = Mesh()
    for c in range(count):
        base = np.array([rng.normal(0, spread), 0.0, rng.normal(0, spread)]) if c else np.zeros(3)
        for q in range(cards):
            ang = q * math.pi / cards + rng.uniform(0, 0.4)
            right = np.array([math.cos(ang), 0, math.sin(ang)])
            s = size * rng.uniform(0.8, 1.15)
            rect = rects[int(rng.integers(0, len(rects)))]
            m.card(base, right, np.array([rng.normal(0, 0.1), 1.0, rng.normal(0, 0.1)]) / 1.01, s, s, rect,
                   np.array([0, 1.0, 0]), sway=1.0)
    save_tile(ROOT / "loophole" / "data" / "tiles", name, tile, ntile, rtile)
    return m.save(name)


def bush(name, seed, src, size=1.3, cards=22):
    rng = np.random.default_rng(seed)
    leaves = sprites(load_rgba(src, "island_tree_01__leaves_diff.jpg", "island_tree_01__leaves_alpha.png"))
    T = TILE // 2
    tile = np.zeros((T, T, 3), np.float32)
    ntile = np.zeros_like(tile)
    ntile[..., :2] = 0.5
    ntile[..., 2] = 1.0
    rtile = np.zeros_like(tile)
    for k in range(2):
        c = round_cluster(leaves, T, seed * 13 + k, n=70, leaf_scale=0.17).resize((T // 2, T), Image.LANCZOS)
        al, nm, rm = rgba_to_maps(c, 0.55)
        tile[:, k * T // 2:(k + 1) * T // 2] = al * np.array([0.85, 0.95, 0.8])
        ntile[:, k * T // 2:(k + 1) * T // 2] = nm
        rtile[:, k * T // 2:(k + 1) * T // 2] = rm
    m = Mesh()
    ctr = np.array([0, size * 0.45, 0])
    for q in range(cards):
        th = rng.uniform(0, 2 * math.pi)
        ph = rng.uniform(0.15, 1.2)
        d = np.array([math.cos(th) * math.sin(ph), math.cos(ph), math.sin(th) * math.sin(ph)])
        base = ctr + d * size * 0.32 - np.array([0, size * 0.1, 0])
        tr, tu = tangent_frame(d, rng)
        ca = rng.uniform(0, 2 * math.pi)
        right = tr * math.cos(ca) + tu * math.sin(ca)
        tilt = rng.uniform(-0.6, 0.6)
        upv = np.cross(d, right) * math.cos(tilt) + d * math.sin(tilt)
        upv /= np.linalg.norm(upv)
        base = base - upv * size * 0.3
        k = int(rng.integers(0, 2))
        w = size * rng.uniform(0.6, 0.9)
        m.card(base, right, upv, w, w, (k * 0.5, 0.0, (k + 1) * 0.5, 1.0), d + np.array([0, 0.3, 0]), sway=0.6,
               billboard=True)
    save_tile(ROOT / "loophole" / "data" / "tiles", name, tile, ntile, rtile)
    return m.save(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--ph", required=True)
    a = ap.parse_args()
    src = Path(a.src)
    ph = Path(a.ph)
    bark = {"diff": ph / "bark_brown_02" / "diff.jpg", "nor": ph / "bark_brown_02" / "nor_gl.jpg"}
    print("oak", broadleaf("oak", 3, src, bark))
    print("birch", broadleaf("birch", 9, src, bark, height=7.5, crown=2.1,
                             clusters=250, tint=(1.5, 1.45, 1.35), leaf_tint=np.array([1.05, 1.08, 0.9])))
    print("maple", broadleaf("maple", 21, src, bark, height=6.8, crown=3.1, clusters=360, tint=(1.1, 1.0, 0.95),
                             leaf_tint=np.array([1.75, 0.8, 0.32])))
    print("willow", willow("willow", 4, src, bark))
    print("pine", pine("pine", 5, src, height=9.0, whorls=11, bare=0.4, width=0.26, shape=0.6, droop=0.1, gap=0.3,
                       tint=(0.5, 0.6, 0.4)))
    print("spruce", pine("spruce", 8, src, height=10.0, whorls=17, bare=0.1, width=0.26, shape=1.1, droop=0.42,
                         gap=0.15, tint=(0.44, 0.58, 0.45)))
    print("bush", bush("bush", 2, src))
    print("grass", clump("grass", 4, src, "grass_medium_01__Diffuse.jpg", "grass_medium_01__Alpha.png", 5, size=0.7,
                         cards=3, count=3, spread=0.3, rough=0.75, tint=(0.95, 1.0, 0.85), region=(0.62, 1.0),
                         flowers=True))
    print("fern", clump("fern", 6, src, "fern_02__Diffuse.jpg", "fern_02__Alpha.png", 0, size=1.0, cards=6, count=1,
                        rough=0.6))


if __name__ == "__main__":
    main()
