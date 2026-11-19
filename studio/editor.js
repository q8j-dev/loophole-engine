import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {TransformControls} from 'three/addons/controls/TransformControls.js';

const S = window.studio;
const $ = id => document.getElementById(id);
const view = $('lview');
const note = $('lnote');
const panel = $('props');

const POINT = new Set(['prop', 'wall_prop', 'light', 'spot', 'object', 'cube', 'door', 'button', 'pickup', 'spawn', 'sign', 'ceiling_light', 'sparks', 'sound']);
const BOX = new Set(['room', 'solid', 'hole', 'trigger', 'goal', 'hazard']);
const AREA = new Set(['forest', 'scatter', 'terrain', 'flatten', 'platform', 'building', 'pool', 'vent', 'ambient']);
const ROTATE = new Set(['prop', 'object', 'cube', 'pickup', 'spawn']);
const SCALE = new Set(['prop', 'object', 'cube', 'pickup', 'lake', 'sound', ...BOX, ...AREA]);
const LABEL = {
  prop: 'Prop', wall_prop: 'Wall prop', light: 'Light', spot: 'Spotlight', strip: 'Strip light', ceiling_light: 'Ceiling light',
  object: 'Object', cube: 'Cube', door: 'Door', button: 'Button', pickup: 'Collectible', spawn: 'Player start', room: 'Room',
  solid: 'Solid block', hole: 'Hole', trigger: 'Trigger zone', goal: 'Goal', hazard: 'Hazard', forest: 'Forest', scatter: 'Scatter',
  terrain: 'Terrain', lake: 'Lake', river: 'River', path: 'Path', building: 'Building', platform: 'Platform', stairs: 'Stairs',
  sign: 'Sign', window: 'Window', flatten: 'Flat ground', pool: 'Pool', vent: 'Vent', catwalk: 'Catwalk', column: 'Column',
  sound: 'Sound', ambient: 'Sound zone',
};
const GROUPS = [
  ['Trees', ['oak', 'birch', 'maple', 'willow', 'pine', 'spruce', 'palm', 'snag']],
  ['Nature', ['bush', 'grass', 'fern', 'bigleaf', 'reeds', 'log', 'deadlog', 'boulder', 'rock', 'mossrock', 'stump']],
  ['House', ['table', 'chair', 'armchair', 'sofa', 'bed', 'bookshelf', 'cabinet', 'nightstand', 'picture', 'chandelier', 'sconce', 'lantern', 'candlestick', 'oillamp']],
  ['Village', ['woodbarrel', 'winebarrel', 'woodcrate', 'bench', 'firepit', 'streetlamp', 'walllamp', 'toolcart', 'bucket']],
  ['Treasure', ['apple', 'goblet', 'treasure', 'statue', 'catstatue']],
  ['Lab', ['crate', 'barrel', 'machine', 'tank', 'rack', 'terminal', 'trolley', 'reel', 'toolbox', 'valve', 'duct', 'jbox', 'fan', 'panel', 'tray', 'ramp', 'drain']],
];
const CROWN = {maple: 0xc86a2e, birch: 0xa3b84a, willow: 0x7d9a45, palm: 0x5d9a3e, pine: 0x2e5b3c, spruce: 0x2e5b3c,
  bush: 0x4f7d36, fern: 0x5d8c3a, grass: 0x6c9440, reeds: 0x7a8f45, bigleaf: 0x3f8a3a, lilypad: 0x3d6b35};
const WOOD = new Set(['oak', 'birch', 'maple', 'willow', 'pine', 'spruce', 'palm', 'snag', 'log', 'deadlog', 'stump', 'table', 'chair', 'bookshelf', 'cabinet', 'nightstand', 'bench', 'woodbarrel', 'winebarrel', 'woodcrate', 'toolcart', 'bed']);
const STONE = new Set(['boulder', 'rock', 'mossrock', 'statue', 'catstatue']);
const GOLD = new Set(['apple', 'goblet', 'treasure']);

const renderer = new THREE.WebGLRenderer({antialias: true});
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
renderer.domElement.className = 'lcanvas';
view.prepend(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xdfe6f1);
const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 2000);
camera.position.set(18, 16, 24);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8f99, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.4);
sun.position.set(0.5, 1, 0.35);
scene.add(sun);
const root = new THREE.Group();
scene.add(root);
const orbit = new OrbitControls(camera, renderer.domElement);
orbit.enableDamping = false;
orbit.screenSpacePanning = true;
const gizmo = new TransformControls(camera, renderer.domElement);
gizmo.setSize(0.9);
scene.add(gizmo);
const outline = new THREE.Box3Helper(new THREE.Box3(), 0x2756e8);
outline.visible = false;
scene.add(outline);

let desc = null;
let level = 0;
let selected = null;
let selKey = null;
let placing = null;
let dirty = true;
let framed = '';
let reqId = 0;
let timer = 0;
let lineMark = null;
let editing = false;
const groups = new Map();
const geoCache = new Map();

