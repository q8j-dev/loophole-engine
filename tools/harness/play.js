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
  await page.setViewport(Object.assign(hd ? {width: 1920, height: 1080} : {width: 1280, height: 720}, process.env.TOUCH ? {hasTouch: true, isMobile: false} : {}));
  await page.goto('file://' + path.join(__dirname, 'harness.html'));
  await page.evaluate(async u => { await window.run(u); }, await serve(path.resolve(sb3)));
  if (process.env.NOLOCK) await page.evaluate(() => { window.NOLOCK = 1; });
  if (process.env.FAKEPAD) await page.evaluate(() => {
    window.rumbles = [];
    window.fakePad = {id: 'Fake pad', index: 0, connected: true, mapping: 'standard', timestamp: 0,
      axes: [0, 0, 0, 0], buttons: Array.from({length: 17}, () => ({pressed: false, touched: false, value: 0})),
      vibrationActuator: {playEffect: (t, o) => { window.rumbles.push(o); return Promise.resolve('complete'); }}};
    navigator.getGamepads = () => [window.fakePad, null, null, null];
  });
  await page.evaluate(() => {
    const st = () => S.vm.runtime.getTargetForStage();
    window.V = n => st().lookupVariableByNameAndType(n, '') || S.vm.runtime.targets.map(t => t.lookupVariableByNameAndType(n, '')).find(Boolean);
    window.Lst = n => st().lookupVariableByNameAndType(n, 'list') || S.vm.runtime.targets.map(t => t.lookupVariableByNameAndType(n, 'list')).find(Boolean);
    window.getv = n => { const v = V(n); return v ? v.value : null; };
    window.setv = (n, x) => { V(n).value = x; };
    window.key = (k, d) => S.vm.postIOData('keyboard', {key: k === 'space' ? ' ' : k, isDown: d});
    window.lockOn = () => { const e = S.vm.runtime.ext_pointerlock; if (e) { e.isLocked = () => true; } const c = S.vm.renderer && S.vm.renderer.canvas; if (c) { Object.defineProperty(document, 'pointerLockElement', {configurable: true, get: () => c}); document.dispatchEvent(new Event('pointerlockchange')); } };
    if (!window.NOLOCK) lockOn();
    window.swingNear = () => {
      const now = performance.now();
      if (window.fdown) { if (now - window.fdown > 90) { key('f', false); window.fdown = 0; window.flast = now; } return; }
      if (window.flast && now - window.flast < 450) return;
      const hp = Lst('obj health').value, ox = Lst('obj x').value, oz = Lst('obj z').value, vis = Lst('obj visible').value;
      const px = getv('player x'), pz = getv('player z');
      for (let i = 0; i < hp.length; i++) if (+hp[i] > 0 && +vis[i] === 1 && Math.hypot(ox[i] - px, oz[i] - pz) < 2.3) { key('f', true); window.fdown = now; return; }
    };
  });
  await sleep(+(process.env.BOOT || 3500));
  const cdpTouch = process.env.TOUCH ? await page.createCDPSession() : null;
  const stageToPage = async (sx, sy) => page.evaluate((sx, sy) => {
    const r = S.renderer.canvas.getBoundingClientRect();
    return [r.left + (sx / 640 + 0.5) * r.width, r.top + (0.5 - sy / 360) * r.height];
  }, sx, sy);
  const touch = async (type, sx, sy) => {
    const pts = type === 'touchEnd' ? [] : [{x: (await stageToPage(sx, sy))[0], y: (await stageToPage(sx, sy))[1], id: 1}];
    await cdpTouch.send('Input.dispatchTouchEvent', {type, touchPoints: pts});
  };
  global.lastTouch = [0, 0];
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
    else if (cmd === 'tdown') { global.lastTouch = [+a, +b]; await touch('touchStart', +a, +b); }
    else if (cmd === 'tmove') {
      const n = +(c || 8);
      const [x0, y0] = global.lastTouch;
      for (let k = 1; k <= n; k++) { await touch('touchMove', x0 + (+a - x0) * k / n, y0 + (+b - y0) * k / n); await sleep(16); }
      global.lastTouch = [+a, +b];
    }
    else if (cmd === 'tup') await touch('touchEnd');
    else if (cmd === 'padaxis') await page.evaluate((i, v) => { window.fakePad.axes[i] = v; }, +a, +b);
    else if (cmd === 'padbtn') await page.evaluate((i, v) => { window.fakePad.buttons[i] = {pressed: !!v, touched: !!v, value: v}; }, +a, +b);
    else if (cmd === 'js') console.log('JS', JSON.stringify(await page.evaluate(step.slice(3))));
    else if (cmd === 'rumbles') console.log('RUMBLES', JSON.stringify(await page.evaluate(() => window.rumbles)));
    else if (cmd === 'throttle') { const cdp = await page.createCDPSession(); await cdp.send('Emulation.setCPUThrottlingRate', {rate: +a}); }
    else if (cmd === 'audio') console.log('AUDIO', a || '', JSON.stringify(await page.evaluate(() => S.vm.runtime.targets
      .filter(t => !t.isOriginal && t.sprite.name === (window.audioSprite || 'Engine Audio'))
      .map(t => {
        const v = Object.values(t.variables).find(x => x.name === 'my_sound');
        const st = t.getCustomState('Scratch.sound') || {};
        const bank = t.sprite.soundBank;
        const playing = t.sprite.sounds.filter(s => bank.soundPlayers[s.soundId] && bank.soundPlayers[s.soundId].isPlaying).map(s => s.name);
        return {sound: v && v.value, volume: Math.round(t.volume), pan: st.effects ? Math.round(st.effects.pan) : null, playing};
      }))));
    else if (cmd === 'prof') console.log('PROF', await page.evaluate(async ms => {
      const gl = S.renderer.gl;
      const st = {};
      const wrap = (obj, name, key) => { const o = obj[name]; obj[name] = function () { const t = performance.now(); const r = o.apply(this, arguments); const e = st[key] || (st[key] = [0, 0, 0]); e[0]++; e[1] += performance.now() - t; if (typeof r === 'string') e[2] += r.length; return r; }; return () => { obj[name] = o; }; };
      const un = [wrap(JSON, 'stringify', 'stringify'), wrap(JSON, 'parse', 'parse'), wrap(gl, 'bufferData', 'bufferData'), wrap(gl, 'drawArrays', 'drawArrays'), wrap(gl, 'uniform4fv', 'uniform4fv'), wrap(gl, 'useProgram', 'useProgram'), wrap(gl, 'bindFramebuffer', 'bindFramebuffer')];
      const hist = {};
      const os = JSON.stringify;
      JSON.stringify = function (v) { const t = performance.now(); const r = os.apply(this, arguments); const k = Array.isArray(v) ? 'L' + v.length : 'x'; const e = hist[k] || (hist[k] = [0, 0]); e[0]++; e[1] += performance.now() - t; return r; };
      un.push(() => { JSON.stringify = os; });
      let frames = 0, busy = 0;
      const t0 = performance.now();
      const cnt = () => { frames++; if (performance.now() - t0 < ms) requestAnimationFrame(cnt); };
      requestAnimationFrame(cnt);
      await new Promise(r => setTimeout(r, ms));
      un.reverse().forEach(f => f());
      return 'frames ' + frames + ' (' + (ms / frames).toFixed(1) + 'ms/f)\n' + Object.entries(st).map(([k, v]) => k + ' ' + (v[0] / frames).toFixed(1) + '/f ' + (v[1] / frames).toFixed(2) + 'ms/f' + (v[2] ? ' ' + (v[2] / v[0] / 1024).toFixed(0) + 'KB avg' : '')).join('\n') + '\n' + Object.entries(hist).sort((a, b) => b[1][1] - a[1][1]).map(([k, v]) => k + ' ' + (v[0] / frames).toFixed(1) + '/f ' + (v[1] / frames).toFixed(2) + 'ms/f').join('  ');
    }, +(a || 3000)));
    else if (cmd === 'cpuprof') {
      const cdp = await page.createCDPSession();
      await cdp.send('Profiler.enable');
      await cdp.send('Profiler.setSamplingInterval', {interval: 200});
      await cdp.send('Profiler.start');
      await sleep(+(a || 3000));
      const {profile} = await cdp.send('Profiler.stop');
      const self = {};
      const dt = {};
      for (let i = 0; i < profile.samples.length; i++) dt[profile.samples[i]] = (dt[profile.samples[i]] || 0) + (profile.timeDeltas[i] || 0);
      for (const n of profile.nodes) {
        const f = n.callFrame;
        const k = (f.functionName || '(anon)') + ' ' + (f.url || '').split('/').pop().slice(0, 30) + ':' + f.lineNumber;
        self[k] = (self[k] || 0) + (dt[n.id] || 0);
      }
      const tot = Object.values(self).reduce((x, y) => x + y, 0);
      console.log('CPU', Object.entries(self).sort((x, y) => y[1] - x[1]).slice(0, +(b || 30)).map(([k, v]) => (100 * v / tot).toFixed(1) + '% ' + k).join('\n'));
    }
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
        if (global.autofight) await page.evaluate(() => window.swingNear && window.swingNear());
        await sleep(30);
      }
      await page.evaluate(() => { for (const k of ['w', 'a', 's', 'd']) key(k, false); });
      await sleep(250);
    }
    else if (cmd === 'waitcs') console.log('WAITCS', await page.evaluate(ms => new Promise(res => {
      let seen = false;
      const t0 = performance.now();
      const iv = setInterval(() => {
        const c = +getv('csi');
        if (c > 0) seen = true;
        if ((seen && c === 0) || performance.now() - t0 > ms) { clearInterval(iv); res(seen && c === 0 ? 'done' : seen ? 'still playing' : 'never started'); }
      }, 30);
    }), +(a || 30000)));
    else if (cmd === 'pclick' || cmd === 'pmove') {
      const r = await page.evaluate(() => { const b = S.renderer.canvas.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; });
      if (!global.mpos) { global.mpos = r; await page.mouse.move(r[0], r[1]); }
      if (cmd === 'pclick') { await page.mouse.move(r[0], r[1]); global.mpos = r; await page.mouse.down(); await sleep(80); await page.mouse.up(); }
      else { const n = +(c || 10); for (let k = 0; k < n; k++) { global.mpos = [global.mpos[0] + +a / n, global.mpos[1] + +b / n]; await page.mouse.move(global.mpos[0], global.mpos[1]); await sleep(16); } }
    }
    else if (cmd === 'autofight') global.autofight = a !== '0';
    else if (cmd === 'fight') {
      const t0 = Date.now();
      while (Date.now() - t0 < +(a || 3000)) { await page.evaluate(() => window.swingNear()); await sleep(30); }
      await page.evaluate(() => key('f', false));
    }
    else if (cmd === 'hideui') await page.evaluate(() => { const o = S.vm.runtime.targets.find(t => t.isOriginal && t.getName() === 'Overlay'); if (o) { o.setVisible(false); o.show = () => {}; for (const th of S.vm.runtime.threads.filter(t => t.target === o)) S.vm.runtime._stopThread(th); } });
    else console.log('unknown command', cmd);
  }
  await browser.close();
})();
