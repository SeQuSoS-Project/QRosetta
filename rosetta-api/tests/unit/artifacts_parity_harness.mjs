// Parity harness: render QRosetta text artifacts with the BROWSER builders so a test can
// compare them to services/publication.py. Input on stdin: {results, requests:[{id,fmt}]}.
// Output on stdout: JSON map "id|fmt" -> rendered text (or {__error__} if missing).
//
// artifact_formats.js is an ES module, so it is imported here rather than eval'd. That
// means this harness exercises the same file the browser loads, through the same import
// graph — if a builder moved or an export was renamed, this fails rather than silently
// testing a stale copy. artifact_formats.js holds only the pure data/text builders (no
// DOM, no network) — the parity-critical surface, kept separate from the viewer/panel
// code in artifacts_renderer.js.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const formatsUrl = new URL(
    'file://' + join(here, '..', '..', 'static', 'js', 'artifact_formats.js'));

const { buildArtifactCatalog } = await import(formatsUrl.href);

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
