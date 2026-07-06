// Parity harness: render QRosetta text artifacts with the BROWSER builders so a test can
// compare them to services/publication.py. Input on stdin: {results, requests:[{id,fmt}]}.
// Output on stdout: JSON map "id|fmt" -> rendered text (or {__error__} if missing).
//
// artifacts_renderer.js is a browser global-scope script; it has no DOM access at load, so
// it evaluates cleanly here once buildArtifactCatalog is surfaced.
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(
    path.join(__dirname, '..', '..', 'static', 'js', 'artifacts_renderer.js'), 'utf8');
const surface = new Function('__out', src + '\n;__out.build = buildArtifactCatalog;');
const holder = {};
surface(holder);

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const catalog = holder.build(input.results);
const byId = {};
for (const item of catalog) byId[item.id] = item;

const out = {};
for (const req of input.requests) {
    const key = req.id + '|' + req.fmt;
    const item = byId[req.id];
    if (!item) { out[key] = { __error__: 'no such artifact id' }; continue; }
    try {
        out[key] = item.getText(req.fmt);
    } catch (e) {
        out[key] = { __error__: String(e && e.message || e) };
    }
}
process.stdout.write(JSON.stringify(out));