function draw() { dirty = true; }
orbit.addEventListener('change', draw);
gizmo.addEventListener('change', () => { if (selected) outline.box.setFromObject(selected); draw(); });
gizmo.addEventListener('dragging-changed', e => { orbit.enabled = !e.value; if (!e.value && selected) commit(selected); });

function loop() {
  requestAnimationFrame(loop);
  if (!dirty || $('pane-level').hidden) return;
  dirty = false;
  renderer.render(scene, camera);
}
loop();

new ResizeObserver(() => {
  const w = Math.max(1, view.clientWidth), h = Math.max(1, view.clientHeight);
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  draw();
}).observe(view);

const mat = (color, extra) => new THREE.MeshLambertMaterial(Object.assign({color}, extra || {}));
const ghost = (color, opacity) => new THREE.MeshBasicMaterial({color, transparent: true, opacity, depthWrite: false});

function lightColor(c) {
  const a = Array.isArray(c) ? c : [1, 1, 1];
  const m = Math.max(a[0], a[1], a[2], 1e-3);
  return new THREE.Color(a[0] / m, a[1] / m, a[2] / m);
}

function kindGeo(kind) {
  if (geoCache.has(kind)) return geoCache.get(kind);
  const k = desc.kinds[kind];
  let out = null;
  if (k) {
    out = {};
    if (k.solid && k.solid.length >= 9) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(k.solid, 3));
      g.computeVertexNormals();
      out.solid = g;
    }
    if (k.crown) {
      const g = new THREE.IcosahedronGeometry(1, 1);
      g.scale(k.crown[3], k.crown[4], k.crown[5]);
      g.translate(k.crown[0], k.crown[1], k.crown[2]);
      out.crown = g;
    }
    if (!out.solid && !out.crown) {
      const b = k.bounds;
      const g = new THREE.BoxGeometry(b[3] - b[0], b[4] - b[1], b[5] - b[2]);
      g.translate((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2);
      out.solid = g;
    }
  }
  geoCache.set(kind, out);
  return out;
}

function solidColor(kind) {
  if (WOOD.has(kind)) return 0x7a5a3e;
  if (STONE.has(kind)) return 0x8d8a83;
  if (GOLD.has(kind)) return 0xd6a740;
  return 0xa3abb6;
}

function addInstances(group, kind, mats) {
  const g = kindGeo(kind);
  if (!g) return;
  const parts = [];
  if (g.solid) parts.push([g.solid, mat(solidColor(kind))]);
  if (g.crown) parts.push([g.crown, mat(CROWN[kind] || 0x4f7f3a, {flatShading: true})]);
  for (const [geo, m] of parts) {
    const im = new THREE.InstancedMesh(geo, m, mats.length);
    mats.forEach((mm, i) => im.setMatrixAt(i, mm));
    im.computeBoundingSphere();
    group.add(im);
  }
}

function decorMatrix(a) {
  const m = new THREE.Matrix4();
  m.set(a[0], a[3], a[6], a[9], a[1], a[4], a[7], a[10], a[2], a[5], a[8], a[11], 0, 0, 0, 1);
  return m;
}

function box(b, material) {
  const g = new THREE.BoxGeometry(Math.max(b[3] - b[0], 0.02), Math.max(b[4] - b[1], 0.02), Math.max(b[5] - b[2], 0.02));
  const m = new THREE.Mesh(g, material);
  m.position.set((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2);
  return m;
}

function edges(mesh, color) {
  const l = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({color}));
  l.position.copy(mesh.position);
  l.rotation.copy(mesh.rotation);
  return l;
}

function groupFor(call) {
  const key = call == null ? -1 : call;
  if (!groups.has(key)) {
    const g = new THREE.Group();
    g.userData.call = key;
    groups.set(key, g);
    root.add(g);
  }
  return groups.get(key);
}

