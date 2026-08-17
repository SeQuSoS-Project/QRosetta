// Parity harness: render QRosetta text artifacts with the BROWSER builders so a test can
// compare them to services/publication.py. Input on stdin: {results, requests:[{id,fmt}]}.
// Output on stdout: JSON map "id|fmt" -> rendered text (or {__error__} if missing).
//
// artifacts_renderer.js is an ES module, so it is imported here rather than eval'd. That
// means this harness exercises the same file the browser loads, through the same import
// graph — if a builder moved or an export was renamed, this fails rather than silently
// testing a stale copy.
//
// The builders themselves need no DOM, but importing the module pulls in its dependencies,
// and state.js reads localStorage while it initialises. Node has no browser globals, so the
// few that are touched at import time are stubbed below. Anything beyond these would throw
// loudly rather than silently returning something wrong.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

// A smaller shim would be possible if the pure data builders lived in their own module
// with no UI imports — worth doing, and it would make the parity-critical surface
// explicit rather than implied.
const store = new Map();
globalThis.localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
};
const noopElement = () => ({
    addEventListener() {}, appendChild() {}, setAttribute() {}, remove() {}, click() {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    style: {}, dataset: {}, children: [], value: '', textContent: '', innerHTML: '',
});
globalThis.document = {
    addEventListener() {},
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: noopElement,
    body: noopElement(),
};
globalThis.window = globalThis;
globalThis.location = { origin: 'http://localhost' };

const here = dirname(fileURLToPath(import.meta.url));
const rendererUrl = new URL(
    'file://' + join(here, '..', '..', 'static', 'js', 'artifacts_renderer.js'));

const { buildArtifactCatalog } = await import(rendererUrl.href);

const input = JSON.parse(readFileSync(0, 'utf8'));
const catalog = buildArtifactCatalog(input.results);
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
        out[key] = { __error__: String((e && e.message) || e) };
    }
}
process.stdout.write(JSON.stringify(out));
