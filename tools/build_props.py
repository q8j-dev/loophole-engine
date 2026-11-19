import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lh_tiles import save_tile

OUT = HERE.parent / "loophole" / "data" / "tiles"


def dilate(arrs, mask, iters=48):
    out = [a.copy() for a in arrs]
    m = mask.copy()
    for _ in range(iters):
        if m.all():
            break
        pm = np.pad(m, 1)
        cnt = pm[:-2, 1:-1].astype(np.float32) + pm[2:, 1:-1] + pm[1:-1, :-2] + pm[1:-1, 2:]
        grow = (~m) & (cnt > 0)
        if not grow.any():
            break
        for k, a in enumerate(out):
            ex = a if a.ndim == 3 else a[..., None]
            pa = np.pad(ex * m[..., None], ((1, 1), (1, 1), (0, 0)))
            sm = pa[:-2, 1:-1] + pa[2:, 1:-1] + pa[1:-1, :-2] + pa[1:-1, 2:]
            val = sm / np.maximum(cnt, 1)[..., None]
            ex = np.where(grow[..., None], val, ex)
            out[k] = ex if a.ndim == 3 else ex[..., 0]
        m = m | grow
    return out


def to_tile(m):
    keys = [k for k in ("col", "nrm", "rough", "metal", "ao", "alpha") if k in m.files]
    mask = (m["ao"] > 0.001) | (m["col"].sum(-1) > 0.001)
    vals = dilate([m[k] for k in keys], mask)
    m = dict(zip(keys, vals))
    m["files"] = keys
    ao = np.clip(m["ao"], 0, 1)
    aoi = Image.fromarray((ao * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.0))
    ao = np.asarray(aoi, np.float32) / 255.0
    col = np.clip(m["col"], 0, 1) * (0.35 + 0.65 * ao)[..., None]
    third = m["alpha"] if "alpha" in m["files"] else np.zeros_like(ao)
    rm = np.stack([np.clip(m["rough"], 0, 1), np.clip(m["metal"], 0, 1), np.clip(third, 0, 1)], -1)
    return np.sqrt(col), np.clip(m["nrm"], 0, 1), rm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--script", default="polyhaven_props.py")
    ap.add_argument("--blender", default=shutil.which("blender") or "blender")
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    cmd = [a.blender, "-b", "-P", str(HERE / "blender" / a.script), "--", a.cache] + a.names
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith(("PROP", "FAILED", "TREE")):
            print(line)
    for f in sorted((Path(a.cache) / "maps").glob("*.npz")):
        if a.names and f.stem not in a.names:
            continue
        m = np.load(f)
        save_tile(OUT, f.stem, *to_tile(m))


if __name__ == "__main__":
    main()
