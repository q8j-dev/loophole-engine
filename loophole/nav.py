import math

import numpy as np

from . import level as lvl

BLOCKED = -999.0
NAV_LISTS = ("NGX0", "NGZ0", "NGC", "NGW", "NGH", "NGB", "NGRID")


def bounds(L, c):
    td = L.terrain_def
    if td:
        return td["x0"], td["z0"], td["x1"], td["z1"]
    o = c.origin
    s = np.array(c.size, float) / lvl.RES
    return o[0], o[2], o[0] + s[0], o[2] + s[2]


def grid(L, c):
    from . import decor_place
    from . import terrain as T
    x0, z0, x1, z1 = bounds(L, c)
    cell = max(0.5, max(x1 - x0, z1 - z0) / 128.0)
    nx = max(1, int(math.ceil((x1 - x0) / cell)))
    nz = max(1, int(math.ceil((z1 - z0) / cell)))
    xs = x0 + (np.arange(nx) + 0.5) * cell
    zs = z0 + (np.arange(nz) + 0.5) * cell
    X, Z = np.meshgrid(xs, zs)
    H = np.full((nz, nx), BLOCKED)
    air = getattr(c, "air", None)
    td = L.terrain_def
    field = None
    if td:
        txs, tzs, TH = T.heights(td)
        field = T.Field(td, txs, tzs, TH)
        H = field.height(X.ravel(), Z.ravel()).reshape(nz, nx).astype(float)
        for w in td.get("waters", []):
            wy = w.get("y")
            if wy is None:
                continue
            deep = H < wy - 0.8
            H[deep] = BLOCKED
    if air is not None and air.size:
        ax, ay, az = air.shape
        ix = np.floor((X - c.origin[0]) * lvl.RES).astype(int)
        iz = np.floor((Z - c.origin[2]) * lvl.RES).astype(int)
        inside = (ix >= 0) & (ix < ax) & (iz >= 0) & (iz < az)
        for j in range(nz):
            for i in range(nx):
                if not inside[j, i]:
                    continue
                col = air[ix[j, i], :, iz[j, i]]
                if field is not None:
                    if H[j, i] <= BLOCKED + 1:
                        continue
                    y0 = int(math.floor((H[j, i] - c.origin[1]) * lvl.RES)) + 1
                    seg = col[max(0, y0):max(0, y0) + 3]
                    if y0 < ay and len(seg) and not seg.all():
                        H[j, i] = BLOCKED
                    continue
                for y in range(1, ay - 3):
                    if not col[y - 1] and col[y:y + 4].all():
                        H[j, i] = c.origin[1] + y / lvl.RES
                        break
    elif field is None:
        return None

    def block_box(bx0, bz0, bx1, bz1, pad=0.25):
        i0 = max(0, int(math.floor((bx0 - pad - x0) / cell)))
        i1 = min(nx, int(math.ceil((bx1 + pad - x0) / cell)))
        j0 = max(0, int(math.floor((bz0 - pad - z0) / cell)))
        j1 = min(nz, int(math.ceil((bz1 + pad - z0) / cell)))
        H[j0:j1, i0:i1] = BLOCKED

    fps = decor_place.footprints(c)
    for k in getattr(L, "solid_props", []):
        if k < len(fps):
            lo, hi = fps[k]
            block_box(lo[0], lo[2], hi[0], hi[2])
    for b in getattr(L, "solid_boxes", []):
        block_box(b[0], b[2], b[3], b[5], 0.15)
    for op, b in L.ops:
        if op == "fill" and td:
            block_box(b[0], b[2], b[3], b[5], 0.1)
    for t in L.triggers:
        if t["kind"] == 1:
            b = t["box"]
            block_box(b[0], b[2], b[3], b[5], 0.0)
    for o in L.objects:
        if o.solid and not o.physics and o.kind == 0 and not o.path and not getattr(o, "mode", None):
            s = float(o.scale) if isinstance(o.scale, (int, float)) else 1.0
            r = 0.45 * s * max(o.size[0], o.size[2])
            block_box(o.pos[0] - r, o.pos[2] - r, o.pos[0] + r, o.pos[2] + r, 0.0)
    return dict(x0=x0, z0=z0, cell=cell, nx=nx, nz=nz, h=H)


def nav_lists(L, Lv, c):
    g = grid(Lv, c)
    L["NGB"].append(len(L["NGRID"]) + 1)
    if g is None:
        for k, v in zip(("NGX0", "NGZ0", "NGC", "NGW", "NGH"), (0, 0, 1, 0, 0)):
            L[k].append(v)
        return 0
    L["NGX0"].append(round(float(g["x0"]), 3))
    L["NGZ0"].append(round(float(g["z0"]), 3))
    L["NGC"].append(round(float(g["cell"]), 4))
    L["NGW"].append(g["nx"])
    L["NGH"].append(g["nz"])
    L["NGRID"].extend(round(float(v), 2) for v in g["h"].ravel())
    return g["nx"] * g["nz"]
