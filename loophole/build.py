import ast
import hashlib
import io
import json
import math
import runpy
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

from . import bake, decor_place, geo, kit, procprops, props, sbc, shaders
from . import level as lvl
from .materials import KILL, MATID, PORTAL, TABLE
from .world import Game, color

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ENGINE_VERSION = "0.1.0"
VERBOSE = False
BAKE_VERSION = 3
PENP_URL = "https://extensions.turbowarp.org/obviousAlexC/penPlus.js"
PLOCK_URL = "https://extensions.turbowarp.org/pointerlock.js"
STAGE_W, STAGE_H = 640, 360

API_VARS = {
    "api_px": "player x", "api_py": "player y", "api_pz": "player z", "api_yaw": "player yaw",
    "api_pitch": "player pitch", "api_speed": "player speed", "api_ground": "player on ground", "api_level": "level",
    "api_lname": "level name", "api_time": "level time", "api_fps": "fps", "api_look": "looking at",
    "api_lookd": "looking distance", "api_hold": "holding", "api_used": "used object", "api_goto": "go to level",
    "api_ctl": "controls", "api_cam": "camera mode", "api_cx": "camera x", "api_cy": "camera y", "api_cz": "camera z",
    "api_cyaw": "camera yaw", "api_cpitch": "camera pitch", "api_cdist": "camera distance",
    "api_fov": "field of view", "api_expo": "exposure", "api_fade": "fade", "api_flash": "flash",
    "api_walk": "walk speed", "api_jump": "jump power", "api_grav": "gravity", "api_paused": "paused",
    "api_locked": "mouse locked", "api_vm": "viewmodel",
}
API_LISTS = {
    "obj_name": "obj name", "obj_x": "obj x", "obj_y": "obj y", "obj_z": "obj z", "obj_yaw": "obj yaw",
    "obj_pitch": "obj pitch", "obj_roll": "obj roll", "obj_scale": "obj scale", "obj_visible": "obj visible",
    "obj_solid": "obj solid", "obj_glow": "obj glow", "obj_open": "obj open", "obj_touch": "obj touching",
    "snd_q": "sound queue", "light_name": "light name", "light_power": "light power", "trig_name": "trigger name",
    "trig_in": "trigger inside",
}
ALIASES = {**API_VARS, **API_LISTS}
FIXED_BROADCASTS = ["level start", "player died", "paused", "resumed", "game complete"]

SH = ("shader", "menu", "penPlusShaders")
UN = ("uniformName", "text", None)
sbc.EXT_STMTS.update({
    "create_rt": ("penP_createRenderTextureOfSize", [("name", "text", None), ("width", "num", None),
                                                     ("height", "num", None)]),
    "target_rt": ("penP_targetRenderTexture", [("name", "menu", "renderTextures")]),
    "clear_rt": ("penP_clearRenderTexture", [("name", "menu", "renderTexturesOnly")]),
    "set_arr4": ("penP_setArrayVec4InShader", [("item", "num", None), UN, SH, ("numberX", "num", None),
                                               ("numberY", "num", None), ("numberZ", "num", None),
                                               ("numberW", "num", None)]),
    "cull": ("penP_setCullMode", [("direction", "menu", "cullMode")]),
})


def hid(prefix, name):
    return prefix + hashlib.md5(name.encode()).hexdigest()[:16]


class Project(sbc.Project):
    def var_id(self, name):
        return self.variables.setdefault(name, hid("lhv", name))

    def list_id(self, name):
        return self.lists.setdefault(name, hid("lhl", name))

    def bc_id(self, name):
        return self.broadcasts.setdefault(name, hid("lhb", name.lower()))


class Compiler(sbc.SpriteCompiler):
    def _call_stmt(self, call, parent):
        f = call.func
        if isinstance(f, ast.Name) and f.id == "set_lock":
            bid = self._new("pointerlock_setLocked", parent)
            mid = self._new("pointerlock_menu_enabled", bid, fields={"enabled": [call.args[0].value, None]},
                            shadow=True)
            self.blocks[bid]["inputs"]["enabled"] = [1, mid]
            return bid, bid
        if isinstance(f, ast.Name) and f.id in ("play", "play_wait") and not isinstance(call.args[0], ast.Constant):
            op = "sound_play" if f.id == "play" else "sound_playuntildone"
            bid = self._new(op, parent)
            mid = self._menu("sound_sounds_menu", "SOUND_MENU", "click", bid)
            rid = self._expr(call.args[0], bid)
            self.blocks[bid]["inputs"]["SOUND_MENU"] = [3, rid, mid]
            return bid, bid
        if isinstance(f, ast.Name) and f.id in ("broadcast", "broadcast_wait") and not isinstance(call.args[0],
                                                                                                 ast.Constant):
            op = "event_broadcast" if f.id == "broadcast" else "event_broadcastandwait"
            bid = self._new(op, parent)
            rid = self._expr(call.args[0], bid)
            self.blocks[bid]["inputs"]["BROADCAST_INPUT"] = [3, rid, [11, "level start", self.p.bc_id("level start")]]
            return bid, bid
        return super()._call_stmt(call, parent)

    def _expr(self, node, parent):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "plocked":
                return self._new("pointerlock_isLocked", parent)
            if node.func.id == "mbtn":
                bid = self._new("tw_getButtonIsDown", parent)
                mid = self._new("tw_menu_mouseButton", bid, fields={"mouseButton": [str(node.args[0].value), None]},
                                shadow=True)
                self.blocks[bid]["inputs"]["MOUSE_BUTTON"] = [1, mid]
                return bid
            if node.func.id == "index_of":
                lname = node.args[0].id
                bid = self._new("data_itemnumoflist", parent, fields={"LIST": self.lref(lname)})
                self.blocks[bid]["inputs"]["ITEM"] = self._input(node.args[1], bid, "text")
                return bid
        return super()._expr(node, parent)


def expand_mklist(src):
    import re

    def rep(m):
        ind, lst, cap = m.group(1), m.group(2), m.group(3)
        return f"{ind}{lst}.clear()\n{ind}for i in times({cap}):\n{ind}    {lst}.append(0)"
    src = re.sub(r"^( *)mklist\((\w+), (.+)\)$", rep, src, flags=re.M)
    return src.replace("@warp\ndef mklist(L, n):\n    pass\n", "")