function terrainMesh(t) {
  const nx = t.xs.length, nz = t.zs.length;
  const pos = new Float32Array(nx * nz * 3);
  const col = new Float32Array(nx * nz * 3);
  const lo = new THREE.Color(0x6f9a4d), hi = new THREE.Color(0xa08f6c);
  let hmin = Infinity, hmax = -Infinity;
  for (const row of t.h) for (const v of row) { hmin = Math.min(hmin, v); hmax = Math.max(hmax, v); }
  for (let j = 0; j < nz; j++) for (let i = 0; i < nx; i++) {
    const k = j * nx + i, h = t.h[j][i];
    pos.set([t.xs[i], h, t.zs[j]], k * 3);
    const c = lo.clone().lerp(hi, hmax > hmin ? Math.pow((h - hmin) / (hmax - hmin), 1.5) : 0);
    col.set([c.r, c.g, c.b], k * 3);
  }
  const idx = [];
  for (let j = 0; j < nz - 1; j++) for (let i = 0; i < nx - 1; i++) {
    const a = j * nx + i, b = a + 1, c = a + nx, d = c + 1;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return new THREE.Mesh(g, new THREE.MeshLambertMaterial({vertexColors: true}));
}

function groundAt(x, z) {
  const t = desc && desc.levels[level].terrain;
  if (!t) return 0;
  const fx = (x - t.xs[0]) / (t.xs[1] - t.xs[0]), fz = (z - t.zs[0]) / (t.zs[1] - t.zs[0]);
  const i = Math.max(0, Math.min(t.xs.length - 2, Math.floor(fx))), j = Math.max(0, Math.min(t.zs.length - 2, Math.floor(fz)));
  const u = Math.max(0, Math.min(1, fx - i)), v = Math.max(0, Math.min(1, fz - j));
  const h = t.h;
  return (h[j][i] * (1 - u) + h[j][i + 1] * u) * (1 - v) + (h[j + 1][i] * (1 - u) + h[j + 1][i + 1] * u) * v;
}

function anchorFor(call, group) {
  const c = desc.calls[call];
  const p = c && c.params;
  const b = new THREE.Box3().setFromObject(group);
  const ctr = b.isEmpty() ? new THREE.Vector3() : b.getCenter(new THREE.Vector3());
  if (c && POINT.has(c.method) && group.userData.pivot) return group.userData.pivot.clone();
  if (c && c.method === 'lake' && p.x && p.z) return new THREE.Vector3(p.x.value, group.userData.waterY || ctr.y, p.z.value);
  return ctr;
}

function rebuild() {
  for (const g of groups.values()) root.remove(g);
  groups.clear();
  geoCache.forEach(v => { if (v) { v.solid && v.solid.dispose(); v.crown && v.crown.dispose(); } });
  geoCache.clear();
  const lv = desc.levels[level];
  if (!lv) return;
  if (lv.terrain) groupFor(lv.terrain.call).add(terrainMesh(lv.terrain));
  else {
    const grid = new THREE.GridHelper(80, 80, 0xb4bfd0, 0xcbd3df);
    groupFor(null).add(grid);
  }
  for (const bx of lv.boxes) {
    const g = groupFor(bx.call);
    if (bx.op === 'carve') {
      const m = box(bx.b, mat(0xf0f3f8, {side: THREE.BackSide}));
      g.add(m, edges(m, 0x9aa7bb));
    } else {
      const m = box(bx.b, mat(0x8f99a8));
      g.add(m);
    }
  }
  const byCall = new Map();
  for (const [kind, a, call] of lv.decor) {
    const key = call + '|' + kind;
    if (!byCall.has(key)) byCall.set(key, {call, kind, mats: []});
    byCall.get(key).mats.push(decorMatrix(a));
  }
  for (const {call, kind, mats} of byCall.values()) {
    const g = groupFor(call);
    addInstances(g, kind, mats);
    if (mats.length === 1 && !g.userData.pivot) g.userData.pivot = new THREE.Vector3().setFromMatrixPosition(mats[0]);
  }
  for (const l of lv.lights) {
    const g = groupFor(l.call);
    const s = new THREE.Mesh(new THREE.SphereGeometry(0.2, 16, 12), new THREE.MeshBasicMaterial({color: lightColor(l.col)}));
    s.position.fromArray(l.p);
    const halo = new THREE.Mesh(new THREE.SphereGeometry(0.42, 16, 12), ghost(lightColor(l.col), 0.25));
    halo.position.copy(s.position);
    g.add(s, halo);
    if (!g.userData.pivot) g.userData.pivot = s.position.clone();
  }
  for (const o of lv.objects) {
    const g = groupFor(o.call);
    const p = new THREE.Vector3().fromArray(o.p);
    const sc = typeof o.scale === 'number' ? o.scale : 1;
    let m = null;
    if (o.model === 'cube') {
      m = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), mat(0xd9dde4));
      m.position.copy(p).add(new THREE.Vector3(0, 0.4, 0));
      g.add(m, edges(m, 0x2756e8));
    } else if (o.model === 'door') {
      m = new THREE.Mesh(new THREE.BoxGeometry(o.size[0] * 2, o.size[1] * 3, 0.16), mat(0xb8c0cc));
      m.position.copy(p);
      m.rotation.y = THREE.MathUtils.degToRad(o.yaw || 0);
      g.add(m, edges(m, 0x5b6880));
    } else if (o.model === 'button') {
      m = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.5, 0.12, 24), mat(0xe5484d));
      m.position.copy(p).add(new THREE.Vector3(0, 0.06, 0));
      g.add(m);
    } else if (desc.kinds[o.model]) {
      const mm = new THREE.Matrix4().compose(p, new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), -THREE.MathUtils.degToRad(o.yaw || 0)), new THREE.Vector3(sc, sc, sc));
      addInstances(g, o.model, [mm]);
    } else {
      m = new THREE.Mesh(new THREE.OctahedronGeometry(0.35), mat(0xd6a740));
      m.position.copy(p).add(new THREE.Vector3(0, 0.4, 0));
      g.add(m);
    }
    g.userData.pivot = p.clone();
  }
  const tcol = {0: 0x3b82f6, 1: 0xe5484d, 2: 0x2fbf71};
  for (const t of lv.triggers) {
    const g = groupFor(t.call);
    const m = box(t.b, ghost(tcol[t.kind] || 0x3b82f6, 0.2));
    g.add(m, edges(m, tcol[t.kind] || 0x3b82f6));
  }
  for (const s of (lv.sounds || [])) {
    const g = groupFor(s.call);
    if (s.kind === 0) {
      const p = new THREE.Vector3().fromArray(s.p);
      const m = new THREE.Mesh(new THREE.OctahedronGeometry(0.32), mat(0x8b5cf6));
      m.position.copy(p);
      const ring = new THREE.Mesh(new THREE.RingGeometry(Math.max(0.05, s.far - 0.08), s.far, 64), ghost(0x8b5cf6, 0.45));
      ring.rotation.x = -Math.PI / 2;
      ring.position.copy(p).setY(p.y - 0.3);
      g.add(m, ring);
      g.userData.pivot = p.clone();
    } else {
      const b = s.box;
      const y = lv.terrain ? groundAt((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) + 0.4 : 0.05;
      const m = box([b[0], y, b[1], b[2], y + 0.05, b[3]], ghost(0x8b5cf6, 0.12));
      g.add(m, edges(m, 0x8b5cf6));
    }
  }
  if (lv.waters) {
    const wc = desc.calls.filter(c => c.level === level && (c.method === 'lake' || c.method === 'river'));
    lv.waters.forEach((w, i) => {
      const g = groupFor(wc[i] ? wc[i].id : null);
      const wm = new THREE.MeshLambertMaterial({color: 0x3f86c8, transparent: true, opacity: 0.75});
      if (w.kind === 'lake') {
        const m = new THREE.Mesh(new THREE.CircleGeometry(w.r, 48), wm);
        m.rotation.x = -Math.PI / 2;
        m.position.set(w.x, (w.y || 0) + 0.02, w.z);
        g.add(m);
        g.userData.waterY = m.position.y;
      } else if (w.pts) {
        for (let k = 0; k + 1 < w.pts.length; k++) {
          const a = w.pts[k], b = w.pts[k + 1];
          const L = Math.hypot(b[0] - a[0], b[1] - a[1]);
          const m = new THREE.Mesh(new THREE.PlaneGeometry(L + w.width * 0.5, w.width), wm);
          m.rotation.set(-Math.PI / 2, 0, -Math.atan2(b[1] - a[1], b[0] - a[0]));
          m.position.set((a[0] + b[0]) / 2, (w.y || 0) + 0.02, (a[1] + b[1]) / 2);
          g.add(m);
        }
      }
    });
  }
  if (lv.spawn) {
    const g = groupFor(lv.spawn.call);
    const p = new THREE.Vector3().fromArray(lv.spawn.p);
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 1.1, 4, 12), mat(0x2756e8));
    body.position.copy(p).add(new THREE.Vector3(0, 0.85, 0));
    const yaw = THREE.MathUtils.degToRad(lv.spawn.yaw || 0);
    const arrow = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.7, 16), mat(0x2756e8));
    arrow.position.copy(p).add(new THREE.Vector3(Math.sin(yaw) * 0.9, 1.1, -Math.cos(yaw) * 0.9));
    arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(Math.sin(yaw), 0, -Math.cos(yaw)));
    g.add(body, arrow);
    g.userData.pivot = p.clone();
  }
  for (const [call, g] of groups) {
    if (call < 0) continue;
    const a = anchorFor(call, g);
    g.userData.anchor = a.clone();
    for (const ch of g.children) ch.position.sub(a);
    g.position.copy(a);
  }
  frame(lv);
  draw();
}

