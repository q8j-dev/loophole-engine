import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import level as lvl
from .materials import ALB, EMIT, MATID, TINT

LMW = 1024
LMH = 512
PAD = 2
LMAX = 4.0
PANEL_L = 4.6
GOO_L = 0.55
EXIT_L = 1.4
STEP = 0.11
PANEL_C = np.array([1.0, 0.97, 0.92])


def face_rects(c):
    out = []
    for axis, sgn, pl, u0, v0, u1, v1, m in c.faces():
        u, v = [a for a in range(3) if a != axis]
        o = c.origin
        out.append(dict(axis=axis, sgn=sgn, pl=pl + o[axis], u=u, v=v, u0=u0 + o[u], u1=u1 + o[u], v0=v0 + o[v],
                        v1=v1 + o[v], mat=m))
    return out


def light_panels(rects):
    panels = []
    for r in rects:
        if r["axis"] == 1 and r["sgn"] < 0 and r["mat"] in ("ceil", "white", "metal"):
            w, h = r["u1"] - r["u0"], r["v1"] - r["v0"]
            if w < 1.9 or h < 1.9:
                continue
            nu = max(1, int(round(w / 4.0)))
            nv = max(1, int(round(h / 4.0)))
            for i in range(nu):
                for j in range(nv):
                    cu = r["u0"] + (i + 0.5) * w / nu
                    cv = r["v0"] + (j + 0.5) * h / nv
                    hu = min(0.75, w / nu / 3)
                    hv = min(0.75, h / nv / 3)
                    panels.append((cu, r["pl"] - 0.006, cv, hu, hv))
    return panels


FINE = 4


class Grid:
    def __init__(self, c):
        self.solid = ~c.air
        self.origin = c.origin
        self.shape = np.array(self.solid.shape)
        self.open_top = (1, -1) in getattr(c, "open_faces", ())
        self.outdoor = len(getattr(c, "open_faces", ())) >= 5
        vol = float(np.prod(self.shape))
        self.F = FINE if vol * FINE ** 3 < 60e6 else (2 if vol * 8 < 60e6 else 1)
        F = self.F
        self.fine = np.repeat(np.repeat(np.repeat(self.solid, F, 0), F, 1), F, 2)
        self.fshape = np.array(self.fine.shape)

    def add_occluders(self, boxes):
        fr = lvl.RES * self.F
        for (x0, y0, z0, x1, y1, z1) in boxes:
            a = np.floor((np.array([x0, y0, z0]) - self.origin) * fr).astype(int)
            b = np.ceil((np.array([x1, y1, z1]) - self.origin) * fr).astype(int)
            a = np.clip(a, 0, self.fshape)
            b = np.clip(b, 0, self.fshape)
            self.fine[a[0]:b[0], a[1]:b[1], a[2]:b[2]] = True

    def add_heightfield(self, xs, zs, H):
        fr = lvl.RES * self.F
        nxf, nyf, nzf = self.fshape
        cx = self.origin[0] + (np.arange(nxf) + 0.5) / fr
        cz = self.origin[2] + (np.arange(nzf) + 0.5) / fr
        hx = np.interp(cx, xs, np.arange(len(xs)), left=-1, right=-1)
        hz = np.interp(cz, zs, np.arange(len(zs)), left=-1, right=-1)
        for i in range(nxf):
            if hx[i] < 0:
                continue
            ok = hz >= 0
            x0 = int(np.floor(hx[i]))
            x1 = min(x0 + 1, len(xs) - 1)
            fx = hx[i] - x0
            zz = hz[ok]
            z0 = np.floor(zz).astype(int)
            z1 = np.minimum(z0 + 1, len(zs) - 1)
            fz = zz - z0
            h = (H[z0, x0] * (1 - fx) + H[z0, x1] * fx) * (1 - fz) + (H[z1, x0] * (1 - fx) + H[z1, x1] * fx) * fz
            top = np.clip(np.floor((h - 0.05 - self.origin[1]) * fr).astype(int), 0, nyf)
            ks = np.nonzero(ok)[0]
            ys = np.arange(nyf)
            self.fine[i][:, ks] |= ys[:, None] < top[None, :]

    def fine_solid(self, P):
        I = np.floor((P - self.origin) * (lvl.RES * self.F)).astype(np.int64)
        ok = np.all((I >= 0) & (I < self.fshape), axis=1)
        out = np.ones(len(I), bool)
        if self.outdoor:
            out[~ok] = I[~ok, 1] < 0
        elif self.open_top:
            out[I[:, 1] >= self.fshape[1]] = False
        J = I[ok]
        out[ok] = self.fine[J[:, 0], J[:, 1], J[:, 2]]
        return out

    def idx(self, P):
        return np.floor((P - self.origin) * lvl.RES).astype(np.int64)

    def is_solid(self, I):
        ok = np.all((I >= 0) & (I < self.shape), axis=1)
        out = np.ones(len(I), bool)
        if self.outdoor:
            out[~ok] = I[~ok, 1] < 0
        elif self.open_top:
            out[I[:, 1] >= self.shape[1]] = False
        J = I[ok]
        out[ok] = self.solid[J[:, 0], J[:, 1], J[:, 2]]
        return out

    def occluded(self, P, D, tmax, t0=0.04):
        n = len(P)
        hit = np.zeros(n, bool)
        act = np.arange(n)
        t = t0
        st = 0.07
        top = self.origin[1] + self.shape[1] / lvl.RES
        while len(act):
            Q = P[act] + D[act] * t
            s = self.fine_solid(Q)
            hit[act[s]] = True
            keep = ~s & (tmax[act] > t + st)
            if self.outdoor:
                lo_ = self.origin
                hi_ = self.origin + self.shape / lvl.RES
                keep &= np.all((Q >= lo_ - 0.5) & (Q <= hi_ + 0.5), axis=1)
            elif self.open_top:
                keep &= Q[:, 1] < top
            act = act[keep]
            t += st
        return hit

    def first_hit(self, P, D, tmax=60.0, t0=0.04):
        n = len(P)
        cell = np.full((n, 3), -1, np.int64)
        axis = np.full(n, -1, np.int64)
        dist = np.full(n, np.inf)
        act = np.arange(n)
        prev = self.idx(P + D * t0)
        t = t0 + STEP
        top = self.shape[1]
        while len(act) and t < tmax:
            I = self.idx(P[act] + D[act] * t)
            if self.outdoor:
                up = np.any((I >= self.shape) | (I < 0), axis=1) & (I[:, 1] >= 0)
                if up.any():
                    act = act[~up]
                    prev = prev[~up]
                    I = I[~up]
            elif self.open_top:
                up = I[:, 1] >= top
                if up.any():
                    act = act[~up]
                    prev = prev[~up]
                    I = I[~up]
            s = self.is_solid(I)
            if s.any():
                a = act[s]
                Is = I[s]
                ch = Is != prev[s]
                w = np.abs(D[a]) * ch
                ax = np.argmax(w, 1)
                ok = ch.any(1)
                cell[a[ok]] = Is[ok]
                axis[a[ok]] = ax[ok]
                dist[a[ok]] = t
            prev = I[~s]
            act = act[~s]
            t += STEP
        return cell, axis, dist


