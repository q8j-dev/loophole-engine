from pathlib import Path

import numpy as np

from .character import trs, write_kit
from .models import flat_normals, open_gltf

WHEELS = ("front-left", "front-right", "back-left", "back-right")
SPECS = {}
BUILTIN = ("kart", "kart_pink", "kart_yellow", "kart_green", "kart_tan", "racecar", "police", "taxi", "suv")


def spec_path(name):
    return SPECS.get(name, Path(__file__).resolve().parent / "data" / "vehicle" / f"{name}.npz")


def wheel_slot(name):
    n = name.lower().replace("_", "-").replace(" ", "-")
    if "wheel" not in n and "tire" not in n and "tyre" not in n:
        return 0
    front = "front" in n or n.endswith("-f") or "-fl" in n or "-fr" in n
    left = "left" in n or "-fl" in n or "-bl" in n or "-rl" in n
    return 1 + (0 if front else 2) + (0 if left else 1)


def convert(path, out_dir, name, length=1.6, size=256, facing="+z"):
    g = open_gltf(path)
    js, acc, mats = g["js"], g["accessor"], list(g["mats"])
    nodes = js["nodes"]
    parent = {}
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []):
            parent[c] = i
    G = [None] * len(nodes)

    def glob(i):
        if G[i] is None:
            nd = nodes[i]
            if "matrix" in nd:
                M = np.array(nd["matrix"], float).reshape(4, 4).T
            else:
                M = trs(np.array(nd.get("translation", [0, 0, 0]), float), np.array(nd.get("rotation", [0, 0, 0, 1]), float),
                        np.array(nd.get("scale", [1, 1, 1]), float))
            G[i] = glob(parent[i]) @ M if i in parent else M
        return G[i]

    P_all, N_all, UV_all, B_all, M_all = [], [], [], [], []
    piv = np.zeros((5, 3))
    seen = [False] * 5
    for ni, nd in enumerate(nodes):
        if "mesh" not in nd:
            continue
        slot = wheel_slot(nd.get("name", ""))
        if slot and seen[slot]:
            slot = 0
        M = glob(ni)
        for prim in js["meshes"][nd["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue
            at = prim["attributes"]
            P = acc(at["POSITION"])
            N = acc(at["NORMAL"]) if "NORMAL" in at else None
            UV = acc(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(P), 2))
            idx = acc(prim["indices"]).astype(np.int64).ravel() if "indices" in prim else np.arange(len(P))
            Pw = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
            Nw = None
            if N is not None:
                Nw = N @ np.linalg.inv(M[:3, :3])
                Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-9)
            P_all.append(Pw[idx])
            N_all.append(Nw[idx] if Nw is not None else flat_normals(Pw[idx]))
            UV_all.append(UV[idx])
            B_all.append(np.full(len(idx), slot))
            M_all.append(np.full(len(idx), prim.get("material", -1)))
        if slot:
            seen[slot] = True
            piv[slot] = M[:3, 3]
    if not P_all:
        raise SystemExit(f"{Path(path).name}: no meshes")
    P = np.concatenate(P_all)
    N = np.concatenate(N_all)
    UV = np.concatenate(UV_all)
    B = np.concatenate(B_all)
    MI = np.concatenate(M_all)
    for s in range(1, 5):
        if seen[s]:
            sel = B == s
            piv[s] = (P[sel].min(0) + P[sel].max(0)) / 2

    lo, hi = P.min(0), P.max(0)
    s = length / max(hi[2] - lo[2], 1e-6)
    T = np.diag([s, s, s, 1.0])
    if facing == "+z":
        T[:3, :3] = np.diag([-s, s, -s])
    T[:3, 3] = -(T[:3, :3] @ np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]))
    P = (np.c_[P, np.ones(len(P))] @ T.T)[:, :3]
    N = N @ np.linalg.inv(T[:3, :3])
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    piv = (np.c_[piv, np.ones(5)] @ T.T)[:, :3]
    rad = np.zeros(5)
    for k in range(1, 5):
        if seen[k]:
            rad[k] = (P[B == k][:, 1].max() - P[B == k][:, 1].min()) / 2
        else:
            piv[k] = [(-1 if k in (1, 3) else 1) * 0.35 * length, 0.15 * length, (-0.3 if k <= 2 else 0.3) * length]
    piv[0] = [0, P[:, 1].max() * 0.4, 0]
    out_dir = write_kit(out_dir, name, P, N, UV, MI, mats, B.astype(np.float32), size)
    (out_dir / "vehicle").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "vehicle" / f"{name}.npz", pivots=piv.astype(np.float32), radius=rad.astype(np.float32),
                        size=(P.max(0) - P.min(0)).astype(np.float32), wheels=np.array(seen[1:], np.int32))
    return len(P) // 3, int(sum(seen[1:]))