function frame(lv) {
  const key = level + ':' + lv.name;
  if (framed === key) return;
  framed = key;
  const b = new THREE.Box3();
  for (const [call, g] of groups) if (call >= 0) b.expandByObject(g);
  if (b.isEmpty()) b.set(new THREE.Vector3(-10, 0, -10), new THREE.Vector3(10, 4, 10));
  const c = b.getCenter(new THREE.Vector3());
  const r = Math.max(6, b.getSize(new THREE.Vector3()).length() * 0.55);
  orbit.target.copy(c);
  camera.position.copy(c).add(new THREE.Vector3(0.55, 0.75, 0.9).normalize().multiplyScalar(r * 1.9));
  camera.near = Math.max(0.05, r / 400);
  camera.far = r * 30;
  camera.updateProjectionMatrix();
  orbit.update();
}

function keyOf(call) {
  const c = desc.calls[call];
  const same = desc.calls.filter(d => d.method === c.method && d.level === c.level);
  return {method: c.method, level: c.level, nth: same.indexOf(c)};
}

function callOfKey(k) {
  if (!k || !desc) return null;
  const same = desc.calls.filter(d => d.method === k.method && d.level === k.level);
  const c = k.nth === 'last' ? same[same.length - 1] : same[k.nth];
  return c ? c.id : null;
}

