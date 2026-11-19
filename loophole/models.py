import base64
import hashlib
import io
import json
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image

CTYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class Part:
    def __init__(self):
        self.P = []
        self.N = []
        self.UV = []
        self.mat = None


class Mat:
    def __init__(self, name):
        self.name = name
        self.color = (0.8, 0.8, 0.8)
        self.base = None
        self.normal = None
        self.mr = None
        self.rough = 0.6
        self.metal = 0.0


def load_gltf(path):
    path = Path(path)
    data = path.read_bytes()
    bins = []
    if data[:4] == b"glTF":
        off = 12
        js = None
        while off < len(data):
            ln, typ = struct.unpack_from("<II", data, off)
            chunk = data[off + 8:off + 8 + ln]
            if typ == 0x4E4F534A:
                js = json.loads(chunk)
            elif typ == 0x004E4942:
                bins.append(chunk)
            off += 8 + ln
    else:
        js = json.loads(data)
    buffers = []
    for i, b in enumerate(js.get("buffers", [])):
        uri = b.get("uri")
        if uri is None:
            buffers.append(bins[0] if bins else b"")
        elif uri.startswith("data:"):
            buffers.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            buffers.append((path.parent / uri).read_bytes())

    def view_bytes(vi):
        v = js["bufferViews"][vi]
        b = buffers[v["buffer"]]
        o = v.get("byteOffset", 0)
        return b[o:o + v["byteLength"]], v.get("byteStride")

    def accessor(ai):
        a = js["accessors"][ai]
        raw, stride = view_bytes(a["bufferView"])
        dt = np.dtype(CTYPES[a["componentType"]])
        nc = NCOMP[a["type"]]
        off = a.get("byteOffset", 0)
        cnt = a["count"]
        if stride and stride != dt.itemsize * nc:
            arr = np.zeros((cnt, nc), dt)
            for i in range(cnt):
                arr[i] = np.frombuffer(raw, dt, nc, off + i * stride)
        else:
            arr = np.frombuffer(raw, dt, cnt * nc, off).reshape(cnt, nc)
        arr = arr.astype(np.float64)
        if a.get("normalized"):
            arr /= float(np.iinfo(dt).max)
        return arr

    def image(ti):
        if ti is None:
            return None
        tex = js["textures"][ti["index"]]
        src = tex.get("source")
        if src is None:
            for ext in tex.get("extensions", {}).values():
                src = ext.get("source", src)
        im = js["images"][src]
        if "bufferView" in im:
            raw, _ = view_bytes(im["bufferView"])
            return Image.open(io.BytesIO(raw))
        uri = im["uri"]
        if uri.startswith("data:"):
            return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
        return Image.open(path.parent / uri)

    mats = []
    for i, m in enumerate(js.get("materials", [])):
        mt = Mat(m.get("name", f"m{i}"))
        pbr = m.get("pbrMetallicRoughness", {})
        mt.color = tuple(pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1])[:3])
        mt.base = image(pbr.get("baseColorTexture"))
        mt.mr = image(pbr.get("metallicRoughnessTexture"))
        mt.normal = image(m.get("normalTexture"))
        mt.rough = pbr.get("roughnessFactor", 0.6)
        mt.metal = pbr.get("metallicFactor", 0.0)
        mats.append(mt)
    default = Mat("default")
    parts = []

    def mat4(node):
        if "matrix" in node:
            return np.array(node["matrix"], float).reshape(4, 4).T
        t = np.array(node.get("translation", [0, 0, 0]), float)
        r = node.get("rotation", [0, 0, 0, 1])
        s = np.array(node.get("scale", [1, 1, 1]), float)
        x, y, z, w = r
        R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        M = np.eye(4)
        M[:3, :3] = R * s[None, :]
        M[:3, 3] = t
        return M

    def walk(ni, parent):
        node = js["nodes"][ni]
        M = parent @ mat4(node)
        if "mesh" in node:
            for prim in js["meshes"][node["mesh"]]["primitives"]:
                if prim.get("mode", 4) != 4:
                    continue
                at = prim["attributes"]
                P = accessor(at["POSITION"])
                N = accessor(at["NORMAL"]) if "NORMAL" in at else None
                UV = accessor(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(P), 2))
                idx = accessor(prim["indices"]).astype(np.int64).ravel() if "indices" in prim else np.arange(len(P))
                Pw = (np.c_[P, np.ones(len(P))] @ M.T)[:, :3]
                pt = Part()
                pt.P = Pw[idx]
                if N is not None:
                    Nm = N @ np.linalg.inv(M[:3, :3])
                    Nm /= np.maximum(np.linalg.norm(Nm, axis=1, keepdims=True), 1e-9)
                    pt.N = Nm[idx]
                else:
                    pt.N = None
                pt.UV = UV[idx]
                pt.mat = mats[prim["material"]] if "material" in prim else default
                parts.append(pt)
        for c in node.get("children", []):
            walk(c, M)

    scene = js.get("scenes", [{"nodes": list(range(len(js.get("nodes", []))))}])[js.get("scene", 0)]
    for ni in scene.get("nodes", []):
        walk(ni, np.eye(4))
    return parts


