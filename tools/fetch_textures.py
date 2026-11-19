import json
import sys
import urllib.request
from pathlib import Path

SETS = {
    "grass": "leafy_grass", "rock": "dark_rock", "sand": "coast_sand_01", "dirt": "brown_mud_dry",
    "brick": "brick_wall_001", "wood": "old_wood_floor", "planks": "brown_planks_05", "asphalt": "asphalt_02",
    "tiles": "floor_tiles_06", "snow": "snow_02", "cliff": "cliff_side", "gravel": "gravel_road",
    "plaster": "painted_plaster_wall", "stone": "castle_brick_07", "cobble": "cobblestone_floor_08",
    "bark": "bark_brown_02", "roof": "clay_roof_tiles_02", "marble": "marble_01",
}
UA = {"User-Agent": "loophole-engine-asset-fetch/0.1"}


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()
KEYS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "AO": "ao"}


def main(dst):
    dst = Path(dst)
    for name, asset in SETS.items():
        files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
        out = dst / asset
        out.mkdir(parents=True, exist_ok=True)
        for key, short in KEYS.items():
            if key not in files:
                continue
            url = files[key]["2k"]["jpg"]["url"]
            f = out / f"{short}.jpg"
            if not f.exists():
                f.write_bytes(get(url))
        print(name, asset, sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main(sys.argv[1])