function select(call, fromCode) {
  gizmo.detach();
  selected = null;
  outline.visible = false;
  selKey = null;
  if (lineMark) { lineMark.doc.removeLineClass(lineMark.line, 'background', 'cm-picked'); lineMark = null; }
  if (call == null || !groups.has(call) || call < 0) { showProps(null); draw(); return; }
  const c = desc.calls[call];
  selected = groups.get(call);
  selKey = keyOf(call);
  outline.box.setFromObject(selected);
  outline.visible = true;
  if (c.editable) {
    const mode = currentMode();
    const ok = mode === 'translate' ? (POINT.has(c.method) || BOX.has(c.method) || AREA.has(c.method) || c.method === 'lake') :
      mode === 'rotate' ? ROTATE.has(c.method) : SCALE.has(c.method);
    if (ok) {
      gizmo.attach(selected);
      gizmo.showX = true; gizmo.showZ = true;
      gizmo.showY = !(AREA.has(c.method) || c.method === 'lake') || mode === 'rotate';
      if (mode === 'rotate') { gizmo.showX = false; gizmo.showZ = false; gizmo.showY = true; }
    }
  }
  const d = S.doc('world.py');
  if (d && c.line != null && c.line < d.lineCount()) {
    d.addLineClass(c.line, 'background', 'cm-picked');
    lineMark = {doc: d, line: c.line};
    if (!fromCode && S.file === 'world.py') S.editor.scrollIntoView({line: c.line, ch: 0}, 80);
  }
  showProps(c);
  draw();
}

function currentMode() {
  const b = document.querySelector('#gizmo [aria-pressed="true"]');
  return b ? b.dataset.mode : 'translate';
}

function setMode(m) {
  for (const b of document.querySelectorAll('#gizmo .tool')) b.setAttribute('aria-pressed', String(b.dataset.mode === m));
  gizmo.setMode(m);
  if (selected) select(selected.userData.call);
}

function py(v) {
  if (typeof v === 'number') {
    const r = Math.round(v * 100) / 100;
    return String(Object.is(r, -0) ? 0 : r);
  }
  if (typeof v === 'boolean') return v ? 'True' : 'False';
  if (v === null || v === undefined) return 'None';
  if (Array.isArray(v)) return '(' + v.map(py).join(', ') + ')';
  return JSON.stringify(String(v));
}

function applyEdits(c, edits) {
  const d = S.doc('world.py');
  if (!d || !c.editable) return;
  const ops = [];
  for (const [name, value] of Object.entries(edits)) {
    const p = c.params[name];
    const text = py(value);
    if (p && p.span) ops.push({from: {line: p.span[0], ch: p.span[1]}, to: {line: p.span[2], ch: p.span[3]}, text});
    else ops.push({from: {line: c.close[0], ch: c.close[1]}, to: null, text: ', ' + name + '=' + text});
  }
  ops.sort((a, b) => b.from.line - a.from.line || b.from.ch - a.from.ch);
  editing = true;
  for (const o of ops) d.replaceRange(o.text, o.from, o.to || o.from);
  editing = false;
  refresh(0);
}

function val(c, name, dflt) {
  const p = c.params[name];
  return p && p.value !== undefined && p.value !== null ? p.value : dflt;
}

function commit(g) {
  const c = desc.calls[g.userData.call];
  if (!c || !c.editable) return;
  const d = g.position.clone().sub(g.userData.anchor);
  const rot = g.rotation.y;
  const sc = g.scale.clone();
  const e = {};
  const m = c.method;
  if (POINT.has(m)) {
    if (d.lengthSq() > 1e-8) {
      if (c.params.x) e.x = val(c, 'x', 0) + d.x;
      if (c.params.y) e.y = val(c, 'y', 0) + d.y;
      if (c.params.z) e.z = val(c, 'z', 0) + d.z;
      if (m === 'spot' && Array.isArray(val(c, 'target'))) {
        const t = val(c, 'target');
        e.target = [t[0] + d.x, t[1] + d.y, t[2] + d.z];
      }
    }
    if (Math.abs(rot) > 1e-4 && ROTATE.has(m)) {
      let y = val(c, 'yaw', 0) - THREE.MathUtils.radToDeg(rot);
      y = ((y % 360) + 540) % 360 - 180;
      e.yaw = Math.round(y);
    }
    if (Math.abs(sc.x - 1) > 1e-3 && m === 'sound') {
      e.radius = val(c, 'radius', 12) * (sc.x + sc.z) / 2;
    } else if (Math.abs(sc.x - 1) > 1e-3 && SCALE.has(m)) {
      const s0 = val(c, 'scale', 1);
      e.scale = (typeof s0 === 'number' ? s0 : 1) * (sc.x + sc.y + sc.z) / 3;
    }
  } else if (BOX.has(m)) {
    const ax = ['x', 'y', 'z'];
    for (let k = 0; k < 3; k++) {
      const a0 = val(c, ax[k] + '0', 0), a1 = val(c, ax[k] + '1', 0);
      const ctr = (a0 + a1) / 2 + d.getComponent(k), half = Math.abs(a1 - a0) / 2 * Math.abs(sc.getComponent(k));
      if (Math.abs(d.getComponent(k)) > 1e-6 || Math.abs(sc.getComponent(k) - 1) > 1e-4) {
        e[ax[k] + '0'] = ctr - half;
        e[ax[k] + '1'] = ctr + half;
      }
    }
  } else if (AREA.has(m)) {
    for (const [k, a] of [[0, 'x'], [2, 'z']]) {
      const a0 = val(c, a + '0', 0), a1 = val(c, a + '1', 0);
      const ctr = (a0 + a1) / 2 + d.getComponent(k), half = Math.abs(a1 - a0) / 2 * Math.abs(sc.getComponent(k));
      if (Math.abs(d.getComponent(k)) > 1e-6 || Math.abs(sc.getComponent(k) - 1) > 1e-4) {
        e[a + '0'] = ctr - half;
        e[a + '1'] = ctr + half;
      }
    }
    if (c.params.y && Math.abs(d.y) > 1e-6 && (m === 'platform' || m === 'building')) e.y = val(c, 'y', 0) + d.y;
  } else if (m === 'lake') {
    if (Math.abs(d.x) + Math.abs(d.z) > 1e-6) { e.x = val(c, 'x', 0) + d.x; e.z = val(c, 'z', 0) + d.z; }
    if (Math.abs(sc.x - 1) > 1e-3) e.radius = val(c, 'radius', 5) * (sc.x + sc.z) / 2;
  }
  if (Object.keys(e).length) applyEdits(c, e);
}

