const puppeteer = require('puppeteer');
const fs = require('fs');
(async () => {
  const shaders = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await puppeteer.launch({headless: 'new', args: ['--enable-gpu', '--ignore-gpu-blocklist', ...(process.platform === 'darwin' ? ['--use-angle=metal'] : [])]});
  const p = await b.newPage();
  const out = await p.evaluate(sh => {
    const gl = document.createElement('canvas').getContext('webgl');
    const res = [];
    for (const [name, [vs, fs]] of Object.entries(sh)) {
      for (const [t, src] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
        const s = gl.createShader(t); gl.shaderSource(s, src); gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) res.push(name + (t === gl.VERTEX_SHADER ? ' VS: ' : ' FS: ') + gl.getShaderInfoLog(s).slice(0, 400));
      }
    }
    return res;
  }, shaders);
  console.log(out.length ? out.join('\n') : 'all shaders compile');
  await b.close();
})();
