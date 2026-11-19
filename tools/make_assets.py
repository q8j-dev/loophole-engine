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
ATLAS2 = [
    ("grass", "leafy_grass", 0.17, 0.05, (0.95, 1.0, 0.85)), ("rock", "dark_rock", 0.16, 0.25, (1.0, 1.0, 1.0)),
    ("sand", "coast_sand_01", 0.42, 0.25, (1.0, 0.97, 0.9)), ("dirt", "brown_mud_dry", 0.2, 0.2, (1.0, 0.95, 0.88)),
    ("brick", "brick_wall_001", 0.24, 0.05, (1.0, 1.0, 1.0)), ("wood", "old_wood_floor", 0.24, 0.05, (1.0, 1.0, 1.0)),
    ("planks", "brown_planks_05", 0.25, 0.05, (1.0, 1.0, 1.0)), ("plaster", "painted_plaster_wall", 0.62, 0.35, (1.0, 0.98, 0.95)),
    ("tiles", "floor_tiles_06", 0.45, 0.2, (1.0, 1.0, 1.0)), ("stone", "castle_brick_07", 0.24, 0.25, (1.0, 0.98, 0.95)),
    ("cobble", "cobblestone_floor_08", 0.2, 0.2, (1.0, 1.0, 1.0)), ("bark", "bark_brown_02", 0.14, 0.1, (1.0, 1.0, 1.0)),
]
ATLAS3 = [
    ("asphalt", "asphalt_02", 0.11, 0.5, (1.0, 1.0, 1.0)), ("snow", "snow_02", 0.78, 0.6, (0.97, 0.99, 1.03)),
    ("cliff", "cliff_side", 0.2, 0.3, (1.0, 1.0, 1.0)), ("gravel", "gravel_road", 0.2, 0.3, (1.0, 1.0, 1.0)),
    ("roof", "clay_roof_tiles_02", 0.24, 0.1, (1.0, 1.0, 1.0)), ("marble", "marble_01", 0.66, 0.3, (1.0, 1.0, 1.0)),
    ("litter", "forest_leaves_02", 0.2, 0.25, (1.0, 1.0, 1.0)),
]
PROPS = [("cube", 1024, 1024 / 0.9), ("device", 1024, 1024 / 0.45), ("door", 1024, 1024 / 3.6),
         ("btnb", 512, 512 / 2.4), ("btnt", 512, 512 / 1.6), ("player", 512, 512 / 2.2), ("arms", 1024, 1024 / 0.9)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--ph", default="")
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
        (OUT / "atlas" / "materials.json").write_text(json.dumps(meta), encoding="utf-8")
        print("materials", arr.shape)
    if a.ph and (only is None or "atlas2" in only):
        import textures as T2
        T2.VENDOR = Path(a.ph)
        for fname, mats in (("materials2", ATLAS2), ("materials3", ATLAS3)):
            T2.SOURCES = {n: (f"{d}/{{}}.jpg", None, tgt, ds, tint) for n, d, tgt, ds, tint in mats}
            T2.BUILDERS = {n: (lambda rng, n=n: T2.scanned(n)) for n, _, _, _, _ in mats}
            T2.MATS = [n for n, _, _, _, _ in mats]
            T2.ATLAS_H = T2.CELL_H * ((2 * len(T2.MATS) + T2.COLS - 1) // T2.COLS)
            arr = T2.build_atlas()
            (OUT / "atlas" / f"{fname}.jpg").write_bytes(T2.encode_jpg(arr, 90))
            avg = {}
            x0, y0, sz = T2.LAYOUT[0]
            for i, nm in enumerate(T2.MATS):
                cid = 2 * i
                cx, cy = (cid % T2.COLS) * T2.CELL_W + x0, (cid // T2.COLS) * T2.CELL_H + y0
                cell = arr[cy:cy + sz, cx:cx + sz, :3].astype(np.float64)
                cell = cell / 255.0 if cell.max() > 1.5 else cell
                avg[nm] = [round(float(v), 4) for v in (cell ** 2.2).reshape(-1, 3).mean(0)]
            (OUT / "atlas" / f"{fname}.json").write_text(json.dumps(dict(ATLAS_W=T2.ATLAS_W, ATLAS_H=T2.ATLAS_H, MATS=T2.MATS,
                                                                          AVG=avg)), encoding="utf-8")
            print(fname, arr.shape)
    if only is None or "decor" in only:
        import decor_atlas
        for name, (data, w, h) in decor_atlas.build().items():
            (OUT / "atlas" / f"{name}.jpg").write_bytes(data)
            print(name, w, h, len(data) // 1024, "KB")
        (OUT / "atlas" / "decor.json").write_text(json.dumps(dict(PW=decor_atlas.PW, PH=decor_atlas.PH,
                                                                    layout=decor_atlas.layout())), encoding="utf-8")
    if only is None or "props" in only:
        import props
        data, w, h, reg = props.build(PROPS)
        (OUT / "props" / "patlas.jpg").write_bytes(data)
        (OUT / "props" / "props.json").write_text(json.dumps(dict(W=w, H=h, regions=reg)), encoding="utf-8")
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
