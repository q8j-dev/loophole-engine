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
  await get('https://extensions.turbowarp.org/gamepad.js', path.join(dir, 'gamepad.js'));
  await get('https://extensions.turbowarp.org/local-storage.js', path.join(dir, 'local-storage.js'));
  console.log('extensions saved to', dir);
})();