def cos_dirs(N, k, rng):
    n = len(N)
    u1 = rng.random((n, k))
    u2 = rng.random((n, k))
    r = np.sqrt(u1)
    ph = 2 * np.pi * u2
    lx, ly, lz = r * np.cos(ph), r * np.sin(ph), np.sqrt(1 - u1)
    T1 = np.zeros((n, 3))
    ax = np.argmax(np.abs(N), 1)
    T1[ax == 0] = [0, 1, 0]
    T1[ax == 1] = [1, 0, 0]
    T1[ax == 2] = [1, 0, 0]
    T2 = np.cross(N, T1)
    return lx[..., None] * T1[:, None, :] + ly[..., None] * T2[:, None, :] + lz[..., None] * N[:, None, :]


def sky_rad(c, D):
    sr = np.array(getattr(c, "sky_rad", (0, 0, 0)), float)
    y = np.clip(D[..., 1], 0, 1)
    return sr * (0.55 + 0.45 * y)[..., None]


def light_list(c, rects):
    out = []
    for L in getattr(c, "lights", []):
        out.append(norm_light(L))
    sun = getattr(c, "sun", None)
    if sun:
        sd = np.array(sun["d"], float)
        sd /= np.linalg.norm(sd)
        out.insert(0, dict(kind="sun", sd=sd, p=sd * 400.0, d=-sd, u=np.array([1.0, 0, 0]), v=np.array([0, 0, 1.0]),
                           hu=0.3, hv=0.3, col=np.array(sun["col"], float) / max(sun["col"]), power=max(sun["col"]),
                           inten=max(sun["col"]), cin=-0.99, cout=-1.0, vol=0.0, fixture=False, name="sun"))
    if not out and not sun:
        for (cx, cy, cz, hu, hv) in light_panels(rects):
            out.append(norm_light(dict(kind="panel", p=(cx, cy, cz), d=(0, -1, 0), size=(hu, hv), col=PANEL_C,
                                       power=PANEL_L)))
    return out


