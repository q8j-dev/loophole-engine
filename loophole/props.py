import json
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent / "data" / "props"

BUILTIN = {
    "cube": dict(file="cube", region="cube", glow=(1.0, 0.45, 0.12)),
    "door": dict(file="door", region="door", glow=(0.8, 0.1, 0.06)),
    "button": dict(file="btnb", region="btnb", glow=(1.6, 0.16, 0.1), top="btnt"),
    "device": dict(file="device", region="device", glow=(0.2, 0.7, 1.0)),
    "arms": dict(file="arms", region="arms", glow=(0.0, 0.0, 0.0)),
    "player": dict(file="player", region="player", glow=(0.3, 0.6, 1.0)),
}


@lru_cache(None)
def meta():
    return json.loads((DATA / "props.json").read_text())


STATE = {"regions": None, "W": None, "H": None, "bytes": None}
CLOSE = {"device", "arms"}


def region(name):
    regs = STATE["regions"] or meta()["regions"]
    x, y, s, t = regs.get(name, (0, 0, 64, 1.0))
    return x, y, s, round(t, 2)


def _mips(s):
    out = [(8.0, 8.0, s), (s + 24.0, 8.0, s / 2)]
    x, y, k, hz = s + 16.0, s / 2 + 16.0, s / 4, 1.0
    for _ in range(2, 8):
        out.append((x + 8, y + 8, k))
        x += hz * (k + 16)
        y += (1 - hz) * (k + 16)
        hz = 1 - hz
        k /= 2
    return out


def _block(src, y, x0, mip):
    mx, my, ms = mip
    return src[int(y + my - 8):int(y + my + ms + 8), int(x0 + mx - 8):int(x0 + mx + ms + 8)]


def configure(used, high=False):
    import io
    from PIL import Image
    src = np.asarray(Image.open(DATA / "patlas.jpg").convert("RGB"))
    regs = meta()["regions"]
    plan = []
    for name in sorted(used, key=lambda n: regs[n][1]):
        x, y, s, t = regs[name]
        f = 1 if high or name in CLOSE or s <= 256 else 2
        plan.append((name, int(x), int(y), int(s), t, f))
    W = int(max([3 * (s // f * 1.5 + 32) for _, _, _, s, _, f in plan] + [64]))
    H = max(sum(s // f + 16 for _, _, _, s, _, f in plan), 64)
    out = np.zeros((H, W, 3), np.uint8)
    newregs = {}
    ny = 0
    for name, x, y, s, t, f in plan:
        ns = s // f
        newregs[name] = (0, ny, ns, t / f)
        so, no = _mips(s), _mips(ns)
        for m in range(3):
            sx0 = x + m * (s * 1.5 + 32)
            nx0 = m * (ns * 1.5 + 32)
            for k in range(8):
                if k + f - 1 <= 7:
                    blk = _block(src, y, sx0, so[k + f - 1])
                else:
                    b0 = _block(src, y, sx0, so[7])
                    tgt = int(no[k][2]) + 16
                    blk = np.asarray(Image.fromarray(np.ascontiguousarray(b0)).resize((tgt, tgt), Image.BOX))
                dx, dy, ds = no[k]
                h_ = min(blk.shape[0], int(ds) + 16)
                w_ = min(blk.shape[1], int(ds) + 16)
                out[int(ny + dy - 8):int(ny + dy - 8) + h_, int(nx0 + dx - 8):int(nx0 + dx - 8) + w_] = blk[:h_, :w_]
        ny += ns + 16
    b = io.BytesIO()
    Image.fromarray(out).save(b, "JPEG", quality=86, subsampling=0, optimize=True)
    STATE.update(regions=newregs, W=W, H=H, bytes=b.getvalue())


@lru_cache(None)
def mesh(name):
    d = np.load(DATA / f"{name}.npz")
    out = dict(pos=d["pos"].astype(float), nrm=d["nrm"].astype(float), uv=d["uv"].astype(float))
    if "bone" in d:
        out["bone"] = d["bone"].astype(float)
    return out


def has_lod(name):
    return (DATA / f"{name}_lod.npz").exists()


def atlas_bytes():
    return STATE["bytes"] or (DATA / "patlas.jpg").read_bytes()


def atlas_size():
    if STATE["W"]:
        return STATE["W"], STATE["H"]
    m = meta()
    return m["W"], m["H"]