def load_obj(path):
    path = Path(path)
    V, VT, VN = [], [], []
    mats = {}
    cur = None
    parts = {}
    for line in path.read_text(errors="ignore").splitlines():
        t = line.strip().split()
        if not t:
            continue
        if t[0] == "v":
            V.append([float(x) for x in t[1:4]])
        elif t[0] == "vt":
            VT.append([float(t[1]), float(t[2]) if len(t) > 2 else 0.0])
        elif t[0] == "vn":
            VN.append([float(x) for x in t[1:4]])
        elif t[0] == "mtllib":
            mats.update(load_mtl(path.parent / " ".join(t[1:])))
        elif t[0] == "usemtl":
            cur = " ".join(t[1:])
        elif t[0] == "f":
            idx = []
            for f in t[1:]:
                s = (f.split("/") + ["", ""])[:3]
                idx.append(tuple(int(x) if x else 0 for x in s))
            pt = parts.setdefault(cur, ([], [], []))
            for k in range(1, len(idx) - 1):
                for (vi, ti, ni) in (idx[0], idx[k], idx[k + 1]):
                    pt[0].append(V[vi - 1 if vi > 0 else vi])
                    pt[1].append(VT[ti - 1 if ti > 0 else ti] if ti else [0.0, 0.0])
                    pt[2].append(VN[ni - 1 if ni > 0 else ni] if ni else None)
    out = []
    for name, (P, UV, N) in parts.items():
        p = Part()
        p.P = np.array(P, float)
        p.UV = np.array(UV, float)
        p.UV[:, 1] = 1 - p.UV[:, 1]
        p.N = None if any(n is None for n in N) else np.array(N, float)
        p.mat = mats.get(name, Mat(name or "default"))
        out.append(p)
    return out


def load_mtl(path):
    mats = {}
    cur = None
    if not path.exists():
        return mats
    for line in path.read_text(errors="ignore").splitlines():
        t = line.strip().split()
        if not t:
            continue
        if t[0] == "newmtl":
            cur = Mat(" ".join(t[1:]))
            mats[cur.name] = cur
        elif cur is None:
            continue
        elif t[0] == "Kd":
            cur.color = tuple(float(x) for x in t[1:4])
        elif t[0] == "map_Kd":
            f = path.parent / t[-1]
            if f.exists():
                cur.base = Image.open(f)
        elif t[0] in ("map_Bump", "bump", "norm"):
            f = path.parent / t[-1]
            if f.exists():
                cur.normal = Image.open(f)
        elif t[0] == "Ns":
            cur.rough = float(np.clip(1 - math.sqrt(float(t[1]) / 1000.0), 0.05, 1.0))
    return mats


def flat_normals(P):
    N = np.zeros_like(P)
    for i in range(0, len(P), 3):
        n = np.cross(P[i + 1] - P[i], P[i + 2] - P[i])
        N[i:i + 3] = n / max(np.linalg.norm(n), 1e-12)
    return N


def tangents(P, N, UV):
    T = np.zeros((len(P), 4))
    for i in range(0, len(P), 3):
        e1, e2 = P[i + 1] - P[i], P[i + 2] - P[i]
        d1, d2 = UV[i + 1] - UV[i], UV[i + 2] - UV[i]
        den = d1[0] * d2[1] - d2[0] * d1[1]
        tg = (e1 * d2[1] - e2 * d1[1]) / den if abs(den) > 1e-12 else np.array([1.0, 0, 0])
        bt = (e2 * d1[0] - e1 * d2[0]) / den if abs(den) > 1e-12 else np.array([0, 1.0, 0])
        for k in range(3):
            n = N[i + k]
            t = tg - n * np.dot(tg, n)
            t /= max(np.linalg.norm(t), 1e-9)
            T[i + k, :3] = t
            T[i + k, 3] = 1.0 if np.dot(np.cross(n, t), bt) >= 0 else -1.0
    return T


def fit(im, s, mode="RGB"):
    if im is None:
        return None
    return np.asarray(im.convert(mode).resize((s, s), Image.LANCZOS), np.float32) / 255.0


