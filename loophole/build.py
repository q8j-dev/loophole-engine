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

from . import bake, decor_place, geo, kit, props, sbc, shaders
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
    "api_locked": "mouse locked", "api_vm": "viewmodel", "api_lcoll": "last collected", "api_ltouch": "last touched",
    "api_ltrig": "last trigger", "api_msg": "message", "api_stat": "status",
}
API_LISTS = {
    "obj_name": "obj name", "obj_x": "obj x", "obj_y": "obj y", "obj_z": "obj z", "obj_yaw": "obj yaw",
    "obj_pitch": "obj pitch", "obj_roll": "obj roll", "obj_scale": "obj scale", "obj_visible": "obj visible",
    "obj_solid": "obj solid", "obj_glow": "obj glow", "obj_open": "obj open", "obj_touch": "obj touching",
    "snd_q": "sound queue", "light_name": "light name", "light_power": "light power", "trig_name": "trigger name",
    "trig_in": "trigger inside",
}
ALIASES = {**API_VARS, **API_LISTS}
FIXED_BROADCASTS = ["level start", "player died", "paused", "resumed", "game complete", "collect", "touch", "enter",
                    "leave"]
USER_ALIASES = {"player_x": "player x", "player_y": "player y", "player_z": "player z", "player_yaw": "player yaw",
                "player_pitch": "player pitch", "player_speed": "player speed", "on_ground": "player on ground",
                "level": "level", "level_name": "level name", "level_time": "level time", "fps": "fps",
                "looking_at": "looking at", "looking_distance": "looking distance", "holding": "holding",
                "used_object": "used object", "go_to_level": "go to level", "controls": "controls",
                "camera_mode": "camera mode", "camera_x": "camera x", "camera_y": "camera y", "camera_z": "camera z",
                "camera_yaw": "camera yaw", "camera_pitch": "camera pitch", "camera_distance": "camera distance",
                "field_of_view": "field of view", "exposure": "exposure", "fade": "fade", "flash": "flash",
                "walk_speed": "walk speed", "jump_power": "jump power", "gravity": "gravity", "paused": "paused",
                "mouse_locked": "mouse locked", "viewmodel": "viewmodel", "last_collected": "last collected",
                "last_touched": "last touched", "last_trigger": "last trigger", "message": "message", "status": "status", "obj_name": "obj name",
                "obj_x": "obj x", "obj_y": "obj y", "obj_z": "obj z", "obj_yaw": "obj yaw", "obj_pitch": "obj pitch",
                "obj_roll": "obj roll", "obj_scale": "obj scale", "obj_visible": "obj visible", "obj_solid": "obj solid",
                "obj_glow": "obj glow", "obj_open": "obj open", "obj_touching": "obj touching",
                "sound_queue": "sound queue", "light_name": "light name", "light_power": "light power",
                "trigger_name": "trigger name", "trigger_inside": "trigger inside"}

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
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            item, cont = node.left, node.comparators[0]
            nm = self.aliases.get(cont.id, cont.id) if isinstance(cont, ast.Name) else None
            if nm is not None and (nm in self.list_names or nm in self.local_lists or nm in self.p.global_lists):
                bid = self._new("data_listcontainsitem", parent, fields={"LIST": self.lref(cont.id)})
                self.blocks[bid]["inputs"]["ITEM"] = self._input(item, bid, "text")
            else:
                bid = self._new("operator_contains", parent)
                self.blocks[bid]["inputs"]["STRING1"] = self._input(cont, bid, "text")
                self.blocks[bid]["inputs"]["STRING2"] = self._input(item, bid, "text")
            if isinstance(node.ops[0], ast.NotIn):
                nid = self._new("operator_not", parent)
                self.blocks[nid]["inputs"]["OPERAND"] = [2, bid]
                self.blocks[bid]["parent"] = nid
                return nid
            return bid
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "plocked":
                return self._new("pointerlock_isLocked", parent)
            if node.func.id == "costume_number":
                return self._new("looks_costumenumbername", parent, fields={"NUMBER_NAME": ["number", None]})
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


