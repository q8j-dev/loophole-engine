const {execFileSync} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const [crypt, starter, racing] = process.argv.slice(2);
if (!racing) {
  console.log('usage: node ux_test.js crypt.sb3 starter.sb3 racing.sb3');
  process.exit(2);
}
const play = path.join(__dirname, 'play.js');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'loophole-ux-'));

function run(sb3, script) {
  const out = execFileSync(process.execPath, [play, path.resolve(sb3), script], {encoding: 'utf8', maxBuffer: 1 << 26, timeout: 600000,
    env: Object.assign({}, process.env, {SHOTS: shots})});
  const v = {};
  for (const line of out.split('\n')) {
    const m = line.match(/^JS (\w+)=(.*)$/) || line.match(/^JS "(\w+)=(.*)"$/);
    if (m) v[m[1]] = m[2];
  }
  return v;
}
const probe = (name, expr) => `js,'${name}='+(${expr})`;
const overlay = "S.vm.runtime.targets.find(t=>t.isOriginal&&t.getName()==='Overlay').visible";
const prompt = "S.vm.runtime.targets.find(t=>t.isOriginal&&t.getName()==='Engine').lookupVariableByNameAndType('lptx','').value";
function black(png) {
  const code = 'import sys\nfrom PIL import Image\nim = Image.open(sys.argv[1]).convert("L")\nw, h = im.size\n' +
    'b = im.crop((0, h // 8, w, h)).tobytes()\nprint(sum(1 for p in b if p < 4) / len(b))';
  return +execFileSync(python, ['-c', code, png], {encoding: 'utf8'}).trim();
}

let failed = 0;
function check(name, ok, detail) {
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : '  ' + detail}`);
}

let v = run(crypt, `tap,space;wait,3500;${probe('ov', overlay)};walkto,11,-1;walkto,11,-3;walkto,6,-3;wait,800;shot,ux_crypt`);
check('crosshair hidden in top down', v.ov === 'false', `overlay visible: ${v.ov}`);
const b = black(path.join(shots, 'ux_crypt.png'));
check('crypt cutaway has no black voids', b < 0.02, `${(b * 100).toFixed(1)}% of the frame is pure black`);

v = run(starter, `wait,1500;${probe('msg', "getv('message')")};walkto,9,9.8;aim,9,0.3,9;wait,800;${probe('p', prompt)}`);
check('starter shows its hint', /cube on the button/.test(v.msg || ''), `message: ${v.msg}`);
check('use prompt on the cube', v.p === 'E  Pick up', `prompt: ${v.p}`);

v = run(racing, `wait,2500;walkto,-11.6,35.6;wait,600;${probe('p', prompt)};${probe('ov', overlay)}`);
check('drive prompt next to a kart', v.p === 'E  Drive', `prompt: ${v.p}`);
check('crosshair hidden in third person', v.ov === 'false', `overlay visible: ${v.ov}`);

process.exit(failed ? 1 : 0);
