import io
from pathlib import Path

import numpy as np
from PIL import Image


def jpg(a, q=92):
    b = io.BytesIO()
    Image.fromarray(np.ascontiguousarray((np.nan_to_num(np.clip(a, 0, 1)) * 255 + 0.5).astype(np.uint8)), "RGB").save(b, "JPEG", quality=q, subsampling=0)
    return b.getvalue()


def save_tile(out, name, al, nm, rm):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}_a.jpg").write_bytes(jpg(al))
    (out / f"{name}_n.jpg").write_bytes(jpg(nm, 94))
    h = rm.shape[0] // 2
    rh = rm.reshape(h, 2, h, 2, 3).mean((1, 3)) if rm.shape[0] >= 64 else rm
    (out / f"{name}_r.jpg").write_bytes(jpg(rh))