function showProps(c) {
  if (!c) { panel.hidden = true; panel.innerHTML = ''; return; }
  panel.hidden = false;
  panel.innerHTML = '';
  const head = document.createElement('div');
  head.className = 'phead';
  const h = document.createElement('h3');
  h.textContent = LABEL[c.method] || c.method;
  const ln = document.createElement('button');
  ln.type = 'button';
  ln.className = 'plink';
  ln.textContent = 'Line ' + (c.line + 1);
  ln.addEventListener('click', () => {
    S.showFile('world.py');
    S.editor.setCursor({line: c.line, ch: 0});
    S.editor.scrollIntoView({line: c.line, ch: 0}, 80);
  });
  head.append(h, ln);
  panel.append(head);
  if (!c.editable) {
    const p = document.createElement('p');
    p.className = 'pmsg';
    p.textContent = 'This line runs more than once or is built in code, so change it in world.py.';
    panel.append(p);
  }
  const form = document.createElement('div');
  form.className = 'pfields';
  const names = c.order.filter(n => n in c.params);
  for (const n of Object.keys(c.params)) if (!names.includes(n)) names.push(n);
  for (const name of names) {
    const p = c.params[name];
    if (p.value === undefined) continue;
    const row = document.createElement('label');
    row.className = 'prow';
    const t = document.createElement('span');
    t.textContent = name;
    let input;
    const v = p.value;
    const choices = name === 'kind' && c.method === 'prop' ? (desc.catalog || []) :
      name === 'name' && (c.method === 'sound' || c.method === 'ambient') ? (desc.levels[level].sound_names || []) : null;
    if (choices && typeof v === 'string') {
      input = document.createElement('select');
      for (const k of choices) {
        const o = document.createElement('option');
        o.value = k; o.textContent = k;
        input.append(o);
      }
      input.value = v;
    } else if (typeof v === 'boolean') {
      input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = v;
    } else {
      input = document.createElement('input');
      input.type = typeof v === 'number' ? 'number' : 'text';
      if (typeof v === 'number') input.step = 'any';
      input.value = Array.isArray(v) ? v.join(', ') : (v === null ? '' : String(v));
      if (v === null) input.placeholder = 'None';
    }
    input.disabled = !c.editable || (p.span && !p.literal);
    input.addEventListener('change', () => {
      let nv;
      if (input.type === 'checkbox') nv = input.checked;
      else if (input.type === 'number') { nv = parseFloat(input.value); if (!isFinite(nv)) return; }
      else if (Array.isArray(v)) { nv = input.value.split(/[\s,()]+/).filter(Boolean).map(Number); if (nv.some(x => !isFinite(x))) return; }
      else if (v === null && input.value.trim() === '') nv = null;
      else if (typeof v === 'number' || (v === null && /^-?[\d.]+$/.test(input.value.trim()))) nv = parseFloat(input.value);
      else nv = input.value;
      applyEdits(c, {[name]: nv});
    });
    row.append(t, input);
    form.append(row);
  }
  panel.append(form);
  if (c.editable && c.stmt) {
    const del = document.createElement('button');
    del.type = 'button';
    del.className = 'pdel';
    del.textContent = 'Delete';
    del.addEventListener('click', () => removeCall(c));
    panel.append(del);
  }
}

function removeCall(c) {
  const d = S.doc('world.py');
  if (!d || !c.stmt) return;
  const [a, b] = c.stmt;
  const end = b + 1 < d.lineCount() ? {line: b + 1, ch: 0} : {line: b, ch: d.getLine(b).length};
  const start = b + 1 < d.lineCount() || a === 0 ? {line: a, ch: 0} : {line: a - 1, ch: d.getLine(a - 1).length};
  selKey = null;
  d.replaceRange('', start, end);
  refresh(0);
}

