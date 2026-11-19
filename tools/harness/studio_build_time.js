const puppeteer = require('puppeteer');

const [site, template, shot] = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 1800000,
    args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PERR', e.message));
  await page.setViewport({width: 1440, height: 900});
  await page.goto(`${site}?t=${template}`, {waitUntil: 'networkidle2', timeout: 120000});
  const status = () => page.evaluate(() => document.getElementById('status').textContent);
  const t0 = Date.now();
  while (!/Ready/.test(await status())) { if (Date.now() - t0 > 600000) throw new Error('never ready: ' + await status()); await sleep(500); }
  console.log(`studio ready in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  const t1 = Date.now();
  await page.click('#build');
  let last = '';
  for (;;) {
    const st = await status();
    if (st !== last) { console.log(`${((Date.now() - t1) / 1000).toFixed(1).padStart(6)} s  ${st.split('\n')[0]}`); last = st; }
    if (/Built|stopped/.test(st)) break;
    if (Date.now() - t1 > 1800000) throw new Error('build timed out');
    await sleep(1000);
  }
  console.log(`build took ${((Date.now() - t1) / 1000).toFixed(1)} s`);
  if (shot) { await sleep(8000); await page.screenshot({path: shot}); }
  await browser.close();
  process.exit(/Built/.test(last) ? 0 : 1);
})().catch(e => { console.log('ERROR', e.message); process.exit(1); });