def voxelize_outdoor(L, li):
    from . import terrain as T
    field = None
    pts = [b for _, b in L.ops]
    if L.terrain_def:
        td = L.terrain_def
        xs, zs, H = T.heights(td)
        field = T.Field(td, xs, zs, H)
        field.holes = [(b[0] + 0.2, b[2] + 0.2, b[3] - 0.2, b[5] - 0.2) for op, b in L.ops if op == "fill"]
        pts.append((td["x0"], float(H.min()) - 1.0, td["z0"], td["x1"], float(H.max()) + 2.0, td["z1"]))
    for d in L.decor:
        pts.append((d[1][0] - 1, d[1][1] - 1, d[1][2] - 1, d[1][0] + 1, d[1][1] + 3, d[1][2] + 1))
    if not pts:
        raise SystemExit(f"level '{L.name}' is empty. Add terrain, solids or props.")
    allb = np.array(pts, float)
    lo = allb[:, :3].min(0)
    hi = allb[:, 3:].max(0)
    if field is None:
        lo[1] = 0.0
    origin = np.floor(lo * lvl.RES) / lvl.RES
    size = np.ceil((hi + 1.0 - origin) * lvl.RES) / lvl.RES
    c = lvl.Level(L.name, tuple(size), tuple(origin))
    c.air[:] = True
    c.air[0:2, 0:2, 0:2] = False
    for op, b in L.ops:
        a = c.g(b[:3])
        e = c.g(b[3:])
        a = [max(a[i], 0) for i in range(3)]
        e = [min(e[i], c.size[i]) for i in range(3)]
        c.air[a[0]:e[0], a[1]:e[1], a[2]:e[2]] = op == "carve"
    c.open_faces = {(0, 1), (0, -1), (1, -1), (2, 1), (2, -1)} | ({(1, 1)} if field is not None else set())
    c.field = field
    sx, sy, sz, _ = L.start
    c.main_box = L.probe or (sx - 20, sy, sz - 20, sx + 20, sy + 12, sz + 20)
    return c


def ground_relative(L):
    from . import terrain as T
    td = L.terrain_def
    if not td or getattr(L, "_grounded", False):
        return
    L._grounded = True
    for b in L.buildings:
        td["flats"].append((b["x0"] - 0.5, b["z0"] - 0.5, b["x1"] + 0.5, b["z1"] + 0.5, b["y"], 4.0))
    xs, zs, H = T.heights(td)
    f = T.Field(td, xs, zs, H)

    def h(x, z):
        return float(f.height(np.array([x]), np.array([z]))[0])

    def box(b):
        d = h((b[0] + b[3]) / 2, (b[2] + b[5]) / 2)
        return (b[0], b[1] + d, b[2], b[3], b[4] + d, b[5])

    L.decor = [(n_, (p[0], p[1] + h(p[0], p[2]), p[2]), fw, up, sc) for n_, p, fw, up, sc in L.decor]
    for q in L.lights:
        p = q["p"]
        q["p"] = (p[0], p[1] + h(p[0], p[2]), p[2])
    for o in L.objects:
        o.pos = (o.pos[0], o.pos[1] + h(o.pos[0], o.pos[2]), o.pos[2])
        if o.path:
            o.path = [(p[0], p[1] + h(p[0], p[2]), p[2]) for p in o.path]
    for t in L.triggers:
        t["box"] = box(t["box"])
    L.occluders = [box(b) for b in L.occluders]
    if hasattr(L, "solid_boxes"):
        L.solid_boxes = [box(b) for b in L.solid_boxes]
    sx, sy, sz, yaw = L.start
    L.start = (sx, sy + h(sx, sz), sz, yaw)


def voxelize(L, li):
    ground_relative(L)
    if L.sky:
        c = voxelize_outdoor(L, li)
        return finish_voxel(c, L, li)
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
    c.open_faces = set(L.open_faces)
    c.main_box = L.probe or boxes[0]
    c.field = None
    return finish_voxel(c, L, li)


def finish_voxel(c, L, li):
    c.paint_ops = list(L.paint_ops)
    c.default_mats = dict(L.default_mats)
    c.decor = list(L.decor)
    from . import buildings as BD
    c.extra = BD.geometry(L.buildings) if L.buildings else None
    if c.extra is not None:
        L.occluders = list(L.occluders)
        c.extra_occ = list(c.extra[4])
    c.lights = [dict(l) for l in L.lights if not l.get("dynamic")]
    c.windows = list(L.windows)
    c.signs = list(L.signs)
    c.occluders = list(L.occluders) + list(getattr(c, "extra_occ", []))
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
    if L.sky:
        c.bake_amb_step = 2.0
        c.bake_amb_rays = 48
    c.terrain = None
    if L.terrain_def and c.field is not None:
        from . import terrain as T
        f = c.field
        TP, TN, TM, TS = T.mesh(L.terrain_def, f.H, f.xs, f.zs, getattr(f, "holes", []))
        RP, RN = f.ring_mesh()
        c.terrain = dict(grid=(f.xs, f.zs, f.H), P=TP, N=TN, M=TM, S=TS, step=L.terrain_def["step"], field=f,
                         ring=(RP, RN), tlm_step=0.5, mat=TM[0] if len(TM) else 70.0)
    if L.sky:
        c.sun = dict(d=L.sun_dir, col=sky_preset(L)["sun"])
        c.sky_rad = sky_preset(L)["amb"]
    return c


