const {execFileSync} = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const build = !process.argv.includes('--no-build');
const shots = fs.mkdtempSync(path.join(os.tmpdir(), 'loophole-check-'));

const EXAMPLES = [
  ['showcase', 'Afterglow', 'Afterglow  -  made with Loophole Engine'],
  ['orchard', 'Orchard Dash', 'Orchard cleared'],
  ['crypt', 'Crypt Crawl', ["You found the crypt's treasure!", 'Crypt Crawl  -  made with Loophole Engine']],
  ['portals', 'Portal Lab', 'Portal Lab complete'],
  ['journey', 'The Long Walk', 'The Long Walk  -  made with Loophole Engine'],
  ['racing', 'Kart Cup', 'Race finished!'],
];

const results = [];
function step(name, fn) {
  const t0 = Date.now();
  let ok = false;
  let note = '';
  try {
    const r = fn();
    ok = r === true;
    if (!ok) note = String(r);
  } catch (e) {
    note = (e.stdout ? String(e.stdout).trim().split('\n').slice(-3).join(' | ') : '') || e.message;
  }
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name} (${Math.round((Date.now() - t0) / 1000)} s)${ok ? '' : '  ' + note}`);
}

for (const [dir, title, expect] of EXAMPLES) {
  const sb3 = path.join(root, 'examples', dir, title + '.sb3');
  if (build) step(`build ${dir}`, () => {
    execFileSync(python, ['-m', 'loophole.cli', 'build', path.join('examples', dir)], {cwd: root, encoding: 'utf8', stdio: 'pipe'});
    return fs.existsSync(sb3) || 'no .sb3 written';
  });
  step(`play ${dir}`, () => {
    const script = fs.readFileSync(path.join(__dirname, 'runs', dir + '.txt'), 'utf8').trim();
    const out = execFileSync(process.execPath, [path.join(__dirname, 'play.js'), sb3, script],
      {encoding: 'utf8', maxBuffer: 1 << 26, timeout: 900000, env: Object.assign({}, process.env, {SHOTS: shots})});
    const msgs = out.split('\n').filter(l => l.startsWith('VAR message '));
    const want = [].concat(expect);
    return msgs.some(l => want.some(w => l.includes(w))) || `never showed "${want[0]}"; last: ${msgs.slice(-1)[0] || 'nothing'}`;
  });
}

const helper = path.join(shots, 'helpertest.sb3');
step('build helper test', () => {
  execFileSync(python, [path.join(__dirname, 'helpertest', 'build_test.py'), helper], {cwd: root, encoding: 'utf8', stdio: 'pipe'});
  return fs.existsSync(helper) || 'no .sb3 written';
});
step('helper blocks and save/load', () => {
  execFileSync(process.execPath, [path.join(__dirname, 'helpertest', 'run_test.js'), helper], {encoding: 'utf8', stdio: 'pipe', timeout: 1800000});
  return true;
});

step('friendly error messages', () => {
  execFileSync(python, [path.join(root, 'tests', 'test_errors.py')], {cwd: root, encoding: 'utf8', stdio: 'pipe', timeout: 600000});
  return true;
});

const starter = path.join(shots, 'starter');
step('first-minute checks: hint, prompts, crosshair, crypt walls', () => {
  execFileSync(python, ['-m', 'loophole.cli', 'new', starter], {cwd: root, encoding: 'utf8', stdio: 'pipe'});
  execFileSync(python, ['-m', 'loophole.cli', 'build', starter], {cwd: root, encoding: 'utf8', stdio: 'pipe'});
  execFileSync(process.execPath, [path.join(__dirname, 'ux_test.js'), path.join(root, 'examples', 'crypt', 'Crypt Crawl.sb3'),
    path.join(starter, 'Starter.sb3'), path.join(root, 'examples', 'racing', 'Kart Cup.sb3')], {encoding: 'utf8', stdio: 'pipe', timeout: 1200000});
  return true;
});

const intros = EXAMPLES.filter(([dir]) => fs.readFileSync(path.join(root, 'examples', dir, 'world.py'), 'utf8').includes('play_at_start=True'))
  .map(([dir, title]) => path.join(root, 'examples', dir, title + '.sb3')).concat([helper]);
step('autoplay intros leave the camera on the player', () => {
  execFileSync(process.execPath, [path.join(__dirname, 'intro_test.js'), ...intros], {encoding: 'utf8', stdio: 'pipe', timeout: 1800000});
  return true;
});

const failed = results.filter(x => !x).length;
console.log(`${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
