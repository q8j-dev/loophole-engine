(() => {
  const $ = id => document.getElementById(id);
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
    del(k) { try { localStorage.removeItem(k); } catch (e) {} },
  };
  const FILES = ['world.py', 'game.py'];
  let templates = [];
  let current = null;
  let file = 'world.py';
  const docs = {};
  let lastBuild = null;
  let building = false;
  let worker = null;
  let workerReady = false;
  const pending = new Map();
  let sceneId = 0;
  const listeners = [];

  const editor = CodeMirror($('editor'), {
    mode: 'python', lineNumbers: true, indentUnit: 4, tabSize: 4, indentWithTabs: false,
    extraKeys: {Tab: cm => cm.replaceSelection('    '), 'Ctrl-Enter': () => build(), 'Cmd-Enter': () => build()},
  });

  function key(f) { return 'lh:' + current.id + ':' + f; }

  function setTemplate(id) {
    current = templates.find(t => t.id === id) || templates[0];
    store.set('lh:template', current.id);
    for (const f of FILES) {
      const saved = store.get(key(f));
      const d = CodeMirror.Doc(saved !== null ? saved : (current.files[f] || ''), 'python');
      d.on('change', () => {
        if (docs[f] !== d) return;
        store.set(key(f), d.getValue());
        updateTurboWarp();
        if (f === 'world.py') for (const cb of listeners) cb('edit');
      });
      docs[f] = d;
    }
    showFile('world.py');
    for (const cb of listeners) cb('template');
    lastBuild = null;
    $('download').disabled = true;
    updateTurboWarp();
  }

  function showFile(f) {
    file = f;
    editor.swapDoc(docs[f]);
    for (const b of document.querySelectorAll('.ftab')) b.setAttribute('aria-selected', String(b.dataset.file === f));
    editor.focus();
  }

  function edited() {
    return FILES.some(f => (docs[f] ? docs[f].getValue() : '') !== (current.files[f] || ''));
  }

  function updateTurboWarp() {
    const a = $('turbowarp');
    if (current && current.game && !edited()) {
      const url = new URL(current.game, location.href).href;
      a.href = 'https://turbowarp.org/editor?project_url=' + encodeURIComponent(url);
      a.textContent = 'Open in TurboWarp';
    } else {
      a.href = 'https://turbowarp.org/editor';
      a.textContent = 'Open TurboWarp';
    }
  }

  function setStatus(text, p, cls) {
    const box = document.querySelector('.status');
    box.classList.remove('ok', 'bad');
    if (cls) box.classList.add(cls);
    $('status').textContent = text;
    if (p !== undefined) $('meter').style.width = Math.round(Math.max(0, Math.min(1, p)) * 100) + '%';
  }

  function log(line) {
    const el = $('log');
    el.textContent += line + '\n';
    el.scrollTop = el.scrollHeight;
  }

  function startWorker() {
    if (worker) return;
    worker = new Worker('worker.js');
    worker.onmessage = e => {
      const m = e.data;
      if (m.type === 'progress') {
        if (building) setStatus(m.text, m.p);
        if (m.line) log(m.line);
      } else if (m.type === 'scene') {
        const p = pending.get(m.id);
        pending.delete(m.id);
        if (p) m.error ? p.reject(Object.assign(new Error(m.error), {line: m.line})) : p.resolve(JSON.parse(m.json));
      } else if (m.type === 'ready') {
        workerReady = true;
        if (!building) setStatus('Ready. Press Build game, or Ctrl+Enter.', 0);
      } else if (m.type === 'done') {
        building = false;
        $('build').disabled = false;
        lastBuild = m.bytes;
        $('download').disabled = false;
        const mb = (m.bytes.byteLength / 1048576).toFixed(1);
        setStatus('Built ' + current.name + ' (' + mb + ' MB). It is playing on the right.', 1, 'ok');
        showPane('play');
        const copy = m.bytes.slice(0);
        $('player').contentWindow.postMessage({type: 'play', bytes: copy.buffer}, location.origin, [copy.buffer]);
      } else if (m.type === 'error') {
        building = false;
        $('build').disabled = false;
        const text = String(m.text).replace(/^SystemExit:\s*/m, '').replace(/^\w+Error:\s*/m, '');
        setStatus('The build stopped: ' + text + '\nFix world.py and press Build game again.', 1, 'bad');
        log(m.text);
      }
    };
  }

  function describe() {
    startWorker();
    const id = ++sceneId;
    worker.postMessage({type: 'describe', id, files: {'world.py': docs['world.py'].getValue()}});
    return new Promise((resolve, reject) => pending.set(id, {resolve, reject}));
  }

  function build() {
    if (building) return;
    startWorker();
    building = true;
    $('build').disabled = true;
    $('log').textContent = '';
    setStatus(workerReady ? 'Reading world.py' : 'Starting Python. The first build downloads about 40 MB.', 0.02);
    const files = {};
    for (const f of FILES) {
      const v = docs[f].getValue();
      if (v.trim()) files[f] = v;
    }
    worker.postMessage({type: 'build', files});
  }

  function download() {
    if (!lastBuild) return;
    const blob = new Blob([lastBuild], {type: 'application/x.scratch.sb3'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = current.name.replace(/[^\w -]/g, '').trim().replace(/\s+/g, '-') + '.sb3';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  async function loadDoc(pane, path) {
    const el = $('pane-' + pane);
    if (el.dataset.loaded) return;
    el.dataset.loaded = '1';
    try {
      const md = await (await fetch(path)).text();
      el.innerHTML = marked.parse(md);
      for (const img of el.querySelectorAll('img[src]')) {
        const s = img.getAttribute('src');
        if (!/^https?:/.test(s)) img.src = new URL(s, new URL(path, location.href)).href;
        img.loading = 'lazy';
      }
      for (const a of el.querySelectorAll('a[href]')) {
        const h = a.getAttribute('href');
        if (h.startsWith('#')) continue;
        a.href = new URL(h, 'https://github.com/q8j-dev/loophole-engine/blob/main/docs/').href;
        a.target = '_blank';
        a.rel = 'noopener';
      }
    } catch (e) {
      el.textContent = 'This guide could not load. It is also on GitHub in the docs folder.';
    }
  }

  function showPane(p) {
    for (const b of document.querySelectorAll('.ptab')) b.setAttribute('aria-selected', String(b.dataset.pane === p));
    for (const id of ['level', 'play', 'tutorial', 'world', 'scratch']) $('pane-' + id).hidden = id !== p;
    for (const cb of listeners) cb('pane:' + p);
    if (p === 'tutorial') loadDoc('tutorial', 'docs/tutorial.md');
    if (p === 'world') loadDoc('world', 'docs/world-api.md');
    if (p === 'scratch') loadDoc('scratch', 'docs/scratch-api.md');
  }

  for (const b of document.querySelectorAll('.ftab')) b.addEventListener('click', () => showFile(b.dataset.file));
  for (const b of document.querySelectorAll('.ptab')) b.addEventListener('click', () => showPane(b.dataset.pane));
  $('template').addEventListener('change', e => setTemplate(e.target.value));
  $('build').addEventListener('click', build);
  $('download').addEventListener('click', download);
  $('reset').addEventListener('click', () => {
    for (const f of FILES) store.del(key(f));
    setTemplate(current.id);
  });

  fetch('templates.json').then(r => r.json()).then(list => {
    templates = list;
    const sel = $('template');
    for (const t of list) {
      const o = document.createElement('option');
      o.value = t.id;
      o.textContent = t.name;
      sel.appendChild(o);
    }
    const want = new URLSearchParams(location.search).get('t') || store.get('lh:template') || 'starter';
    setTemplate(want);
    sel.value = current.id;
    startWorker();
  });
  window.studio = {
    build, describe, editor, showFile, showPane,
    doc: name => docs[name],
    on: cb => listeners.push(cb),
    get file() { return file; },
    get bytes() { return lastBuild; },
    get building() { return building; },
  };
  window.dispatchEvent(new Event('studio-ready'));
})();
