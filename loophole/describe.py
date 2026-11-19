import ast
import inspect
import json
import math
import sys
from pathlib import Path

import numpy as np

from . import decor_place, lod
from . import world as W

LISTS = ("ops", "decor", "lights", "objects", "triggers", "signs", "windows")
GROUNDED = {"prop", "wall_prop", "light", "spot", "strip", "ceiling_light", "object", "cube", "door", "button",
            "pickup", "trigger", "goal", "hazard", "spawn"}


def _literal(node):
    try:
        return True, ast.literal_eval(node)
    except Exception:
        return False, None


def _jsonable(v):
    if isinstance(v, (bool, int, str)) or v is None:
        return v
    if isinstance(v, float):
        return round(v, 4) if math.isfinite(v) else None
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        return _jsonable(v.tolist())
    if isinstance(v, (np.floating, np.integer)):
        return _jsonable(v.item())
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return repr(v)


class _Src:
    def __init__(self, text):
        self.lines = text.splitlines(True)

    def ch(self, line, col):
        if line - 1 >= len(self.lines):
            return col
        return len(self.lines[line - 1].encode("utf-8")[:col].decode("utf-8", "ignore"))

    def span(self, node):
        return [node.lineno - 1, self.ch(node.lineno, node.col_offset),
                node.end_lineno - 1, self.ch(node.end_lineno, node.end_col_offset)]


def _instrument(path, records):
    depth = [0]
    saved = {}
    target = str(path)

    def wrap(name, fn):
        sig = inspect.signature(fn)

        def w(self, *a, **k):
            if depth[0] > 0:
                return fn(self, *a, **k)
            fr = sys._getframe(1)
            mine = fr.f_code.co_filename == target
            line = fr.f_lineno
            before = {n: len(getattr(self, n, None) or []) for n in LISTS}
            depth[0] += 1
            try:
                res = fn(self, *a, **k)
            finally:
                depth[0] -= 1
            if mine:
                try:
                    b = sig.bind(self, *a, **k)
                    b.apply_defaults()
                    args = {n: v for n, v in b.arguments.items() if n != "self"}
                except TypeError:
                    args = {}
                spans = {n: [before[n], len(getattr(self, n, None) or [])] for n in LISTS}
                records.append(dict(level=self, method=name, line=line, args=args, spans=spans, sig=sig))
            return res
        return w

    for name, fn in inspect.getmembers(W.Level, inspect.isfunction):
        if not name.startswith("_"):
            saved[name] = fn
            setattr(W.Level, name, wrap(name, fn))
    return saved


def _kind_mesh(kind):
    d = decor_place.raw(kind)
    P = np.asarray(d["pos"], float)
    fl, _ = decor_place.vflags(kind)
    ft = np.asarray(fl, float).reshape(-1, 3)[:, 0]
    tris = P.reshape(-1, 3, 3)
    solid = tris[ft < 4.5].reshape(-1, 3)
    if len(solid) // 3 > 500:
        res = lod.cluster(solid, np.arange(len(solid)).reshape(-1, 3))
        if res is not None and len(res[0]) >= 9:
            solid = res[0]
    if len(solid) // 3 > 900:
        solid = solid[: 900 * 3]
    out = {"solid": np.round(solid, 3).ravel().tolist()}
    cards = tris[ft >= 4.5].reshape(-1, 3)
    if len(cards):
        lo, hi = cards.min(0), cards.max(0)
        pad = 0.9 if (ft > 5.5).any() else 0.05
        out["crown"] = [round(float(x), 3) for x in np.concatenate([(lo + hi) / 2, (hi - lo) / 2 + pad])]
    lo, hi = P.min(0), P.max(0)
    out["bounds"] = [round(float(x), 3) for x in np.concatenate([lo, hi])]
    return out


