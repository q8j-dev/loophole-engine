const fs = require('fs');
const path = require('path');
const https = require('https');
const dir = path.join(__dirname, 'ext');
fs.mkdirSync(dir, {recursive: true});
const get = (url, out) => new Promise((res, rej) => https.get(url, r => {
  if (r.statusCode !== 200) return rej(new Error(url + ' ' + r.statusCode));
  r.pipe(fs.createWriteStream(out)).on('finish', res);
}).on('error', rej));
(async () => {
  await get('https://extensions.turbowarp.org/obviousAlexC/penPlus.js', path.join(dir, 'penPlus.js'));
  await get('https://extensions.turbowarp.org/pointerlock.js', path.join(dir, 'pointerlock.js'));
  console.log('extensions saved to', dir);
})();
