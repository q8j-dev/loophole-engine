const {execFileSync} = require('child_process');
const path = require('path');

const args = process.argv.slice(2);
const rates = (process.env.RATES || '4,6').split(',').map(Number);
const walk = 'wait,6000;log,a;hold,w,3000;log,b;look,90,0;hold,w,2500;log,c;look,200,0;wait,2000;log,d';
const levels = +(process.env.LEVELS || 1);

function run(file, rate) {
  let script = `throttle,${rate};set,quality,1;${walk}`;
  for (let lv = 2; lv <= levels; lv++) script += `;set,go to level,${lv};wait,9000;log,L${lv}a;hold,w,3000;log,L${lv}b;look,120,0;wait,2000;log,L${lv}c`;
  const out = execFileSync(process.execPath, [path.join(__dirname, 'play.js'), file, script], {encoding: 'utf8', maxBuffer: 1 << 26, timeout: 600000});
  const fps = {};
  for (const line of out.split('\n')) {
    const m = line.match(/^(\w+) (\{.*\})$/);
    if (!m) continue;
    const o = JSON.parse(m[2]);
    const lv = o.level;
    (fps[lv] = fps[lv] || []).push(o.fps);
  }
  return fps;
}

for (const file of args) {
  for (const rate of rates) {
    const fps = run(file, rate);
    const parts = Object.entries(fps).map(([lv, v]) => `level ${lv}: min ${Math.min(...v)} avg ${Math.round(v.reduce((a, b) => a + b, 0) / v.length)}`);
    console.log(`${path.basename(file)} x${rate} ${parts.join(', ')}`);
  }
}
