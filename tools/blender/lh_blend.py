import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "loophole" / "data" / "kit"
TILES = ROOT / "loophole" / "data" / "tiles"


def args():
    a = sys.argv
    return a[a.index("--") + 1:] if "--" in a else []


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    use = None
    for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                use = kind
                break
        except TypeError:
            continue
    sc.cycles.device = "GPU" if use else "CPU"
    sc.cycles.samples = 16
    sc.render.bake.margin = 16
    return sc


def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def apply_all(ob):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except RuntimeError:
            ob.modifiers.remove(m)


def join(obs, name):
    obs = [o for o in obs if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    for o in obs:
        if o.parent:
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(obs) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    return ob


def recenter(ob, scale=1.0):
    vs = np.array([v.co[:] for v in ob.data.vertices])
    lo, hi = vs.min(0), vs.max(0)
    c = Vector(((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]))
    for v in ob.data.vertices:
        v.co = (v.co - c) * scale
    ob.data.update()


def duplicate(ob, name):
    c = ob.copy()
    c.data = ob.data.copy()
    c.name = name
    bpy.context.scene.collection.objects.link(c)
    return c


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def decimate(ob, target):
    for _ in range(6):
        n = tri_count(ob)
        if n <= target * 1.15:
            return
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0005)
        bpy.ops.object.mode_set(mode="OBJECT")
        m = ob.modifiers.new("dec", "DECIMATE")
        m.decimate_type = "COLLAPSE"
        m.ratio = max(0.01, target / max(tri_count(ob), 1))
        m.use_collapse_triangulate = True
        apply_all(ob)


def triangulate(ob):
    m = ob.modifiers.new("tri", "TRIANGULATE")
    apply_all(ob)


def smooth(ob, angle=40):
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
    except Exception:
        pass


def unwrap(ob, margin=0.008, angle=70):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    while ob.data.uv_layers:
        ob.data.uv_layers.remove(ob.data.uv_layers[0])
    ob.data.uv_layers.new(name="bake")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             scale_to_bounds=True)
    try:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True, shape_method="CONCAVE")
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake(hi, lo, size, alpha=False, ext=0.04, samples=16):
    sc = bpy.context.scene
    sc.render.bake.use_selected_to_active = hi is not lo
    sc.render.bake.cage_extrusion = ext
    sc.render.bake.max_ray_distance = ext * 3
    lm = bpy.data.materials.new("lowbake")
    lm.use_nodes = True
    tn = lm.node_tree.nodes.new("ShaderNodeTexImage")
    lm.node_tree.nodes.active = tn
    lo.data.materials.clear()
    lo.data.materials.append(lm)
    for p in lo.data.polygons:
        p.material_index = 0
    bpy.ops.object.select_all(action="DESELECT")
    hi.select_set(True)
    lo.select_set(True)
    bpy.context.view_layer.objects.active = lo
    out = {}

    def target(key):
        im = bpy.data.images.new(f"b_{key}", size, size, alpha=False, float_buffer=True)
        im.colorspace_settings.name = "Non-Color"
        tn.image = im
        return im

    def grab(im):
        return np.array(im.pixels[:], dtype=np.float32).reshape(size, size, 4)[::-1, :, :3]

    sc.cycles.samples = samples
    im = target("nrm")
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", use_clear=True)
    out["nrm"] = grab(im)
    im = target("rough")
    bpy.ops.object.bake(type="ROUGHNESS", use_clear=True)
    out["rough"] = grab(im)[..., 0]
    sc.cycles.samples = 96
    im = target("ao")
    bpy.ops.object.bake(type="AO", use_clear=True)
    out["ao"] = grab(im)[..., 0]
    sc.cycles.samples = 1
    saved = []
    for slot in hi.material_slots:
        mt = slot.material
        if mt is None or not mt.use_nodes:
            continue
        nt = mt.node_tree
        b = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        o = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if b is None or o is None:
            continue
        em = nt.nodes.new("ShaderNodeEmission")
        prev = o.inputs["Surface"].links[0].from_socket if o.inputs["Surface"].links else None
        nt.links.new(em.outputs[0], o.inputs["Surface"])
        saved.append((nt, prev, o, em, b))

    def route(inp):
        for nt, prev, o, em, b in saved:
            for l in list(em.inputs["Color"].links):
                nt.links.remove(l)
            si = b.inputs[inp]
            if si.is_linked:
                nt.links.new(si.links[0].from_socket, em.inputs["Color"])
            else:
                v = si.default_value
                em.inputs["Color"].default_value = (v[0], v[1], v[2], 1) if hasattr(v, "__len__") else (v, v, v, 1)

    for key, inp in (("col", "Base Color"), ("metal", "Metallic")) + ((("alpha", "Alpha"),) if alpha else ()):
        route(inp)
        im = target(key)
        bpy.ops.object.bake(type="EMIT", use_clear=True)
        g = grab(im)
        out[key] = g if key == "col" else g[..., 0]
    for nt, prev, o, em, b in saved:
        if prev is not None:
            nt.links.new(prev, o.inputs["Surface"])
        nt.nodes.remove(em)
    sc.render.bake.use_selected_to_active = False
    return out


def save_maps(name, maps, cache):
    d = Path(cache) / "maps"
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / f"{name}.npz", **maps)


def export_mesh(ob, name, flag=None, sway=None):
    me = ob.data
    me.calc_loop_triangles()
    uvn = me.uv_layers.active.name
    me.calc_tangents(uvmap=uvn)
    uvl = me.uv_layers.active.data
    P, N, UV, T, F, S = [], [], [], [], [], []
    vf = flag
    for t in me.loop_triangles:
        for li in t.loops:
            lp = me.loops[li]
            v = lp.vertex_index
            co = me.vertices[v].co
            n = lp.normal
            tg = lp.tangent
            P.append((co.x, co.z, -co.y))
            N.append((n.x, n.z, -n.y))
            T.append((tg.x, tg.z, -tg.y, lp.bitangent_sign))
            u = uvl[li].uv
            UV.append((min(max(u[0], 0.0), 1.0), 1.0 - min(max(u[1], 0.0), 1.0)))
            F.append(vf[v] if vf is not None else (2.0 if lp.bitangent_sign < 0 else 1.0))
            S.append(sway[v] if sway is not None else 0.0)
    KIT.mkdir(parents=True, exist_ok=True)
    extra = {}
    if flag is not None:
        extra["flag"] = np.array(F, np.float32)
        extra["sway"] = np.array(S, np.float32)
    np.savez_compressed(KIT / f"kit_{name}.npz", pos=np.array(P, np.float32), nrm=np.array(N, np.float32),
                        uv=np.array(UV, np.float32), tan=np.array(T, np.float32), **extra)
    return len(P) // 3
