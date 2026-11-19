const puppeteer = require('puppeteer');

(async () => {
  const [projectUrl, sprite, out, zoomOut] = process.argv.slice(2);
  const browser = await puppeteer.launch({headless: 'new', args: ['--enable-gpu', '--ignore-gpu-blocklist',
    '--disable-features=BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessSendPreflights,PrivateNetworkAccessRespectPreflightResults,LocalNetworkAccessChecks',
    ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  await page.setViewport({width: 1600, height: 1000});
  await page.goto('https://turbowarp.org/editor?project_url=' + encodeURIComponent(projectUrl), {waitUntil: 'networkidle2', timeout: 180000});
  let found = false;
  for (let i = 0; i < 120 && !found; i++) {
    await new Promise(r => setTimeout(r, 1000));
    found = await page.evaluate(name => {
      for (const b of document.querySelectorAll('button')) if (/^(Allow|OK)$/i.test(b.textContent.trim())) b.click();
      const el = [...document.querySelectorAll('[class*="sprite-selector-item_sprite-name"]')].find(e => e.textContent.trim() === name);
      if (el) { el.click(); return true; }
      return false;
    }, sprite);
  }
  if (!found) { await page.screenshot({path: out}); throw new Error('sprite ' + sprite + ' never appeared'); }
  const small = await page.evaluate(() => {
    const btns = [...document.querySelectorAll('[class*="stage-header_stage-button"]')];
    const b = btns.length >= 3 ? btns[0] : null;
    if (!b) return null;
    const r = b.getBoundingClientRect();
    return [r.x + r.width / 2, r.y + r.height / 2];
  });
  if (small) await page.mouse.click(small[0], small[1]);
  await new Promise(r => setTimeout(r, 2500));
  for (let i = 0; i < +(zoomOut || 0); i++) {
    const box = await page.evaluate(() => {
      const imgs = [...document.querySelectorAll('.blocklyZoom > image')];
      const b = imgs.find(e => /zoom-out/.test(e.getAttribute('xlink:href') || e.getAttribute('href') || ''));
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return [r.x + r.width / 2, r.y + r.height / 2];
    });
    if (box) await page.mouse.click(box[0], box[1]);
    await new Promise(r => setTimeout(r, 400));
  }
  if (+(process.argv[6] || 0)) {
    await page.mouse.move(800, 500);
    await page.mouse.wheel({deltaY: +process.argv[6]});
  }
  await new Promise(r => setTimeout(r, 800));
  await page.screenshot({path: out});
  await browser.close();
})().catch(e => { console.log('FAIL', e.message); process.exit(1); });
