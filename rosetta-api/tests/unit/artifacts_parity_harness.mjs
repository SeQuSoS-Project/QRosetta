// Renders publication text artifacts and the artifact catalog with the browser builders
// (static/js/artifact_formats.js) for tests/unit/test_artifacts_parity.py.
// stdin: {results, requests: [{id, fmt}], nums?: [{v, d}], ints?: [v], ps?: [v]}
// stdout: {texts: {"id|fmt": text | {__error__}}, catalog: [...], nums: [...], ints: [...], ps: [...]}
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const formatsUrl = new URL(
    'file://' + join(here, '..', '..', 'static', 'js', 'artifact_formats.js'));

const { buildArtifactCatalog, _artNum, _artInt, _artP } = await import(formatsUrl.href);

const SPECIAL = { __nan__: NaN, __inf__: Infinity, '__-inf__': -Infinity };
const _special = v => (typeof v === 'string' && v in SPECIAL) ? SPECIAL[v] : v;

const input = JSON.parse(readFileSync(0, 'utf8'));
const catalog = buildArtifactCatalog(input.results || {});
const byId = {};
for (const item of catalog) byId[item.id] = item;

const texts = {};
for (const req of input.requests || []) {
    const key = req.id + '|' + req.fmt;
    const item = byId[req.id];
    if (!item) { texts[key] = { __error__: 'no such artifact id' }; continue; }
    try {
        texts[key] = item.getText(req.fmt);
    } catch (e) {
        texts[key] = { __error__: String((e && e.message) || e) };
    }
}
const out = {
    texts,
    catalog: catalog.map(({ id, label, group, view, formats, legend }) => ({ id, label, group, view, formats, legend })),
    nums: (input.nums || []).map(({ v, d }) => _artNum(_special(v), d)),
    ints: (input.ints || []).map(v => _artInt(_special(v))),
    ps: (input.ps || []).map(v => _artP(_special(v))),
};
process.stdout.write(JSON.stringify(out));
