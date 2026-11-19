const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const [site, game, outDir] = [process.argv[2], process.argv[3] || 'crypt', process.argv[4] || '.'];
const asset = {crypt: 'Crypt-Crawl.sb3', orchard: 'Orchard-Dash.sb3', showcase: 'Afterglow.sb3', portals: 'Portal-Lab.sb3',
  woods: 'Autumn-Woods.sb3', journey: 'The-Long-Walk.sb3', racing: 'Kart-Cup.sb3', starter: 'Starter.sb3'}[game];
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function readCamera(frame) {
  return frame.evaluate(() => {
    const st = S.vm.runtime.getTargetForStage();
    const g = n => { const v = st.lookupVariableByNameAndType(n, ''); return v ? +v.value : null; };
    return {mode: g('camera mode'), camY: g('camera y'), playerY: g('player y'), pitch: g('camera pitch'), health: g('health')};
  });
}

async function playIn(page, frame, tag) {
  const box = await (await frame.frameElement()).boundingBox();
  await sleep(1500);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await sleep(14000);
  const cam = await readCamera(frame);
  const file = path.join(outDir, tag + '.png');
  await page.screenshot({path: file, clip: box});
  const ok = cam.mode !== 1 && cam.camY > cam.playerY + 1;
  console.log(`${ok ? 'PASS' : 'FAIL'} ${tag}: camera mode ${cam.mode}, camera y ${cam.camY}, player y ${cam.playerY}, pitch ${cam.pitch}  ${file}`);
  return ok;
}

(async () => {
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 900000,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  let ok = true;
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PERR', e.message));
  await page.setViewport({width: 1440, height: 900});
  await page.evaluateOnNewDocument(() => { try { localStorage.clear(); } catch (e) {} });

  await page.goto(`${site}play.html?game=games/${asset}&v=${Date.now()}`, {waitUntil: 'networkidle2', timeout: 120000});
  const t0 = Date.now();
  while (!(await page.evaluate(() => !!(window.S && S.vm)))) { if (Date.now() - t0 > 120000) throw new Error('released game never loaded'); await sleep(500); }
  const iframeLike = page.mainFrame();
  iframeLike.frameElement = async () => page.$('body');
  ok = (await playIn(page, iframeLike, `${game}_released`)) && ok;

  await page.goto(`${site}?t=${game}&v=${Date.now()}`, {waitUntil: 'networkidle2', timeout: 120000});
  const t1 = Date.now();
  while (!(await page.evaluate(() => /Ready/.test(document.getElementById('status').textContent)))) { if (Date.now() - t1 > 300000) throw new Error('studio never got ready'); await sleep(500); }
  await page.click('#build');
  while (!(await page.evaluate(() => /Built|stopped/.test(document.getElementById('status').textContent)))) { if (Date.now() - t1 > 900000) throw new Error('studio build timed out'); await sleep(1000); }
  const frame = page.frames().find(f => f.url().includes('play.html'));
  const t2 = Date.now();
  while (!(await frame.evaluate(() => !!(window.S && S.vm)))) { if (Date.now() - t2 > 120000) throw new Error('built game never started'); await sleep(500); }
  ok = (await playIn(page, frame, `${game}_studio_build`)) && ok;
  await browser.close();
  process.exit(ok ? 0 : 1);
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
