const {execFileSync} = require('child_process');
const path = require('path');

const sb3 = path.resolve(process.argv[2] || path.join(__dirname, 'test.sb3'));
const play = path.join(__dirname, '..', 'play.js');

function run(script, env) {
  const out = execFileSync(process.execPath, [play, sb3, script], {encoding: 'utf8', maxBuffer: 1 << 26, timeout: 600000,
    env: Object.assign({}, process.env, env || {})});
  const r = {logs: {}, vars: {}, lists: {}, rumbles: null};
  for (const line of out.split('\n')) {
    let m;
    if (line.startsWith('VAR ') || line.startsWith('LIST ')) {
      const body = line.slice(line.indexOf(' ') + 1);
      for (let i = body.indexOf(' '); i > 0; i = body.indexOf(' ', i + 1)) {
        try {
          const v = JSON.parse(body.slice(i + 1));
          (line.startsWith('VAR ') ? r.vars : r.lists)[body.slice(0, i)] = v;
          break;
        } catch (e) {}
      }
    } else if ((m = line.match(/^RUMBLES (.*)$/))) r.rumbles = JSON.parse(m[1]);
    else if ((m = line.match(/^(\w+) (\{.*\})$/))) r.logs[m[1]] = JSON.parse(m[2]);
  }
  return r;
}

const results = [];
function check(name, ok, detail) {
  results.push([name, ok]);
  console.log((ok ? 'PASS ' : 'FAIL ') + name + (ok ? '' : '  ' + JSON.stringify(detail)));
}
const near = (a, x, z, tol = 0.25) => !!a && Math.abs(a['player x'] - x) < tol && Math.abs(a['player z'] - z) < tol;
const watchKeys = ['w1', 'w3', 'w6'];
const held = (r, lv) => watchKeys.every(k => near(r.logs[k], r.logs.saved['player x'], r.logs.saved['player z']) && +r.logs[k].level === lv);
const rising = r => watchKeys.every((k, i) => i === 0 || +r.logs[k]['level time'] > +r.logs[watchKeys[i - 1]]['level time']);
const watch = 'wait,1000;log,w1;wait,2000;log,w3;wait,3000;log,w6';
const intro = 'wait,1500;tap,space;wait,800';

let r = run(`${intro};tap,t;wait,2500;list,obj x;list,obj yaw;list,obj visible;list,obj open;list,light power;get,weather;get,status;rumbles`, {FAKEPAD: '1'});
check('helper blocks', r.lists['obj x'][0] === 2 && r.lists['obj yaw'][0] === 45 && r.lists['obj visible'][1] === 0 &&
  r.lists['obj open'][2] === 1 && r.lists['light power'][0] === 0 && r.vars.weather === 'rain' && r.vars.status === 'tested 1' &&
  r.rumbles.some(x => x.strongMagnitude === 0.5), r);

r = run(`${intro};walkto,8,4;log,saved;tap,3;wait,500;walkto,4,8;tap,4;${watch};get,save found`);
check('save code, same level, held 6 s', held(r, 1) && rising(r) && +r.vars['save found'] === 1, r.logs);

r = run(`${intro};walkto,8,4;log,saved;tap,1;wait,800;get,message;walkto,4,8;tap,2;${watch}`);
check('save slot, same level, held 6 s', r.vars.message === 'Game saved' && held(r, 1) && rising(r), r.logs);

r = run(`${intro};walkto,10,10.5;walkto,6,9;wait,300;walkto,8,6;log,saved;tap,1;wait,800;walkto,1.2,13,5000;wait,2500;log,respawn;walkto,3,3;tap,2;${watch};get,checkpoint x;list,obj visible`);
check('checkpoint respawn', near(r.logs.respawn, 10, 10.5), r.logs.respawn);
check('slot after checkpoint, held 6 s', held(r, 1) && rising(r) && +r.vars['checkpoint x'] === 10 && +r.lists['obj visible'][3] === 0, r);

r = run(`${intro};walkto,8,4;log,saved;tap,1;wait,800;set,go to level,2;wait,5000;tap,2;wait,2000;get,cutscene;get,controls;${watch};list,obj open;list,save data`);
check('slot from another level, held 6 s, no intro', held(r, 1) && rising(r) && r.vars.cutscene === '' && +r.vars.controls === 1 &&
  JSON.stringify(r.lists['obj open'].map(Number)) === JSON.stringify([0, 0, 1, 0, 0]) && r.lists['save data'][1] == 42, r);

r = run(`${intro};walkto,8,4;log,saved;tap,3;wait,500;set,go to level,2;wait,5000;tap,4;wait,2000;${watch}`);
check('save code from another level, held 6 s', held(r, 1) && rising(r), r.logs);

const failed = results.filter(x => !x[1]).length;
console.log(`${results.length - failed}/${results.length} passed`);
process.exit(failed ? 1 : 0);
