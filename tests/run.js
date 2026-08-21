/**
 * Esegue ogni pagina di dist/ in un DOM simulato e intercetta gli errori runtime.
 * Non sostituisce il test in un browser vero (rete, rendering, font), ma prende
 * tutta la classe di bug piu' frequente: script che muore e porta giu' la pagina.
 *
 *   node tests/run.js
 */
const { JSDOM, VirtualConsole } = require('jsdom');
const fs = require('fs');
const path = require('path');

const DIST = path.join(__dirname, '..', 'dist');

function stub(win) {
  let frames = 0;
  win.__err = [];
  // loop di animazione limitato: i file girano davvero ma il test termina
  win.requestAnimationFrame = (cb) =>
    frames++ > 4 ? 0 : setTimeout(() => { try { cb(win.performance.now()); } catch (e) { win.__err.push(e.message); } }, 0);
  win.cancelAnimationFrame = clearTimeout;
  win.HTMLCanvasElement.prototype.getContext = function () {
    const noop = () => {};
    return new Proxy({}, { get: (t, p) => (p === 'measureText' ? () => ({ width: 10 }) : noop), set: () => true });
  };
  win.HTMLCanvasElement.prototype.setPointerCapture = function () {};
  win.HTMLCanvasElement.prototype.getBoundingClientRect = () => ({ left: 0, top: 0, width: 1300, height: 1300 });
  win.HTMLElement.prototype.scrollIntoView = function () {};
}

async function testPage(file) {
  const html = fs.readFileSync(file, 'utf-8');
  const errors = [];
  // CRITICO: gli errori di sintassi non arrivano a window.onerror, solo qui.
  // Senza questo il test dichiara "OK" pagine che nel browser non partono.
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => errors.push(e.message));
  const dom = new JSDOM(html, {
    virtualConsole: vc,
    runScripts: 'dangerously',
    url: 'https://wreck-atlas.test/' + path.basename(file),
    beforeParse: stub,
    pretendToBeVisual: true,
  });
  dom.window.addEventListener('error', (e) => errors.push(e.message || String(e.error)));
  await new Promise((r) => setTimeout(r, 600));
  const doc = dom.window.document;
  const all = errors.concat(dom.window.__err || []);
  const result = {
    name: path.basename(file),
    errors: all,
    title: (doc.title || '').slice(0, 40),
    sections: doc.querySelectorAll('section').length,
    listButtons: doc.querySelectorAll('.list button').length,
  };
  dom.window.close();
  return result;
}

(async () => {
  if (!fs.existsSync(DIST)) {
    console.error('dist/ non esiste. Esegui prima: python3 build.py');
    process.exit(1);
  }
  const files = fs.readdirSync(DIST)
    .filter((f) => f.endsWith('.html') && f !== 'index.html')
    .map((f) => path.join(DIST, f));
  const enDir = path.join(DIST, 'en');
  if (fs.existsSync(enDir)) {
    fs.readdirSync(enDir)
      .filter((f) => f.endsWith('.html'))
      .forEach((f) => files.push(path.join(enDir, f)));
  }
  let failed = 0;
  for (const f of files) {
    const r = await testPage(f);
    if (r.errors.length) failed++;
    console.log(
      (r.errors.length ? 'FAIL ' : 'OK   ') + r.name.padEnd(16) +
      '| sezioni: ' + String(r.sections).padStart(2) +
      ' | elenco: ' + String(r.listButtons).padStart(2) +
      (r.errors.length ? ' | ' + JSON.stringify(r.errors.slice(0, 2)) : '')
    );
  }
  console.log(failed ? `\n${failed} pagina/e con errori.` : '\nTutte le pagine passano.');
  process.exit(failed ? 1 : 0);
})();
