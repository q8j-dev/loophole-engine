from pathlib import Path

import numpy as np
from PIL import Image

from .models import Mat, fit, flat_normals, open_gltf, tangents

CLIPS = {
    "idle": ["idle", "unarmed_idle", "breathing"],
    "walk": ["walking_a", "walk", "walking"],
    "run": ["running_a", "run", "running", "jog"],
    "jump": ["jump_idle", "jump", "fall", "falling"],
    "attack": ["1h_melee_attack_chop", "unarmed_melee_attack_punch_a", "melee_attack", "attack", "punch"],
    "hit": ["hit_a", "hit", "hurt"],
    "death": ["death_c_skeletons", "death_a", "death", "die"],
}
CLIP_ORDER = ("idle", "walk", "run", "jump", "attack", "hit", "death")
FPS = 15
MAXJ = 32
ANIMS = {}
BUILTIN = ("knight", "mage", "rogue", "barbarian", "skeleton", "skeleton_minion")


def anim_path(name):
    return ANIMS.get(name, Path(__file__).resolve().parent / "data" / "anim" / f"{name}.npz")


def quat_mat(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def slerp(a, b, t):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        r = a + (b - a) * t
    else:
        th = np.arccos(min(d, 1.0))
        r = (np.sin((1 - t) * th) * a + np.sin(t * th) * b) / np.sin(th)
    return r / np.linalg.norm(r)


def trs(t, r, s):
    M = np.eye(4)
    M[:3, :3] = quat_mat(r) * np.asarray(s)[None, :]
    M[:3, 3] = t
    return M


def pick_clip(names, want):
    low = {n.lower(): n for n in names}
    for w in CLIPS[want]:
        if w in low:
            return low[w]
    for w in CLIPS[want]:
        for k, n in low.items():
            if w in k:
                return n
    return None


def sample(acc, ch, t):
    times = acc(ch["input"]).ravel()
    vals = acc(ch["output"])
    interp = ch.get("interpolation", "LINEAR")
    if interp == "CUBICSPLINE":
        vals = vals.reshape(len(times), 3, -1)[:, 1]
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    i = int(np.searchsorted(times, t)) - 1
    if interp == "STEP":
        return vals[i]
    f = (t - times[i]) / max(times[i + 1] - times[i], 1e-9)
    if vals.shape[1] == 4:
        return slerp(vals[i], vals[i + 1], f)
    return vals[i] + (vals[i + 1] - vals[i]) * f


def convert(path, out_dir, name, height=1.8, keep=None, size=512, facing="+z", attach=()):
    g = open_gltf(path)
    js, acc, mats = g["js"], g["accessor"], list(g["mats"])
    nodes = js["nodes"]
    parent = {}
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []):
            parent[c] = i
    rest = [(np.array(nd.get("translation", [0, 0, 0]), float), np.array(nd.get("rotation", [0, 0, 0, 1]), float),
             np.array(nd.get("scale", [1, 1, 1]), float)) for nd in nodes]

    def globals_for(local):
        G = [None] * len(nodes)

        def get(i):
            if G[i] is None:
                if "matrix" in nodes[i]:
                    M = np.array(nodes[i]["matrix"], float).reshape(4, 4).T
                else:
                    M = trs(*local[i])
                G[i] = (get(parent[i]) @ M) if i in parent else M
            return G[i]
        for i in range(len(nodes)):
            get(i)
        return G

    skins = js.get("skins", [])
    if not skins:
        raise SystemExit(f"{Path(path).name}: no skin found. Characters need a rigged glTF/GLB with a skeleton.")
    skin = skins[0]
    joints = skin["joints"]
    ibm = acc(skin["inverseBindMatrices"]).reshape(-1, 4, 4).transpose(0, 2, 1) if "inverseBindMatrices" in skin \
        else np.repeat(np.eye(4)[None], len(joints), 0)
    jset = set(joints)
    anims = {a.get("name", f"anim{i}"): a for i, a in enumerate(js.get("animations", []))}
    chosen = {k: pick_clip(list(anims), k) for k in CLIPS}
    if not chosen["idle"] and not chosen["walk"]:
        raise SystemExit(f"{Path(path).name}: needs at least an idle or walk animation (found: {', '.join(anims) or 'none'})")
    base_clip = chosen["idle"] or chosen["walk"]

    def pose_local(aname, t):
        local = [tuple(x.copy() for x in r) for r in rest]
        a = anims[aname]
        for ch in a["channels"]:
            tgt = ch["target"]
            ni = tgt.get("node")
            if ni is None:
                continue
            v = sample(acc, a["samplers"][ch["sampler"]], t)
            tt, rr, ss = local[ni]
            if tgt["path"] == "translation":
                tt = v
            elif tgt["path"] == "rotation":
                rr = v / np.linalg.norm(v)
            elif tgt["path"] == "scale":
                ss = v
            local[ni] = (tt, rr, ss)
        return local

    G0 = globals_for(pose_local(base_clip, 0.0))
    Gr = globals_for(rest)

    def joint_anc(ni):
        while ni is not None:
            if ni in jset:
                return ni
            ni = parent.get(ni)
        return None

    P_all, N_all, UV_all, B_all, M_all = [], [], [], [], []
    for ni, nd in enumerate(nodes):
        if "mesh" not in nd:
            continue
        nm = nd.get("name", "")
        skinned = "skin" in nd
        if keep is not None:
            if not skinned and nm not in keep:
                continue
        elif not skinned and joint_anc(parent.get(ni)) is not None:
            pj = nodes[parent[ni]].get("name", "").lower()
            if "hand" in pj or "slot" in pj:
                continue
        for prim in js["meshes"][nd["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue
            at = prim["attributes"]
            P = acc(at["POSITION"])
            N = acc(at["NORMAL"]) if "NORMAL" in at else None
            UV = acc(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(P), 2))
            idx = acc(prim["indices"]).astype(np.int64).ravel() if "indices" in prim else np.arange(len(P))
            if skinned and "JOINTS_0" in at:
                J = acc(at["JOINTS_0"]).astype(int)
                W = acc(at["WEIGHTS_0"])
                jb = J[np.arange(len(J)), np.argmax(W, 1)]
                nodes_j = np.array([joints[j] for j in jb])
                Pw = np.zeros((len(P), 3))
                Nw = np.zeros((len(P), 3))
                for j in np.unique(jb):
                    sel = jb == j
                    S = G0[joints[j]] @ ibm[j]
                    Pw[sel] = (np.c_[P[sel], np.ones(sel.sum())] @ S.T)[:, :3]
                    if N is not None:
                        Nw[sel] = N[sel] @ np.linalg.inv(S[:3, :3])
                bones = nodes_j
            else:
                ja = joint_anc(ni)
                M = G0[ni]
                Pw = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
                Nw = N @ np.linalg.inv(M[:3, :3]) if N is not None else None
                bones = np.full(len(P), ja if ja is not None else -1)
            if N is not None:
                Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-9)
            P_all.append(Pw[idx])
            N_all.append(Nw[idx] if N is not None else flat_normals(Pw[idx]))
            UV_all.append(UV[idx])
            B_all.append(bones[idx])
            M_all.append(np.full(len(idx), prim.get("material", -1)))
    if not P_all:
        raise SystemExit(f"{Path(path).name}: no visible meshes")
    body = np.concatenate(P_all)
    names = [nd.get("name", "") for nd in nodes]
    for apath, slot in attach:
        if slot not in names:
            raise SystemExit(f"{Path(path).name}: no node called '{slot}' to attach {Path(apath).name} to")
        si = names.index(slot)
        ja = joint_anc(si)
        ag = open_gltf(apath)
        aj, aacc = ag["js"], ag["accessor"]
        moff = len(mats)
        mats.extend(ag["mats"])
        for nd in aj["nodes"]:
            if "mesh" not in nd:
                continue
            for prim in aj["meshes"][nd["mesh"]]["primitives"]:
                at = prim["attributes"]
                Pa = aacc(at["POSITION"])
                Na = aacc(at["NORMAL"]) if "NORMAL" in at else None
                UVa = aacc(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(Pa), 2))
                ia = aacc(prim["indices"]).astype(np.int64).ravel() if "indices" in prim else np.arange(len(Pa))
                M = G0[si]
                Pw = (np.c_[Pa, np.ones(len(Pa))] @ M.T)[:, :3]
                Nw = (Na @ np.linalg.inv(M[:3, :3])) if Na is not None else None
                if Nw is not None:
                    Nw = Nw / np.maximum(np.linalg.norm(Nw, axis=1, keepdims=True), 1e-9)
                P_all.append(Pw[ia])
                N_all.append(Nw[ia] if Nw is not None else flat_normals(Pw[ia]))
                UV_all.append(UVa[ia])
                B_all.append(np.full(len(ia), ja if ja is not None else -1))
                M_all.append(np.full(len(ia), moff + prim.get("material", 0)))
    P = np.concatenate(P_all)
    N = np.concatenate(N_all)
    UV = np.concatenate(UV_all)
    B = np.concatenate(B_all)
    MI = np.concatenate(M_all)

    lo, hi = body.min(0), body.max(0)
    s = height / max(hi[1] - lo[1], 1e-6)
    T = np.eye(4)
    T[:3, :3] *= s
    if facing == "+z":
        T[:3, :3] = np.diag([-s, s, -s])
    T[:3, 3] = -(T[:3, :3] @ np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]))
    Ti = np.linalg.inv(T)
    P = (np.c_[P, np.ones(len(P))] @ T.T)[:, :3]
    N = N @ np.linalg.inv(T[:3, :3])
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)

    used = sorted(set(int(b) for b in B))
    if len(used) > MAXJ:
        raise SystemExit(f"{Path(path).name}: uses {len(used)} bones, the limit is {MAXJ}")
    remap = {b: i for i, b in enumerate(used)}
    bone = np.array([remap[int(b)] for b in B], np.float32)

    clips = {}
    frames = []
    for k in CLIP_ORDER:
        an = chosen[k] or base_clip
        a = anims[an]
        dur = max(float(acc(smp["input"]).max()) for smp in a["samplers"])
        n = max(2, int(round(dur * FPS)))
        clips[k] = (len(frames), n)
        for f in range(n):
            Gt = globals_for(pose_local(an, f / FPS))
            row = []
            for b in used:
                S = np.eye(4) if b < 0 else Gt[b] @ np.linalg.inv(G0[b])
                S = T @ S @ Ti
                row.append(S[:3, :4])
            frames.append(np.array(row))
    frames = np.array(frames, np.float32)

    mats_used = sorted(set(int(m) for m in MI))
    gsz = int(np.ceil(np.sqrt(len(mats_used))))
    cell = size // gsz
    al = np.zeros((size, size, 3), np.float32)
    nm_ = np.zeros((size, size, 3), np.float32)
    nm_[..., :2] = 0.5
    nm_[..., 2] = 1.0
    rm = np.zeros((size, size, 3), np.float32)
    UVo = np.zeros_like(UV)
    for k, mi in enumerate(mats_used):
        m = mats[mi] if mi >= 0 else Mat("default")
        x, y = (k % gsz) * cell, (k // gsz) * cell
        pad = max(2, cell // 64)
        inner = cell - 2 * pad
        base = fit(m.base, inner)
        col = np.array([v ** (1 / 2.2) for v in m.color], np.float32)
        base = np.ones((inner, inner, 3), np.float32) * col if base is None else base * col
        r = np.stack([np.full((inner, inner), max(m.rough, 0.55)), np.full((inner, inner), m.metal),
                      np.zeros((inner, inner))], -1)
        al[y:y + cell, x:x + cell] = np.pad(base, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        rm[y:y + cell, x:x + cell] = np.pad(r, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        sel = MI == mi
        uv = UV[sel] - np.floor(UV[sel].reshape(-1, 3, 2).min(1)).repeat(3, 0)
        uv = np.clip(uv, 0, 1)
        UVo[sel] = np.stack([(x + pad + uv[:, 0] * inner) / size, (y + pad + uv[:, 1] * inner) / size], 1)
    Tn = tangents(P, N, UVo)
    out_dir = Path(out_dir)
    (out_dir / "kit").mkdir(parents=True, exist_ok=True)
    (out_dir / "tiles").mkdir(parents=True, exist_ok=True)
    (out_dir / "anim").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "kit" / f"kit_{name}.npz", pos=P.astype(np.float32), nrm=N.astype(np.float32),
                        uv=UVo.astype(np.float32), tan=Tn.astype(np.float32), bone=bone)
    np.savez_compressed(out_dir / "anim" / f"{name}.npz", frames=frames,
                        clips=np.array([clips[k] for k in CLIP_ORDER], np.int32),
                        fps=np.array([FPS], np.float32))
    from .decor_pack import jpg
    (out_dir / "tiles" / f"{name}_a.jpg").write_bytes(jpg(np.sqrt(np.clip(al, 0, 1) ** 2.2), 92))
    (out_dir / "tiles" / f"{name}_n.jpg").write_bytes(jpg(nm_, 94))
    h = size // 2
    (out_dir / "tiles" / f"{name}_r.jpg").write_bytes(jpg(rm.reshape(h, 2, h, 2, 3).mean((1, 3)), 92))
    return len(P) // 3, len(used), {k: chosen[k] for k in CLIPS}
