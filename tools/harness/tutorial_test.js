const puppeteer = require('puppeteer');
const {execFileSync} = require('child_process');
const fs = require('fs');
const path = require('path');

(async () => {
  const [url, outDir] = process.argv.slice(2);
  fs.mkdirSync(outDir, {recursive: true});
  const browser = await puppeteer.launch({headless: 'new', protocolTimeout: 900000, args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PERR', e.message));
  await page.setViewport({width: 1440, height: 900});
  await page.evaluateOnNewDocument(() => { try { localStorage.clear(); } catch (e) {} });
  await page.goto(url + '?t=starter', {waitUntil: 'networkidle2', timeout: 120000});
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const waitFor = async (fn, ms, label, arg) => {
    const t0 = Date.now();
    for (;;) {
      if (await page.evaluate(fn, arg)) return;
      if (Date.now() - t0 > ms) throw new Error('timed out waiting for ' + label);
      await sleep(250);
    }
  };
  const lines = () => page.evaluate(() => window.studio.doc('world.py').getValue().split('\n').length);
  const place = async (tool, p) => {
    const before = await lines();
    await page.click(`#palette [data-place="${tool}"]`);
    const [x, y] = await page.evaluate(q => window.levelEditor.project(q), p);
    await page.mouse.click(x, y);
    await waitFor(n => window.studio.doc('world.py').getValue().split('\n').length > n, 20000, tool, before);
    await waitFor(() => window.levelEditor.selected !== null, 20000, tool + ' selected');
    await sleep(300);
  };
  await waitFor(() => window.levelEditor && window.levelEditor.desc, 120000, 'level');
  for (const p of [[4, 0, 9], [8, 0, 6], [4, 0, 3]]) await place('pickup', p);
  await place('enemy', [6, 0, 1]);
  await place('checkpoint', [6, 0, 7]);
  const code = await page.evaluate(() => window.studio.doc('world.py').getValue());
  console.log(code.trim().split('\n').slice(-5).join('\n'));
  await page.click('#build');
  await waitFor(() => !!window.studio.bytes || document.querySelector('.status').classList.contains('bad'), 600000, 'build');
  console.log('status:', await page.$eval('#status', e => e.textContent));
  const b64 = await page.evaluate(() => { const b = new Uint8Array(window.studio.bytes || []); let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode.apply(null, b.subarray(i, i + 32768)); return btoa(s); });
  const sb3 = path.join(outDir, 'tutorial.sb3');
  fs.writeFileSync(sb3, Buffer.from(b64, 'base64'));
  await browser.close();

  const xs = [...code.matchAll(/pickup\("apple\d+", "apple", ([\d.-]+), [\d.-]+, ([\d.-]+)/g)].map(m => [+m[1], +m[2]]);
  const walk = xs.map(([x, z]) => `walkto,${x},${z};wait,300`).join(';');
  const out = execFileSync(process.execPath, [path.join(__dirname, 'play.js'), sb3,
    `wait,2500;list,obj name;${walk};get,status;list,obj mode;list,obj sees player;log,end`], {encoding: 'utf8'});
  const status = (out.match(/^VAR status (.*)$/m) || [])[1];
  const sees = (out.match(/^LIST obj sees player (.*)$/m) || [])[1];
  console.log('status after apples:', status, ' rat sees player:', sees);
  const ok = status === '"Coins: 3"';
  console.log(ok ? 'PASS tutorial steps 3 to 6' : 'FAIL tutorial steps 3 to 6');
  process.exit(ok ? 0 : 1);
})().catch(e => { console.log('FAIL', e.message); process.exit(1); });