SKIES = {
    "day": dict(zen=(0.09, 0.27, 0.78), hor=(0.62, 0.78, 1.0), ground=(0.16, 0.15, 0.13), sun=(3.7, 3.35, 2.85),
                amb=(0.22, 0.32, 0.55), fog=(0.58, 0.7, 0.9)),
    "sunset": dict(zen=(0.06, 0.16, 0.42), hor=(1.15, 0.66, 0.36), ground=(0.1, 0.07, 0.06), sun=(3.8, 2.2, 0.95),
                   amb=(0.2, 0.24, 0.34), fog=(0.78, 0.56, 0.42)),
    "dusk": dict(zen=(0.025, 0.05, 0.16), hor=(0.55, 0.32, 0.24), ground=(0.04, 0.035, 0.03), sun=(1.2, 0.55, 0.25),
                 amb=(0.08, 0.1, 0.17), fog=(0.3, 0.24, 0.24)),
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
    for kind in sorted({d[0] for d in c.decor}):
        f = decor_place.mesh_path(kind)
        if f.exists():
            h.update(hashlib.md5(f.read_bytes()).digest())
    if getattr(c, "extra", None) is not None:
        h.update(np.round(c.extra[0], 3).tobytes())
    h.update(repr((c.size, tuple(c.origin), [(m, tuple(a), tuple(b), f) for m, a, b, f in c.paint_ops],
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
        tl = json.loads(bytes(d["tlmmeta"]).decode()) if "tlmmeta" in d else None
        if tl:
            tl["png"] = bytes(d["tlm"])
        return json.loads(bytes(d["meta"]).decode()), bytes(d["lm"]), d["dirr"], tl, d["rirr"]
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
    tl = None
    extra = {}
    if res["tlm"] is not None:
        t = res["tlm"]
        png = bake.png_bytes(t["img"])
        tl = dict(x0=t["x0"], z0=t["z0"], w=t["w"], d=t["d"], W=int(t["img"].shape[1]), H=int(t["img"].shape[0]))
        extra = dict(tlm=np.frombuffer(png, np.uint8), tlmmeta=np.frombuffer(json.dumps(tl).encode(), np.uint8))
        tl["png"] = png
    np.savez_compressed(f, meta=np.frombuffer(json.dumps(meta).encode(), np.uint8), lm=np.frombuffer(lm, np.uint8),
                        dirr=res["dirr"].astype(np.float32), rirr=res["rirr"].astype(np.float32), **extra)
    log(f"  {L.name}: baked in {time.time() - t0:.0f}s")
    return meta, lm, res["dirr"].astype(np.float32), tl, res["rirr"].astype(np.float32)


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

    def kit(self, name):
        key = "kit:" + name
        if key in self.cache:
            return self.cache[key]
        P, N, UV, T = decor_place.module(name)
        flag, sway = decor_place.vflags(name)
        irr = np.full((len(P), 3), 0.5)
        bone = decor_place.raw(name).get("bone")
        gid = self.reg(self.pk.add(P, N, UV, np.full(len(P), 40.0), np.where(flag > 4.5, sway, 1.0), irr=irr, flag=flag,
                                   tan=T[:, :3], bone=bone))
        hs, ctr = model_bounds(P)
        self.cache[key] = (gid, hs, ctr)
        return self.cache[key]


def build(world_path, out=None, log=print, cache=None):
    world_path = Path(world_path).resolve()
    game = load_game(world_path)
    props.configure(used_regions(game), high=game.textures == "high")
    if game.models or game.characters:
        from . import models as MD
        MD.import_models(game, world_path.parent, log)
    if game.player_model != "suit" and game.player_model not in decor_place.KINDS:
        raise SystemExit(f"unknown player_model '{game.player_model}'. Use suit, knight, mage, rogue, barbarian, "
                         f"or a name added with game.character(...)")
    out = Path(out) if out else world_path.parent / (safe_name(game.title) + ".sb3")
    cache = Path(cache) if cache else world_path.parent / ".loophole" / "cache"
    log(f"loophole {ENGINE_VERSION}: building '{game.title}' ({len(game.levels)} level{'s' * (len(game.levels) != 1)})")
    L = {k: [] for k in LIST_NAMES}
    for k in ["GTEX", "GB", "GC", "GH", "GIB", "GNC", "GOX", "GOY", "GOZ", "GR", "GIDW"]:
        L[k] = []
    groups = []
    lms = {}
    tlms = {}
    pkm = geo.Pack()
    models = Models(pkm, L)
    broadcasts = set(FIXED_BROADCASTS)
    from . import decor_pack
    tiles = set()
    for Lv in game.levels:
        tiles.update(d[0] for d in Lv.decor)
        tiles.update(o.model for o in Lv.objects if o.model in decor_place.KINDS)
    tiles.update(v for v in game.viewmodels if v in decor_place.KINDS)
    if game.player_model != "suit":
        tiles.add(game.player_model)
    if any(Lv.terrain_def for Lv in game.levels):
        tiles.add("grass")
    tiles = sorted(t for t in tiles if t in decor_pack.available())
    dlay, dimgs = decor_pack.build(tiles, 1024 if game.textures == "high" else 512, keep=game.viewmodels)
    decor_place.set_layout(dlay)
    used_ids = set()
    has_terrain = False
    for li, Lv in enumerate(game.levels, start=1):
        c = voxelize(Lv, li)
        meta, lm, dirr, tl, rirr = baked(c, Lv, cache, log)
        lms[li] = lm
        tlms[li] = tl
        P_, N_, UV_, M_, A_, S_, I_, F_, T_ = kit.build(c, meta, dirr)
        if c.terrain is not None:
            t = c.terrain
            RP, RN = t["ring"]
            parts = [(t["P"], t["N"], t["M"], t["S"], np.full((len(t["P"]), 3), 0.4), 4.0),
                     (RP, RN, np.full(len(RP), t["mat"]), np.zeros(len(RP)),
                      rirr if len(rirr) == len(RP) else np.full((len(RP), 3), 0.4), 3.0)]
            for (pp, nn, mm, ss, ii, fl) in parts:
                n = len(pp)
                P_, N_, UV_ = np.concatenate([P_, pp]), np.concatenate([N_, nn]), np.concatenate([UV_, np.zeros((n, 2))])
                M_, A_, S_ = np.concatenate([M_, mm]), np.concatenate([A_, np.ones(n)]), np.concatenate([S_, ss])
                I_, F_ = np.concatenate([I_, ii]), np.concatenate([F_, np.full(n, fl)])
                T_ = np.concatenate([T_, np.zeros((n, 3))])
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
    char_lists(L, game, models)
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
    proj = assemble(game, L, lms, gcost, gids, broadcasts, world_path, out, log, used_ids, has_terrain, tlms, dimgs)
    return proj


def safe_name(s):
    keep = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in s).strip()
    return keep or "game"


THM = {}
TPM = {}
LIST_NAMES = ["LNAME", "LH0", "LHN", "HAX", "HSG", "HPL", "HU0", "HU1", "HV0", "HV1", "HKILL", "HPORT", "LSX", "LSY",
              "LSZ", "LSYAW", "LSPIT", "LKILL", "LO0", "LON", "LT0", "LTN", "TNAME", "TKIND", "TARG", "TX0", "TY0",
              "TZ0", "TX1", "TY1", "TZ1", "LL0", "LLN", "LNM", "LTX", "LTY", "LTZ", "LTW", "LDDX", "LDDY", "LDDZ",
              "LDDW", "LCR", "LCG", "LCB", "LCW", "LDYN", "LLON", "LFLK", "LCUT", "LK0", "LKN", "KH", "KU0", "KU1", "KV0", "KV1", "LVN", "LHZ", "LHA", "LEXP", "LAE", "LGR", "LGG", "LGB", "LSAT",
              "AMB0", "AMBNX", "AMBNY", "AMBNZ", "AMBST", "AMBOX", "AMBOY", "AMBOZ", "AMB", "LPX", "LPY", "LPZ",
              "LB0X", "LB0Y", "LB0Z", "LB1X", "LB1Y", "LB1Z", "LFY", "LCY_", "LV0", "LVNN", "VX0", "VZ0", "VX1",
              "VZ1", "VY0", "VY1", "VPW", "LSP0", "LSPN", "SPX", "SPY", "SPZ", "LSKY", "LSUN", "LTER", "TOX", "TOZ",
              "TST", "TNX", "TNZ", "TH0", "THT", "DNAME", "DG", "DG2", "DPRX", "DPRY", "DPRS", "DPRT", "DPRX2",
              "DPRY2", "DPRS2", "DPRT2", "DBX", "DBY", "DBZ", "DBCX", "DBCY", "DBCZ", "DSX", "DSY", "DSZ", "DKIND",
              "DPHYS", "DCARRY", "DUSE", "DSHAD", "DSOLID", "DVIS", "DX", "DY", "DZ", "DYAW", "DPITCH", "DROLL",
              "DSCALE", "DGLOW", "DGR", "DGG", "DGB", "DHR", "DHG", "DHB", "DBOB", "DLNK", "DSLIDE", "DOSP", "DSPIN", "DCOLL", "DPN", "DP0",
              "DPSP", "DPLOOP", "DPFACE", "PWX", "PWY", "PWZ", "PLEN", "PCLOSE", "SKY", "TLMX", "TLMZ", "TLMW", "TLMD", "THX", "THZ", "THW", "THD", "THMN", "THRG", "GRX", "GRY", "GRW", "GRH", "LGRASS"]


def portal_blockers(L, Lv, c, rects, h0):
    boxes = []
    for lo, hi in decor_place.footprints(c):
        boxes.append((np.array(lo, float), np.array(hi, float)))
    for (x, y, z, n, h, text) in getattr(c, "signs", []):
        n = np.array(n, float)
        right = np.cross(-n, np.array([0.0, 1.0, 0.0]))
        w = (0.3 * len(text) + 0.3) * h
        p0 = np.array([x, y - 0.35 * h, z]) - np.abs(right) * w - np.abs(n) * 0.1
        p1 = np.array([x, y + 1.2 * h, z]) + np.abs(right) * w + np.abs(n) * 0.1
        boxes.append((np.minimum(p0, p1), np.maximum(p0, p1)))
    for (x0, y0, z0, x1, y1, z1, _) in getattr(c, "windows", []):
        boxes.append((np.array([min(x0, x1), min(y0, y1), min(z0, z1)]) - 0.15,
                      np.array([max(x0, x1), max(y0, y1), max(z0, z1)]) + 0.15))
    for o in Lv.objects:
        p = np.array(o.pos, float)
        boxes.append((p - np.array([0.7, 0.2, 0.7]), p + np.array([0.7, 2.2, 0.7])))
    uvax = {0: (2, 1), 1: (0, 2), 2: (0, 1)}
    L["LK0"].append(len(L["KH"]) + 1)
    n0 = len(L["KH"])
    for i, r in enumerate(rects):
        if r["mat"] not in PORTAL:
            continue
        ax = r["axis"]
        ua, va = uvax[ax]
        if ax == 0:
            ru0, ru1, rv0, rv1 = r["v0"], r["v1"], r["u0"], r["u1"]
        else:
            ru0, ru1, rv0, rv1 = r["u0"], r["u1"], r["v0"], r["v1"]
        for lo, hi in boxes:
            if not (lo[ax] - 0.35 <= r["pl"] <= hi[ax] + 0.35):
                continue
            u0, u1, v0, v1 = max(lo[ua], ru0), min(hi[ua], ru1), max(lo[va], rv0), min(hi[va], rv1)
            if u1 > u0 and v1 > v0:
                L["KH"].append(h0 + i)
                for k, v in zip(("KU0", "KU1", "KV0", "KV1"), (u0, u1, v0, v1)):
                    L[k].append(r4(v))
    L["LKN"].append(len(L["KH"]) - n0)


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
    portal_blockers(L, Lv, c, rects, len(L["HAX"]) + 1)
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
            q["on"] = 1.0 if dl.get("on", True) else 0.0
            q["flicker"] = float(dl.get("flicker", 0.0))
            lts.append(q)
    lts = sorted(lts, key=lambda q: (q["kind"] != "sun", -q["vol"], -int(q["dynamic"]), -int(bool(q.get("name")))))[:24]
    L["LL0"].append(len(L["LTX"]) + 1)
    L["LLN"].append(len(lts))
    L["LVN"].append(min(8, sum(1 for q in lts if q["vol"] > 0)))
    L["LHZ"].append(Lv.haze)
    L["LCUT"].append(r4(getattr(Lv, "cut", 0.0)))
    L["LHA"].append(Lv.haze_amb)
    L["LEXP"].append(Lv.exposure)
    L["LAE"].append(Lv.auto_exposure)
    L["LGR"].append(Lv.grade_rgb[0])
    L["LGG"].append(Lv.grade_rgb[1])
    L["LGB"].append(Lv.grade_rgb[2])
    L["LSAT"].append(Lv.saturation)
    for i, q in enumerate(lts):
        L["LNM"].append(q.get("name") or f"light{i + 1}")
        L["LFLK"].append(r4(q.get("flicker", 0.0)))
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
        L["LLON"].append(q.get("on", 1.0))
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
        fb = float(c.field.base) if getattr(c, "field", None) is not None else 0.0
        vals = [r4(x) for x in (*sd, *sp["sun"], *sp["zen"], Lv.clouds, *sp["hor"], 0.9996, *sp["ground"],
                                 *sp["fog"], Lv.fog or 0.0, fb, 0.04)]
    else:
        vals = [0.0] * 21
    L["SKY"].extend(vals + [0.0] * (24 - len(vals)))
    for k in ("TLMX", "TLMZ", "TLMW", "TLMD", "THX", "THZ", "THW", "THD", "THMN", "THRG", "GRX", "GRY", "GRW", "GRH",
              "LGRASS"):
        L[k].append(0)
    if c.terrain is not None:
        from . import terrain as T
        f = c.field
        res_ = 0.5
        xs2 = np.arange(f.x0, f.x1 + 1e-6, res_)
        zs2 = np.arange(f.z0, f.z1 + 1e-6, res_)
        X2, Z2 = np.meshgrid(xs2, zs2)
        H2 = f.inner(X2, Z2)
        dens, pm = T.masks(Lv.terrain_def, xs2, zs2, H2, getattr(f, "holes", []), res_)
        hmn, hmx = float(H2.min()) - 0.5, float(H2.max()) + 0.5
        q = np.clip(np.round((H2 - hmn) / (hmx - hmn) * 65535), 0, 65535).astype(np.int64)
        img = np.stack([(q >> 8) & 255, q & 255, np.round(dens * 255)], -1).astype(np.uint8)
        from PIL import Image
        b = io.BytesIO()
        Image.fromarray(img, "RGB").save(b, "PNG")
        THM[c.level_index] = (b.getvalue(), img.shape[1], img.shape[0])
        pimg = np.repeat(np.round(pm * 255).astype(np.uint8)[..., None], 3, -1)
        b2 = io.BytesIO()
        Image.fromarray(pimg, "RGB").save(b2, "PNG")
        TPM[c.level_index] = (b2.getvalue(), pimg.shape[1], pimg.shape[0])
        L["THX"][-1] = r4(xs2[0])
        L["THZ"][-1] = r4(zs2[0])
        L["THW"][-1] = r4(1.0 / (xs2[-1] - xs2[0]))
        L["THD"][-1] = r4(1.0 / (zs2[-1] - zs2[0]))
        L["THMN"][-1] = r4(hmn)
        L["THRG"][-1] = r4(hmx - hmn)
        lay = decor_place.LAYOUT
        if "grass" in lay["layout"] and Lv.terrain_def.get("grass", 1.0) > 0:
            gx, gy, gs = lay["layout"]["grass"]
            L["GRX"][-1] = r4(gx / lay["PW"])
            L["GRY"][-1] = r4(gy / lay["PH"])
            L["GRW"][-1] = r4(gs / lay["PW"])
            L["GRH"][-1] = r4(gs / lay["PH"])
            L["LGRASS"][-1] = 1
    if Lv.sky and c.field is not None:
        f = c.field
        for (lo, hi) in ((np.array([f.x0 - 1, -50, f.z0 - 1]), np.array([f.x0, 200, f.z1 + 1])),
                         (np.array([f.x1, -50, f.z0 - 1]), np.array([f.x1 + 1, 200, f.z1 + 1])),
                         (np.array([f.x0 - 1, -50, f.z0 - 1]), np.array([f.x1 + 1, 200, f.z0])),
                         (np.array([f.x0 - 1, -50, f.z1]), np.array([f.x1 + 1, 200, f.z1 + 1]))):
            for r in box_rects(lo, hi):
                ax = r["axis"]
                u0, u1, v0, v1 = (r["v0"], r["v1"], r["u0"], r["u1"]) if ax == 0 else (r["u0"], r["u1"], r["v0"], r["v1"])
                L["HAX"].append(ax + 1)
                L["HSG"].append(r["sgn"])
                L["HPL"].append(r4(r["pl"]))
                L["HU0"].append(r4(u0))
                L["HU1"].append(r4(u1))
                L["HV0"].append(r4(v0))
                L["HV1"].append(r4(v1))
                L["HKILL"].append(0)
                L["HPORT"].append(0)
                L["LHN"][-1] += 1
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
    hl = color(o.highlight) if o.highlight else (0.0, 0.0, 0.0)
    for k, v in zip(["DHR", "DHG", "DHB"], hl):
        L[k].append(r4(v * 0.9))
    L["DBOB"].append(r4(o.bob))
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
    man = json.loads((DATA / "sfx" / "manifest.json").read_text(encoding="utf-8"))
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
        srcs.append(p.read_text(encoding="utf-8"))
    if not srcs:
        return None
    src = "\n\n".join(srcs)
    al = dict(USER_ALIASES)
    for g in game.globals:
        al[g.replace(" ", "_")] = g
    c = Compiler(proj, src, list(API_LISTS.values()), consts=consts, aliases=al)
    blocks = c.compile()
    return {"isStage": False, "name": "Game", "variables": {vid: [n, 0] for n, vid in c.new_vars.items()},
            "lists": {lid: [n, []] for n, lid in c.new_lists.items()}, "broadcasts": {}, "blocks": blocks,
            "comments": {}, "currentCostume": 0,
            "costumes": [A.svg("blank", '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"></svg>', 1, 1)],
            "sounds": [], "volume": 100, "layerOrder": 3, "visible": False, "x": 0, "y": 0, "size": 100,
            "direction": 90, "draggable": False, "rotationStyle": "don't rotate"}


def used_regions(game):
    regs = set()
    for Lv in game.levels:
        for o in Lv.objects:
            b = props.BUILTIN.get(o.model)
            if b:
                regs.add(b["region"])
                if b.get("top"):
                    regs.add(b["top"])
    for v in game.viewmodels:
        b = props.BUILTIN.get(v)
        if b:
            regs.add(b["region"])
    if game.viewmodels:
        regs.add("arms")
    if "device" in game.viewmodels:
        regs.add("device")
    if game.camera != 0 or game.scripts:
        regs.add("player")
    return regs


def placeholder_jpg():
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(b, "JPEG")
    return b.getvalue()


def assemble(game, L, lms, gcost, gids, broadcasts, world_path, out, log, used_ids=(), has_terrain=False, tlms=None,
             dimgs=None):
    A = Assets()
    proj = Project(global_names=list(API_VARS.values()) + list(game.globals), global_lists=list(API_LISTS.values()))
    for b in sorted(broadcasts):
        proj.bc_id(b)
    paw, pah = props.atlas_size()
    pcol = []
    for cname in game.portal_colors:
        cc = np.array(color(cname), float)
        pcol.append(tuple(r4(v) for v in cc / max(cc.max(), 1e-3)))
    consts = {"NLEV": len(game.levels), "START_LEVEL": max(1, min(len(game.levels), game.start_level)),
              "QUALITY": game.quality, "FOV": game.fov, "VMDEF": game.viewmodel,
              "CAM0": game.camera, "CDIST0": game.camera_distance, "CPITCH0": game.camera_pitch, "WALK": game.walk_speed, "JUMPV": game.jump_power, "GRAV": 20.0, "FRIC": 5.0, "STOPSPD": 1.9, "ACCEL": 10.0, "AIRACC": 12.0,
              "AIRCAP": 0.8, "STEPH": 0.55, "EYE": 1.6, "EYEC": 1.05, "PHT": 1.75, "PHTC": 1.2, "PW": 0.3,
              "ENVT": 192, "NEAR": 0.01, "FAR": 150.0, "SENS": 0.11, "EXPO": 0.72, "AMBS": 0.01, "HOLDD": 1.6,
              "USED": 2.6, "NSHAD": 4, "HASTER": 1 if has_terrain else 0, "PAW": paw, "PAH": pah,
              "CH0": 5, "PORTALS": 1 if game.portals_on else 0, "PORW": 0.62, "PORH": 1.02, "MAXD": 3, "MINA": 0.004,
              "COLAR": pcol[0][0], "COLAG": pcol[0][1], "COLAB": pcol[0][2], "COLBR": pcol[1][0], "COLBG": pcol[1][1],
              "COLBB": pcol[1][2],
              "CHAR": gids["char"], "CNJ": L.pop("_CNJ", 0), "CFPS": 15, "G_DEVICE": gids["device"], "G_ARMS": gids["arms"], "G_PLAYER": gids["player"]}
    for n in ("device", "arms", "player"):
        x, y, s, t = props.region(n)
        consts.update({f"PR_{n.upper()}_X": x, f"PR_{n.upper()}_Y": y, f"PR_{n.upper()}_S": s, f"PR_{n.upper()}_T": t})
    L["FADV"] = json.loads((DATA / "font.json").read_text(encoding="utf-8"))["adv"]
    L["JX"] = [0.5, 0.25, 0.75, 0.125, 0.625, 0.375, 0.875, 0.0625]
    L["JY"] = [0.3333, 0.6667, 0.1111, 0.4444, 0.7778, 0.2222, 0.5556, 0.8889]
    src = expand_mklist((HERE / "runtime" / "engine.py").read_text(encoding="utf-8"))
    gc = Compiler(proj, src, list(API_LISTS.values()), consts=consts, aliases=ALIASES)
    gblocks = gc.compile()
    eng_lists = {}
    from . import mesh as M
    meshes = {"QUAD": M.quad_mesh(), "DUST": M.particles(320, 5), "IMPACT": M.particles(56, 21),
              "VENTP": M.particles(140, 13), "GRASS": M.grass_cards(3000, 9), "TEXT": M.text_quads(128), "DISC": M.portal_disc()}
    for name, m in meshes.items():
        eng_lists[proj.uid("l")] = [name, m.items()]
    eng_lists[proj.uid("l")] = ["IC", geo.index_items(geo.CHUNK)]
    eng_lists[proj.uid("l")] = ["ICS", geo.index_items(geo.SCHUNK)]
    for name, lid in gc.new_lists.items():
        if name in ("IC", "ICS") or name in meshes:
            continue
        eng_lists[lid] = [name, L.get(name, [])]
    blank = A.svg("blank", '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2" viewBox="0 0 2 2"></svg>', 1, 1)
    mj = json.loads((DATA / "atlas" / "materials.json").read_text(encoding="utf-8"))
    from . import texpack
    matimgs, atlas_src, _ = texpack.build(used_ids, has_terrain, high=game.textures == "high")
    d1, w1, h1 = matimgs[1]
    costumes = [blank, A.bitmap("atlas", d1, "jpg", w1, h1),
                A.bitmap("patlas", props.atlas_bytes(), "jpg", paw, pah),
                A.bitmap("font", (DATA / "font.png").read_bytes(), "png", 1024, 576)]
    for i in range(33, 127):
        costumes.append(dict(blank, name="ch" + chr(i)))
    for nm, k in (("atlas2", 2), ("atlas3", 3)):
        if matimgs[k]:
            costumes.append(A.bitmap(nm, *matimgs[k][:1], "jpg", *matimgs[k][1:]))
        else:
            costumes.append(A.bitmap(nm, placeholder_jpg(), "jpg", 8, 8))
    for nm in ("dA", "dN", "dR"):
        data, w, h = dimgs[nm]
        costumes.append(A.bitmap(nm, data, "jpg", w, h))
    for li, data in lms.items():
        costumes.append(A.bitmap(f"lm{li}", data, "png", bake.LMW, bake.LMH * 3))
    for li in range(1, len(game.levels) + 1):
        for pre, store in (("thm", THM), ("tpm", TPM)):
            if li in store:
                data, w, h = store[li]
                costumes.append(A.bitmap(f"{pre}{li}", data, "png", w, h))
            else:
                costumes.append(A.bitmap(f"{pre}{li}", placeholder_jpg(), "jpg", 8, 8))
    for li, tl in (tlms or {}).items():
        if tl:
            costumes.append(A.bitmap(f"tlm{li}", tl["png"], "png", tl["W"], tl["H"]))
            L["TLMX"][li - 1:li] = [r4(tl["x0"])]
            L["TLMZ"][li - 1:li] = [r4(tl["z0"])]
            L["TLMW"][li - 1:li] = [r4(1.0 / max(tl["w"], 1e-3))]
            L["TLMD"][li - 1:li] = [r4(1.0 / max(tl["d"], 1e-3))]
        else:
            costumes.append(A.bitmap(f"tlm{li}", placeholder_jpg(), "jpg", 8, 8))
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
    api_values = {"message": "", "status": "", "viewmodel": game.viewmodel, "controls": 1, "camera mode": game.camera, "field of view": game.fov,
                  "exposure": 1, "walk speed": game.walk_speed, "jump power": game.jump_power, "gravity": 20.0,
                  "camera distance": game.camera_distance, "camera pitch": game.camera_pitch,
                  "level": game.start_level}
    shader_store = {name: {"projectData": {"vertShader": vs.replace(shaders.ATLAS, atlas_src),
                                           "fragShader": fs.replace(shaders.ATLAS, atlas_src)},
                           "modifyDate": 1763400000000}
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
        elif name in decor_place.KINDS:
            g, hs, ctr = models.kit(name)
            pr = (0, 0, 0, 0)
            sc = 0.2 / max(hs.max() * 2, 1e-3)
            off = (0.07 - ctr[0] * sc, -0.1 - ctr[1] * sc, 0.12 - ctr[2] * sc)
            arms = 1 if game.viewmodel_arms else 0
            glow = (1.0, 0.75, 0.45)
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


def char_lists(L, game, models):
    L["CBM"] = []
    L["CCL"] = []
    if game.player_model == "suit":
        L["_G"]["char"] = 0
        L["_CNJ"] = 0
        return
    from . import character
    gid, _, _ = models.kit(game.player_model)
    L["_G"]["char"] = gid
    a = np.load(character.anim_path(game.player_model))
    fr = a["frames"]
    L["_CNJ"] = int(fr.shape[1])
    L["CBM"] = [r4(v) for v in fr.reshape(-1)]
    for s, n in a["clips"]:
        L["CCL"] += [int(s), int(n)]


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
    api_v = {proj.var_id(n): n for n in list(API_VARS.values()) + list(game.globals)}
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
        monitors = [m for m in po.get("monitors", []) if not m.get("loophole")]
        have = {m.get("id") for m in monitors}
        monitors += [m for m in hud_monitors(proj, game) if m["id"] not in have]
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
        monitors = hud_monitors(proj, game)
    for i, t in enumerate(targets):
        t["layerOrder"] = i
    ext_urls.update({"penP": PENP_URL, "pointerlock": PLOCK_URL})
    ext_store["penP"] = {"shaders": shader_store, "version": "7.1.9",
                         "prefixes": {"penPlusTextures": "", "renderTextures": ""}}
    return {"targets": targets, "monitors": monitors, "extensions": exts, "extensionURLs": ext_urls,
            "extensionStorage": ext_store,
            "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": f"loophole {ENGINE_VERSION}",
                     "platform": {"name": "TurboWarp", "url": "https://turbowarp.org/"}}}


def hud_monitors(proj, game):
    out = []
    for i, n in enumerate(game.hud):
        out.append({"id": proj.var_id(n), "mode": "default", "opcode": "data_variable", "params": {"VARIABLE": n},
                    "spriteName": None, "value": 0, "width": 0, "height": 0, "x": 8, "y": 8 + i * 30,
                    "visible": True, "sliderMin": 0, "sliderMax": 100, "isDiscrete": True})
    return out


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
