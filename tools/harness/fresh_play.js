const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const [url, outDir, script] = process.argv.slice(2);
const W = +(process.env.W || 1920), H = +(process.env.H || 1080);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const KEYS = {w: 'KeyW', a: 'KeyA', s: 'KeyS', d: 'KeyD', e: 'KeyE', f: 'KeyF', g: 'KeyG', r: 'KeyR', p: 'KeyP', c: 'KeyC',
  space: 'Space', shift: 'ShiftLeft', left: 'ArrowLeft', right: 'ArrowRight', up: 'ArrowUp', down: 'ArrowDown', esc: 'Escape'};

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 600000,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  page.on('console', m => { if (m.type() === 'error' && !/404|favicon/.test(m.text())) console.log('CONSOLE', m.text().slice(0, 200)); });
  await page.setViewport({width: W, height: H});
  await page.evaluateOnNewDocument(() => { try { localStorage.clear(); } catch (e) {} });
  await page.goto(url, {waitUntil: 'networkidle2', timeout: 180000});
  const t0 = Date.now();
  while (!(await page.evaluate(() => !!(window.S && S.vm)))) { if (Date.now() - t0 > 180000) throw new Error('game never loaded'); await sleep(300); }
  const canvas = async () => page.evaluate(() => { const b = S.renderer.canvas.getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2, b.width, b.height]; });
  const read = () => page.evaluate(() => {
    const st = S.vm.runtime.getTargetForStage();
    const g = n => { const v = st.lookupVariableByNameAndType(n, ''); return v ? v.value : null; };
    const r = x => Math.round(x * 100) / 100;
    return {msg: g('message'), status: g('status'), level: g('level name'), fps: g('fps'), x: r(+g('player x')), y: r(+g('player y')), z: r(+g('player z')), cam: g('camera mode'), driving: g('driving'), health: g('health')};
  });
  for (const step of script.split(';').filter(Boolean)) {
    const [cmd, a, b] = step.split(',');
    if (cmd === 'wait') await sleep(+a);
    else if (cmd === 'click') {
      const [x, y] = await canvas();
      await page.mouse.click(x, y);
      await page.evaluate(() => {
        const c = S.renderer.canvas;
        Object.defineProperty(document, 'pointerLockElement', {configurable: true, get: () => c});
        document.dispatchEvent(new Event('pointerlockchange'));
        const e = S.vm.runtime.ext_pointerlock; if (e) e.isLocked = () => true;
      });
    }
    else if (cmd === 'hold') { await page.keyboard.down(KEYS[a]); await sleep(+b); await page.keyboard.up(KEYS[a]); }
    else if (cmd === 'down') await page.keyboard.down(KEYS[a]);
    else if (cmd === 'up') await page.keyboard.up(KEYS[a]);
    else if (cmd === 'tap') { await page.keyboard.down(KEYS[a]); await sleep(110); await page.keyboard.up(KEYS[a]); }
    else if (cmd === 'shot') { await page.screenshot({path: path.join(outDir, a + '.png')}); console.log('SHOT', a, JSON.stringify(await read())); }
    else if (cmd === 'read') console.log('READ', a || '', JSON.stringify(await read()));
    else console.log('unknown', cmd);
  }
  await browser.close();
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
