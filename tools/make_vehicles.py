import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from loophole import vehicle

KENNEY = {"kart": ("kart-oobi", 1.5), "kart_pink": ("kart-oodi", 1.5), "kart_yellow": ("kart-ooli", 1.5),
          "kart_green": ("kart-oopi", 1.5), "kart_tan": ("kart-oozi", 1.5), "racecar": ("race", 3.2),
          "police": ("police", 3.9), "taxi": ("taxi", 3.9), "suv": ("suv", 4.1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kenney", help="the 'Models/GLB format' folder of the Kenney Car Kit")
    a = ap.parse_args()
    out = ROOT / "loophole" / "data"
    for name, (f, length) in KENNEY.items():
        print(name, vehicle.convert(Path(a.kenney) / f"{f}.glb", out, name, length=length))


if __name__ == "__main__":
    main()