def describe(path):
    from . import build as B
    from . import terrain as T
    path = Path(path).resolve()
    text = path.read_text(encoding="utf-8")
    src = _Src(text)
    tree = ast.parse(text)
    by_line = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            by_line.setdefault(node.lineno, []).append(node)
    stmts = {}
    var_last = {}
    level_vars = []
    for st in tree.body:
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call):
            stmts[id(st.value)] = [st.lineno - 1, st.end_lineno - 1]
        for node in ast.walk(st):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                var_last[node.func.value.id] = max(var_last.get(node.func.value.id, 0), st.end_lineno)
        if (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)
                and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Attribute)
                and st.value.func.attr == "level"):
            level_vars.append(st.targets[0].id)
            var_last.setdefault(st.targets[0].id, st.end_lineno)
    records = []
    saved = _instrument(path, records)
    try:
        game = B.load_game(path)
    finally:
        for name, fn in saved.items():
            setattr(W.Level, name, fn)
    seen = {}
    for r in records:
        seen[(r["line"], r["method"])] = seen.get((r["line"], r["method"]), 0) + 1
    calls = []
    for i, r in enumerate(records):
        li = game.levels.index(r["level"]) if r["level"] in game.levels else 0
        cand = [n for n in by_line.get(r["line"], []) if n.func.attr == r["method"]]
        node = cand[0] if len(cand) == 1 else None
        params = {}
        names = [p for p in r["sig"].parameters if p != "self"]
        kinds = {p.name: p.kind for p in r["sig"].parameters.values()}
        defaults = {p.name: p.default for p in r["sig"].parameters.values()
                    if p.default is not inspect.Parameter.empty}
        if node is not None:
            pos = [p for p in names if kinds[p] in (inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                                    inspect.Parameter.POSITIONAL_ONLY)]
            for k, a in enumerate(node.args):
                if isinstance(a, ast.Starred) or k >= len(pos):
                    break
                ok, _ = _literal(a)
                params[pos[k]] = dict(span=src.span(a), literal=ok)
            for kw in node.keywords:
                if kw.arg:
                    ok, _ = _literal(kw.value)
                    params[kw.arg] = dict(span=src.span(kw.value), literal=ok, kw=True)
        for n, v in r["args"].items():
            if kinds.get(n) == inspect.Parameter.VAR_KEYWORD:
                for kk, vv in v.items():
                    params.setdefault(kk, {})["value"] = _jsonable(vv)
            elif kinds.get(n) != inspect.Parameter.VAR_POSITIONAL:
                params.setdefault(n, {})["value"] = _jsonable(v)
        for n, v in defaults.items():
            if n in params and "default" not in params[n]:
                params[n]["default"] = _jsonable(v)
        editable = node is not None and seen[(r["line"], r["method"])] == 1
        names = [n for n in names if kinds[n] not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL)]
        c = dict(id=i, level=li, method=r["method"], line=r["line"] - 1, params=params, order=names,
                 editable=editable, var=node.func.value.id if node is not None else None)
        if node is not None:
            c["close"] = [node.end_lineno - 1, src.ch(node.end_lineno, node.end_col_offset) - 1]
            c["stmt"] = stmts.get(id(node))
        calls.append(c)
    levels = []
    used = set()
    for li, L in enumerate(game.levels):
        B.ground_relative(L)
        own = {n: [-1] * len(getattr(L, n, None) or []) for n in LISTS}
        for c, r in zip(calls, records):
            if r["level"] is not L:
                continue
            for n, (a, b) in r["spans"].items():
                for k in range(a, min(b, len(own[n]))):
                    own[n][k] = c["id"]
        lv = dict(name=L.name, var=level_vars[li] if li < len(level_vars) else None,
                  insert=var_last.get(level_vars[li], len(src.lines)) if li < len(level_vars) else len(src.lines),
                  outdoor=bool(L.terrain_def) or bool(L.sky_on))
        lv["boxes"] = [dict(op=op, b=_jsonable(b), call=own["ops"][k]) for k, (op, b) in enumerate(L.ops)]
        dec = []
        for k, (name, p, fw, up, sc) in enumerate(L.decor):
            if name not in decor_place.KINDS:
                continue
            used.add(name)
            R = decor_place.basis(fw, up) * np.asarray(sc, float)[None, :]
            dec.append([name, _jsonable(np.concatenate([R.T.ravel(), np.asarray(p, float)])),
                        own["decor"][k] if k < len(own["decor"]) else -1])
        lv["decor"] = dec
        lv["lights"] = [dict(kind=q["kind"], p=_jsonable(q["p"]), d=_jsonable(q.get("d")), col=_jsonable(q["col"]),
                             call=own["lights"][k]) for k, q in enumerate(L.lights)]
        objs = []
        for k, o in enumerate(L.objects):
            if o.model in decor_place.KINDS:
                used.add(o.model)
            objs.append(dict(name=o.name, model=o.model, p=_jsonable(o.pos), yaw=_jsonable(o.yaw),
                             scale=_jsonable(o.scale), size=_jsonable(o.size), call=own["objects"][k]))
        lv["objects"] = objs
        lv["triggers"] = [dict(name=t["name"], kind=t["kind"], b=_jsonable(t["box"]), call=own["triggers"][k])
                          for k, t in enumerate(L.triggers)]
        sx, sy, sz, syaw = L.start
        lv["spawn"] = dict(p=_jsonable((sx, sy, sz)), yaw=_jsonable(syaw),
                           call=next((c["id"] for c in calls if c["method"] == "spawn" and records[c["id"]]["level"] is L), -1))
        td = L.terrain_def
        if td:
            xs, zs, H = T.heights(td)
            st = max(1, int(math.ceil(max(len(xs), len(zs)) / 160)))
            lv["terrain"] = dict(xs=_jsonable(xs[::st]), zs=_jsonable(zs[::st]), h=_jsonable(np.round(H[::st, ::st], 2)),
                                 call=next((c["id"] for c in calls if c["method"] == "terrain" and records[c["id"]]["level"] is L), -1))
            lv["waters"] = [_jsonable({k: v for k, v in w.items() if k in ("kind", "x", "z", "r", "y", "pts", "width")})
                            for w in td.get("waters", [])]
        levels.append(lv)
    kinds = {}
    for k in sorted(used):
        try:
            kinds[k] = _kind_mesh(k)
        except Exception:
            pass
    return dict(levels=levels, calls=calls, kinds=kinds, catalog=list(decor_place.KINDS))


def describe_json(path):
    return json.dumps(describe(path), separators=(",", ":"))
