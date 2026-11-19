const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const [site, outDir, only] = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));
let failed = 0;
const check = (name, ok, detail) => { if (!ok) failed++; console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${ok ? '' : '  ' + (detail || '')}`); };

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 1800000,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('dialog', d => d.accept());
  await page.setViewport({width: 1440, height: 900});
  await page.evaluateOnNewDocument(() => { try { localStorage.clear(); } catch (e) {} });
  await page.goto(site, {waitUntil: 'networkidle2', timeout: 180000});
  const templates = await page.evaluate(() => fetch('templates.json').then(r => r.json()));
  const status = () => page.evaluate(() => document.getElementById('status').textContent);
  const waitFor = async (fn, ms, arg) => { const t0 = Date.now(); for (;;) { const v = await page.evaluate(fn, arg); if (v) return v; if (Date.now() - t0 > ms) return null; await sleep(400); } };

  for (const t of templates) {
    if (only && !only.split(',').includes(t.id)) continue;
    await page.goto(`${site}?t=${t.id}`, {waitUntil: 'networkidle2', timeout: 180000});
    const lvl = await waitFor(() => { const n = document.getElementById('lnote'); return n && !/Loading/.test(n.textContent) ? n.textContent || 'ok' : null; }, 240000);
    check(`${t.id}: level view loads`, lvl && !/problem/i.test(lvl), lvl);
    await page.screenshot({path: path.join(outDir, `${t.id}_level.png`)});
    const t0 = Date.now();
    await page.click('#build');
    const st = await waitFor(() => /Built|stopped/.test(document.getElementById('status').textContent) ? document.getElementById('status').textContent : null, 1500000);
    check(`${t.id}: builds (${Math.round((Date.now() - t0) / 1000)} s)`, st && /Built/.test(st), st);
    await sleep(6000);
    await page.screenshot({path: path.join(outDir, `${t.id}_play.png`)});
    const dl = await page.evaluate(() => !document.getElementById('download').disabled);
    check(`${t.id}: download button enabled after build`, dl);
    const tw = await page.evaluate(() => document.getElementById('turbowarp').href);
    check(`${t.id}: TurboWarp link`, /turbowarp\.org/.test(tw), tw);
  }

  if (!only || only.includes('starter')) {
    await page.goto(`${site}?t=starter`, {waitUntil: 'networkidle2', timeout: 180000});
    await waitFor(() => !!(window.studio && window.studio.doc('world.py')), 60000);
    for (const pane of ['level', 'play', 'tutorial', 'world', 'scratch']) {
      await page.click(`.ptab[data-pane="${pane}"]`);
      await sleep(1500);
      const ok = await page.evaluate(p => { const el = document.getElementById('pane-' + p); return el && !el.hidden && (p === 'level' || p === 'play' || el.textContent.trim().length > 200); }, pane);
      check(`tab ${pane} shows its pane`, ok);
    }
    await page.click('.ftab[data-file="game.py"]');
    await sleep(300);
    check('game.py tab switches the editor', await page.evaluate(() => document.querySelector('.ftab[data-file="game.py"]').getAttribute('aria-selected') === 'true'));
    await page.click('.ftab[data-file="world.py"]');
    const orig = await page.evaluate(() => window.studio.doc('world.py').getValue());
    await page.evaluate(() => { const d = window.studio.doc('world.py'); d.setValue(d.getValue().replace('lab.room(5, 0, -6', 'lab.romo(5, 0, -6')); });
    await page.click('#build');
    const err = await waitFor(() => /Built|stopped/.test(document.getElementById('status').textContent) ? document.getElementById('status').textContent : null, 600000);
    check('typo gives a friendly message', /line 7: levels don't have romo\(\)\. Did you mean room\?/.test(err || ''), err);
    check('typo line is highlighted', await page.evaluate(() => document.querySelectorAll('.cm-error').length > 0));
    await page.screenshot({path: path.join(outDir, 'typo.png')});
    await page.click('#reset');
    await sleep(800);
    check('reset template restores world.py', await page.evaluate(o => window.studio.doc('world.py').getValue() === o, orig));
  }
  check('no page errors', errors.length === 0, errors.slice(0, 3).join(' | '));
  await browser.close();
  process.exit(failed ? 1 : 0);
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
