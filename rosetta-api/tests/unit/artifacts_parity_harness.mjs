// Renders publication text artifacts, the artifact catalog and the export-view helpers with
// the browser builders (static/js/artifact_catalog.js, artifact_views.js) for
// tests/unit/test_artifacts_parity.py.
// stdin: {results, requests: [{id, fmt, params?}], catalogParams?, normalize?: [{view, params}],
//         slugs?: [{view, params}], itemPaths?: [{view, slug, formats}], subsets?: [[sim]],
//         nums?: [{v, d}], ints?: [v], ps?: [v], fulls?: [v]}
// stdout: {texts: [text | {__error__}] in request order, catalog: [...], normalized: [...],
//          slugs: [...], itemPaths: [...], subsets: [...], nums: [...], ints: [...], ps: [...], fulls: [...]}
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const js = name => new URL('file://' + join(here, '..', '..', 'static', 'js', name)).href;

const { _artNum, _artInt, _artP, _artFull } = await import(js('artifact_formats.js'));
const { buildArtifactCatalog, scopedCatalog, _subsetResults } = await import(js('artifact_catalog.js'));
const { VIEW_OF_ARTIFACT, itemPaths, normalizeParams, viewSlug } = await import(js('artifact_views.js'));

const SPECIAL = { __nan__: NaN, __inf__: Infinity, '__-inf__': -Infinity };
const _special = v => (typeof v === 'string' && v in SPECIAL) ? SPECIAL[v] : v;
const _try = fn => { try { return fn(); } catch (e) { return { __error__: String((e && e.message) || e) }; } };

const input = JSON.parse(readFileSync(0, 'utf8'));
const results = input.results || {};

const texts = (input.requests || []).map(req => _try(() => {
        const vid = VIEW_OF_ARTIFACT[req.id];
        const catalog = req.params && vid ? scopedCatalog(results, vid, req.params).catalog : buildArtifactCatalog(results);
        const item = catalog.find(a => a.id === req.id);
        if (!item) throw new Error('no such artifact id');
        return item.getText(req.fmt);
}));
const catalog = _try(() => buildArtifactCatalog(results, input.catalogParams || {}));
const out = {
    texts,
    catalog: catalog.__error__ ? catalog : catalog.map(({ id, label, group, view, view_id, formats, legend }) => ({ id, label, group, view, view_id, formats, legend })),
    normalized: (input.normalize || []).map(r => _try(() => normalizeParams(r.view, r.params, results))),
    slugs: (input.slugs || []).map(r => _try(() => viewSlug(r.view, normalizeParams(r.view, r.params, results), results))),
    itemPaths: (input.itemPaths || []).map(r => itemPaths(r.view, r.slug, r.formats)),
    subsets: (input.subsets || []).map(sims => _subsetResults(results, new Set(sims))),
    nums: (input.nums || []).map(({ v, d }) => _artNum(_special(v), d)),
    ints: (input.ints || []).map(v => _artInt(_special(v))),
    ps: (input.ps || []).map(v => _artP(_special(v))),
    fulls: (input.fulls || []).map(v => _artFull(v)),
};
process.stdout.write(JSON.stringify(out));
