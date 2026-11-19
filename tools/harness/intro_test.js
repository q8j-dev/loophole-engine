const {execFileSync} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const play = path.join(__dirname, 'play.js');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'loophole-intro-'));
const files = process.argv.slice(2);
if (!files.length) {
  console.log('usage: node intro_test.js game.sb3 [more.sb3 ...]');
  process.exit(2);
}

const ENGINE = ['ccx', 'ccy', 'ccz', 'cfx', 'cfy', 'cfz', 'csi', 'player x', 'player y', 'player z', 'player pitch',
  'camera mode', 'camera distance'];
const readout = tag => ENGINE.map(n => `get,${n}`).join(';') + `;shot,${tag}`;

const SCENARIOS = [
  ['plays to the end', {}, 'hideui;js,S.vm.greenFlag();waitcs,40000;wait,1200;'],
  ['skipped', {}, 'hideui;js,S.vm.greenFlag();wait,1500;get,csi;tap,space;wait,1800;'],
  ['click to play, mouse and keys during it', {NOLOCK: '1'}, 'js,S.vm.greenFlag();wait,900;pclick;wait,400;pmove,220,90,12;down,w;wait,500;up,w;pmove,-300,-60,12;wait,600;tap,e;waitcs,40000;wait,1200;'],
];

function run(sb3, script, env) {
  const out = execFileSync(process.execPath, [play, sb3, script], {encoding: 'utf8', maxBuffer: 1 << 26, timeout: 600000,
    env: Object.assign({}, process.env, {SHOTS: shots}, env)});
  const vars = {};
  const gets = [];
  for (const line of out.split('\n')) {
    if (line.startsWith('WAITCS ')) vars.waitcs = line.slice(7).trim();
    if (!line.startsWith('VAR ')) continue;
    const body = line.slice(4);
    for (let i = body.indexOf(' '); i > 0; i = body.indexOf(' ', i + 1)) {
      try { const v = JSON.parse(body.slice(i + 1)); vars[body.slice(0, i)] = v; gets.push([body.slice(0, i), v]); break; } catch (e) {}
    }
  }
  vars.gets = gets;
  return vars;
}

function brightness(png) {
  const code = 'import sys\nfrom PIL import Image\nim = Image.open(sys.argv[1]).convert("L")\nw, h = im.size\n' +
    'c = im.crop((w // 4, h // 4, w * 3 // 4, h * 3 // 4)).resize((1, 1), Image.BOX)\nprint(c.getpixel((0, 0)) / 255.0)';
  return +execFileSync(python, ['-c', code, png], {encoding: 'utf8'}).trim();
}

function judge(v, png) {
  const bad = [];
  const mode = +v['camera mode'];
  if (mode === 1) bad.push('camera still in cutscene mode');
  if (+v.csi !== 0) bad.push('cutscene still running');
  const px = +v['player x'], py = +v['player y'], pz = +v['player z'];
  if (mode === 2 || mode === 3) {
    const tx = px - v.ccx, ty = py + 1.4 - v.ccy, tz = pz - v.ccz;
    const d = Math.hypot(tx, ty, tz);
    const dot = (tx * v.cfx + ty * v.cfy + tz * v.cfz) / Math.max(d, 1e-6);
    if (v.ccy < py + 1.0) bad.push(`camera at y ${(+v.ccy).toFixed(2)}, below the player's head (feet at ${py.toFixed(2)})`);
    if (d > +v['camera distance'] + 0.6) bad.push(`camera ${d.toFixed(1)} m from the player`);
    if (dot < 0.95) bad.push(`camera not facing the player (dot ${dot.toFixed(2)})`);
  } else if (mode === 0) {
    if (v.ccy < py + 1.0) bad.push(`eye at y ${(+v.ccy).toFixed(2)}, below the player's head`);
    if (Math.abs(+v['player pitch']) > 70) bad.push(`looking straight ${+v['player pitch'] > 0 ? 'up' : 'down'}`);
  }
  const b = brightness(png);
  if (b < 0.05) bad.push(`frame is almost black (brightness ${b.toFixed(3)})`);
  return bad;
}

let failed = 0;
files.forEach((sb3, fi) => {
  const name = path.basename(sb3, '.sb3');
  SCENARIOS.forEach(([label, env, pre], i) => {
    const tag = `${fi + 1}_${name.replace(/\W+/g, '_')}_${i}`;
    let bad;
    try {
      const v = run(path.resolve(sb3), pre + readout(tag), env);
      bad = judge(v, path.join(shots, tag + '.png'));
      if (pre.includes('waitcs') && v.waitcs !== 'done' && !(pre.includes('tap,e') && v.waitcs === 'never started')) bad.unshift(`intro ${v.waitcs}`);
      if (label === 'skipped') {
        const first = v.gets.find(g => g[0] === 'csi');
        if (!first || +first[1] === 0) bad.unshift('no cutscene was playing at 1.5 s');
      }
    } catch (e) {
      bad = [(e.stdout ? String(e.stdout).trim().split('\n').slice(-2).join(' | ') : '') || e.message];
    }
    if (bad.length) failed++;
    console.log(`${bad.length ? 'FAIL' : 'PASS'} ${name}: intro ${label}${bad.length ? '  ' + bad.join('; ') : ''}`);
  });
});
console.log(`screenshots in ${shots}`);
process.exit(failed ? 1 : 0);
