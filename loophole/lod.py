import numpy as np

from . import decor_place

NEAR, SHARED = 0, 1


def instances(c, nkit):
    spans = []
    v = nkit
    for k, it in enumerate(getattr(c, "decor", [])):
        n = len(decor_place.module(it[0])[0])
        spans.append((k, it, v, v + n))
        v += n
    return spans


def nearest(src, dst):
    out = np.empty(len(dst), np.int64)
    for i in range(0, len(dst), 256):
        d = ((dst[i:i + 256, None, :] - src[None, :, :]) ** 2).sum(-1)
        out[i:i + 256] = d.argmin(1)
    return out


def prism(Pv, pos, up, sides=6):
    up = np.asarray(up, float)
    up = up / max(np.linalg.norm(up), 1e-9)
    base = np.asarray(pos, float)
    rel = Pv - base
    h_all = rel @ up
    y0 = float(h_all.min())
    span = float(h_all.max()) - y0
    if span < 1.5:
        return None
    low = h_all < y0 + min(0.5, span * 0.08)
    radial = rel - np.outer(h_all, up)
    r0 = float(np.clip(np.median(np.linalg.norm(radial[low], axis=1)), 0.05, 1.2))
    h = span * 0.62
    a = np.abs(up).argmin()
    e = np.zeros(3)
    e[a] = 1.0
    t1 = np.cross(up, e)
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(up, t1)
    P, N = [], []
    ring = [(np.cos(2 * np.pi * s / sides), np.sin(2 * np.pi * s / sides)) for s in range(sides)]
    for s in range(sides):
        c0, s0 = ring[s]
        c1, s1 = ring[(s + 1) % sides]
        d0 = t1 * c0 + t2 * s0
        d1 = t1 * c1 + t2 * s1
        b0 = base + up * y0 + d0 * r0
        b1 = base + up * y0 + d1 * r0
        u0 = base + up * (y0 + h) + d0 * r0 * 0.5
        u1 = base + up * (y0 + h) + d1 * r0 * 0.5
        for p, n in ((b0, d0), (b1, d1), (u1, d1), (b0, d0), (u1, d1), (u0, d0)):
            P.append(p)
            N.append(n)
    return np.array(P), np.array(N)


def cluster(Pv, tris):
    lo, hi = Pv.min(0), Pv.max(0)
    ext = hi - lo
    cell = max(float(ext.min()) * 0.3, 0.06)
    key = np.floor((Pv - lo) / cell).astype(np.int64)
    _, cid = np.unique(key, axis=0, return_inverse=True)
    cid = cid.ravel()
    nc = cid.max() + 1
    mean = np.zeros((nc, 3))
    np.add.at(mean, cid, Pv)
    cnt = np.bincount(cid, minlength=nc)[:, None]
    mean /= np.maximum(cnt, 1)
    d = ((Pv - mean[cid]) ** 2).sum(1)
    rep = np.full(nc, -1)
    best = np.full(nc, np.inf)
    for i in np.argsort(d):
        if rep[cid[i]] < 0:
            rep[cid[i]] = i
            best[cid[i]] = d[i]
    T = cid[tris]
    ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])
    T = T[ok]
    if not len(T):
        return None
    srt = np.sort(T, 1)
    _, first = np.unique(srt, axis=0, return_index=True)
    T = T[np.sort(first)]
    return mean[T.ravel()], rep[T.ravel()]


def split(c, cols, nkit):
    P = cols[0]
    F = np.asarray(cols[7], float)
    ntri = len(P) // 3
    cls = np.full(ntri, SHARED, np.int8)
    inst = np.full(ntri, -1, np.int64)
    lod_cols = [[] for _ in cols]
    lod_inst = []
    for k, it, v0, v1 in instances(c, nkit):
        t0, t1 = v0 // 3, v1 // 3
        if t1 <= t0:
            continue
        inst[t0:t1] = k
        Pv = P[v0:v1]
        fl = F[v0:v1:3]
        solid = fl < 4.5
        ext = Pv.max(0) - Pv.min(0)
        if not solid.any():
            if float(ext.max()) < 2.2:
                cls[t0:t1] = NEAR
            continue
        bb = np.nonzero(fl > 5.5)[0]
        if len(bb) >= 8:
            q = np.arange(len(bb)) // 2
            drop = ((q * 2654435761) >> 9) & 1 == 1
            cls[t0 + bb[drop]] = NEAR
        st = np.nonzero(solid)[0]
        if len(st) < 120:
            continue
        sv = (st[:, None] * 3 + np.arange(3)[None, :]).ravel()
        Ps = Pv[sv]
        name, pos, fwd, up, scale = it
        res = prism(Ps, pos, up) if float(ext[1]) > 3.0 and solid.sum() < len(solid) else None
        if res is not None:
            LP, LN = res
            src = nearest(Ps, LP)
        else:
            if float(ext.max()) < 0.9:
                continue
            res = cluster(Ps, np.arange(len(Ps)).reshape(-1, 3))
            if res is None:
                continue
            LP, src = res
            LN = None
        if len(LP) // 3 > len(st) * 0.6:
            continue
        gidx = v0 + sv[src]
        cls[t0 + st] = NEAR
        for j, col in enumerate(cols):
            if j == 0:
                lod_cols[j].append(LP)
            elif j == 1 and LN is not None:
                lod_cols[j].append(LN)
            else:
                lod_cols[j].append(np.asarray(col)[gidx])
        lod_inst.append(np.full(len(LP) // 3, k))
    if lod_inst:
        lod_cols = [np.concatenate(x) for x in lod_cols]
        lod_inst = np.concatenate(lod_inst)
    else:
        lod_cols = None
        lod_inst = np.zeros(0, np.int64)
    return cls, inst, lod_cols, lod_inst


def layout(order, cls, inst, n_lod, lod_inst, chunk):
    ntri = len(order)
    cid = np.arange(ntri) // chunk
    nch = int(cid.max()) + 1 if ntri else 0
    oc = cls[order]
    oi = inst[order]
    home = {}
    for k in np.unique(lod_inst):
        sel = (oi == k) & (oc == NEAR)
        if sel.any():
            home[int(k)] = int(np.bincount(cid[sel]).argmax())
    lod_ch = np.array([home.get(int(k), 0) for k in lod_inst], np.int64)
    seq, info = [], []
    start = 0
    for j in range(nch):
        idx = order[cid == j]
        b = idx[cls[idx] == NEAR]
        a = idx[cls[idx] != NEAR]
        cc = np.nonzero(lod_ch == j)[0] + ntri
        seq += [b, a, cc]
        info.append((start * 3, len(b) * 3, (len(b) + len(a)) * 3, (len(a) + len(cc)) * 3))
        start += len(b) + len(a) + len(cc)
    return np.concatenate(seq) if seq else np.zeros(0, np.int64), info
