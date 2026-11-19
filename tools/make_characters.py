import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loophole import character

NAMES = {"knight": "Knight", "mage": "Mage", "rogue": "Rogue_Hooded", "barbarian": "Barbarian"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kaykit", help="folder with the KayKit Adventurers .glb files")
    a = ap.parse_args()
    src = Path(a.kaykit)
    for name, f in NAMES.items():
        print(name, character.convert(src / f"{f}.glb", ROOT / "loophole" / "data", name))


if __name__ == "__main__":
    main()
