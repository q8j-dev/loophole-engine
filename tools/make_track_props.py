import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loophole import models
from loophole.character import write_kit

FACES = [((1, 0, 0), (0, 0, -1), (0, 1, 0)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)), ((0, 1, 0), (1, 0, 0), (0, 0, -1)),
         ((0, -1, 0), (1, 0, 0), (0, 0, 1)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)), ((0, 0, -1), (-1, 0, 0), (0, 1, 0))]


def box(c, h, mat, out):
    c, h = np.array(c, float), np.array(h, float)
    for n, u, v in FACES:
        n, u, v = np.array(n, float), np.array(u, float), np.array(v, float)
        corners = [c + (n + su * u + sv * v) * h for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
        for tri in ((0, 1, 2), (0, 2, 3)):
            for i in tri:
                out["P"].append(corners[i])
                out["N"].append(n)
                out["UV"].append(uvs[i])
                out["M"].append(mat)


def solid_mat(name, rgb, rough=0.6, metal=0.0, image=None):
    m = models.Mat(name)
    m.color = rgb
    m.rough = rough
    m.metal = metal
    m.base = image
    return m


def gate(out_dir):
    chk = np.indices((2, 20)).sum(0) % 2
    img = Image.fromarray(np.kron(chk, np.ones((128, 26)))[:256, :520].astype(np.uint8) * 230 + 12).convert("RGB")
    img = img.resize((256, 256), Image.NEAREST)
    mats = [solid_mat("post", (0.75, 0.08, 0.06), 0.45), solid_mat("beam", (0.9, 0.9, 0.88), 0.5),
            solid_mat("banner", (1.0, 1.0, 1.0), 0.7, image=img), solid_mat("foot", (0.12, 0.12, 0.14), 0.8)]
    g = {"P": [], "N": [], "UV": [], "M": []}
    for sx in (-1, 1):
        box((sx * 5.35, 2.25, 0), (0.25, 2.25, 0.25), 0, g)
        box((sx * 5.35, 0.15, 0), (0.45, 0.15, 0.45), 3, g)
        for yb in (0.9, 2.1, 3.3):
            box((sx * 5.35, yb, 0), (0.27, 0.12, 0.27), 1, g)
    box((0, 4.65, 0), (5.7, 0.2, 0.22), 1, g)
    box((0, 3.95, 0), (5.1, 0.5, 0.04), 2, g)
    P, N, UV = np.array(g["P"]), np.array(g["N"]), np.array(g["UV"], float)
    write_kit(out_dir, "gate", P, N, UV, np.array(g["M"]), mats, np.zeros(len(P), np.float32), 256)
    return len(P) // 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kenney", help="the 'Models/GLB format' folder of the Kenney Car Kit")
    a = ap.parse_args()
    out = ROOT / "loophole" / "data"
    print("gate", gate(out))
    print("cone", models.convert(Path(a.kenney) / "cone.glb", out, "cone", scale=1.0, size=256))


if __name__ == "__main__":
    main()
