const puppeteer = require('puppeteer');
const fs = require('fs');
(async () => {
  const [url, out, tpl] = process.argv.slice(2);
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 900000, args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('console', m => { if (m.type() === 'error') console.log('CON', m.text().slice(0, 300)); });
  page.on('pageerror', e => console.log('PERR', e.message));
  await page.setViewport({width: 1440, height: 900});
  await page.goto(url + (tpl ? '?t=' + tpl : ''), {waitUntil: 'networkidle2', timeout: 120000});
  const t0 = Date.now();
  await page.click('#build');
  let last = '';
  for (;;) {
    const st = await page.evaluate(() => ({s: document.getElementById('status').textContent, w: document.getElementById('meter').style.width, done: !!(window.studio.bytes), bad: document.querySelector('.status').classList.contains('bad')}));
    const line = st.w + ' ' + st.s;
    if (line !== last) { console.log(((Date.now() - t0) / 1000).toFixed(1) + 's', line); last = line; }
    if (st.done || st.bad) break;
    if (Date.now() - t0 > 840000) { console.log('timeout'); break; }
    await new Promise(r => setTimeout(r, 1000));
  }
  await page.screenshot({path: out.replace(/\.sb3$/, '.png')});
  const b64 = await page.evaluate(() => { const b = new Uint8Array(window.studio.bytes || []); let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return btoa(s); });
  fs.writeFileSync(out, Buffer.from(b64, 'base64'));
  console.log('saved', out, Buffer.from(b64, 'base64').length);
  await new Promise(r => setTimeout(r, 4000));
  await page.screenshot({path: out.replace(/\.sb3$/, '_play.png')});
  await browser.close();
})();
