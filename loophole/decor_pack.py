import io
from pathlib import Path

import numpy as np
from PIL import Image

TILES = Path(__file__).resolve().parent / "data" / "tiles"
NMIP = 8


EXTRA_TILES = {}


def tdir(name):
    return EXTRA_TILES.get(name, TILES)


def available():
    return sorted(set(p.name[:-6] for p in TILES.glob("*_a.jpg")) | set(EXTRA_TILES))


CAP = [1024]
KEEP = set()


def tile_size(name):
    from .library import FOLIAGE
    with Image.open(tdir(name) / f"{name}_a.jpg") as im:
        return im.size[0] if name in FOLIAGE or name in KEEP else min(im.size[0], CAP[0])


def layout(names, width=4096):
    items = sorted(((tile_size(n), n) for n in names), key=lambda t: (-t[0], t[1]))
    if not items:
        return {}, 256, 256
    area = sum(s * s for s, _ in items)
    W = 256
    while W < width and W * W < area * 1.15:
        W *= 2
    W = max(W, items[0][0])
    G = 64
    gw = W // G
    occ = np.zeros((0, gw), bool)
    out = {}
    for s, n in items:
        c = s // G
        placed = False
        y = 0
        while not placed:
            if y + c > occ.shape[0]:
                occ = np.concatenate([occ, np.zeros((y + c - occ.shape[0], gw), bool)])
            for x in range(0, gw - c + 1):
                if not occ[y:y + c, x:x + c].any():
                    occ[y:y + c, x:x + c] = True
                    out[n] = (x * G, y * G, s)
                    placed = True
                    break
            y += 1 if not placed else 0
    H = occ.shape[0] * G
    H = 1 << int(np.ceil(np.log2(max(H, 64))))
    return out, W, H


def down2(a):
    return (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) * 0.25


def keep_coverage(cur, regions, target):
    for (x, y, s), t in zip(regions, target):
        if t <= 0.002 or s < 2:
            continue
        a = cur[y:y + s, x:x + s, 2]
        lo, hi = 1.0, 8.0
        for _ in range(14):
            mid = (lo + hi) / 2
            if (a * mid > 0.5).mean() < t:
                lo = mid
            else:
                hi = mid
        cur[y:y + s, x:x + s, 2] = np.minimum(a * (lo + hi) / 2, 1.0)


def with_mips(page, normal=False, regions=None):
    H, W = page.shape[:2]
    out = np.zeros((H + H // 2, W, 3), np.float32)
    out[:H] = page
    cur = page
    x = 0
    target = None
    if regions:
        target = [float((page[y:y + s, x_:x_ + s, 2] > 0.5).mean()) if (page[y:y + s, x_:x_ + s, 2] < 0.99).any() else 0.0
                  for (x_, y, s) in regions]
    lvl = 0
    for _ in range(1, NMIP):
        if cur.shape[0] < 2 or cur.shape[1] < 2:
            break
        cur = down2(cur)
        lvl += 1
        if target is not None:
            keep_coverage(cur, [(x_ >> lvl, y >> lvl, s >> lvl) for (x_, y, s) in regions], target)
        if normal:
            v = cur * 2 - 1
            v = v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
            cur = v * 0.5 + 0.5
        h, w = cur.shape[:2]
        out[H:H + h, x:x + w] = cur
        x += w
    return out


def load(name, kind, s):
    im = Image.open(tdir(name) / f"{name}_{kind}.jpg").convert("RGB")
    if im.size[0] != s:
        im = im.resize((s, s), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


def jpg(a, q=86, sub=0):
    b = io.BytesIO()
    Image.fromarray(np.ascontiguousarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)), "RGB").save(
        b, "JPEG", quality=q, subsampling=sub, optimize=True)
    return b.getvalue()


def build(names, cap=1024, keep=()):
    CAP[0] = cap
    KEEP.clear()
    KEEP.update(keep)
    lay, W, H = layout(names)
    A = np.zeros((H, W, 3), np.float32)
    N = np.zeros((H // 2, W // 2, 3), np.float32)
    N[..., 0] = 0.5
    N[..., 1] = 0.5
    N[..., 2] = 1.0
    R = np.zeros((H // 2, W // 2, 3), np.float32)
    R[..., 0] = 0.6
    for n, (x, y, s) in lay.items():
        A[y:y + s, x:x + s] = load(n, "a", s)
        N[y // 2:y // 2 + s // 2, x // 2:x // 2 + s // 2] = load(n, "n", s // 2)
        R[y // 2:y // 2 + s // 2, x // 2:x // 2 + s // 2] = load(n, "r", s // 2)
    imgs = {"dA": (jpg(with_mips(A), 86, 2), W, H * 3 // 2), "dN": (jpg(with_mips(N, True), 88), W // 2, H * 3 // 4),
            "dR": (jpg(with_mips(R, regions=[(x // 2, y // 2, s // 2) for (x, y, s) in lay.values()]), 84), W // 2,
                   H * 3 // 4)}
    return dict(layout=lay, PW=W, PH=H), imgs
