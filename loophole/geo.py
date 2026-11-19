import io

import numpy as np
from PIL import Image

TPV = 8
VPR = 256
GW = TPV * VPR
BUCKETS = [256, 1024, 4096, 16384, 32768, 65536]


def bucket(ntri):
    for b in BUCKETS:
        if ntri <= b:
            return b
    raise ValueError(f"mesh too large: {ntri}")


def index_items(ntri):
    first = '{"aI":[' + ",".join(str(i) for i in range(ntri * 3)) + "]}"
    return [first] + [0] * (ntri - 1)


def q16(x):
    v = np.clip(np.round(x * 65535.0), 0, 65535).astype(np.int64)
    return v >> 8, v & 255


CHUNK = 8192
SCHUNK = 4096
IX = [256 << k for k in range(7)]


class Pack:
    def __init__(self):
        self.parts = []
        self.idx = []
        self.nv = 0
        self.nc = 0

    def add(self, pos, nrm, uv, mat, ao=None, seed=None, bone=None, irr=None, flag=None, tan=None):
        pos = np.asarray(pos, float).reshape(-1, 3)
        nrm = np.asarray(nrm, float).reshape(-1, 3)
        uv = np.asarray(uv, float).reshape(-1, 2)
        mat = np.asarray(mat, float).reshape(-1)
        n = len(pos)
        if ao is None:
            ao = np.ones(n)
        if seed is None:
            seed = np.zeros(n)
        lo = pos.min(0)
        hi = pos.max(0)
        org = lo - 0.01
        rng = float(max((hi - lo).max() + 0.02, 0.05))
        p = (pos - org) / rng
        px_h, px_l = q16(p[:, 0])
        py_h, py_l = q16(p[:, 1])
        pz_h, pz_l = q16(p[:, 2])
        u_h, u_l = q16(np.clip(uv[:, 0], 0, 1))
        v_h, v_l = q16(np.clip(uv[:, 1], 0, 1))
        ln = np.linalg.norm(nrm, axis=1, keepdims=True)
        nn = nrm / np.maximum(ln, 1e-9)
        nq = np.clip(np.round((nn * 0.5 + 0.5) * 255), 0, 255).astype(np.int64)
        t = np.zeros((n, TPV, 3), np.uint8)
        t[:, 0] = np.stack([px_h, py_h, pz_h], 1)
        t[:, 1] = np.stack([px_l, py_l, pz_l], 1)
        t[:, 2] = nq
        t[:, 3] = np.stack([u_h, u_l, v_h], 1)
        t[:, 4] = np.stack([v_l, np.clip(mat, 0, 255).astype(np.int64),
                            np.clip(np.round(np.asarray(ao) * 255), 0, 255).astype(np.int64)], 1)
        t[:, 5, 0] = np.clip(np.asarray(seed), 0, 255).astype(np.uint8)
        if bone is not None:
            t[:, 5, 1] = np.clip(np.asarray(bone), 0, 255).astype(np.uint8)
        if flag is not None:
            t[:, 5, 2] = np.clip(np.asarray(flag), 0, 255).astype(np.uint8)
        if tan is not None:
            t[:, 7] = np.clip(np.round((np.asarray(tan) * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
        if irr is not None:
            t[:, 6] = np.clip(np.round(np.sqrt(np.clip(np.asarray(irr), 0, 4) / 4) * 255), 0, 255).astype(np.uint8)
        key = np.ascontiguousarray(t.reshape(n, -1))
        uq, inv = np.unique(key, axis=0, return_inverse=True)
        cbase = self.nc
        self.parts.append(uq.reshape(-1, TPV, 3))
        self.idx.append(inv.ravel() + self.nv)
        self.nv += len(uq)
        self.nc += n
        return {"base": cbase, "count": n, "ox": float(org[0]), "oy": float(org[1]), "oz": float(org[2]), "r": rng}

    def add_mesh(self, m):
        d = m.data
        return self.add(d["aPos"], d["aNrm"], d.get("aLM", np.zeros(len(d["aPos"]) // 3 * 2)), d["aMat"],
                        d.get("aAO"))

    def png(self):
        vv = np.concatenate(self.parts, 0) if self.parts else np.zeros((1, TPV, 3), np.uint8)
        nvp = -(-len(vv) // GW) * GW
        v = np.zeros((nvp * TPV, 3), np.uint8)
        for k in range(TPV):
            v[k * nvp:k * nvp + len(vv)] = vv[:, k]
        ib = nvp * TPV
        ix = np.concatenate(self.idx) if self.idx else np.zeros(1, np.int64)
        it = np.stack([(ix >> 16) & 255, (ix >> 8) & 255, ix & 255], 1).astype(np.uint8)
        total = ib + len(it)
        h = max(1, -(-total // GW))
        img = np.zeros((h * GW, 3), np.uint8)
        img[:len(v)] = v
        img[ib:ib + len(it)] = it
        b = io.BytesIO()
        Image.fromarray(img.reshape(h, GW, 3), "RGB").save(b, "PNG", optimize=True)
        return b.getvalue(), GW, h, ib
