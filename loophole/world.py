import math

import numpy as np

from . import level as lvl
from .materials import resolve

FACINGS = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1),
           "x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1), "up": (0, 1, 0), "down": (0, -1, 0),
           "east": (1, 0, 0), "west": (-1, 0, 0), "north": (0, 0, -1), "south": (0, 0, 1)}

FLOOR_PROPS = {"crate", "barrel", "machine", "tank", "rack", "terminal", "trolley", "reel", "toolbox", "ramp", "column",
               "catwalk", "tray"}

COLORS = {"white": (1.0, 0.97, 0.92), "warm": (1.0, 0.82, 0.6), "cool": (0.8, 0.9, 1.0), "red": (1.0, 0.2, 0.1),
          "orange": (1.0, 0.55, 0.2), "amber": (1.0, 0.7, 0.3), "green": (0.35, 1.0, 0.45),
          "blue": (0.35, 0.6, 1.0), "cyan": (0.3, 0.9, 1.0), "purple": (0.7, 0.4, 1.0), "pink": (1.0, 0.4, 0.7),
          "yellow": (1.0, 0.9, 0.35), "sodium": (1.0, 0.62, 0.28), "daylight": (0.95, 0.97, 1.0),
          "gold": (1.0, 0.6, 0.1), "magenta": (1.0, 0.12, 0.8)}


def facing(f):
    if isinstance(f, str):
        if f not in FACINGS:
            raise ValueError(f"unknown facing '{f}'. Use one of +x -x +y -y +z -z")
        return FACINGS[f]
    v = np.array(f, float)
    return tuple(v / np.linalg.norm(v))