function uniqueName(base) {
  const names = new Set();
  for (const lv of desc.levels) for (const o of lv.objects) names.add(o.name);
  for (const lv of desc.levels) for (const t of lv.triggers) names.add(t.name);
  let i = 1;
  while (names.has(base + i)) i++;
  return base + i;
}

function place(hit) {
  const lv = desc.levels[level];
  if (!lv.var) { note.textContent = 'Give this level a name in world.py, like lab = game.level("Lab"), to add things to it.'; return; }
  const n = v => py(v);
  const x = hit.x, z = hit.z;
  const rel = lv.terrain ? hit.y - groundAt(x, z) : hit.y;
  const y = Math.max(0, Math.round(rel * 100) / 100);
  const v = lv.var;
  let line = null, method = null;
  switch (placing.type) {
    case 'prop': line = `${v}.prop(${py(placing.kind)}, ${n(x)}, ${n(y)}, ${n(z)})`; method = 'prop'; break;
    case 'light': line = `${v}.light(${n(x)}, ${n(y + 2.6)}, ${n(z)}, power=10)`; method = 'light'; break;
    case 'pickup': line = `${v}.pickup(${py(uniqueName('apple'))}, "apple", ${n(x)}, ${n(y + 0.4)}, ${n(z)}, scale=3)`; method = 'pickup'; break;
    case 'cube': line = `${v}.cube(${py(uniqueName('cube'))}, ${n(x)}, ${n(y)}, ${n(z)})`; method = 'cube'; break;
    case 'trigger': line = `${v}.trigger(${py(uniqueName('zone'))}, ${n(x - 1.5)}, ${n(y)}, ${n(z - 1.5)}, ${n(x + 1.5)}, ${n(y + 2.5)}, ${n(z + 1.5)})`; method = 'trigger'; break;
    case 'goal': line = `${v}.goal(${n(x - 1)}, ${n(y)}, ${n(z - 1)}, ${n(x + 1)}, ${n(y + 3)}, ${n(z + 1)})`; method = 'goal'; break;
    case 'lake': line = `${v}.lake(${n(x)}, ${n(z)}, 6)`; method = 'lake'; break;
    case 'forest': line = `${v}.forest(${n(x - 10)}, ${n(z - 10)}, ${n(x + 10)}, ${n(z + 10)}, kind="mixed")`; method = 'forest'; break;
    case 'sound': line = `${v}.sound("birds", ${n(x)}, ${n(y + 1)}, ${n(z)}, radius=12)`; method = 'sound'; break;
  }
  if (!line) return;
  const d = S.doc('world.py');
  const at = Math.min(lv.insert, d.lineCount()) - 1;
  d.replaceRange('\n' + line, {line: at, ch: d.getLine(at).length});
  selKey = {method, level, nth: 'last'};
  stopPlacing();
  refresh(0);
}

function startPlacing(type, kind) {
  const lv = desc && desc.levels[level];
  if ((type === 'lake') && lv && !lv.terrain) {
    note.textContent = 'Water needs terrain. Add a line like ' + (lv.var || 'level') + '.terrain(-40, -40, 40, 40) first.';
    return;
  }
  placing = {type, kind};
  for (const b of document.querySelectorAll('#palette .tool')) b.setAttribute('aria-pressed', String(b.dataset.place === type));
  view.classList.add('placing');
  note.textContent = 'Click where the ' + (kind || (LABEL[type] || type).toLowerCase()) + ' should go. Esc cancels.';
}

function stopPlacing() {
  placing = null;
  for (const b of document.querySelectorAll('#palette .tool')) b.removeAttribute('aria-pressed');
  view.classList.remove('placing');
  $('kinds').hidden = true;
  note.textContent = '';
}

const ray = new THREE.Raycaster();
function pick(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  const v = new THREE.Vector2(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(v, camera);
  const hits = ray.intersectObjects(root.children, true).filter(h => h.object.isMesh);
  return hits;
}

let down = null;
renderer.domElement.addEventListener('pointerdown', e => { down = {x: e.clientX, y: e.clientY}; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4 || gizmo.dragging || !desc) return;
  down = null;
  const hits = pick(e);
  if (placing) {
    let p = null;
    if (hits.length) {
      p = hits[0].point.clone();
      const n = hits[0].face ? hits[0].face.normal.clone().transformDirection(hits[0].object.matrixWorld) : null;
      if (n && n.y < 0.5) p.add(n.multiplyScalar(0.5));
    } else {
      const pl = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
      p = ray.ray.intersectPlane(pl, new THREE.Vector3());
    }
    if (p) place(p);
    return;
  }
  for (const h of hits) {
    let o = h.object;
    while (o && o.userData.call === undefined) o = o.parent;
    if (o && o.userData.call >= 0) { select(o.userData.call); return; }
  }
  select(null);
});

