import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy

import lh_blend as LB

UA = {"User-Agent": "loophole-engine-asset-build/0.1"}
SPECS = {
    "table": ("WoodenTable_01", 2000, 512), "chair": ("WoodenChair_01", 2500, 512),
    "bookshelf": ("wooden_bookshelf_worn", 3500, 512), "sofa": ("Sofa_01", 3000, 512),
    "bed": ("GothicBed_01", 4000, 512), "woodbarrel": ("Barrel_01", 1800, 512),
    "woodcrate": ("wooden_crate_01", 2500, 512), "bench": ("painted_wooden_bench", 1200, 512),
    "firepit": ("stone_fire_pit", 2500, 512), "walllamp": ("industrial_wall_lamp", 1500, 256),
    "streetlamp": ("street_lamp_01", 3000, 512), "lantern": ("Lantern_01", 5000, 1024), "log": ("dead_tree_trunk", 2500, 512), "mossrock": ("rock_moss_set_01", 2500, 512),
    "boulder": ("boulder_01", 3000, 1024), "rock": ("namaqualand_boulder_02", 2500, 512),
    "stump": ("tree_stump_01", 2500, 512), "armchair": ("ArmChair_01", 3000, 512),
    "nightstand": ("ClassicNightstand_01", 1500, 512), "cabinet": ("painted_wooden_cabinet", 2500, 512),
    "picture": ("hanging_picture_frame_01", 600, 256), "chandelier": ("Chandelier_01", 3000, 512),
    "toolcart": ("tool_cart", 2500, 512), "sconce": ("industrial_wall_sconce", 1200, 256),
    "apple": ("food_apple_01", 600, 256), "rat": ("street_rat", 1500, 512), "treasure": ("treasure_chest", 3000, 512),
    "candlestick": ("wooden_candlestick", 800, 256), "oillamp": ("vintage_oil_lamp", 1500, 256),
    "statue": ("gothic_statue", 4000, 1024), "catstatue": ("concrete_cat_statue", 2000, 512),
    "bucket": ("wooden_bucket_01", 1000, 256), "winebarrel": ("wine_barrel_01", 1800, 512),
    "goblet": ("brass_goblets", 1000, 256),
}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()


def fetch(asset, cache, res="1k"):
    d = Path(cache) / asset
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
    g = files["gltf"][res]["gltf"]
    d.mkdir(parents=True, exist_ok=True)
    main = d / Path(g["url"]).name
    if not main.exists():
        main.write_bytes(get(g["url"]))
    for rel, info in g.get("include", {}).items():
        f = d / rel
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(get(info["url"]))
    return main


def process(name, cache):
    asset, target, size = SPECS[name]
    path = fetch(asset, cache)
    LB.setup()
    obs = LB.import_gltf(path)
    hi = LB.join(obs, name + "_hi")
    LB.recenter(hi)
    lo = LB.duplicate(hi, name)
    LB.decimate(lo, target)
    LB.triangulate(lo)
    LB.smooth(lo)
    LB.unwrap(lo)
    maps = LB.bake(hi, lo, size)
    LB.save_maps(name, maps, cache)
    n = LB.export_mesh(lo, name)
    print("PROP", name, asset, n, "tris")


def main():
    a = LB.args()
    cache = a[0]
    names = a[1:] or list(SPECS)
    for n in names:
        try:
            process(n, cache)
        except Exception as e:
            print("FAILED", n, repr(e))


main()