def color(c):
    if isinstance(c, str):
        if c.startswith("#") and len(c) == 7:
            return tuple(int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return COLORS[c]
    return tuple(float(x) for x in c)


def _box(x0, y0, z0, x1, y1, z1):
    return (min(x0, x1), min(y0, y1), min(z0, z1), max(x0, x1), max(y0, y1), max(z0, z1))


class Obj:
    def __init__(self, name, model, pos, yaw=0.0, pitch=0.0, roll=0.0, scale=1.0, size=(1, 1, 1), visible=True,
                 solid=True, physics=False, carry=False, use=False, shadow=True, glow=1.0, glow_color=None,
                 collect=False, spin=0.0, path=None, speed=2.0, loop=True, face_path=True, kind=0, opens=None,
                 slide=0.0, open_speed=0.8, texture=None, highlight=None, bob=0.0):
        self.__dict__.update(locals())
        del self.__dict__["self"]


class Level:
    def __init__(self, game, name):
        self.game = game
        self.name = name
        self.ops = []
        self.paint_ops = []
        self.decor = []
        self.lights = []
        self.windows = []
        self.signs = []
        self.occluders = []
        self.open_panels = []
        self.objects = []
        self.triggers = []
        self.vents = []
        self.spark_pts = []
        self.buildings = []
        self.start = (0.0, 0.0, 0.0, 0.0)
        self.start_pitch = 0.0
        self.default_mats = {"floor": "floor", "ceil": "ceil", "wall": "white"}
        self.haze = 0.02
        self.haze_amb = 0.3
        self.exposure = 1.0
        self.auto_exposure = 0.5
        self.grade_rgb = (1.0, 1.0, 1.0)
        self.saturation = 1.0
        self.kill_height = None
        self.lit_windows = True
        self.window_style = "lab"
        self.style_name = "lab"
        self.beams = True
        self.stripe = True
        self.probe = None
        self.sky = None
        self.sun_light = None
        self.fog = None
        self.terrain_def = None
        self.open_faces = set()
        self.bake_quality = "normal"

    def style(self, name):
        presets = {
            "lab": dict(mats=("floor", "white", "ceil"), beams=True, stripe=True, win="lab", haze=0.02),
            "house": dict(mats=("wood", "plaster", "plaster"), beams=False, stripe=False, win="sky", haze=0.012),
            "dungeon": dict(mats=("cobble", "stone", "stone"), beams=False, stripe=False, win="sky", haze=0.03),
            "outdoor": dict(mats=("grass", "brick", "concrete"), beams=False, stripe=False, win="sky", haze=0.0),
            "plain": dict(mats=("concrete", "concrete", "concrete"), beams=False, stripe=False, win="sky", haze=0.01),
        }
        if name not in presets:
            raise ValueError(f"unknown style '{name}'. Styles: {', '.join(presets)}")
        p = presets[name]
        self.default_mats = {"floor": p["mats"][0], "wall": p["mats"][1], "ceil": p["mats"][2]}
        self.beams = p["beams"]
        self.stripe = p["stripe"]
        self.window_style = p["win"]
        self.haze = p["haze"]
        self.style_name = name
        return self

    def room(self, x0, y0, z0, x1, y1, z1, floor=None, walls=None, ceiling=None):
        b = _box(x0, y0, z0, x1, y1, z1)
        self.ops.append(("carve", b))
        for name, mat, facing_ in (("floor", floor, (0, 1, 0)), ("ceiling", ceiling, (0, -1, 0))):
            if mat:
                y = b[1] if name == "floor" else b[4]
                self.paint_ops.append((resolve(mat), np.array([b[0], y, b[2]]), np.array([b[3], y, b[5]]), facing_))
        if walls:
            self.paint_ops.append((resolve(walls), np.array([b[0], b[1], b[2]]), np.array([b[3], b[4], b[5]]), "walls"))
        return self

    def hole(self, x0, y0, z0, x1, y1, z1):
        self.ops.append(("carve", _box(x0, y0, z0, x1, y1, z1)))
        return self

    def solid(self, x0, y0, z0, x1, y1, z1, material=None):
        b = _box(x0, y0, z0, x1, y1, z1)
        self.ops.append(("fill", b))
        if material:
            self.paint(material, *b)
        return self

    def platform(self, x0, z0, x1, z1, height, y=0.0, material=None):
        return self.solid(x0, y, z0, x1, y + height, z1, material=material)

    def stairs(self, x0, z0, x1, z1, height, direction="+z", y=0.0, step=0.5, material=None):
        n = max(1, int(round(height / step)))
        d = facing(direction)
        for k in range(n):
            f0 = k / n
            if abs(d[2]) > 0.5:
                za = z0 + (z1 - z0) * f0 if d[2] > 0 else z1 - (z1 - z0) * f0
                b = (x0, y, min(za, z1 if d[2] > 0 else z0), x1, y + step * (k + 1), max(za, z1 if d[2] > 0 else z0))
            else:
                xa = x0 + (x1 - x0) * f0 if d[0] > 0 else x1 - (x1 - x0) * f0
                b = (min(xa, x1 if d[0] > 0 else x0), y, z0, max(xa, x1 if d[0] > 0 else x0), y + step * (k + 1), z1)
            self.solid(*b, material=material)
        return self

    def paint(self, material, x0, y0, z0, x1, y1, z1, facing=None):
        f = None if facing is None else ("walls" if facing == "walls" else tuple(int(round(v)) for v in globals()["facing"](facing)))
        b = _box(x0, y0, z0, x1, y1, z1)
        self.paint_ops.append((resolve(material), np.array(b[:3]), np.array(b[3:]), f))
        return self

    def materials(self, floor=None, walls=None, ceiling=None):
        if floor:
            self.default_mats["floor"] = resolve(floor)
        if walls:
            self.default_mats["wall"] = resolve(walls)
        if ceiling:
            self.default_mats["ceil"] = resolve(ceiling)
        return self

    def building(self, x0, z0, x1, z1, height=3.0, y=0.0, walls="brick", inside="plaster", floor="wood",
                 ceiling="plaster", roof="roof", thickness=0.5, door=None, windows=(), door_size=(1.5, 2.5),
                 window_size=(2.0, 1.5), sill=1.0, foundation=1.5, roof_shape="gable", pitch=32.0, trim="wood",
                 sill_material="concrete", plinth="stone"):
        def sn(v):
            return round(v * 2) / 2
        x0, x1 = sn(min(x0, x1)), sn(max(x0, x1))
        z0, z1 = sn(min(z0, z1)), sn(max(z0, z1))
        y, height, thickness, sill = sn(y), max(sn(height), 2.0), max(sn(thickness), 0.5), sn(sill)
        door_size = (max(sn(door_size[0]), 1.0), sn(door_size[1]))
        window_size = (max(sn(window_size[0]), 0.5), max(sn(window_size[1]), 0.5))
        t = thickness
        top = y + height + 0.5
        self.solid(x0, y - foundation, z0, x1, top, z1, material=walls)
        self.paint(roof, x0, top, z0, x1, top, z1, facing="+y")
        self.ops.append(("carve", (x0 + t, y, z0 + t, x1 - t, y + height, z1 - t)))
        self.paint(inside, x0 + t, y + 0.01, z0 + t, x1 - t, y + height - 0.01, z1 - t, facing="walls")
        self.paint(floor, x0 + t, y, z0 + t, x1 - t, y, z1 - t, facing="+y")
        self.paint(ceiling, x0 + t, y + height, z0 + t, x1 - t, y + height, z1 - t, facing="-y")

        def opening(side, at, w, h, bottom):
            at = sn(at - w / 2) + w / 2
            if side in ("-z", "+z"):
                zz = z0 if side == "-z" else z1 - t
                self.ops.append(("carve", (at - w / 2, y + bottom, zz, at + w / 2, y + bottom + h, zz + t)))
            else:
                xx = x0 if side == "-x" else x1 - t
                self.ops.append(("carve", (xx, y + bottom, at - w / 2, xx + t, y + bottom + h, at + w / 2)))
        ops = []
        if door:
            side, at = door
            opening(side, at, door_size[0], door_size[1], 0.0)
            ops.append((side, sn(at - door_size[0] / 2) + door_size[0] / 2, door_size[0], door_size[1], 0.0, "door"))
        for (side, at) in windows:
            opening(side, at, window_size[0], window_size[1], sill)
            ops.append((side, sn(at - window_size[0] / 2) + window_size[0] / 2, window_size[0], window_size[1], sill,
                        "window"))
        self.buildings.append(dict(x0=x0, z0=z0, x1=x1, z1=z1, y=y, t=t, height=height, top=top, openings=ops,
                                   walls=resolve(walls), roof=resolve(roof), roof_shape=roof_shape, pitch=pitch,
                                   trim=resolve(trim), sill=resolve(sill_material), plinth=resolve(plinth)))
        return self

    def pool(self, material, x0, z0, x1, z1, y=0.0, depth=1.5):
        self.ops.append(("carve", _box(x0, y - depth, z0, x1, y, z1)))
        self.paint(material, x0, y - depth, z0, x1, y - depth + 0.01, z1, facing="+y")
        self.pool_walls = getattr(self, "pool_walls", []) + [(x0, y - depth, z0, x1, y, z1)]
        return self

    def spawn(self, x, y, z, yaw=0.0, pitch=0.0):
        self.start = (float(x), float(y), float(z), float(yaw))
        self.start_pitch = float(pitch)
        return self

    def cutaway(self, height=2.4):
        self.cut = float(height)
        return self

    def light(self, x, y, z, color="white", power=8.0, fixture="cage", facing="-y", dynamic=False, name=None,
              haze=0.0, on=True, flicker=0.0):
        n = np.array(globals()["facing"](facing), float)
        if fixture == "cage":
            if abs(n[1]) < 0.9:
                self.deco("cage", (x, y, z), tuple(np.cross((0, 1, 0), n)), tuple(n))
            else:
                self.deco("cage", (x, y, z), (1, 0, 0), tuple(n))
        p = tuple(np.array([x, y, z], float) + n * 0.11)
        self.lights.append(dict(kind="point", p=p, d=tuple(n), size=(0.05, 0.05), col=color_(color), power=power,
                                vol=haze, dynamic=dynamic, name=name, on=on))
        if flicker > 0 and not dynamic:
            self.lights.append(dict(kind="point", p=p, d=tuple(n), size=(0.05, 0.05), col=color_(color),
                                    power=power * 0.45, vol=0.0, dynamic=True, name=None, on=on, flicker=flicker))
        elif flicker > 0:
            self.lights[-1]["flicker"] = flicker
        return self

    def spot(self, x, y, z, target, color="white", power=40.0, cone=(18, 32), haze=1.0, fixture=True, dynamic=False,
             name=None, size=0.07):
        pos = np.array([x, y, z], float)
        d = np.array(target, float) - pos
        d /= np.linalg.norm(d)
        if fixture:
            self.deco("spot", pos - d * 0.1, d, (0, 1, 0))
        self.lights.append(dict(kind="spot", p=tuple(pos + d * 0.02), d=tuple(d), size=(size, size), col=color_(color),
                                power=power, cone=cone, vol=haze, fixture=fixture, dynamic=dynamic, name=name))
        return self

    def strip(self, x0, y0, z0, x1, y1, z1, color="cool", power=8.0, facing="-y", haze=0.0, name=None):
        p0 = np.array([x0, y0, z0], float)
        p1 = np.array([x1, y1, z1], float)
        L = np.linalg.norm(p1 - p0)
        u = (p1 - p0) / L
        n = max(1, int(round(L)))
        f = np.array(globals()["facing"](facing), float)
        for k in range(n):
            c = p0 + u * (k + 0.5) * L / n
            self.deco("strip", c, u, tuple(-f), (L / n, 1, 1))
        self.lights.append(dict(kind="strip", p=tuple((p0 + p1) / 2 + f * 0.01), d=tuple(f), u=tuple(u),
                                size=(L / 2, 0.03), col=color_(color), power=power, vol=haze, name=name))
        return self

    def ceiling_light(self, x, y, z, width=1.5, depth=1.5, color="white", power=4.6, name=None):
        self.lights.append(dict(kind="panel", p=(x, y - 0.006, z), d=(0, -1, 0), size=(width / 2, depth / 2),
                                col=color_(color), power=power, name=name))
        return self

    def prop(self, kind, x, y, z, yaw=0.0, scale=1.0, solid=None, up=(0, 1, 0), seed=None, light=True, name=None,
             on=True, flicker=0.0):
        from . import library
        if light and kind in library.LIGHTS:
            off, col, pw = library.LIGHTS[kind]
            a = math.radians(yaw)
            o = (off[0] * math.cos(a) - off[2] * math.sin(a), off[1], off[0] * math.sin(a) + off[2] * math.cos(a))
            s_ = scale if isinstance(scale, (int, float)) else scale[1]
            self.light(x + o[0] * s_, y + o[1] * s_, z + o[2] * s_, color=col, power=pw * s_ * s_, fixture=None, haze=0.6,
                       dynamic=name is not None, name=name, on=on, flicker=flicker)
        if kind in library.TRUNK and (solid is None or solid):
            r = library.TRUNK[kind] * (scale if isinstance(scale, (int, float)) else scale[0])
            self.solid_boxes = getattr(self, "solid_boxes", []) + [(x - r, y, z - r, x + r, y + 6.0, z + r)]
            solid = False
        sc = (scale, scale, scale) if isinstance(scale, (int, float)) else tuple(scale)
        f = (math.cos(math.radians(yaw)), 0.0, math.sin(math.radians(yaw)))
        self.deco(kind, (x, y, z), f, up, sc)
        if solid if solid is not None else kind in library.SOLID:
            self.solid_props = getattr(self, "solid_props", []) + [len(self.decor) - 1]
        return self

    def wall_prop(self, kind, x, y, z, facing="+x", scale=1.0):
        n = np.array(globals()["facing"](facing), float)
        sc = (scale, scale, scale) if isinstance(scale, (int, float)) else tuple(scale)
        f = np.cross(np.array([0.0, 1.0, 0.0]), n)
        if np.linalg.norm(f) < 1e-6:
            f = np.array([1.0, 0.0, 0.0])
        self.deco(kind, (x, y, z), tuple(f), tuple(n), sc)
        return self

    def deco(self, name, pos, fwd=(1, 0, 0), up=(0, 1, 0), scale=(1, 1, 1)):
        from . import decor_place
        if name not in decor_place.KINDS and name not in self.game.models:
            raise ValueError(f"unknown prop '{name}'. Built-in props: {', '.join(decor_place.KINDS)}")
        self.decor.append((name, tuple(map(float, pos)), tuple(map(float, fwd)), tuple(map(float, up)),
                           tuple(map(float, scale))))

    def pipe(self, *points, radius=1.0):
        pts = [np.array(p, float) for p in points]
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            d = b - a
            L = np.linalg.norm(d)
            u = d / L
            n = max(1, int(round(L / 2)))
            up = (0, 1, 0) if abs(u[1]) < 0.9 else (1, 0, 0)
            for k in range(n):
                c = a + u * ((k + 0.5) * L / n)
                self.deco("pipe", c, u, up, (L / n / 2, radius, radius))
        return self

    def catwalk(self, x0, y, z0, x1, z1, rails="both"):
        a = np.array([x0, y, z0], float)
        b = np.array([x1, y, z1], float)
        L = np.linalg.norm(b - a)
        u = (b - a) / L
        n = max(1, int(round(L / 2)))
        side = np.cross(u, np.array([0.0, 1.0, 0.0]))
        on = {"both": (True, True), "left": (True, False), "right": (False, True), "none": (False, False)}[rails]
        for k in range(n):
            c = a + u * (k + 0.5) * L / n
            self.deco("catwalk", c, u, (0, 1, 0), (L / n / 2, 1, 1))
            for sd, o in zip((-1, 1), on):
                if o:
                    self.deco("railing", c + side * sd * 0.5, u, (0, 1, 0), (L / n / 2, 1, 1))
        lo = np.minimum(a, b) - np.abs(side) * 0.5 - np.array([0, 0.18, 0])
        hi = np.maximum(a, b) + np.abs(side) * 0.5
        self.occluders.append(tuple(lo) + tuple(hi))
        self.solid_boxes = getattr(self, "solid_boxes", []) + [tuple(lo + np.array([0, 0.1, 0])) + tuple(hi)]
        return self

    def column(self, x, z, y0, y1, facing="+x"):
        n = max(1, int(round(y1 - y0)))
        h = (y1 - y0) / n
        for k in range(n):
            self.deco("column", (x, y0 + (k + 0.5) * h, z), globals()["facing"](facing), (0, 1, 0), (1, h, 1))
        return self

    def window(self, x0, y0, z0, x1, y1, z1, facing):
        self.windows.append((x0, y0, z0, x1, y1, z1, globals()["facing"](facing)))
        return self

    def sign(self, text, x, y, z, facing="+z", height=1.6):
        bad = sorted(set(ch for ch in str(text) if not (32 <= ord(ch) < 127)))
        if bad:
            raise ValueError(f"sign text can use letters, digits and basic punctuation, not {' '.join(bad)}")
        self.signs.append((x, y, z, globals()["facing"](facing), height, str(text)))
        return self

    def sparks(self, x, y, z):
        self.spark_pts.append((x, y, z))
        return self

    def vent(self, x0, z0, x1, z1, y=0.0, height=6.0, power=1.0):
        self.vents.append((x0, z0, x1, z1, y, y + height, power))
        self.paint("hazard", x0 - 0.5, y - 0.01, z0 - 0.5, x1 + 0.5, y + 0.01, z1 + 0.5, facing="+y")
        self.paint("vent", x0, y - 0.01, z0, x1, y + 0.01, z1, facing="+y")
        cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
        self.spot(cx, y + 0.05, cz, (cx, y + 5.0, cz), color=(0.6, 0.85, 1.0), power=26.0 * power, cone=(22, 34),
                  fixture=False)
        return self

    def object(self, name, model, x, y, z, **kw):
        if any(o.name == name for o in self.objects):
            raise ValueError(f"{self.name}: object name '{name}' is used twice")
        o = Obj(name, model, (float(x), float(y), float(z)), **kw)
        self.objects.append(o)
        return o

    def cube(self, name, x, y, z, **kw):
        kw.setdefault("physics", True)
        kw.setdefault("carry", True)
        return self.object(name, "cube", x, y, z, **kw)

    def door(self, name, x, y, z, facing="+z", width=2.0, height=3.0, **kw):
        n = globals()["facing"](facing)
        yaw = math.degrees(math.atan2(n[0], n[2])) if abs(n[1]) < 0.9 else 0.0
        kw.setdefault("shadow", True)
        return self.object(name, "door", x, y + height / 2, z, yaw=yaw, size=(width / 2, height / 3, 1.0), kind=1,
                           slide=height * 0.98, **kw)

    def button(self, name, x, y, z, opens=None, **kw):
        kw.setdefault("solid", False)
        kw.setdefault("shadow", False)
        return self.object(name, "button", x, y, z, kind=2, opens=opens, **kw)

    def pickup(self, name, model, x, y, z, **kw):
        kw.setdefault("collect", True)
        kw.setdefault("solid", False)
        kw.setdefault("spin", 90.0)
        kw.setdefault("shadow", False)
        kw.setdefault("highlight", "gold")
        kw.setdefault("bob", 0.12)
        return self.object(name, model, x, y, z, **kw)

    def trigger(self, name, x0, y0, z0, x1, y1, z1):
        self.triggers.append(dict(name=name, box=_box(x0, y0, z0, x1, y1, z1), kind=0, to=0))
        return self

    def goal(self, x0, y0, z0, x1, y1, z1, to=None, name="goal", paint=True):
        self.triggers.append(dict(name=name, box=_box(x0, y0, z0, x1, y1, z1), kind=2, to=to or 0))
        if paint:
            b = _box(x0, y0, z0, x1, y1, z1)
            self.paint("exit", b[0], b[1], b[2], b[3], b[1] + 0.01, b[5], facing="+y")
        return self

    def hazard(self, x0, y0, z0, x1, y1, z1, name="hazard"):
        self.triggers.append(dict(name=name, box=_box(x0, y0, z0, x1, y1, z1), kind=1, to=0))
        return self

    def wind(self, direction=(1.0, 0.35), strength=1.0):
        d = np.array(direction, float)
        d = d / max(np.linalg.norm(d), 1e-6)
        self.wind_def = (float(d[0]), float(d[1]), float(strength))
        return self

    def grade(self, r=1.0, g=1.0, b=1.0, saturation=1.0, exposure=None, auto_exposure=None):
        self.grade_rgb = (r, g, b)
        self.saturation = saturation
        if exposure is not None:
            self.exposure = exposure
        if auto_exposure is not None:
            self.auto_exposure = auto_exposure
        return self

    def outdoor(self, sky="day", sun=(0.4, 0.75, 0.3), sun_color=None, fog=0.0035, clouds=0.45):
        self.sky = sky
        self.sun_dir = tuple(np.array(sun, float) / np.linalg.norm(sun))
        self.sun_color = sun_color
        self.fog = fog
        self.clouds = clouds
        self.open_faces = {(1, -1)}
        self.haze = 0.0
        self.beams = False
        self.stripe = False
        self.window_style = "sky"
        return self

    GRASS_STYLES = {"lawn": (0.75, 1.15, 0.0, 0.02), "meadow": (1.45, 1.0, 0.1, 0.12), "dry": (1.1, 0.8, 0.85, 0.02),
                    "forest": (0.9, 0.55, 0.15, 0.04)}

    def terrain(self, x0, z0, x1, z1, height=None, base=0.0, step=1.0, material="terrain", seed=1, hills=4.0, grass=1.0,
                grass_style="lawn"):
        if grass_style not in self.GRASS_STYLES:
            raise ValueError(f"grass_style must be one of {', '.join(self.GRASS_STYLES)}")
        self.terrain_def = dict(x0=x0, z0=z0, x1=x1, z1=z1, height=height, base=base, step=step, material=material,
                                seed=seed, hills=hills, flats=[], paths=[], grass=grass, grass_style=grass_style)
        return self

    def path(self, *points, width=2.0, material="gravel"):
        if not self.terrain_def:
            raise ValueError("call level.terrain(...) before level.path(...)")
        self.terrain_def.setdefault("paths", []).append(([tuple(map(float, p)) for p in points], float(width), material))
        return self

    def _blocked(self, x, z, margin):
        for b in self.buildings:
            if b["x0"] - margin < x < b["x1"] + margin and b["z0"] - margin < z < b["z1"] + margin:
                return True
        sx, _, sz, _ = self.start
        if (x - sx) ** 2 + (z - sz) ** 2 < (margin + 2.0) ** 2:
            return True
        for pts, w, _ in (self.terrain_def or {}).get("paths", []):
            for a, b in zip(pts, pts[1:]):
                ax, az, bx, bz = a[0], a[1], b[0], b[1]
                dx, dz = bx - ax, bz - az
                L2 = dx * dx + dz * dz or 1e-9
                t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L2))
                if (x - ax - dx * t) ** 2 + (z - az - dz * t) ** 2 < (w / 2 + margin) ** 2:
                    return True
        for o in self.objects:
            if (x - o.pos[0]) ** 2 + (z - o.pos[2]) ** 2 < (margin + 0.8) ** 2:
                return True
        return False

    def scatter(self, kinds, x0, z0, x1, z1, spacing=3.0, scale=(0.8, 1.2), seed=0, clearance=0.8, fill=1.0,
                taken=None):
        import random
        rng = random.Random(seed)
        kinds = [kinds] if isinstance(kinds, str) else list(kinds)
        weights = None
        if kinds and isinstance(kinds[0], (tuple, list)):
            weights = [w for _, w in kinds]
            kinds = [k for k, _ in kinds]
        x0, x1 = min(x0, x1), max(x0, x1)
        z0, z1 = min(z0, z1), max(z0, z1)
        cell = spacing / 1.4142
        grid = {}
        pts = list(taken or [])
        for (px, pz, r) in pts:
            for ix in range(int(px // cell) - 1, int(px // cell) + 2):
                for iz in range(int(pz // cell) - 1, int(pz // cell) + 2):
                    grid.setdefault((ix, iz), [])
            grid.setdefault((int(px // cell), int(pz // cell)), []).append((px, pz, r))
        tries = int((x1 - x0) * (z1 - z0) / (spacing * spacing) * 4 * fill) + 8
        placed = []
        for _ in range(tries):
            x, z = rng.uniform(x0, x1), rng.uniform(z0, z1)
            if self._blocked(x, z, clearance):
                continue
            gx, gz = int(x // cell), int(z // cell)
            ok = True
            for ix in range(gx - 2, gx + 3):
                for iz in range(gz - 2, gz + 3):
                    for (qx, qz, r) in grid.get((ix, iz), []):
                        lim = spacing if r is None else r
                        if (x - qx) ** 2 + (z - qz) ** 2 < lim * lim:
                            ok = False
            if not ok:
                continue
            grid.setdefault((gx, gz), []).append((x, z, None))
            kind = rng.choices(kinds, weights)[0] if weights else rng.choice(kinds)
            self.prop(kind, x, 0, z, yaw=rng.uniform(0, 360), scale=rng.uniform(*scale))
            placed.append((x, z, spacing))
        return placed

    FORESTS = {
        "mixed": [("oak", 3), ("birch", 2), ("pine", 2), ("spruce", 2)],
        "broadleaf": [("oak", 3), ("birch", 2)],
        "pine": [("pine", 3), ("spruce", 2)],
        "birch": [("birch", 4), ("oak", 1)],
    }

    def forest(self, x0, z0, x1, z1, kind="mixed", density=1.0, undergrowth=True, seed=1):
        if kind not in self.FORESTS:
            raise ValueError(f"forest kind must be one of {', '.join(self.FORESTS)}")
        d = max(0.2, float(density))
        trees = self.scatter(self.FORESTS[kind], x0, z0, x1, z1, spacing=3.8 / d ** 0.5, scale=(0.8, 1.25),
                             seed=seed, clearance=1.2)
        if undergrowth:
            taken = [(x, z, 1.4) for x, z, _ in trees]
            under = [("bush", 3), ("fern", 4), ("grass", 3)]
            if "log" in self._kinds():
                under.append(("log", 1))
            self.scatter(under, x0, z0, x1, z1, spacing=2.2 / d ** 0.5, scale=(0.7, 1.2), seed=seed + 1,
                         clearance=0.4, taken=taken)
            self.scatter([("boulder", 1), ("rock", 2), ("stump", 1)], x0, z0, x1, z1, spacing=9.0, scale=(0.5, 1.1),
                         seed=seed + 2, clearance=0.6, fill=0.5, taken=taken)
        return self

    def _kinds(self):
        from . import decor_place
        return set(decor_place.KINDS)

    def flatten(self, x0, z0, x1, z1, height=0.0, falloff=6.0):
        if not self.terrain_def:
            raise ValueError("call level.terrain(...) before level.flatten(...)")
        self.terrain_def["flats"].append((min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1), height, falloff))
        return self


def color_(c):
    return color(c)


class Game:
    def __init__(self, title="My Game", viewmodel="none", viewmodels=None, hand_color="cyan", quality=3, fov=72,
                 start_level=1, hands=None, camera="first person", camera_distance=4.0, walk_speed=6.0,
                 jump_power=7.0, textures="normal", viewmodel_arms=False, camera_pitch=None, player_model="suit",
                 portals=False, auto_quality=True):
        self.title = title
        self.auto_quality = bool(auto_quality)
        self.portals_on = bool(portals)
        self.portal_colors = ("cyan", "magenta")
        self.player_model = player_model
        self.characters = {}
        self.camera_pitch = camera_pitch if camera_pitch is not None else (60.0 if camera == "top down" else 20.0)
        self.viewmodel_arms = viewmodel_arms
        if textures not in ("normal", "high"):
            raise ValueError("textures must be 'normal' or 'high'")
        self.textures = textures
        cams = {"first person": 0, "free": 1, "third person": 2, "top down": 3}
        if camera not in cams:
            raise ValueError(f"camera must be one of {', '.join(cams)}")
        self.camera = cams[camera]
        self.camera_distance = camera_distance
        self.walk_speed = walk_speed
        self.jump_power = jump_power
        if hands is not None:
            viewmodel = "device" if hands else "none"
        self.viewmodel = viewmodel
        self.viewmodels = [v for v in dict.fromkeys([viewmodel] + list(viewmodels or [])) if v != "none"]
        self.hand_color = color(hand_color)
        self.quality = quality
        self.fov = fov
        self.start_level = start_level
        self.levels = []
        self.scripts = []
        self.models = {}
        self.globals = []
        self.hud = []

    def model(self, name, path, scale=1.0, texture=1024, up="y"):
        self.models[name] = dict(path=str(path), scale=scale, texture=texture, up=up)
        return self

    def character(self, name, path, height=1.8, keep=None, facing="+z"):
        self.characters[name] = dict(path=str(path), height=height, keep=keep, facing=facing)
        return self

    def portals(self, on=True, colors=("cyan", "magenta")):
        self.portals_on = bool(on)
        self.portal_colors = tuple(colors)
        return self

    def level(self, name):
        L = Level(self, name)
        self.levels.append(L)
        return L

    def script(self, path):
        self.scripts.append(path)
        return self

    def variable(self, name, show=False):
        if name not in self.globals:
            self.globals.append(name)
        if show and name not in self.hud:
            self.hud.append(name)
        return self
