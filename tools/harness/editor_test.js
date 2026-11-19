const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

(async () => {
  const [url, outDir] = process.argv.slice(2);
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 900000, args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log('CON', m.text().slice(0, 300)); });
  page.on('pageerror', e => console.log('PERR', e.message));
  await page.setViewport({width: 1440, height: 900});
  await page.evaluateOnNewDocument(() => { try { localStorage.clear(); } catch (e) {} });
  await page.goto(url + '?t=starter', {waitUntil: 'networkidle2', timeout: 120000});
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms, label) => {
    const t0 = Date.now();
    for (;;) {
      if (await page.evaluate(fn)) return;
      if (Date.now() - t0 > ms) throw new Error('timed out waiting for ' + label);
      await sleep(250);
    }
  };
  const lastLine = () => page.evaluate(() => window.studio.doc('world.py').getValue().trim().split('\n').pop());
  const t0 = Date.now();
  await waitFor(() => window.levelEditor && window.levelEditor.desc, 120000, 'level description');
  console.log('level shown after', ((Date.now() - t0) / 1000).toFixed(1) + 's');
  await sleep(500);
  await page.screenshot({path: path.join(outDir, 'editor.png')});

  await page.click('#palette [data-place="prop"]');
  await page.type('#kindq', 'crate');
  await page.evaluate(() => [...document.querySelectorAll('#kindlist .kitem')].find(b => b.textContent === 'crate').click());
  const [x, y] = await page.evaluate(() => window.levelEditor.project([6, 0, 8.5]));
  await page.mouse.click(x, y);
  await waitFor(() => /\.prop\("crate", [\d.]+, 0, [\d.]+\)$/.test(window.studio.doc('world.py').getValue().trim()), 20000, 'new prop line');
  console.log('placed:', await lastLine());
  await waitFor(() => window.levelEditor.selected !== null && window.levelEditor.desc.calls[window.levelEditor.selected].method === 'prop', 20000, 'selection of the new prop');
  await sleep(300);
  await page.screenshot({path: path.join(outDir, 'placed.png')});

  for (const row of await page.$$('#props .prow')) {
    if (await row.$eval('span', s => s.textContent) !== 'yaw') continue;
    const inp = await row.$('input');
    await inp.click({clickCount: 3});
    await inp.type('30');
    await inp.press('Enter');
  }
  await waitFor(() => /yaw=30\)$/.test(window.studio.doc('world.py').getValue().trim()), 20000, 'yaw edit from the panel');
  console.log('panel edit:', await lastLine());

  const [p0, p1] = await page.evaluate(() => [window.levelEditor.project([6, 0, 8.5]), window.levelEditor.project([7, 0, 8.5])]);
  const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]);
  const dir = [(p1[0] - p0[0]) / len, (p1[1] - p0[1]) / len];
  const grab = [p0[0] + dir[0] * 62, p0[1] + dir[1] * 62];
  await page.mouse.move(grab[0], grab[1]);
  await sleep(100);
  await page.mouse.down();
  for (let k = 1; k <= 10; k++) await page.mouse.move(grab[0] + dir[0] * len * 0.2 * k, grab[1] + dir[1] * len * 0.2 * k);
  await page.mouse.up();
  await waitFor(() => !/\.prop\("crate", 6, 0, 8\.5, yaw=30\)$/.test(window.studio.doc('world.py').getValue().trim()), 20000, 'gizmo drag');
  console.log('gizmo drag:', await lastLine());

  await page.evaluate(() => {
    const d = window.studio.doc('world.py');
    const n = d.lineCount();
    d.replaceRange('\nlab.prop("barrel", 9, 0, 6)', {line: n - 1, ch: d.getLine(n - 1).length});
  });
  await waitFor(() => window.levelEditor.desc.levels[0].decor.filter(d => d[0] === 'barrel').length === 2, 20000, 'code edit reaching the viewport');
  console.log('code edit reached the viewport');

  await page.click('#palette [data-place="enemy"]');
  const [ex, ey] = await page.evaluate(() => window.levelEditor.project([3, 0, 9]));
  await page.mouse.click(ex, ey);
  await waitFor(() => /\.object\("rat1", "rat", [\d.]+, 0, [\d.]+, scale=6, solid=False, mode="follow", sight=8, speed=2.5\)$/.test(window.studio.doc('world.py').getValue().trim()), 20000, 'enemy line');
  await waitFor(() => window.levelEditor.selected !== null && window.levelEditor.desc.calls[window.levelEditor.selected].method === 'object', 20000, 'enemy selected');
  await sleep(300);
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('#props .prow')].find(r => r.querySelector('span').textContent === 'mode');
    const sel = row.querySelector('select');
    sel.value = 'wander';
    sel.dispatchEvent(new Event('change'));
  });
  await waitFor(() => /mode="wander"/.test(window.studio.doc('world.py').getValue()), 20000, 'mode change from the panel');
  console.log('enemy:', await lastLine());
  await page.click('#palette [data-place="checkpoint"]');
  const [kx, ky] = await page.evaluate(() => window.levelEditor.project([9, 0, 11]));
  await page.mouse.click(kx, ky);
  await waitFor(() => /\.checkpoint\(/.test(window.studio.doc('world.py').getValue()), 20000, 'checkpoint line');
  console.log('checkpoint:', await lastLine());
  await sleep(500);
  await page.screenshot({path: path.join(outDir, 'enemy.png')});

  await page.click('#build');
  await waitFor(() => !!window.studio.bytes || document.querySelector('.status').classList.contains('bad'), 600000, 'build');
  console.log('status:', await page.$eval('#status', e => e.textContent));
  const b64 = await page.evaluate(() => { const b = new Uint8Array(window.studio.bytes || []); let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return btoa(s); });
  fs.writeFileSync(path.join(outDir, 'edited.sb3'), Buffer.from(b64, 'base64'));
  fs.writeFileSync(path.join(outDir, 'world.py'), await page.evaluate(() => window.studio.doc('world.py').getValue()));
  await browser.close();
})().catch(e => { console.log('FAIL', e.message); process.exit(1); });
