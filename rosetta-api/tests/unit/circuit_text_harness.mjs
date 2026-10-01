// Calls the pure Circuits-view modules (static/js/text_diff.js, qasm_text.js,
// circuit_panes.js) for tests/unit/test_circuit_explorer.py.
// stdin: {calls: [{fn, args}]}; stdout: {results: [value | {__error__}]}
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const js = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'static', 'js');
const load = name => import(new URL('file://' + join(js, name)).href);
const modules = await Promise.all(['text_diff.js', 'qasm_text.js', 'circuit_panes.js'].map(load));
const functions = Object.assign({}, ...modules);

const input = JSON.parse(readFileSync(0, 'utf8'));
const results = input.calls.map(({ fn, args }) => {
    try {
        const value = typeof functions[fn] === 'function' ? functions[fn](...args) : functions[fn];
        return value === undefined ? null : value;
    } catch (e) {
        return { __error__: String((e && e.message) || e) };
    }
});
process.stdout.write(JSON.stringify({ results }));
