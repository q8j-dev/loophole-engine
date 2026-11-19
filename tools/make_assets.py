import argparse
import json
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "loophole" / "data"

EXTRA = {
    "rust": ("rusty_metal_02/{}.jpg", None, 0.2, 0.3, (1.0, 1.0, 1.0)),
    "grate": ("metal_grate_rusty/{}.jpg", None, 0.17, 0.45, (1.0, 1.0, 1.0)),
    "shutter": ("painted_metal_shutter/{}.jpg", None, 0.3, 0.25, (1.0, 1.0, 1.0)),
    "concrete": ("smooth_concrete_floor/{}.jpg", None, 0.34, 0.6, (1.0, 0.99, 0.97)),
}
PROPS = [("cube", 1024, 1024 / 0.9), ("device", 1024, 1024 / 0.45), ("door", 1024, 1024 / 3.6),
         ("btnb", 512, 512 / 2.4), ("btnt", 512, 512 / 1.6), ("player", 512, 512 / 2.2), ("arms", 1024, 1024 / 0.9)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    src = Path(a.src).resolve()
    sys.path.insert(0, str(src / "tw"))
    only = set(a.only.split(",")) if a.only else None
    import textures
    if only is None or "materials" in only:
        textures.SOURCES.update(EXTRA)
        textures.MATS = ["white", "metal", "floor", "ceil", "dark", "cube", "panel", "rust", "grate", "shutter",
                         "concrete", "noise"]
        textures.TILE.update({"rust": 2.0, "grate": 1.0, "shutter": 2.0, "concrete": 3.0})
        textures.BUILDERS.update({k: (lambda rng, k=k: textures.scanned(k)) for k in EXTRA})
        textures.ATLAS_H = textures.CELL_H * ((2 * len(textures.MATS) + textures.COLS - 1) // textures.COLS)
        arr = textures.build_atlas()
        (OUT / "atlas" / "materials.jpg").write_bytes(textures.encode_jpg(arr, 90))
        meta = dict(S=textures.S, G=textures.G, COLS=textures.COLS, CELL_W=textures.CELL_W, CELL_H=textures.CELL_H,
                    ATLAS_W=textures.ATLAS_W, ATLAS_H=textures.ATLAS_H, LAYOUT=textures.LAYOUT, MATS=textures.MATS,
                    TILE=textures.TILE)
        (OUT / "atlas" / "materials.json").write_text(json.dumps(meta))
        print("materials", arr.shape)
    if only is None or "decor" in only:
        import decor_atlas
        for name, (data, w, h) in decor_atlas.build().items():
            (OUT / "atlas" / f"{name}.jpg").write_bytes(data)
            print(name, w, h, len(data) // 1024, "KB")
        (OUT / "atlas" / "decor.json").write_text(json.dumps(dict(PW=decor_atlas.PW, PH=decor_atlas.PH,
                                                                    layout=decor_atlas.layout())))
    if only is None or "props" in only:
        import props
        data, w, h, reg = props.build(PROPS)
        (OUT / "props" / "patlas.jpg").write_bytes(data)
        (OUT / "props" / "props.json").write_text(json.dumps(dict(W=w, H=h, regions=reg)))
        for name, _, _ in PROPS:
            for suf in ("", "_lod"):
                f = src / "art" / "out" / f"{name}{suf}_mesh.npz"
                if f.exists():
                    p, n, uv = props.mesh(name + suf)
                    extra = {}
                    if name == "player":
                        extra["bone"] = props.player_bones(p).astype(np.uint8)
                    np.savez_compressed(OUT / "props" / f"{name}{suf}.npz", pos=p.astype(np.float32),
                                        nrm=n.astype(np.float32), uv=uv.astype(np.float32), **extra)
        print("props", w, h, len(data) // 1024, "KB")
    if only is None or "glyphs" in only:
        g = src / "art" / "out" / "glyphs.npz"
        (OUT / "glyphs.npz").write_bytes(g.read_bytes())


if __name__ == "__main__":
    main()