def convert(path, out_dir, name, scale=1.0, size=1024, up_axis="y"):
    path = Path(path)
    parts = load_gltf(path) if path.suffix.lower() in (".glb", ".gltf") else load_obj(path)
    if not parts:
        raise SystemExit(f"{path.name}: no triangles found")
    if up_axis == "z":
        for p in parts:
            p.P = p.P[:, [0, 2, 1]] * np.array([1, 1, -1])
            if p.N is not None:
                p.N = p.N[:, [0, 2, 1]] * np.array([1, 1, -1])
    mats = list(dict.fromkeys(p.mat for p in parts))
    g = int(math.ceil(math.sqrt(len(mats))))
    cell = size // g
    al = np.zeros((size, size, 3), np.float32)
    nm = np.zeros((size, size, 3), np.float32)
    nm[..., :2] = 0.5
    nm[..., 2] = 1.0
    rm = np.zeros((size, size, 3), np.float32)
    rects = {}
    for k, m in enumerate(mats):
        x, y = (k % g) * cell, (k // g) * cell
        pad = max(2, cell // 64)
        inner = cell - 2 * pad
        base = fit(m.base, inner)
        if base is None:
            base = np.ones((inner, inner, 3), np.float32) * np.array([v ** (1 / 2.2) for v in m.color], np.float32)
        else:
            base = base * np.array([v ** (1 / 2.2) for v in m.color], np.float32)
        lin = base ** 2.2
        a = np.sqrt(lin)
        n = fit(m.normal, inner)
        r = np.stack([np.full((inner, inner), m.rough), np.full((inner, inner), m.metal), np.zeros((inner, inner))], -1)
        mr = fit(m.mr, inner)
        if mr is not None:
            r[..., 0] = np.clip(mr[..., 1] * m.rough, 0, 1)
            r[..., 1] = np.clip(mr[..., 2] * m.metal, 0, 1)
        for arr, img in ((al, a), (nm, n), (rm, r)):
            if img is None:
                continue
            p = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
            arr[y:y + cell, x:x + cell] = p
        rects[m] = ((x + pad) / size, (y + pad) / size, inner / size)
    P_all, N_all, UV_all = [], [], []
    for p in parts:
        P = p.P
        N = p.N if p.N is not None else flat_normals(P)
        x0, y0, s = rects[p.mat]
        uv = p.UV - np.floor(p.UV.reshape(-1, 3, 2).min(1)).repeat(3, 0)
        uv = np.clip(uv, 0, 1)
        P_all.append(P)
        N_all.append(N)
        UV_all.append(np.stack([x0 + uv[:, 0] * s, y0 + uv[:, 1] * s], 1))
    P = np.concatenate(P_all)
    N = np.concatenate(N_all)
    UV = np.concatenate(UV_all)
    lo, hi = P.min(0), P.max(0)
    P = (P - np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])) * scale
    T = tangents(P, N, UV)
    out_dir = Path(out_dir)
    (out_dir / "kit").mkdir(parents=True, exist_ok=True)
    (out_dir / "tiles").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "kit" / f"kit_{name}.npz", pos=P.astype(np.float32), nrm=N.astype(np.float32),
                        uv=UV.astype(np.float32), tan=T.astype(np.float32))
    from .decor_pack import jpg
    (out_dir / "tiles" / f"{name}_a.jpg").write_bytes(jpg(al, 92))
    (out_dir / "tiles" / f"{name}_n.jpg").write_bytes(jpg(nm, 94))
    h = size // 2
    (out_dir / "tiles" / f"{name}_r.jpg").write_bytes(jpg(rm.reshape(h, 2, h, 2, 3).mean((1, 3)), 92))
    return len(P) // 3


def import_models(game, project_dir, log=print):
    from . import decor_pack, decor_place
    out = Path(project_dir) / ".loophole" / "models"
    for name, spec in game.models.items():
        src = (Path(project_dir) / spec["path"]).resolve()
        if not src.exists():
            raise SystemExit(f"model '{name}': file not found: {spec['path']}")
        key = hashlib.md5(src.read_bytes() + repr(sorted(spec.items())).encode()).hexdigest()[:12]
        stamp = out / f"{name}.key"
        if not (stamp.exists() and stamp.read_text() == key and (out / "kit" / f"kit_{name}.npz").exists()):
            n = convert(src, out, name, scale=spec.get("scale", 1.0), size=spec.get("texture", 1024),
                        up_axis=spec.get("up", "y"))
            stamp.write_text(key)
            log(f"  model {name}: {n} triangles from {src.name}")
        decor_place.EXTRA[name] = out / "kit" / f"kit_{name}.npz"
        decor_pack.EXTRA_TILES[name] = out / "tiles"
    decor_place.refresh()
