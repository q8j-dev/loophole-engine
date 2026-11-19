const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const http = require('http');

const serve = f => new Promise(res => {
  const srv = http.createServer((q, r) => { r.writeHead(200, {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/octet-stream'}); fs.createReadStream(f).pipe(r); });
  srv.listen(0, '127.0.0.1', () => { srv.unref(); res('http://127.0.0.1:' + srv.address().port + '/p.sb3'); });
});
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const [sb3, script] = process.argv.slice(2);
  const out = process.env.SHOTS || '.';
  const hd = !!process.env.HD;
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 240000, args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('console', m => { if (m.type() === 'error' || m.text().includes('RTERR')) console.log('CON', m.type(), m.text().slice(0, 300)); });
  page.on('pageerror', e => console.log('PERR', e.message, (e.stack || '').split('\n').slice(0, 6).join(' | ')));
  await page.setViewport(hd ? {width: 1920, height: 1080} : {width: 1280, height: 720});
  await page.goto('file://' + path.join(__dirname, 'harness.html'));
  await page.evaluate(async u => { await window.run(u); }, await serve(path.resolve(sb3)));
  await page.evaluate(() => {
    const st = () => S.vm.runtime.getTargetForStage();
    window.V = n => st().lookupVariableByNameAndType(n, '') || S.vm.runtime.targets.map(t => t.lookupVariableByNameAndType(n, '')).find(Boolean);
    window.Lst = n => st().lookupVariableByNameAndType(n, 'list') || S.vm.runtime.targets.map(t => t.lookupVariableByNameAndType(n, 'list')).find(Boolean);
    window.getv = n => { const v = V(n); return v ? v.value : null; };
    window.setv = (n, x) => { V(n).value = x; };
    window.key = (k, d) => S.vm.postIOData('keyboard', {key: k === 'space' ? ' ' : k, isDown: d});
    window.lockOn = () => { const e = S.vm.runtime.ext_pointerlock; if (e) { e.isLocked = () => true; } const c = S.vm.renderer && S.vm.renderer.canvas; if (c) { Object.defineProperty(document, 'pointerLockElement', {configurable: true, get: () => c}); document.dispatchEvent(new Event('pointerlockchange')); } };
    lockOn();
  });
  await sleep(+(process.env.BOOT || 3500));
  const api = ['player x', 'player y', 'player z', 'player yaw', 'player pitch', 'player on ground', 'level', 'level time', 'fps', 'looking at', 'holding', 'paused'];
  const log = async label => {
    const o = await page.evaluate(names => Object.fromEntries(names.map(n => [n, getv(n)])), api);
    console.log(label, JSON.stringify(o));
  };
  for (const step of (script || '').split(';').filter(Boolean)) {
    const [cmd, a, b, c, d] = step.split(',');
    if (cmd === 'wait') await sleep(+a);
    else if (cmd === 'shot') await page.screenshot({path: path.join(out, a + '.png')});
    else if (cmd === 'log') await log(a || 'log');
    else if (cmd === 'set') await page.evaluate((n, x) => setv(n, x === undefined || x === '' || isNaN(+x) ? (x || '') : +x), a, b);
    else if (cmd === 'item') await page.evaluate((n, i, x) => { Lst(n).value[+i - 1] = isNaN(+x) ? x : +x; Lst(n)._monitorUpToDate = false; }, a, b, c);
    else if (cmd === 'recstart') { global.recOn = true; global.recDone = (async () => { let i = 0; while (global.recOn) { await page.screenshot({path: path.join(out, `${a}_${String(i++).padStart(3, '0')}.png`)}); await sleep(+(b || 40)); } })(); }
    else if (cmd === 'recstop') { global.recOn = false; await global.recDone; }
    else if (cmd === 'rec') { for (let i = 0; i < +a; i++) { await page.screenshot({path: path.join(out, `${b}_${String(i).padStart(3, '0')}.png`)}); await sleep(+(c || 60)); } }
    else if (cmd === 'click') { await page.evaluate(bt => S.vm.postIOData('mouse', {isDown: true, button: +bt, x: 240, y: 180, canvasWidth: 480, canvasHeight: 360}), a); await sleep(150); await page.evaluate(bt => S.vm.postIOData('mouse', {isDown: false, button: +bt, x: 240, y: 180, canvasWidth: 480, canvasHeight: 360}), a); }
    else if (cmd === 'get') console.log('VAR', a, JSON.stringify(await page.evaluate(n => getv(n), a)));
    else if (cmd === 'list') console.log('LIST', a, JSON.stringify(await page.evaluate(n => Lst(n).value, a)));
    else if (cmd === 'pos') await page.evaluate((x, y, z) => { setv('player x', x); setv('player y', y); setv('player z', z); }, +a, +b, +c);
    else if (cmd === 'look') await page.evaluate((y, p) => { setv('player yaw', y); setv('player pitch', p); }, +a, +b);
    else if (cmd === 'aim') await page.evaluate((x, y, z) => { const px = getv('player x'), py = getv('player y') + 1.6, pz = getv('player z'); const dx = x - px, dy = y - py, dz = z - pz; setv('player yaw', Math.atan2(dx, -dz) * 180 / Math.PI); setv('player pitch', Math.atan2(dy, Math.hypot(dx, dz)) * 180 / Math.PI); }, +a, +b, +c);
    else if (cmd === 'down') await page.evaluate(k => key(k, true), a);
    else if (cmd === 'up') await page.evaluate(k => key(k, false), a);
    else if (cmd === 'tap') { await page.evaluate(k => key(k, true), a); await sleep(120); await page.evaluate(k => key(k, false), a); }
    else if (cmd === 'hold') { await page.evaluate(k => key(k, true), a); await sleep(+b); await page.evaluate(k => key(k, false), a); }
    else if (cmd === 'walkto' || cmd === 'walkportal' || cmd === 'walkexact') {
      let tx = +a, tz = +b, lim = +(c || 8000);
      if (cmd === 'walkportal') { const q = +a; tx = await page.evaluate(q => Lst('QCX').value[q - 1], q); tz = await page.evaluate(q => Lst('QCZ').value[q - 1], q); tz += +(b || 0); lim = +(c || 6000); }
      const t0 = Date.now();
      global.lastp = null;
      const lv0 = await page.evaluate(() => getv('level'));
      const top = await page.evaluate(() => getv('camera mode') == 3);
      if (!top) await page.evaluate(() => key('w', true));
      while (Date.now() - t0 < lim) {
        const dist = await page.evaluate((tx, tz, top) => {
          const px = getv('player x'), pz = getv('player z'); const dx = tx - px, dz = tz - pz; const dd = Math.hypot(dx, dz);
          if (top) {
            const cy = getv('camera yaw') * Math.PI / 180;
            const df = (dx * Math.sin(cy) - dz * Math.cos(cy)) / Math.max(dd, 1e-6), dr = (dx * Math.cos(cy) + dz * Math.sin(cy)) / Math.max(dd, 1e-6);
            key('w', dd > 0.3 && df > 0.38); key('s', dd > 0.3 && df < -0.38); key('d', dd > 0.3 && dr > 0.38); key('a', dd > 0.3 && dr < -0.38);
          } else if (dd > 0.3) setv(getv('camera mode') >= 2 ? 'camera yaw' : 'player yaw', Math.atan2(dx, -dz) * 180 / Math.PI);
          return dd; }, tx, tz, top);
        const exact = cmd === 'walkportal' || cmd === 'walkexact';
        if (dist < (exact ? 0.15 : 0.4)) break;
        if (exact && dist < 0.8) {
          await page.evaluate(() => key('w', false));
          await sleep(350);
          for (let k = 0; k < 20; k++) {
            const d2 = await page.evaluate((tx, tz) => { const dx = tx - getv('player x'), dz = tz - getv('player z'); const dd = Math.hypot(dx, dz); if (dd > 0.1) setv('player yaw', Math.atan2(dx, -dz) * 180 / Math.PI); return dd; }, tx, tz);
            if (d2 < 0.15) break;
            await page.evaluate(() => key('w', true)); await sleep(d2 > 0.4 ? 90 : 50); await page.evaluate(() => key('w', false)); await sleep(220);
          }
          break;
        }
        if (await page.evaluate(() => getv('level')) !== lv0) break;
        const jp = await page.evaluate(() => [getv('player x'), getv('player y'), getv('player z')]);
        if (global.lastp && Math.hypot(jp[0] - global.lastp[0], jp[1] - global.lastp[1], jp[2] - global.lastp[2]) > 2) { global.lastp = null; break; }
        global.lastp = jp;
        await sleep(30);
      }
      await page.evaluate(() => { for (const k of ['w', 'a', 's', 'd']) key(k, false); });
      await sleep(250);
    }
    else if (cmd === 'hideui') await page.evaluate(() => { const o = S.vm.runtime.targets.find(t => t.isOriginal && t.getName() === 'Overlay'); if (o) { o.setVisible(false); o.show = () => {}; for (const th of S.vm.runtime.threads.filter(t => t.target === o)) S.vm.runtime._stopThread(th); } });
    else console.log('unknown command', cmd);
  }
  await browser.close();
})();
