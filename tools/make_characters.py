import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loophole import character

ADVENTURERS = {"knight": "Knight", "mage": "Mage", "rogue": "Rogue_Hooded", "barbarian": "Barbarian"}
SKELETONS = {"skeleton": ("Skeleton_Warrior", "Skeleton_Blade"), "skeleton_minion": ("Skeleton_Minion", "Skeleton_Axe")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adventurers", help="folder with the KayKit Character Pack: Adventurers .glb files")
    ap.add_argument("--skeletons", help="folder with the KayKit Character Pack: Skeletons .glb files and weapon .gltf files")
    a = ap.parse_args()
    out = ROOT / "loophole" / "data"
    if a.adventurers:
        for name, f in ADVENTURERS.items():
            print(name, character.convert(Path(a.adventurers) / f"{f}.glb", out, name))
    if a.skeletons:
        src = Path(a.skeletons)
        for name, (f, weapon) in SKELETONS.items():
            print(name, character.convert(src / f"{f}.glb", out, name, attach=[(src / f"{weapon}.gltf", "handslot.r")]))


if __name__ == "__main__":
    main()
