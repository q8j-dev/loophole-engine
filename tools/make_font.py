import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "loophole" / "data"
COLS, ROWS = 16, 6
CW, CH = 64, 96
PAD = 8
SS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    ap.add_argument("--weight", type=int, default=600)
    a = ap.parse_args()
    f = ImageFont.truetype(a.font, int(CH * 0.62) * SS)
    try:
        f.set_variation_by_axes([a.weight])
    except (OSError, AttributeError):
        pass
    asc, desc = f.getmetrics()
    base = int(CH * 0.74) * SS
    cov = Image.new("L", (COLS * CW * SS, ROWS * CH * SS), 0)
    d = ImageDraw.Draw(cov)
    adv = []
    for i in range(COLS * ROWS):
        ch = chr(32 + i)
        x = (i % COLS) * CW * SS
        y = (i // COLS) * CH * SS
        if ch.isprintable() and i < 95:
            d.text((x + PAD * SS, y + base), ch, font=f, fill=255, anchor="ls")
            adv.append(round(f.getlength(ch) / (CH * SS), 4))
        else:
            adv.append(0.3)
    cov = cov.resize((COLS * CW, ROWS * CH), Image.LANCZOS)
    sh = Image.new("L", cov.size, 0)
    sh.paste(cov, (2, 3))
    sh = sh.filter(ImageFilter.GaussianBlur(3.2))
    sh = Image.fromarray(np.clip(np.asarray(sh, float) * 1.6, 0, 255).astype(np.uint8))
    rgb = Image.merge("RGB", (cov, sh, Image.new("L", cov.size, 0)))
    rgb.save(OUT / "font.png", optimize=True)
    (OUT / "font.json").write_text(json.dumps({"cols": COLS, "rows": ROWS, "cw": CW, "ch": CH, "pad": PAD / CH,
                                               "adv": adv}))
    print("font atlas", rgb.size)


if __name__ == "__main__":
    main()