class Assets:
    def __init__(self):
        self.files = {}

    def add(self, data, ext):
        md5 = hashlib.md5(data).hexdigest()
        fn = f"{md5}.{ext}"
        self.files[fn] = data
        return md5, fn

    def svg(self, name, svg, cx, cy):
        md5, fn = self.add(svg.encode(), "svg")
        return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": fn,
                "rotationCenterX": cx, "rotationCenterY": cy}

    def bitmap(self, name, data, ext, w, h):
        md5, fn = self.add(data, ext)
        return {"name": name, "bitmapResolution": 2, "dataFormat": ext, "assetId": md5, "md5ext": fn,
                "rotationCenterX": w // 2, "rotationCenterY": h // 2}

    def sound(self, name, data, ext, rate, count):
        md5, fn = self.add(data, ext)
        return {"name": name, "assetId": md5, "dataFormat": ext, "format": "", "rate": rate, "sampleCount": count,
                "md5ext": fn}


def load_game(path):
    path = Path(path).resolve()
    sys.path.insert(0, str(path.parent))
    try:
        ns = runpy.run_path(str(path), run_name="world")
    finally:
        sys.path.pop(0)
    games = [v for v in ns.values() if isinstance(v, Game)]
    if not games:
        raise SystemExit(f"{path.name}: no Game(...) found. Create one with game = Game(\"My Game\").")
    return games[0]


def voxelize(L, li):
    boxes = [b for op, b in L.ops if op == "carve"]
    if not boxes:
        raise SystemExit(f"level '{L.name}' has no rooms. Add one with level.room(x0, y0, z0, x1, y1, z1).")
    allb = np.array([b for _, b in L.ops], float)
    lo = allb[:, :3].min(0)
    hi = allb[:, 3:].max(0)
    if L.terrain_def:
        t = L.terrain_def
        lo = np.minimum(lo, [t["x0"], lo[1], t["z0"]])
        hi = np.maximum(hi, [t["x1"], hi[1], t["z1"]])
    open_top = (1, -1) in L.open_faces
    origin = np.floor(lo * lvl.RES - 2) / lvl.RES
    top = hi[1] if open_top else hi[1] + 1.0
    size = np.ceil((np.array([hi[0] + 1.0, top, hi[2] + 1.0]) - origin) * lvl.RES) / lvl.RES
    c = lvl.Level(L.name, tuple(size), tuple(origin))
    if open_top:
        c.size = (c.size[0], int(round((hi[1] - origin[1]) * lvl.RES)), c.size[2])
        c.air = np.zeros(c.size, bool)
    for op, b in L.ops:
        a = c.g(b[:3])
        e = c.g(b[3:])
        a = [max(a[i], 1) for i in range(3)]
        e = [min(e[i], c.size[i] - (0 if (open_top and i == 1) else 1)) for i in range(3)]
        c.air[a[0]:e[0], a[1]:e[1], a[2]:e[2]] = op == "carve"
    c.paint_ops = list(L.paint_ops)
    c.default_mats = dict(L.default_mats)
    c.open_faces = set(L.open_faces)
    c.main_box = L.probe or boxes[0]
    c.decor = list(L.decor)
    c.procs = list(L.procs)
    c.lights = [dict(l) for l in L.lights if not l.get("dynamic")]
    c.windows = list(L.windows)
    c.signs = list(L.signs)
    c.occluders = list(L.occluders)
    c.open_panels = list(L.open_panels)
    c.lit_windows = L.lit_windows
    c.window_style = L.window_style
    c.beams = L.beams
    c.stripe = L.stripe
    c.rings = [o.pos for o in L.objects if o.kind == 2]
    c.level_index = li
    c.sky = L.sky
    q = {"draft": (48, 10, 2, 2, 64), "normal": (128, 24, 3, 3, 96), "high": (256, 32, 4, 4, 128)}[L.bake_quality]
    c.bake_gi_rays, c.bake_ao_rays, c.bake_dres, c.bake_ns, c.bake_amb_rays = q
    c.terrain = None
    if L.terrain_def:
        from . import terrain as T
        xs, zs, H = T.heights(L.terrain_def)
        TP, TN, TM, TS = T.mesh(L.terrain_def, H, xs, zs)
        c.terrain = dict(grid=(xs, zs, H), P=TP, N=TN, M=TM, S=TS, step=L.terrain_def["step"])
    if L.sky:
        c.sun = dict(d=L.sun_dir, col=sky_preset(L)["sun"])
        c.sky_rad = sky_preset(L)["amb"]
    return c


SKIES = {
    "day": dict(zen=(0.25, 0.5, 1.05), hor=(0.85, 0.95, 1.1), ground=(0.2, 0.19, 0.17), sun=(3.4, 3.15, 2.8),
                amb=(0.32, 0.42, 0.6), fog=(0.62, 0.72, 0.86)),
    "sunset": dict(zen=(0.14, 0.2, 0.48), hor=(1.35, 0.72, 0.38), ground=(0.12, 0.09, 0.08), sun=(3.6, 2.0, 0.9),
                   amb=(0.32, 0.27, 0.33), fog=(0.9, 0.58, 0.42)),
    "night": dict(zen=(0.01, 0.015, 0.04), hor=(0.04, 0.06, 0.11), ground=(0.01, 0.01, 0.012), sun=(0.35, 0.42, 0.62),
                  amb=(0.025, 0.035, 0.06), fog=(0.04, 0.05, 0.08)),
    "overcast": dict(zen=(0.55, 0.58, 0.62), hor=(0.8, 0.82, 0.85), ground=(0.2, 0.2, 0.2), sun=(0.7, 0.7, 0.72),
                     amb=(0.6, 0.62, 0.66), fog=(0.62, 0.64, 0.68)),
}


def sky_preset(L):
    p = dict(SKIES.get(L.sky, SKIES["day"]))
    if L.sun_color:
        p["sun"] = tuple(np.array(color(L.sun_color)) * 3.4)
    return p


def level_key(c, L):
    h = hashlib.sha1()
    h.update(f"{BAKE_VERSION}|{bake.LMW}|{bake.LMH}".encode())
    h.update(np.packbits(c.air).tobytes())
    h.update(repr((c.procs, c.size, tuple(c.origin), [(m, tuple(a), tuple(b), f) for m, a, b, f in c.paint_ops],
                   c.default_mats, sorted(c.open_faces), c.decor, c.lights, c.windows, c.occluders, c.main_box,
                   c.bake_gi_rays, c.bake_ao_rays, c.bake_dres, c.bake_ns, c.bake_amb_rays,
                   getattr(c, "sun", None), getattr(c, "sky_rad", None))).encode())
    if c.terrain is not None:
        h.update(np.round(c.terrain["grid"][2], 3).tobytes())
        h.update(repr((tuple(c.terrain["grid"][0][:2]), tuple(c.terrain["grid"][1][:2]))).encode())
    return h.hexdigest()[:20]


def baked(c, L, cache, log):
    key = level_key(c, L)
    f = cache / f"{key}.npz"
    if f.exists():
        d = np.load(f, allow_pickle=False)
        log(f"  {L.name}: cached bake")
        return json.loads(bytes(d["meta"]).decode()), bytes(d["lm"]), d["dirr"], d["tirr"]
    log(f"  {L.name}: baking (first time, cached afterwards)")
    t0 = time.time()
    bake.LOG = log if VERBOSE else None
    res = bake.bake_level(c, seed=c.level_index)
    meta = dict(rects=[{k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, np.integer) else v))
                        for k, v in r.items()} for r in res["rects"]],
                panels=[list(map(float, p)) for p in res["panels"]],
                lights=[light_json(Lt) for Lt in res["lights"]],
                amb=dict(origin=list(map(float, res["amb"]["origin"])), dims=list(map(int, res["amb"]["dims"])),
                         step=float(res["amb"]["step"]), cube=np.round(res["amb"]["cube"], 4).tolist()))
    lm = bake.png_bytes(res["lightmap"])
    cache.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f, meta=np.frombuffer(json.dumps(meta).encode(), np.uint8), lm=np.frombuffer(lm, np.uint8),
                        dirr=res["dirr"].astype(np.float32), tirr=res["tirr"].astype(np.float32))
    log(f"  {L.name}: baked in {time.time() - t0:.0f}s")
    return meta, lm, res["dirr"].astype(np.float32), res["tirr"].astype(np.float32)