def norm_light(L):
    L = dict(L)
    d = np.array(L.get("d", (0, -1, 0)), float)
    d /= np.linalg.norm(d)
    up = np.array([0.0, 1.0, 0.0]) if abs(d[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(up, d)
    u /= np.linalg.norm(u)
    if "u" in L:
        u = np.array(L["u"], float)
        u = u - d * np.dot(u, d)
        u /= np.linalg.norm(u)
    v = np.cross(d, u)
    hu, hv = L.get("size", (0.1, 0.1))
    kind = L["kind"]
    col = np.array(L.get("col", (1, 1, 1)), float)
    pw = float(L.get("power", 1.0))
    if kind in ("panel", "strip"):
        area = 4 * hu * (hv if kind == "panel" else 0.03)
        inten = pw * area / np.pi
        cin, cout = -2.0, -1.0
    else:
        inten = pw
        cout = math.cos(math.radians(L.get("cone", (30, 45))[1])) if kind == "spot" else -1.0
        cin = math.cos(math.radians(L.get("cone", (30, 45))[0])) if kind == "spot" else -0.99
    return dict(kind=kind, p=np.array(L["p"], float), d=d, u=u, v=v, hu=hu, hv=hv, col=col, power=pw,
                inten=inten, cin=cin, cout=cout, vol=float(L.get("vol", 1.0 if kind == "spot" else 0.0)),
                fixture=L.get("fixture", True))


def light_profile(L, w):
    c = np.einsum("ij,j->i", w, L["d"])
    if L["kind"] in ("panel", "strip"):
        return np.clip(c, 0, None)
    if L["kind"] == "spot":
        t = np.clip((c - L["cout"]) / max(L["cin"] - L["cout"], 1e-4), 0, 1)
        return t * t * (3 - 2 * t)
    return np.ones(len(w))


CULL = 0.004


LOG = None


def _log(msg):
    if LOG:
        LOG(msg)


def stage(t0, msg):
    _log(f"    [{time.time() - t0:6.1f}s] {msg}")


def direct(P, N, lights, grid, rng, ns=3):
    n = len(P)
    E = np.zeros((n, 3))
    Dv = np.zeros((n, 3))
    for L in lights:
        if L["kind"] == "sun":
            k = max(2, ns)
            sd = L["sd"]
            up = np.array([0.0, 1.0, 0.0]) if abs(sd[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
            tu = np.cross(up, sd)
            tu /= np.linalg.norm(tu)
            tv = np.cross(sd, tu)
            cp0 = N @ sd
            for s_ in range(k * k):
                a = ((s_ % k + rng.random(n)) / k * 2 - 1) * 0.012
                b = ((s_ // k + rng.random(n)) / k * 2 - 1) * 0.012
                Vn = sd[None] + tu[None] * a[:, None] + tv[None] * b[:, None]
                Vn /= np.linalg.norm(Vn, axis=1, keepdims=True)
                ok = cp0 > 0
                if not ok.any():
                    continue
                idx = np.nonzero(ok)[0]
                occ = grid.occluded(P[idx], Vn[idx], np.full(len(idx), 400.0))
                vis = idx[~occ]
                c = L["inten"] * np.clip(np.einsum("ij,ij->i", Vn[vis], N[vis]), 0, None) / (k * k)
                E[vis] += c[:, None] * L["col"][None]
                Dv[vis] += Vn[vis] * (c * L["col"].mean())[:, None]
            continue
        k = ns if L["kind"] in ("panel", "strip") else max(2, ns - 1)
        for s in range(k * k):
            a = (s % k + rng.random(n)) / k * 2 - 1
            b = (s // k + rng.random(n)) / k * 2 - 1
            if L["kind"] == "panel":
                off = L["u"][None] * (a * L["hu"])[:, None] + L["v"][None] * (b * L["hv"])[:, None]
            elif L["kind"] == "strip":
                off = L["u"][None] * (a * L["hu"])[:, None] + L["v"][None] * (b * 0.03)[:, None]
            else:
                r = L["hu"]
                off = L["u"][None] * (a * r)[:, None] + L["v"][None] * (b * r)[:, None]
            Ls = L["p"][None] + off + L["d"][None] * 0.01
            V = Ls - P
            d2 = np.einsum("ij,ij->i", V, V)
            d = np.sqrt(d2)
            Vn = V / d[:, None]
            cp = np.einsum("ij,ij->i", Vn, N)
            prof = light_profile(L, -Vn)
            ok = (cp > 0) & (prof > 0) & (L["inten"] * cp * prof / (d2 + 0.05) > CULL)
            if not ok.any():
                continue
            idx = np.nonzero(ok)[0]
            occ = grid.occluded(P[idx], Vn[idx], d[idx] - 0.06)
            vis = idx[~occ]
            c = L["inten"] * cp[vis] * prof[vis] / (d2[vis] + 0.05) / (k * k)
            E[vis] += c[:, None] * L["col"][None]
            Dv[vis] += Vn[vis] * (c * L["col"].mean())[:, None]
    return E, Dv


def bake_level(c, seed=1, ao_rays=32, gi_rays=256):
    t0 = time.time()
    gi_rays = getattr(c, "bake_gi_rays", gi_rays)
    ao_rays = getattr(c, "bake_ao_rays", ao_rays)
    dres = getattr(c, "bake_dres", 4)
    ns_q = getattr(c, "bake_ns", 4)
    global FOCUS
    FOCUS = getattr(c, "bake_focus", None)
    rng = np.random.default_rng(seed)
    grid = Grid(c)
    rects = face_rects(c)
    lights = light_list(c, rects)
    panels = [(L["p"][0], L["p"][1], L["p"][2], L["hu"], L["hv"]) for L in lights
              if L["kind"] == "panel" and abs(L["d"][1] + 1) < 1e-3 and L["fixture"]]
    from . import decor_place
    DP, DN, DM, DA, DS, dboxes = decor_place.build(c)
    DFL = np.where(DM[:, 6] > 0.5, 0.0, DM[:, 7]) if len(DM) and DM.shape[1] > 7 else None
    grid.add_occluders(list(getattr(c, "occluders", [])) + dboxes)
    TER = getattr(c, "terrain", None)
    if TER is not None:
        grid.add_heightfield(*TER["grid"])
    cf = []
    for ri, r in enumerate(rects):
        nu = int(round((r["u1"] - r["u0"]) * 2))
        nv = int(round((r["v1"] - r["v0"]) * 2))
        r["nu"], r["nv"] = nu, nv
        r["cf0"] = len(cf)
        for j in range(nv):
            for i in range(nu):
                p = np.zeros(3)
                p[r["axis"]] = r["pl"]
                p[r["u"]] = r["u0"] + (i + 0.5) * 0.5
                p[r["v"]] = r["v0"] + (j + 0.5) * 0.5
                cf.append((ri, p))
    CP = np.array([p for _, p in cf])
    CN = np.zeros_like(CP)
    calb = np.zeros((len(cf), 3))
    cem = np.zeros((len(cf), 3))
    for k, (ri, p) in enumerate(cf):
        r = rects[ri]
        CN[k, r["axis"]] = r["sgn"]
        calb[k] = ALB[r["mat"]] * np.array(TINT[r["mat"]])
        if r["mat"] in EMIT:
            cem[k] = EMIT[r["mat"]]
    cem_g = cem.copy()
    for L in lights:
        if L["kind"] != "panel" or abs(L["d"][1] + 1) > 1e-3:
            continue
        cx, cy, cz, hu, hv = L["p"][0], L["p"][1], L["p"][2], L["hu"], L["hv"]
        m = (CN[:, 1] < -0.5) & (np.abs(CP[:, 1] - cy) < 0.12)
        ox = np.clip(np.minimum(CP[:, 0] + 0.25, cx + hu) - np.maximum(CP[:, 0] - 0.25, cx - hu), 0, None)
        oz = np.clip(np.minimum(CP[:, 2] + 0.25, cz + hv) - np.maximum(CP[:, 2] - 0.25, cz - hv), 0, None)
        cov = ox * oz / 0.25
        cem[m] += L["col"] * L["power"] * cov[m, None]
    F = {}
    for d in range(6):
        F[d] = np.full(grid.solid.shape, -1, np.int64)
    behind = grid.idx(CP - CN * 0.25)
    okb = np.all((behind >= 0) & (behind < grid.shape), 1)
    for k in np.nonzero(okb)[0]:
        r = rects[cf[k][0]]
        d = r["axis"] * 2 + (0 if r["sgn"] > 0 else 1)
        F[d][tuple(behind[k])] = k
    P0 = CP + CN * 0.02
    stage(t0, f"{len(rects)} rects, {len(CP)} cell faces, {len(lights)} lights, {len(DP)} decor verts; direct on cells")
    Ed, Dd = direct(P0, CN, lights, grid, rng, ns=min(3, ns_q))
    stage(t0, f"gi rays {len(CP) * gi_rays}")
    Ld = Ed
    dirs = cos_dirs(CN, gi_rays, rng)
    n = len(CP)
    hit_ids = np.full((n, gi_rays), -1, np.int64)
    Dr = dirs.reshape(-1, 3)
    CH = gi_rays * max(1, 1500000 // gi_rays)
    cell = np.zeros((len(Dr), 3), np.int64)
    axis = np.zeros(len(Dr), np.int64)
    for c0 in range(0, len(Dr), CH):
        Pr = np.repeat(P0[c0 // gi_rays:(c0 + CH) // gi_rays + 1], gi_rays, 0)[:min(CH, len(Dr) - c0)]
        ce, ax_, _ = grid.first_hit(Pr, Dr[c0:c0 + CH])
        cell[c0:c0 + len(ce)] = ce
        axis[c0:c0 + len(ce)] = ax_
    del Pr
    ok = axis >= 0
    sg = np.where(Dr[np.arange(len(Dr)), np.clip(axis, 0, 2)] > 0, 1, 0)
    dcode = axis * 2 + sg
    hid = np.full(len(Dr), -1, np.int64)
    for d in range(6):
        m = ok & (dcode == d)
        I = cell[m]
        inb = np.all((I >= 0) & (I < grid.shape), 1)
        sel = np.nonzero(m)[0][inb]
        hid[sel] = F[d][I[inb, 0], I[inb, 1], I[inb, 2]]
    hit_ids = hid.reshape(n, gi_rays)
    Li = np.zeros((n, 3))
    skyB = sky_rad(c, dirs) if getattr(c, "sky_rad", None) is not None else 0.0
    for it in range(4):
        B = cem_g + calb * (Ld + Li)
        Bh = np.where(hit_ids[..., None] >= 0, B[np.clip(hit_ids, 0, None)], skyB)
        Li = Bh.mean(1)
    for r in rects:
        base, nu, nv = r["cf0"], r["nu"], r["nv"]
        g = Li[base:base + nu * nv].reshape(nv, nu, 3)
        for _ in range(3):
            p_ = np.pad(g, ((1, 1), (1, 1), (0, 0)), mode="edge")
            g = (p_[:-2, 1:-1] + p_[2:, 1:-1] + p_[1:-1, :-2] + p_[1:-1, 2:] + 2 * p_[1:-1, 1:-1]) / 6
        Li[base:base + nu * nv] = g.reshape(-1, 3)
    Bh = np.where(hit_ids[..., None] >= 0, B[np.clip(hit_ids, 0, None)], skyB)
    Lw = Bh.mean(2)
    Di = np.einsum("nk,nkj->nj", Lw, dirs) / gi_rays
    _log(f"  {c.name}: {len(rects)} rects, {n} cell faces, {len(lights)} lights, gi {time.time() - t0:.1f}s")
    stage(t0, "gi done; lightmap alloc")
    texels = alloc(rects)
    TP, TN, TR, TIJ = [], [], [], []
    for ri, r in enumerate(rects):
        tu, tv = r["tu"], r["tv"]
        ii, jj = np.meshgrid(np.arange(-PAD, tu + PAD), np.arange(-PAD, tv + PAD))
        uu = r["u0"] + (np.clip(ii, 0, tu - 1) + 0.5) / tu * (r["u1"] - r["u0"])
        vv = r["v0"] + (np.clip(jj, 0, tv - 1) + 0.5) / tv * (r["v1"] - r["v0"])
        p = np.zeros(uu.shape + (3,))
        p[..., r["axis"]] = r["pl"]
        p[..., r["u"]] = uu
        p[..., r["v"]] = vv
        nn = np.zeros(3)
        nn[r["axis"]] = r["sgn"]
        TP.append(p.reshape(-1, 3))
        TN.append(np.tile(nn, (p.shape[0] * p.shape[1], 1)))
        TR.append(np.full(p.shape[0] * p.shape[1], ri))
        TIJ.append(np.stack([ii.ravel() + PAD + r["ax"], jj.ravel() + PAD + r["ay"]], 1))
    TP = np.concatenate(TP)
    TN = np.concatenate(TN)
    TR = np.concatenate(TR)
    TIJ = np.concatenate(TIJ)
    DRES = dres
    QP, QN = [], []
    for ri, r in enumerate(rects):
        nu4 = max(2, int(round((r["u1"] - r["u0"]) * DRES)))
        nv4 = max(2, int(round((r["v1"] - r["v0"]) * DRES)))
        r["q0"], r["qu"], r["qv"] = len(QP), nu4, nv4
        for j in range(nv4):
            for i in range(nu4):
                p = np.zeros(3)
                p[r["axis"]] = r["pl"]
                p[r["u"]] = r["u0"] + (i + 0.5) / nu4 * (r["u1"] - r["u0"])
                p[r["v"]] = r["v0"] + (j + 0.5) / nv4 * (r["v1"] - r["v0"])
                nn = np.zeros(3)
                nn[r["axis"]] = r["sgn"]
                QP.append(p)
                QN.append(nn)
    QP = np.array(QP)
    QN = np.array(QN)
    stage(t0, f"{len(TP)} texels; direct on {len(QP)} samples")
    Eq, Dq = direct(QP + QN * 0.02, QN, lights, grid, rng, ns=ns_q)
    stage(t0, "ao + dirt")
    Et = np.zeros((len(TP), 3))
    Dt = np.zeros((len(TP), 3))
    Lt_ind = np.zeros((len(TP), 3))
    Dt_ind = np.zeros((len(TP), 3))
    for ri, r in enumerate(rects):
        m = TR == ri
        uu = (TP[m, r["u"]] - r["u0"]) / (r["u1"] - r["u0"])
        vv = (TP[m, r["v"]] - r["v0"]) / (r["v1"] - r["v0"])
        base, nu, nv = r["cf0"], r["nu"], r["nv"]
        Lt_ind[m] = interp(Li[base:base + nu * nv].reshape(nv, nu, 3), uu, vv)
        Dt_ind[m] = interp(Di[base:base + nu * nv].reshape(nv, nu, 3), uu, vv)
        base, nu, nv = r["q0"], r["qu"], r["qv"]
        Et[m] = interp(Eq[base:base + nu * nv].reshape(nv, nu, 3), uu, vv)
        Dt[m] = interp(Dq[base:base + nu * nv].reshape(nv, nu, 3), uu, vv)
    aod = cos_dirs(TN, ao_rays, rng)
    Pa = np.repeat(TP + TN * 0.02, ao_rays, 0)
    occ = grid.occluded(Pa, aod.reshape(-1, 3), np.full(len(Pa), 0.6), t0=0.03)
    ao = 1 - occ.reshape(-1, ao_rays).mean(1)
    dirt, rust = dirt_map(c, grid, TP, TN, ao)
    ao = 0.35 + 0.65 * ao
    Lt = Et + Lt_ind * ao[:, None]
    Dv = Dt + Dt_ind * ao[:, None]
    wsum = Et.mean(1) + Lt_ind.mean(1) * ao
    Dv = Dv / np.maximum(wsum, 1e-5)[:, None]
    img = np.zeros((LMH, LMW, 3))
    dimg = np.zeros((LMH, LMW, 3))
    dimg[...] = 0.5
    img[TIJ[:, 1], TIJ[:, 0]] = Lt
    dimg[TIJ[:, 1], TIJ[:, 0]] = np.clip(Dv * 0.5 + 0.5, 0, 1)
    gimg = np.zeros((LMH, LMW, 3))
    gimg[TIJ[:, 1], TIJ[:, 0], 0] = dirt
    gimg[TIJ[:, 1], TIJ[:, 0], 1] = rust
    img = denoise(img, rects)
    dimg = denoise(dimg, rects)
    gimg = denoise(gimg, rects)
    enc = np.sqrt(np.clip(img / LMAX, 0, 1))
    full = np.concatenate([enc, dimg, np.clip(gimg, 0, 1)], 0)
    _log(f"  texels {len(TP)} density {rects[0]['dens']:.1f}/m, total {time.time() - t0:.1f}s")
    stage(t0, "ambient grid")
    amb = ambient_grid(c, grid, F, B, rng, step=getattr(c, "bake_amb_step", 1.0), k=getattr(c, "bake_amb_rays", 128))
    stage(t0, "decor vertex lighting")
    dirr = np.zeros((0, 3))
    if len(DP):
        key = np.round(np.concatenate([DP * 200, DN * 20], 1)).astype(np.int64)
        uq, inv = np.unique(key, axis=0, return_inverse=True)
        first = np.zeros(len(uq), np.int64)
        first[inv[::-1]] = np.arange(len(DP))[::-1]
        UP, UN = DP[first], DN[first]
        off = np.full(len(UP), 0.03)
        if DFL is not None:
            off = np.where(DFL[first] > 4.5, 0.45, 0.03)
        Ed, _ = direct(UP + UN * off[:, None], UN, lights, grid, rng, ns=2)
        Ei = amb_sample(amb, UP + UN * 0.1, UN)
        dirr = (Ed + Ei)[inv.ravel()]
        _log(f"  decor {len(DP) // 3} tris, {len(UP)} lit vertices")
    tlm = None
    rirr = np.zeros((0, 3))
    if TER is not None:
        from . import terrain as T
        field = TER["field"]
        res_ = TER["tlm_step"]
        xs2 = np.arange(field.x0, field.x1 + 1e-6, res_)
        zs2 = np.arange(field.z0, field.z1 + 1e-6, res_)
        X2, Z2 = np.meshgrid(xs2, zs2)
        H2 = field.inner(X2, Z2)
        gx = np.gradient(H2, res_, axis=1)
        gz = np.gradient(H2, res_, axis=0)
        N2 = np.stack([-gx, np.ones_like(H2), -gz], -1)
        N2 /= np.linalg.norm(N2, axis=-1, keepdims=True)
        P2 = np.stack([X2, H2, Z2], -1).reshape(-1, 3)
        stage(t0, f"terrain lightmap {len(xs2)}x{len(zs2)}")
        E2 = T.light_points(P2, N2.reshape(-1, 3), field, grid, getattr(c, "sun", None), getattr(c, "sky_rad", None),
                            lights, direct, rng, k_sky=12)
        img2 = np.sqrt(np.clip(E2.reshape(len(zs2), len(xs2), 3) / LMAX, 0, 1))
        for _ in range(1):
            p_ = np.pad(img2, ((1, 1), (1, 1), (0, 0)), mode="edge")
            img2 = (p_[:-2, 1:-1] + p_[2:, 1:-1] + p_[1:-1, :-2] + p_[1:-1, 2:] + 4 * p_[1:-1, 1:-1]) / 8
        tlm = dict(img=img2, x0=float(xs2[0]), z0=float(zs2[0]), w=float(xs2[-1] - xs2[0]), d=float(zs2[-1] - zs2[0]))
        RP, RN = TER["ring"]
        key = np.round(RP * 10).astype(np.int64)
        uq, inv = np.unique(key, axis=0, return_inverse=True)
        first = np.zeros(len(uq), np.int64)
        first[inv[::-1]] = np.arange(len(RP))[::-1]
        stage(t0, f"far terrain {len(uq)} vertices")
        Er = T.light_points(RP[first], RN[first], field, grid, getattr(c, "sun", None), getattr(c, "sky_rad", None),
                            [], direct, rng, k_sky=10)
        rirr = Er[inv.ravel()]
    return dict(rects=rects, panels=panels, lights=lights, lightmap=full, amb=amb, B=B, dirr=dirr, tlm=tlm, rirr=rirr)


def amb_sample(amb, P, N):
    o = np.array(amb["origin"])
    st = amb["step"]
    cube = amb["cube"]
    dims = np.array(cube.shape[:3])
    f = (P - o) / st
    i0 = np.clip(np.floor(f).astype(int), 0, dims - 2)
    t = np.clip(f - i0, 0, 1)
    acc = np.zeros((len(P), 6, 3))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (t[:, 0] if dx else 1 - t[:, 0]) * (t[:, 1] if dy else 1 - t[:, 1]) * (t[:, 2] if dz else 1 - t[:, 2])
                acc += cube[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz] * w[:, None, None]
    n2 = N * N
    E = np.zeros((len(P), 3))
    for a in range(3):
        pos = acc[:, 2 * a]
        neg = acc[:, 2 * a + 1]
        E += n2[:, a:a + 1] * np.where(N[:, a:a + 1] > 0, pos, neg)
    return E


def vnoise3(P, scale, seed=0):
    rng = np.random.default_rng(seed)
    perm = rng.random(4096)
    q = P * scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3 - 2 * f)

    def h(a, b, c):
        return perm[((a * 73856093) ^ (b * 19349663) ^ (c * 83492791)) & 4095]
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * h(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out


SOURCES = {"pipe", "elbow", "valve", "tray", "vent", "machine", "fan", "duct", "bracket", "cage", "spot", "rack", "jbox",
           "breaker", "tank", "terminal"}


RUST = {"pipe", "elbow", "valve", "bracket", "column", "tank", "jbox", "duct"}
OILY = {"machine", "rack", "tank", "terminal", "trolley", "barrel", "breaker", "crate"}


def streaks(TP, TN, wall, srcs, length, width, gain, seed):
    out = np.zeros(len(TP))
    for S in srcs:
        R = TP - S
        dy = -R[:, 1]
        dn = np.abs(np.einsum("ij,ij->i", R, TN))
        dh = np.sqrt(np.maximum(np.einsum("ij,ij->i", R, R) - dy * dy - dn * dn, 0))
        m = wall & (dy > -0.05) & (dy < 5.0) & (dn < 0.9) & (dh < width * 3)
        if not m.any():
            continue
        hc = TP[m, 0] + TP[m, 2]
        col = vnoise3(np.stack([hc * 9.0, np.zeros(m.sum()), np.zeros(m.sum())], 1), 1.0, seed)
        out[m] += np.exp(-np.maximum(dy[m], 0) / length) * np.exp(-(dh[m] / width) ** 2) * (0.25 + 1.1 * col) * gain
    return out


def dirt_map(c, grid, TP, TN, ao):
    n = len(TP)
    d = (1 - ao) * 0.75
    wall = np.abs(TN[:, 1]) < 0.5
    floor = TN[:, 1] > 0.5
    Pw = TP + TN * 0.25
    h = np.full(n, 3.0)
    for k in range(31):
        q = Pw - np.array([0.0, 0.1 * k, 0.0])
        sol = grid.is_solid(grid.idx(q)) & (h >= 3.0)
        h[sol] = 0.1 * k
    kick = np.exp(-h / 0.22) * (0.5 + 0.5 * vnoise3(TP * np.array([1, 0.2, 1]), 3.0, 3))
    d += np.where(wall, kick * 0.8, 0.0)
    dist_seam = np.ceil(TP[:, 1] - 1e-3) - TP[:, 1]
    hc = TP[:, 0] + TP[:, 2]
    colv = vnoise3(np.stack([hc * 6.0, np.floor(TP[:, 1]), np.zeros(n)], 1), 1.0, 9)
    d += np.where(wall, np.exp(-dist_seam / 0.28) * np.clip(colv * 1.6 - 0.45, 0, 1) * 0.4, 0.0)
    items = getattr(c, "decor", [])
    src = [np.array(it[1], float) for it in items if it[0] in SOURCES]
    d += streaks(TP, TN, wall, src, 1.6, 0.22, 0.9, 11)
    rsrc = [np.array(it[1], float) for it in items if it[0] in RUST]
    for it in items:
        if it[0] == "pipe":
            p = np.array(it[1], float)
            f = np.array(it[2], float)
            for sg in (-1, 1):
                rsrc.append(p + f * sg * it[4][0] * 0.98)
    rust = streaks(TP, TN, wall, rsrc, 0.9, 0.08, 0.8, 13)
    for path in getattr(c, "paths", []):
        pts = [np.array(p, float) for p in path]
        for a_, b_ in zip(pts[:-1], pts[1:]):
            ab = b_ - a_
            t = np.clip(np.einsum("ij,j->i", TP - a_, ab) / max(np.dot(ab, ab), 1e-6), 0, 1)
            dd = np.linalg.norm(TP - (a_ + t[:, None] * ab), axis=1)
            d += np.where(floor, np.exp(-(dd / 0.55) ** 2) * (0.3 + 0.5 * vnoise3(TP, 4.0, 21)) * 0.55, 0.0)
    oil = [np.array(it[1], float) for it in items if it[0] in OILY]
    for S in oil:
        dd = np.linalg.norm((TP - S) * np.array([1, 0, 1]), axis=1)
        bl = vnoise3(TP, 2.3, 17)
        d += np.where(floor & (np.abs(TP[:, 1] - S[1]) < 0.4), np.exp(-(dd / 1.0) ** 2) * np.clip(bl * 1.8 - 0.4, 0, 1)
                      * 0.85, 0.0)
    ceil = TN[:, 1] < -0.5
    d[ceil] *= 0.6
    g = getattr(c, "grime", 1.0)
    return np.clip(d * g, 0, 1), np.clip(rust * g, 0, 1)


def interp(g, uu, vv):
    nv, nu = g.shape[:2]
    pu = uu * nu - 0.5
    pv = vv * nv - 0.5
    i0 = np.clip(np.floor(pu).astype(int), 0, max(0, nu - 2))
    j0 = np.clip(np.floor(pv).astype(int), 0, max(0, nv - 2))
    i1 = np.minimum(i0 + 1, nu - 1)
    j1 = np.minimum(j0 + 1, nv - 1)
    fu = np.clip(pu - i0, 0, 1)[:, None]
    fv = np.clip(pv - j0, 0, 1)[:, None]
    return (g[j0, i0] * (1 - fu) + g[j0, i1] * fu) * (1 - fv) + (g[j1, i0] * (1 - fu) + g[j1, i1] * fu) * fv


FOCUS = None


def rect_w(r):
    if FOCUS is None:
        return 1.0
    fx, fz, rad = FOCUS
    lo = [0.0, 0.0, 0.0]
    hi = [0.0, 0.0, 0.0]
    lo[r["axis"]] = hi[r["axis"]] = r["pl"]
    lo[r["u"]], hi[r["u"]] = r["u0"], r["u1"]
    lo[r["v"]], hi[r["v"]] = r["v0"], r["v1"]
    dx = max(lo[0] - fx, 0, fx - hi[0])
    dz = max(lo[2] - fz, 0, fz - hi[2])
    return 1.0 if (dx * dx + dz * dz) ** 0.5 < rad else 0.3


def alloc(rects):
    for r in rects:
        r["dw"] = rect_w(r)
    total = sum((r["u1"] - r["u0"]) * (r["v1"] - r["v0"]) * r["dw"] ** 2 for r in rects)
    dens = min(12.0, math.sqrt(LMW * LMH * 0.62 / total))
    while True:
        order = sorted(range(len(rects)), key=lambda i: -(rects[i]["v1"] - rects[i]["v0"]))
        x = y = sh = 0
        okp = True
        for i in order:
            r = rects[i]
            tu = max(2, int(math.ceil((r["u1"] - r["u0"]) * dens * r["dw"])))
            tv = max(2, int(math.ceil((r["v1"] - r["v0"]) * dens * r["dw"])))
            w, h = tu + 2 * PAD, tv + 2 * PAD
            if w > LMW:
                okp = False
                break
            if x + w > LMW:
                x = 0
                y += sh
                sh = 0
            if y + h > LMH:
                okp = False
                break
            r["ax"], r["ay"], r["tu"], r["tv"], r["dens"] = x, y, tu, tv, dens
            x += w
            sh = max(sh, h)
        if okp:
            return
        dens *= 0.93


def denoise(img, rects):
    out = img.copy()
    k = np.array([1, 2, 1], float)
    for r in rects:
        x0, y0 = r["ax"], r["ay"]
        w, h = r["tu"] + 2 * PAD, r["tv"] + 2 * PAD
        blk = img[y0:y0 + h, x0:x0 + w].copy()
        for _ in range(2):
            p = np.pad(blk, ((1, 1), (1, 1), (0, 0)), mode="edge")
            blk = (p[:-2, 1:-1] * k[0] + p[1:-1, 1:-1] * k[1] + p[2:, 1:-1] * k[2]) / 4
            p = np.pad(blk, ((1, 1), (1, 1), (0, 0)), mode="edge")
            blk = (p[1:-1, :-2] * k[0] + p[1:-1, 1:-1] * k[1] + p[1:-1, 2:] * k[2]) / 4
        out[y0:y0 + h, x0:x0 + w] = blk
    return out


def ambient_grid(c, grid, F, B, rng, step=1.0, k=128):
    lo = c.origin
    hi = c.origin + np.array(grid.shape) / lvl.RES
    xs = np.arange(lo[0] + 0.5, hi[0], step)
    ys = np.arange(lo[1] + 0.5, hi[1], step)
    zs = np.arange(lo[2] + 0.5, hi[2], step)
    P = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), -1).reshape(-1, 3)
    I = grid.idx(P)
    air = ~grid.is_solid(I)
    Pa = P[air]
    n = len(Pa)
    v = rng.normal(size=(n, k, 3))
    v /= np.linalg.norm(v, axis=2, keepdims=True)
    Pr = np.repeat(Pa, k, 0)
    Dr = v.reshape(-1, 3)
    cell, axis, dist = grid.first_hit(Pr, Dr, t0=0.0)
    ok = axis >= 0
    sg = np.where(Dr[np.arange(len(Dr)), np.clip(axis, 0, 2)] > 0, 1, 0)
    dcode = axis * 2 + sg
    rad = np.zeros((len(Dr), 3))
    for d in range(6):
        m = ok & (dcode == d)
        Ii = cell[m]
        inb = np.all((Ii >= 0) & (Ii < grid.shape), 1)
        sel = np.nonzero(m)[0][inb]
        h = F[d][Ii[inb, 0], Ii[inb, 1], Ii[inb, 2]]
        good = h >= 0
        rad[sel[good]] = B[h[good]]
    if getattr(c, "sky_rad", None) is not None:
        miss = ~ok
        rad[miss] = sky_rad(c, Dr[miss])
    rad = rad.reshape(n, k, 3)
    cube = np.zeros((n, 6, 3))
    axes = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    for a in range(6):
        w = np.clip(np.einsum("nkj,j->nk", v, axes[a]), 0, None)
        cube[:, a] = (rad * w[..., None]).sum(1) / np.maximum(w.sum(1), 1e-6)[:, None]
    full = np.zeros((len(P), 6, 3))
    full[air] = cube
    dims = (len(xs), len(ys), len(zs))
    filled = full.reshape(dims + (6, 3))
    airm = air.reshape(dims)
    for _ in range(3):
        acc = np.zeros_like(filled)
        cnt = np.zeros(dims)
        for ax in range(3):
            for s in (-1, 1):
                acc += np.roll(filled * airm[..., None, None], s, ax)
                cnt += np.roll(airm.astype(float), s, ax)
        fill = (~airm) & (cnt > 0)
        filled[fill] = acc[fill] / cnt[fill][:, None, None]
        airm = airm | fill
    return dict(origin=(xs[0], ys[0], zs[0]), dims=dims, step=step, cube=filled)


def png_bytes(arr):
    im = Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()
