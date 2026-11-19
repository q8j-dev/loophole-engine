import argparse
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "loophole" / "data" / "tiles"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(Path(a.src).resolve() / "tw"))
    import decor_atlas
    from lh_tiles import save_tile
    for name, size in decor_atlas.SIZES.items():
        if not (decor_atlas.KIT / f"kit_{name}_maps.npz").exists():
            continue
        al, nm, rm = decor_atlas.load(name, size)
        save_tile(OUT, name, al, nm, rm)
        print(name, size)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
