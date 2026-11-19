const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
importScripts(PYODIDE + 'pyodide.js');

let py = null;
const post = (type, data, transfer) => self.postMessage(Object.assign({type}, data || {}), transfer || []);

const STAGES = [
  ['rects', 0.05], ['gi rays', 0.12], ['gi done', 0.45], ['texels', 0.55], ['ao + dirt', 0.62],
  ['ambient grid', 0.72], ['decor vertex lighting', 0.82], ['terrain lightmap', 0.88], ['far terrain', 0.95],
];

function mkdirs(FS, path) {
  const dir = path.split('/').slice(0, -1).join('/');
  if (dir) FS.mkdirTree(dir);
  return dir;
}

function syncCache(populate) {
  return new Promise(res => {
    try { py.FS.syncfs(populate, () => res()); } catch (e) { res(); }
  });
}

async function boot() {
  post('progress', {text: 'Starting Python', p: 0.01});
  py = await loadPyodide({indexURL: PYODIDE});
  post('progress', {text: 'Loading numpy and Pillow', p: 0.04});
  await py.loadPackage(['numpy', 'pillow']);
  post('progress', {text: 'Loading the engine', p: 0.08});
  const man = await (await fetch('py/manifest.json')).json();
  const FS = py.FS;
  for (const [path, text] of Object.entries(man.source)) {
    mkdirs(FS, '/lh/' + path);
    FS.writeFile('/lh/' + path, text);
  }
  const base = new URL('py/', self.location.href).href;
  for (const [path] of man.data) {
    const dir = mkdirs(FS, '/lh/' + path);
    FS.createLazyFile(dir, path.split('/').pop(), base + path, true, false);
  }
  FS.mkdirTree('/cache');
  try { FS.mount(FS.filesystems.IDBFS, {}, '/cache'); await syncCache(true); } catch (e) {}
  py.runPython("import sys\nsys.path.insert(0, '/lh')\nimport loophole.build");
  post('ready', {});
}

const booting = boot().catch(e => post('error', {text: 'Python could not start: ' + e.message}));

function tracker() {
  let levels = 1, idx = -1, frac = 0;
  return line => {
    const m = line.match(/\((\d+) levels?\)/);
    if (m) levels = +m[1];
    if (/: baking|: cached bake/.test(line)) { idx += 1; frac = /cached/.test(line) ? 1 : 0; }
    if (/baked in/.test(line)) frac = 1;
    for (const [key, f] of STAGES) if (line.includes(key)) frac = Math.max(frac, f);
    let p = 0.1 + 0.82 * (Math.max(idx, 0) + frac) / levels;
    if (line.startsWith('wrote')) p = 1;
    const name = line.match(/^\s+(.+?): (baking|cached bake|baked in)/);
    return {p, name: name ? name[1] : null};
  };
}

async function build(files) {
  await booting;
  const FS = py.FS;
  try { FS.mkdirTree('/proj'); } catch (e) {}
  for (const f of FS.readdir('/proj')) if (f.endsWith('.py')) FS.unlink('/proj/' + f);
  for (const [name, text] of Object.entries(files)) FS.writeFile('/proj/' + name, text);
  const track = tracker();
  let level = '';
  py.globals.set('jslog', line => {
    line = String(line);
    const t = track(line);
    if (t.name) level = t.name;
    const text = line.startsWith('wrote') ? 'Packing the game' :
      level ? 'Lighting ' + level : 'Reading world.py';
    post('progress', {text, p: t.p, line});
  });
  try {
    py.runPython(`
import loophole.build as B
B.VERBOSE = True
B.build('/proj/world.py', out='/proj/game.sb3', log=jslog, cache='/cache')
`);
    const bytes = FS.readFile('/proj/game.sb3');
    await syncCache(false);
    post('done', {bytes}, [bytes.buffer]);
  } catch (e) {
    const full = String(e.message || e).trim();
    const at = full.lastIndexOf('SystemExit: ');
    const lines = full.split('\n').filter(l => l.trim());
    const text = at >= 0 ? full.slice(at + 12).trim() : lines[lines.length - 1];
    post('error', {text, trace: full});
  }
}

async function describe(id, files) {
  await booting;
  const FS = py.FS;
  try { FS.mkdirTree('/scene'); } catch (e) {}
  for (const [name, text] of Object.entries(files)) FS.writeFile('/scene/' + name, text);
  try {
    py.globals.set('scene_id', id);
    const json = py.runPython(`
import loophole.describe as D
D.describe_json('/scene/world.py')
`);
    post('scene', {id, json});
  } catch (e) {
    const msg = String(e.message || e).trim().split('\n').filter(l => l.trim());
    const line = msg.reverse().find(l => /File "\/scene\/world.py", line \d+/.test(l));
    const where = line ? line.match(/line (\d+)/)[1] : null;
    post('scene', {id, error: msg[0], line: where ? +where : null});
  }
}

self.onmessage = e => {
  if (e.data.type === 'build') build(e.data.files);
  else if (e.data.type === 'describe') describe(e.data.id, e.data.files);
};