def light_json(Lt):
    return dict(kind=Lt["kind"], p=list(map(float, Lt["p"])), d=list(map(float, Lt["d"])), u=list(map(float, Lt["u"])),
                hu=float(Lt["hu"]), hv=float(Lt["hv"]), col=list(map(float, Lt["col"])), inten=float(Lt["inten"]),
                cin=float(Lt["cin"]), cout=float(Lt["cout"]), vol=float(Lt["vol"]), fixture=bool(Lt["fixture"]),
                name=Lt.get("name"), dynamic=bool(Lt.get("dynamic", False)))


def pack_amb(cube):
    v = np.clip(np.round(cube * 100), 0, 999).astype(np.int64)
    return (v[..., 0] * 1000000 + v[..., 1] * 1000 + v[..., 2]).reshape(-1)


def box_rects(lo, hi):
    out = []
    for ax in range(3):
        u, v = [a for a in range(3) if a != ax]
        for sg in (-1, 1):
            pl = hi[ax] if sg > 0 else lo[ax]
            out.append(dict(axis=ax, sgn=sg, pl=float(pl), u=u, v=v, u0=float(lo[u]), u1=float(hi[u]),
                            v0=float(lo[v]), v1=float(hi[v]), mat="metal"))
    return out


def model_bounds(P):
    lo = P.min(0)
    hi = P.max(0)
    return (hi - lo) / 2, (hi + lo) / 2


