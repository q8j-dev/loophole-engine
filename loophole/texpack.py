import io
import json
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from . import shaders

DATA = Path(__file__).resolve().parent / "data"
FILES = {1: "materials", 2: "materials2", 3: "materials3"}
G = 8


def _branches():
    fs = shaders.WORLD_FS
    a = fs.index("float cidA = 0.0;")
    b = fs.index("else { tex = false; }", a)
    out = []
    for m in re.finditer(r"if \((.*?)\) \{(.*?)\}", fs[a:b]):
        cond = m.group(1).replace("&&", " and ").replace("||", " or ")
        body = m.group(2)
        atl = re.search(r"atl = ([\d.]+);", body)
        cid = re.search(r"cidA = ([\d.]+);", body)
        if cid:
            out.append((cond, float(atl.group(1)) if atl else 1.0, int(float(cid.group(1)))))
    return out


def _literals():
    fs = shaders.WORLD_FS
    lit = {(int(float(a)), int(float(c))) for a, c in re.findall(r"sampA\(([\d.]+), ([\d.]+),", fs)}
    always = {(1, int(float(c))) for c in re.findall(r"samp\(([\d.]+),", fs)}
    return lit, always


def used_cells(used_ids, has_terrain):
    cells = {1: set(), 2: set(), 3: set()}
    br = _branches()
    for mid in used_ids:
        for cond, atl, cid in br:
            if eval(cond, {}, {"mat": float(mid)}):
                cells[int(atl)].update((cid, cid + 1))
                break
    lit, always = _literals()
    for atl, cid in always:
        cells[atl].add(cid)
    if has_terrain:
        for atl, cid in lit:
            cells[atl].add(cid)
    return cells


def gen_layout(S, n):
    out = [(G, G, S)]
    x, y, s = G + S + 2 * G, G, S // 2
    horiz = False
    while len(out) < n:
        out.append((x, y, s))
        if horiz:
            x += s + 2 * G
        else:
            y += s + 2 * G
        horiz = not horiz
        s //= 2
    return out


@lru_cache(None)
def _src(k):
    return np.asarray(Image.open(DATA / "atlas" / f"{FILES[k]}.jpg").convert("RGB"))


def _jpg(arr, q):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, "JPEG", quality=q, subsampling=0, optimize=True)
    return b.getvalue()


def build(used_ids, has_terrain, high=False, quality=88):
    S = shaders.S
    src_lay = shaders.LAYOUT
    cw0, ch0, cols = shaders.CELL_W, shaders.CELL_H, shaders.COLS
    if high:
        lay = list(src_lay)
        cw, ch = cw0, ch0
        pairs = [(k, k) for k in range(len(src_lay))]
        glsl_levels = lay
    else:
        lay = gen_layout(S // 2, len(src_lay) - 1)
        cw = max(x + s for x, y, s in lay) + G
        ch = lay[0][2] + 2 * G
        pairs = [(k + 1, k) for k in range(len(lay))]
        glsl_levels = [lay[0]] + lay
    cells = used_cells(used_ids, has_terrain)
    imgs = {}
    heights = {}
    for k in (1, 2, 3):
        if not cells[k]:
            imgs[k] = None
            heights[k] = 8
            continue
        src = _src(k)
        rows = src.shape[0] // ch0
        top = max(cells[k]) // cols + 1
        out = np.zeros((top * ch, cols * cw, 3), np.uint8)
        for cid in range(top * cols):
            cx0, cy0 = (cid % cols) * cw0, (cid // cols) * ch0
            cx1, cy1 = (cid % cols) * cw, (cid // cols) * ch
            if cid // cols >= rows:
                continue
            if cid not in cells[k]:
                x, y, s = src_lay[-1]
                out[cy1:cy1 + ch, cx1:cx1 + cw] = src[cy0 + y:cy0 + y + s, cx0 + x:cx0 + x + s].reshape(-1, 3).mean(0)
                continue
            for si, di in pairs:
                sx, sy, ss = src_lay[si]
                dx, dy, ds = lay[di]
                p = G
                out[cy1 + dy - p:cy1 + dy + ds + p, cx1 + dx - p:cx1 + dx + ds + p] = \
                    src[cy0 + sy - p:cy0 + sy + ss + p, cx0 + sx - p:cx0 + sx + ss + p]
        imgs[k] = (_jpg(out, quality), out.shape[1], out.shape[0])
        heights[k] = out.shape[0]
    glsl = shaders.atlas_glsl(glsl_levels, cw, ch, cols * cw, heights[1], heights[2], heights[3])
    return imgs, glsl, cells