window.addEventListener('keydown', e => {
  if ($('pane-level').hidden || e.target.closest('input, select, textarea, .CodeMirror')) return;
  if (e.key === 'Escape') { if (placing) stopPlacing(); else select(null); }
  else if (e.key === 'w' || e.key === 'W') setMode('translate');
  else if (e.key === 'e' || e.key === 'E') setMode('rotate');
  else if (e.key === 'r' || e.key === 'R') setMode('scale');
  else if ((e.key === 'Delete' || e.key === 'Backspace') && selected) {
    const c = desc.calls[selected.userData.call];
    if (c && c.editable && c.stmt) { e.preventDefault(); removeCall(c); }
  }
});

for (const b of document.querySelectorAll('#gizmo .tool')) b.addEventListener('click', () => setMode(b.dataset.mode));
for (const b of document.querySelectorAll('#palette .tool')) b.addEventListener('click', () => {
  if (placing && placing.type === b.dataset.place) { stopPlacing(); return; }
  if (b.dataset.place === 'prop') { openKinds(b); return; }
  $('kinds').hidden = true;
  startPlacing(b.dataset.place);
});

function openKinds(btn) {
  const box = $('kinds');
  box.hidden = !box.hidden;
  if (box.hidden) return;
  $('kindq').value = '';
  listKinds('');
  $('kindq').focus();
}

function listKinds(q) {
  const list = $('kindlist');
  list.innerHTML = '';
  const have = new Set(desc ? desc.catalog : []);
  for (const [g, ks] of GROUPS) {
    const items = ks.filter(k => have.has(k) && k.includes(q.toLowerCase()));
    if (!items.length) continue;
    const h = document.createElement('div');
    h.className = 'kgroup';
    h.textContent = g;
    list.append(h);
    const wrap = document.createElement('div');
    wrap.className = 'kitems';
    for (const k of items) {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'kitem';
      b.textContent = k;
      b.addEventListener('click', () => { $('kinds').hidden = true; startPlacing('prop', k); });
      wrap.append(b);
    }
    list.append(wrap);
  }
}
$('kindq').addEventListener('input', e => listKinds(e.target.value));
$('kindq').addEventListener('keydown', e => {
  if (e.key === 'Enter') { const first = $('kindlist').querySelector('.kitem'); if (first) first.click(); }
  if (e.key === 'Escape') $('kinds').hidden = true;
});

$('levelsel').addEventListener('change', e => { level = +e.target.value; select(null); rebuild(); });

function levelsUI() {
  const sel = $('levelsel');
  const names = desc.levels.map(l => l.name);
  if (sel.dataset.names !== names.join('|')) {
    sel.innerHTML = '';
    names.forEach((n, i) => { const o = document.createElement('option'); o.value = i; o.textContent = n; sel.append(o); });
    sel.dataset.names = names.join('|');
  }
  if (level >= names.length) level = 0;
  sel.value = level;
  $('levelwrap').hidden = names.length < 2;
}

async function describeNow() {
  const id = ++reqId;
  if (!desc) note.textContent = 'Loading the level';
  try {
    const d = await S.describe();
    if (id !== reqId) return;
    desc = d;
    window.levelDesc = d;
    levelsUI();
    rebuild();
    if (!placing) note.textContent = '';
    const want = callOfKey(selKey);
    select(want);
    view.classList.remove('stale');
  } catch (err) {
    if (id !== reqId) return;
    view.classList.add('stale');
    note.textContent = 'world.py has a problem' + (err.line ? ' on line ' + err.line : '') + ': ' + err.message;
  }
}

function refresh(delay) {
  clearTimeout(timer);
  timer = setTimeout(describeNow, delay === undefined ? 500 : delay);
}

S.on(ev => {
  if (ev === 'edit') { if (!editing) refresh(); }
  else if (ev === 'template') { framed = ''; selKey = null; level = 0; refresh(0); }
  else if (ev === 'pane:level') draw();
});

S.editor.on('cursorActivity', cm => {
  if (!desc || S.file !== 'world.py' || !cm.hasFocus()) return;
  const line = cm.getCursor().line;
  const c = desc.calls.find(k => k.line === line || (k.stmt && k.stmt[0] <= line && line <= k.stmt[1]));
  if (!c) return;
  if (c.level !== level) { level = c.level; levelsUI(); rebuild(); }
  if (!selected || selected.userData.call !== c.id) select(c.id, true);
});

window.levelEditor = {
  get desc() { return desc; },
  get selected() { return selected ? selected.userData.call : null; },
  select, startPlacing, place: p => place(new THREE.Vector3(p[0], p[1], p[2])), setMode, refresh: () => describeNow(),
  project(p) {
    const v = new THREE.Vector3(p[0], p[1], p[2]).project(camera);
    const r = renderer.domElement.getBoundingClientRect();
    return [r.left + (v.x + 1) / 2 * r.width, r.top + (1 - v.y) / 2 * r.height];
  },
};
if (S.doc('world.py')) refresh(0);
