// Calls exported functions of pure frontend modules (static/js/<module>.js) for the unit tests.
// stdin: {modules: [name], calls: [{fn, args}]}; stdout: {results: [value | {__error__}]}
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const js = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'static', 'js');
const input = JSON.parse(readFileSync(0, 'utf8'));
const modules = await Promise.all(input.modules.map(name => import(new URL('file://' + join(js, name)).href)));
const functions = Object.assign({}, ...modules);

const results = input.calls.map(({ fn, args }) => {
    try {
        const value = typeof functions[fn] === 'function' ? functions[fn](...args) : functions[fn];
        return value === undefined ? null : value;
    } catch (e) {
        return { __error__: String((e && e.message) || e) };
    }
});
process.stdout.write(JSON.stringify({ results }));