class Models:
    def __init__(self, pk, L):
        self.pk = pk
        self.L = L
        self.cache = {}

    def reg(self, info, tex="gm"):
        L = self.L
        L["GTEX"].append(tex)
        L["GB"].append(info["base"])
        L["GC"].append(info["count"])
        L["GNC"].append(0 if info["count"] <= geo.SCHUNK * 3 else -(-info["count"] // (geo.CHUNK * 3)))
        L["GIB"].append(0)
        L["GOX"].append(round(info["ox"], 5))
        L["GOY"].append(round(info["oy"], 5))
        L["GOZ"].append(round(info["oz"], 5))
        L["GR"].append(round(info["r"], 5))
        L["GH"].append(0)
        return len(L["GTEX"])

    def builtin(self, name):
        if name in self.cache:
            return self.cache[name]
        m = props.mesh(name)
        P, N, UV = m["pos"], m["nrm"], m["uv"]
        gid = self.reg(self.pk.add(P, N, UV, np.full(len(P), 30.0), bone=m.get("bone")))
        hs, ctr = model_bounds(P)
        self.cache[name] = (gid, hs, ctr)
        return self.cache[name]

    def proc(self, name):
        key = "proc:" + name
        if key in self.cache:
            return self.cache[key]
        from . import procprops
        P, N, M, S = procprops.mesh(name, 1)
        gid = self.reg(self.pk.add(P, N, np.zeros((len(P), 2)), M, None, S, irr=np.full((len(P), 3), 0.5),
                                   flag=np.full(len(P), 3.0)))
        hs, ctr = model_bounds(P)
        self.cache[key] = (gid, hs, ctr)
        return self.cache[key]

    def kit(self, name):
        key = "kit:" + name
        if key in self.cache:
            return self.cache[key]
        P, N, UV, T = decor_place.module(name)
        flag = np.where(T[:, 3] < 0, 2.0, 1.0)
        irr = np.full((len(P), 3), 0.5)
        gid = self.reg(self.pk.add(P, N, UV, np.full(len(P), 40.0), irr=irr, flag=flag, tan=T[:, :3]))
        hs, ctr = model_bounds(P)
        self.cache[key] = (gid, hs, ctr)
        return self.cache[key]


def build(world_path, out=None, log=print, cache=None):
    world_path = Path(world_path).resolve()
    game = load_game(world_path)
    out = Path(out) if out else world_path.parent / (safe_name(game.title) + ".sb3")
    cache = Path(cache) if cache else world_path.parent / ".loophole" / "cache"
    log(f"loophole {ENGINE_VERSION}: building '{game.title}' ({len(game.levels)} level{'s' * (len(game.levels) != 1)})")
    L = {k: [] for k in LIST_NAMES}
    for k in ["GTEX", "GB", "GC", "GH", "GIB", "GNC", "GOX", "GOY", "GOZ", "GR", "GIDW"]:
        L[k] = []
    groups = []
    lms = {}
    pkm = geo.Pack()
    models = Models(pkm, L)
    broadcasts = set(FIXED_BROADCASTS)
    used_ids = set()
    has_terrain = False
    for li, Lv in enumerate(game.levels, start=1):
        c = voxelize(Lv, li)
        meta, lm, dirr, tirr = baked(c, Lv, cache, log)
        lms[li] = lm
        P_, N_, UV_, M_, A_, S_, I_, F_, T_ = kit.build(c, meta, dirr)
        if c.terrain is not None:
            t = c.terrain
            n = len(t["P"])
            ti = tirr if len(tirr) == n else np.full((n, 3), 0.4)
            P_, N_, UV_ = np.concatenate([P_, t["P"]]), np.concatenate([N_, t["N"]]), np.concatenate([UV_, np.zeros((n, 2))])
            M_, A_, S_ = np.concatenate([M_, t["M"]]), np.concatenate([A_, np.ones(n)]), np.concatenate([S_, t["S"]])
            I_, F_, T_ = np.concatenate([I_, ti]), np.concatenate([F_, np.full(n, 3.0)]), np.concatenate([T_, np.zeros((n, 3))])
            has_terrain = True
        used_ids.update(np.unique(M_).astype(int).tolist())
        pk = geo.Pack()
        info = pk.add(P_, N_, UV_, M_, A_, S_, irr=I_, flag=F_, tan=T_)
        L["GIDW"].append(models.reg(info, f"g{li}"))
        groups.append((f"g{li}", pk))
        level_lists(L, Lv, c, meta, li, models, broadcasts)
    for name in ("device", "arms", "player"):
        gid, _, _ = models.builtin(name)
        L.setdefault("_G", {})[name] = gid
    viewmodel_lists(L, game, models)
    groups.append(("gm", pkm))
    gcost = {}
    for gname, pk in groups:
        data, w, h, ib = pk.png()
        gcost[gname] = (data, w, h)
        for i, t in enumerate(L["GTEX"]):
            if t == gname:
                L["GH"][i] = 1.0 / h
                L["GIB"][i] = ib
    gids = L.pop("_G")
    for key in models.cache:
        if key.startswith("proc:"):
            used_ids.update(np.unique(procprops.mesh(key[5:], 1)[2]).astype(int).tolist())
    proj = assemble(game, L, lms, gcost, gids, broadcasts, world_path, out, log, used_ids, has_terrain)
    return proj


def safe_name(s):
    keep = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in s).strip()
    return keep or "game"


LIST_NAMES = ["LNAME", "LH0", "LHN", "HAX", "HSG", "HPL", "HU0", "HU1", "HV0", "HV1", "HKILL", "HPORT", "LSX", "LSY",
              "LSZ", "LSYAW", "LSPIT", "LKILL", "LO0", "LON", "LT0", "LTN", "TNAME", "TKIND", "TARG", "TX0", "TY0",
              "TZ0", "TX1", "TY1", "TZ1", "LL0", "LLN", "LNM", "LTX", "LTY", "LTZ", "LTW", "LDDX", "LDDY", "LDDZ",
              "LDDW", "LCR", "LCG", "LCB", "LCW", "LDYN", "LVN", "LHZ", "LHA", "LEXP", "LGR", "LGG", "LGB", "LSAT",
              "AMB0", "AMBNX", "AMBNY", "AMBNZ", "AMBST", "AMBOX", "AMBOY", "AMBOZ", "AMB", "LPX", "LPY", "LPZ",
              "LB0X", "LB0Y", "LB0Z", "LB1X", "LB1Y", "LB1Z", "LFY", "LCY_", "LV0", "LVNN", "VX0", "VZ0", "VX1",
              "VZ1", "VY0", "VY1", "VPW", "LSP0", "LSPN", "SPX", "SPY", "SPZ", "LSKY", "LSUN", "LTER", "TOX", "TOZ",
              "TST", "TNX", "TNZ", "TH0", "THT", "DNAME", "DG", "DG2", "DPRX", "DPRY", "DPRS", "DPRT", "DPRX2",
              "DPRY2", "DPRS2", "DPRT2", "DBX", "DBY", "DBZ", "DBCX", "DBCY", "DBCZ", "DSX", "DSY", "DSZ", "DKIND",
              "DPHYS", "DCARRY", "DUSE", "DSHAD", "DSOLID", "DVIS", "DX", "DY", "DZ", "DYAW", "DPITCH", "DROLL",
              "DSCALE", "DGLOW", "DGR", "DGG", "DGB", "DLNK", "DSLIDE", "DOSP", "DSPIN", "DCOLL", "DPN", "DP0",
              "DPSP", "DPLOOP", "DPFACE", "PWX", "PWY", "PWZ", "PLEN", "PCLOSE", "SKY"]


def r4(v):
    return round(float(v), 4)


def level_lists(L, Lv, c, meta, li, models, broadcasts):
    rects = [dict(r) for r in meta["rects"]]
    for k in getattr(Lv, "solid_props", []):
        lo, hi = decor_place.footprints(c)[k]
        rects += box_rects(lo, hi)
    for b in getattr(Lv, "solid_boxes", []):
        rects += box_rects(np.array(b[:3]), np.array(b[3:]))
    L["LNAME"].append(Lv.name)
    L["LH0"].append(len(L["HAX"]) + 1)
    L["LHN"].append(len(rects))
    fy, cy = 99.0, -99.0
    for r in rects:
        ax = r["axis"]
        if ax == 0:
            u0, u1, v0, v1 = r["v0"], r["v1"], r["u0"], r["u1"]
        else:
            u0, u1, v0, v1 = r["u0"], r["u1"], r["v0"], r["v1"]
        L["HAX"].append(ax + 1)
        L["HSG"].append(r["sgn"])
        L["HPL"].append(r4(r["pl"]))
        L["HU0"].append(r4(u0))
        L["HU1"].append(r4(u1))
        L["HV0"].append(r4(v0))
        L["HV1"].append(r4(v1))
        L["HKILL"].append(1 if r["mat"] in KILL else 0)
        L["HPORT"].append(1 if r["mat"] in PORTAL else 0)
        if ax == 1 and r["sgn"] > 0:
            fy = min(fy, r["pl"])
        if ax == 1 and r["sgn"] < 0:
            cy = max(cy, r["pl"])
    sx, sy, sz, syaw = Lv.start
    L["LSX"].append(sx)
    L["LSY"].append(sy)
    L["LSZ"].append(sz)
    L["LSYAW"].append(syaw)
    L["LSPIT"].append(Lv.start_pitch)
    L["LKILL"].append(Lv.kill_height if Lv.kill_height is not None else float(c.origin[1]) - 4.0)
    mb = c.main_box
    L["LPX"].append(r4((mb[0] + mb[3]) / 2))
    L["LPY"].append(r4(mb[1] + min(2.2, (mb[4] - mb[1]) / 2)))
    L["LPZ"].append(r4((mb[2] + mb[5]) / 2))
    for k, v in zip(["LB0X", "LB0Y", "LB0Z", "LB1X", "LB1Y", "LB1Z"], mb):
        L[k].append(r4(v))
    L["LFY"].append(r4(fy if fy < 99 else 0))
    L["LCY_"].append(r4(cy if cy > -99 else 20))
    lts = [q for q in meta["lights"]]
    from .bake import norm_light
    for dl in Lv.lights:
        if dl.get("dynamic"):
            q = norm_light(dl)
            q = light_json(dict(q, name=dl.get("name"), dynamic=True))
            lts.append(q)
    lts = sorted(lts, key=lambda q: (q["kind"] != "sun", -q["vol"], -int(q["dynamic"]), -int(bool(q.get("name")))))[:24]
    L["LL0"].append(len(L["LTX"]) + 1)
    L["LLN"].append(len(lts))
    L["LVN"].append(min(8, sum(1 for q in lts if q["vol"] > 0)))
    L["LHZ"].append(Lv.haze)
    L["LHA"].append(Lv.haze_amb)
    L["LEXP"].append(Lv.exposure)
    L["LGR"].append(Lv.grade_rgb[0])
    L["LGG"].append(Lv.grade_rgb[1])
    L["LGB"].append(Lv.grade_rgb[2])
    L["LSAT"].append(Lv.saturation)
    for i, q in enumerate(lts):
        L["LNM"].append(q.get("name") or f"light{i + 1}")
        L["LTX"].append(r4(q["p"][0]))
        L["LTY"].append(r4(q["p"][1]))
        L["LTZ"].append(r4(q["p"][2]))
        L["LTW"].append(r4(q["hu"] * 0.6 if q["kind"] == "strip" else max(q["hu"], q["hv"] if q["kind"] == "panel" else 0.32)))
        L["LDDX"].append(r4(q["d"][0]))
        L["LDDY"].append(r4(q["d"][1]))
        L["LDDZ"].append(r4(q["d"][2]))
        L["LDDW"].append(r4(q["cout"]))
        sk = 160000.0 if q["kind"] == "sun" else 1.0
        L["LCR"].append(r4(q["col"][0] * q["inten"] * sk))
        L["LCG"].append(r4(q["col"][1] * q["inten"] * sk))
        L["LCB"].append(r4(q["col"][2] * q["inten"] * sk))
        L["LCW"].append(r4(q["cin"]))
        L["LDYN"].append(1 if q["dynamic"] else 0)
    amb = meta["amb"]
    cube = np.array(amb["cube"])
    L["AMB0"].append(len(L["AMB"]) + 1)
    L["AMBNX"].append(amb["dims"][0])
    L["AMBNY"].append(amb["dims"][1])
    L["AMBNZ"].append(amb["dims"][2])
    L["AMBST"].append(amb.get("step", 1.0))
    L["AMBOX"].append(r4(amb["origin"][0]))
    L["AMBOY"].append(r4(amb["origin"][1]))
    L["AMBOZ"].append(r4(amb["origin"][2]))
    L["AMB"].extend(int(x) for x in pack_amb(cube))
    L["LV0"].append(len(L["VX0"]) + 1)
    L["LVNN"].append(len(Lv.vents))
    for v in Lv.vents:
        for k, val in zip(["VX0", "VZ0", "VX1", "VZ1", "VY0", "VY1", "VPW"], v):
            L[k].append(val)
    L["LSP0"].append(len(L["SPX"]) + 1)
    L["LSPN"].append(len(Lv.spark_pts))
    for p in Lv.spark_pts:
        L["SPX"].append(p[0])
        L["SPY"].append(p[1])
        L["SPZ"].append(p[2])
    L["LSKY"].append(1 if Lv.sky else 0)
    if Lv.sky:
        sp = sky_preset(Lv)
        sd = Lv.sun_dir
        vals = [r4(x) for x in (*sd, *sp["sun"], *sp["zen"], Lv.clouds, *sp["hor"], 0.9996, *sp["ground"],
                                 *sp["fog"], Lv.fog or 0.0)]
    else:
        vals = [0.0] * 21
    L["SKY"].extend(vals + [0.0] * (24 - len(vals)))
    if c.terrain is not None:
        xs, zs, H = c.terrain["grid"]
        L["LTER"].append(1)
        L["TOX"].append(r4(xs[0]))
        L["TOZ"].append(r4(zs[0]))
        L["TST"].append(r4(c.terrain["step"]))
        L["TNX"].append(len(xs))
        L["TNZ"].append(len(zs))
        L["TH0"].append(len(L["THT"]) + 1)
        L["THT"].extend(r4(v) for v in H.ravel())
    else:
        L["LTER"].append(0)
        for k in ("TOX", "TOZ", "TST", "TNX", "TNZ"):
            L[k].append(0)
        L["TH0"].append(1)
    L["LT0"].append(len(L["TNAME"]) + 1)
    L["LTN"].append(len(Lv.triggers))
    for t in Lv.triggers:
        L["TNAME"].append(t["name"])
        L["TKIND"].append(t["kind"])
        L["TARG"].append(t["to"])
        for k, v in zip(["TX0", "TY0", "TZ0", "TX1", "TY1", "TZ1"], t["box"]):
            L[k].append(r4(v))
        broadcasts.add(f"enter {t['name']}")
        broadcasts.add(f"leave {t['name']}")
    L["LO0"].append(len(L["DNAME"]) + 1)
    L["LON"].append(len(Lv.objects))
    names = [o.name for o in Lv.objects]
    for o in Lv.objects:
        object_lists(L, o, names, models, Lv)
        for pre in ("touch", "use", "collect", "press", "release"):
            broadcasts.add(f"{pre} {o.name}")


def object_lists(L, o, names, models, Lv):
    g2 = 0
    pr2 = (0, 0, 0, 0)
    if o.model in props.BUILTIN:
        b = props.BUILTIN[o.model]
        gid, hs, ctr = models.builtin(b["file"])
        pr = props.region(b["region"])
        glow = b["glow"]
        if "top" in b:
            g2, _, _ = models.builtin(b["top"])
            pr2 = props.region(b["top"])
    elif o.model in decor_place.KINDS:
        gid, hs, ctr = models.kit(o.model)
        pr = (0, 0, 0, 0)
        glow = (1.0, 0.6, 0.3)
    elif o.model in procprops.KINDS:
        gid, hs, ctr = models.proc(o.model)
        pr = (0, 0, 0, 0)
        glow = (1.0, 0.75, 0.3)
    else:
        raise SystemExit(f"{Lv.name}: object '{o.name}' uses unknown model '{o.model}'. Built-in models: "
                         f"{', '.join(sorted(set(props.BUILTIN) - {'arms', 'device'}) + decor_place.KINDS)}")
    if o.glow_color:
        glow = color(o.glow_color)
    L["DNAME"].append(o.name)
    L["DG"].append(gid)
    L["DG2"].append(g2)
    for k, v in zip(["DPRX", "DPRY", "DPRS", "DPRT"], pr):
        L[k].append(v)
    for k, v in zip(["DPRX2", "DPRY2", "DPRS2", "DPRT2"], pr2):
        L[k].append(v)
    for k, v in zip(["DBX", "DBY", "DBZ"], hs):
        L[k].append(r4(v))
    for k, v in zip(["DBCX", "DBCY", "DBCZ"], ctr):
        L[k].append(r4(v))
    sz = o.size if not isinstance(o.size, (int, float)) else (o.size,) * 3
    for k, v in zip(["DSX", "DSY", "DSZ"], sz):
        L[k].append(r4(v))
    L["DKIND"].append(o.kind)
    L["DPHYS"].append(int(bool(o.physics)))
    L["DCARRY"].append(int(bool(o.carry)))
    L["DUSE"].append(int(bool(o.use)))
    L["DSHAD"].append(int(bool(o.shadow)))
    L["DSOLID"].append(int(bool(o.solid)))
    L["DVIS"].append(int(bool(o.visible)))
    for k, v in zip(["DX", "DY", "DZ"], o.pos):
        L[k].append(r4(v))
    L["DYAW"].append(r4(o.yaw))
    L["DPITCH"].append(r4(o.pitch))
    L["DROLL"].append(r4(o.roll))
    L["DSCALE"].append(r4(o.scale))
    L["DGLOW"].append(r4(o.glow))
    L["DGR"].append(r4(glow[0]))
    L["DGG"].append(r4(glow[1]))
    L["DGB"].append(r4(glow[2]))
    if o.opens and o.opens not in names:
        raise SystemExit(f"{Lv.name}: button '{o.name}' opens '{o.opens}', but there is no object with that name")
    L["DLNK"].append(names.index(o.opens) + 1 if o.opens else 0)
    L["DSLIDE"].append(r4(o.slide))
    L["DOSP"].append(r4(o.open_speed))
    L["DSPIN"].append(r4(o.spin))
    L["DCOLL"].append(int(bool(o.collect)))
    path = [tuple(map(float, p)) for p in (o.path or [])]
    path = [(p[0], o.pos[1], p[1]) if len(p) == 2 else p for p in path]
    L["DPN"].append(len(path))
    L["DP0"].append(len(L["PWX"]) + 1)
    L["DPSP"].append(r4(o.speed))
    L["DPLOOP"].append(int(bool(o.loop)))
    L["DPFACE"].append(int(bool(o.face_path)))
    acc = 0.0
    for i, p in enumerate(path):
        if i > 0:
            acc += math.dist(p, path[i - 1])
        L["PWX"].append(r4(p[0]))
        L["PWY"].append(r4(p[1]))
        L["PWZ"].append(r4(p[2]))
        L["PLEN"].append(r4(acc))
        L["PCLOSE"].append(r4(math.dist(p, path[0])) if i == len(path) - 1 else 0)


SFX = ["arrive", "button", "click", "door_close", "door_open", "fail", "impact", "jump", "land", "pickup", "release",
       "step1", "step2", "step3", "step4", "step5", "success", "unpress", "whoosh", "alarm", "boost", "hum", "rumble"]


def sounds(A):
    man = json.loads((DATA / "sfx" / "manifest.json").read_text())
    out = []
    for n in SFX:
        rate, cnt = man[n]
        out.append(A.sound(n, (DATA / "sfx" / f"{n}.mp3").read_bytes(), "mp3", rate, cnt))
    return out


def overlay_sprite(A, proj):
    cross = ('<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
             '<circle cx="6" cy="6" r="2.2" fill="#ffffff" fill-opacity="0.9" stroke="#000000" stroke-opacity="0.35" '
             'stroke-width="1"/></svg>')
    click = ('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="44" viewBox="0 0 240 44">'
             '<rect x="0.5" y="0.5" width="239" height="43" rx="8" fill="#0b0d12" fill-opacity="0.78" '
             'stroke="#ffffff" stroke-opacity="0.25"/>'
             '<text x="120" y="28" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" font-size="17" '
             'font-weight="600" fill="#ffffff">Click to play</text></svg>')
    src = """
@when_flag
def overlay():
    go_front()
    goto(0, 0)
    while True:
        if api_locked == 1 and api_paused == 0:
            costume("crosshair")
        else:
            costume("click")
        show()
"""
    src = src.replace("go_front()", "front()")
    c = Compiler(proj, src, list(API_LISTS.values()), aliases=ALIASES)
    blocks = c.compile()
    return {"isStage": False, "name": "Overlay", "variables": {}, "lists": {}, "broadcasts": {}, "blocks": blocks,
            "comments": {}, "currentCostume": 0,
            "costumes": [A.svg("crosshair", cross, 6, 6), A.svg("click", click, 120, 22)], "sounds": [],
            "volume": 100, "layerOrder": 2, "visible": True, "x": 0, "y": 0, "size": 100, "direction": 90,
            "draggable": False, "rotationStyle": "don't rotate"}


def game_sprite(A, proj, game, world_path, consts):
    srcs = []
    for s in game.scripts:
        p = (Path(world_path).parent / s).resolve()
        srcs.append(p.read_text())
    if not srcs:
        return None
    src = "\n\n".join(srcs)
    c = Compiler(proj, src, list(API_LISTS.values()), consts=consts, aliases=ALIASES)
    blocks = c.compile()
    return {"isStage": False, "name": "Game", "variables": {vid: [n, 0] for n, vid in c.new_vars.items()},
            "lists": {lid: [n, []] for n, lid in c.new_lists.items()}, "broadcasts": {}, "blocks": blocks,
            "comments": {}, "currentCostume": 0,
            "costumes": [A.svg("blank", '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"></svg>', 1, 1)],
            "sounds": [], "volume": 100, "layerOrder": 3, "visible": False, "x": 0, "y": 0, "size": 100,
            "direction": 90, "draggable": False, "rotationStyle": "don't rotate"}


def placeholder_jpg():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(b, "JPEG")
    return b.getvalue()


def assemble(game, L, lms, gcost, gids, broadcasts, world_path, out, log, used_ids=(), has_terrain=False):
    A = Assets()
    proj = Project(global_names=list(API_VARS.values()), global_lists=list(API_LISTS.values()))
    for b in sorted(broadcasts):
        proj.bc_id(b)
    paw, pah = props.atlas_size()
    consts = {"NLEV": len(game.levels), "START_LEVEL": max(1, min(len(game.levels), game.start_level)),
              "QUALITY": game.quality, "FOV": game.fov, "VMDEF": game.viewmodel,
              "WALK": 6.0, "JUMPV": 7.0, "GRAV": 20.0, "FRIC": 5.0, "STOPSPD": 1.9, "ACCEL": 10.0, "AIRACC": 12.0,
              "AIRCAP": 0.8, "STEPH": 0.55, "EYE": 1.6, "EYEC": 1.05, "PHT": 1.75, "PHTC": 1.2, "PW": 0.3,
              "ENVT": 192, "NEAR": 0.01, "FAR": 150.0, "SENS": 0.11, "EXPO": 0.72, "AMBS": 0.01, "HOLDD": 1.6,
              "USED": 2.6, "NSHAD": 4, "HASTER": 1 if has_terrain else 0, "PAW": paw, "PAH": pah,
              "G_DEVICE": gids["device"], "G_ARMS": gids["arms"], "G_PLAYER": gids["player"]}
    for n in ("device", "arms", "player"):
        x, y, s, t = props.region(n)
        consts.update({f"PR_{n.upper()}_X": x, f"PR_{n.upper()}_Y": y, f"PR_{n.upper()}_S": s, f"PR_{n.upper()}_T": t})
    L["JX"] = [0.5, 0.25, 0.75, 0.125, 0.625, 0.375, 0.875, 0.0625]
    L["JY"] = [0.3333, 0.6667, 0.1111, 0.4444, 0.7778, 0.2222, 0.5556, 0.8889]
    src = expand_mklist((HERE / "runtime" / "engine.py").read_text())
    gc = Compiler(proj, src, list(API_LISTS.values()), consts=consts, aliases=ALIASES)
    gblocks = gc.compile()
    eng_lists = {}
    from . import mesh as M
    meshes = {"QUAD": M.quad_mesh(), "DUST": M.particles(320, 5), "IMPACT": M.particles(56, 21),
              "VENTP": M.particles(140, 13)}
    for name, m in meshes.items():
        eng_lists[proj.uid("l")] = [name, m.items()]
    eng_lists[proj.uid("l")] = ["IC", geo.index_items(geo.CHUNK)]
    eng_lists[proj.uid("l")] = ["ICS", geo.index_items(geo.SCHUNK)]
    for name, lid in gc.new_lists.items():
        if name in ("IC", "ICS") or name in meshes:
            continue
        eng_lists[lid] = [name, L.get(name, [])]
    blank = A.svg("blank", '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"></svg>', 1, 1)
    mj = json.loads((DATA / "atlas" / "materials.json").read_text())
    costumes = [blank, A.bitmap("atlas", (DATA / "atlas" / "materials.jpg").read_bytes(), "jpg", mj["ATLAS_W"],
                                mj["ATLAS_H"]),
                A.bitmap("patlas", props.atlas_bytes(), "jpg", paw, pah)]
    need2 = any(49 < i < 62 or i in (70, 72) for i in used_ids)
    need3 = any(61 < i < 68 for i in used_ids)
    for nm, need, f in (("atlas2", need2, "materials2"), ("atlas3", need3, "materials3")):
        if need:
            mj2 = json.loads((DATA / "atlas" / f"{f}.json").read_text())
            costumes.append(A.bitmap(nm, (DATA / "atlas" / f"{f}.jpg").read_bytes(), "jpg", mj2["ATLAS_W"], mj2["ATLAS_H"]))
        else:
            costumes.append(A.bitmap(nm, placeholder_jpg(), "jpg", 8, 8))
    dj = json.loads((DATA / "atlas" / "decor.json").read_text())
    costumes.append(A.bitmap("dA", (DATA / "atlas" / "dA.jpg").read_bytes(), "jpg", dj["PW"], dj["PH"] * 3 // 2))
    costumes.append(A.bitmap("dN", (DATA / "atlas" / "dN.jpg").read_bytes(), "jpg", dj["PW"], dj["PH"] * 3 // 2))
    costumes.append(A.bitmap("dR", (DATA / "atlas" / "dR.jpg").read_bytes(), "jpg", dj["PW"] // 2, dj["PH"] * 3 // 4))
    for li, data in lms.items():
        costumes.append(A.bitmap(f"lm{li}", data, "png", bake.LMW, bake.LMH * 3))
    for gname, (gdata, gw, gh) in gcost.items():
        costumes.append(A.bitmap(gname, gdata, "png", gw, gh))
    engine = {"isStage": False, "name": "Engine", "variables": {vid: [n, 0] for n, vid in gc.new_vars.items()},
              "lists": eng_lists, "broadcasts": {}, "blocks": gblocks, "comments": {}, "currentCostume": 0,
              "costumes": costumes, "sounds": sounds(A), "volume": 100, "layerOrder": 1, "visible": False, "x": 0,
              "y": 0, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "don't rotate"}
    gsprite = game_sprite(A, proj, game, world_path, level_consts(game))
    tw_cfg = {"framerate": 60, "runtimeOptions": {"maxClones": 300, "miscLimits": False, "fencing": False},
              "interpolation": False, "turbo": False, "hq": True, "width": STAGE_W, "height": STAGE_H}
    cfg_text = ("Configuration for https://turbowarp.org/\nYou can move, resize, and minimize this comment, "
                "but don't edit it by hand. This comment can be deleted to remove the stored settings.\n"
                + json.dumps(tw_cfg, separators=(",", ":")) + " // _twconfig_")
    api_values = {"viewmodel": game.viewmodel, "controls": 1, "camera mode": 0, "field of view": game.fov, "exposure": 1, "walk speed": 6.0,
                  "jump power": 7.0, "gravity": 20.0, "camera distance": 4, "level": game.start_level}
    shader_store = {name: {"projectData": {"vertShader": vs, "fragShader": fs}, "modifyDate": 1763400000000}
                    for name, (vs, fs) in shaders.SHADERS.items()}
    bg = A.svg("bg", f'<svg xmlns="http://www.w3.org/2000/svg" width="{STAGE_W}" height="{STAGE_H}" '
                     f'viewBox="0 0 {STAGE_W} {STAGE_H}"><rect width="{STAGE_W}" height="{STAGE_H}" fill="#07080b"/></svg>',
                STAGE_W // 2, STAGE_H // 2)
    old = read_sb3(out) if out.exists() else None
    pj = merge_project(old, engine, gsprite, overlay_sprite(A, proj), proj, api_values, shader_store, cfg_text, bg, A,
                       game)
    js = json.dumps(pj, separators=(",", ":"))
    files = dict(old["files"]) if old else {}
    keep = referenced_assets(pj)
    files = {k: v for k, v in files.items() if k in keep}
    files.update({k: v for k, v in A.files.items() if k in keep})
    tmp = out.with_suffix(".sb3.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.json", js)
        for fn, d in files.items():
            z.writestr(fn, d)
    tmp.replace(out)
    nb = sum(len(t["blocks"]) for t in pj["targets"])
    log(f"wrote {out.name} ({out.stat().st_size // 1024} KB, {nb} blocks)" + (" merged into existing project" if old else ""))
    return out


def viewmodel_lists(L, game, models):
    for k in ("VMN", "VMG", "VMPRX", "VMPRY", "VMPRS", "VMPRT", "VMS", "VMOX", "VMOY", "VMOZ", "VMARM", "VMR", "VMGC",
              "VMB"):
        L[k] = []
    for name in game.viewmodels:
        arms = 1
        off = (0.0, 0.0, 0.0)
        glow = game.hand_color
        if name == "arms":
            g, pr, sc = 0, (0, 0, 0, 0), 1.0
        elif name == "device":
            g, _, _ = models.builtin("device")
            pr, sc = props.region("device"), 1.0
        elif name in props.BUILTIN:
            b = props.BUILTIN[name]
            g, hs, _ = models.builtin(b["file"])
            pr = props.region(b["region"])
            sc = 0.32 / max(hs.max() * 2, 1e-3)
            glow = b["glow"]
            off = (0.0, -0.02, 0.05)
        elif name in procprops.KINDS:
            g, hs, ctr = models.proc(name)
            pr = (0, 0, 0, 0)
            sc = 0.42 / max(hs.max() * 2, 1e-3)
            off = (-ctr[0] * sc, 0.02 - ctr[1] * sc, 0.06 - ctr[2] * sc)
            glow = (1.0, 0.7, 0.3)
        elif name in decor_place.KINDS:
            g, hs, ctr = models.kit(name)
            pr = (0, 0, 0, 0)
            sc = 0.36 / max(hs.max() * 2, 1e-3)
            off = (-ctr[0] * sc, -ctr[1] * sc, 0.05 - ctr[2] * sc)
        else:
            raise SystemExit(f"unknown viewmodel '{name}'. Use none, arms, device, or any prop or model name")
        L["VMN"].append(name)
        L["VMG"].append(g)
        for k, v in zip(["VMPRX", "VMPRY", "VMPRS", "VMPRT"], pr):
            L[k].append(v)
        L["VMS"].append(r4(sc))
        for k, v in zip(["VMOX", "VMOY", "VMOZ"], off):
            L[k].append(r4(v))
        L["VMARM"].append(arms)
        for k, v in zip(["VMR", "VMGC", "VMB"], glow):
            L[k].append(r4(v))


def level_consts(game):
    out = {}
    for i, Lv in enumerate(game.levels, start=1):
        out["LEVEL_" + "".join(ch if ch.isalnum() else "_" for ch in Lv.name.upper())] = i
    return out


def read_sb3(path):
    with zipfile.ZipFile(path) as z:
        pj = json.loads(z.read("project.json"))
        files = {n: z.read(n) for n in z.namelist() if n != "project.json"}
    return {"project": pj, "files": files}


def referenced_assets(pj):
    keep = set()
    for t in pj["targets"]:
        for c in t.get("costumes", []) + t.get("sounds", []):
            keep.add(c["md5ext"])
    return keep


def merge_project(old, engine, gsprite, overlay, proj, api_values, shader_store, cfg_text, bg, A, game):
    api_v = {proj.var_id(n): n for n in API_VARS.values()}
    api_l = {proj.list_id(n): n for n in API_LISTS.values()}
    bcs = {bid: n for n, bid in proj.broadcasts.items()}
    if old:
        po = old["project"]
        stage = next(t for t in po["targets"] if t["isStage"])
        others = [t for t in po["targets"] if not t["isStage"] and t["name"] != "Engine" and
                  not (gsprite and t["name"] == "Game")]
        names_v = {v[0]: k for k, v in stage["variables"].items()}
        for vid, n in api_v.items():
            if n in names_v and names_v[n] != vid:
                old_id = names_v[n]
                del stage["variables"][old_id]
                rewrite_ids(po, old_id, vid)
            if vid not in stage["variables"]:
                stage["variables"][vid] = [n, api_values.get(n, 0)]
        names_l = {v[0]: k for k, v in stage["lists"].items()}
        for lid, n in api_l.items():
            if n in names_l and names_l[n] != lid:
                old_id = names_l[n]
                del stage["lists"][old_id]
                rewrite_ids(po, old_id, lid)
            stage["lists"][lid] = [n, []]
        bnames = {v.lower(): k for k, v in stage.get("broadcasts", {}).items()}
        for bid, n in bcs.items():
            if n.lower() in bnames and bnames[n.lower()] != bid:
                old_id = bnames[n.lower()]
                del stage["broadcasts"][old_id]
                rewrite_ids(po, old_id, bid)
            stage["broadcasts"][bid] = n
        stage["comments"]["twconfig"] = {"blockId": None, "x": 0, "y": 0, "width": 350, "height": 170,
                                         "minimized": True, "text": cfg_text}
        targets = [stage, engine] + ([gsprite] if gsprite else []) + others
        exts = list(dict.fromkeys(po.get("extensions", []) + ["pen", "penP", "pointerlock", "tw"]))
        ext_urls = dict(po.get("extensionURLs", {}))
        ext_store = dict(po.get("extensionStorage", {}))
        monitors = po.get("monitors", [])
    else:
        stage = {"isStage": True, "name": "Stage", "variables": {vid: [n, api_values.get(n, 0)] for vid, n in api_v.items()},
                 "lists": {lid: [n, []] for lid, n in api_l.items()}, "broadcasts": bcs, "blocks": {},
                 "comments": {"twconfig": {"blockId": None, "x": 0, "y": 0, "width": 350, "height": 170,
                                           "minimized": True, "text": cfg_text}},
                 "currentCostume": 0, "costumes": [bg], "sounds": [], "volume": 100, "layerOrder": 0, "tempo": 60,
                 "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None}
        targets = [stage, engine] + ([gsprite] if gsprite else []) + [overlay]
        exts = ["pen", "penP", "pointerlock", "tw"]
        ext_urls = {}
        ext_store = {}
        monitors = []
    for i, t in enumerate(targets):
        t["layerOrder"] = i
    ext_urls.update({"penP": PENP_URL, "pointerlock": PLOCK_URL})
    ext_store["penP"] = {"shaders": shader_store, "version": "7.1.9",
                         "prefixes": {"penPlusTextures": "", "renderTextures": ""}}
    return {"targets": targets, "monitors": monitors, "extensions": exts, "extensionURLs": ext_urls,
            "extensionStorage": ext_store,
            "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": f"loophole {ENGINE_VERSION}",
                     "platform": {"name": "TurboWarp", "url": "https://turbowarp.org/"}}}


def rewrite_ids(po, old, new):
    def walk(x):
        if isinstance(x, list):
            for i, v in enumerate(x):
                if v == old and i > 0 and isinstance(x[i - 1], str):
                    x[i] = new
                else:
                    walk(v)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    for t in po["targets"]:
        walk(t.get("blocks", {}))
    for m in po.get("monitors", []):
        if m.get("id") == old:
            m["id"] = new
