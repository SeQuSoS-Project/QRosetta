// Calls exported functions of frontend modules (static/js/<module>.js) for the unit tests.
// stdin: {modules: [name], calls: [{fn, args}]}; stdout: {results: [value | {__error__}]}
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const js = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'static', 'js');

// Minimal stand-ins for the browser globals some modules read when they load.
const memory = new Map();
globalThis.localStorage ??= { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: k => memory.delete(k) };
const sessionMemory = new Map();
globalThis.sessionStorage ??= { getItem: k => sessionMemory.get(k) ?? null, setItem: (k, v) => sessionMemory.set(k, String(v)), removeItem: k => sessionMemory.delete(k) };
globalThis.window ??= Object.assign(globalThis, { location: { hostname: 'localhost', origin: 'http://localhost' } });
globalThis.document ??= { getElementById: () => null, querySelector: () => null, querySelectorAll: () => [], addEventListener: () => {} };
const input = JSON.parse(readFileSync(0, 'utf8'));
const modules = await Promise.all(input.modules.map(name => import(new URL('file://' + join(js, name)).href)));
const functions = Object.assign({ __newTab__: () => sessionMemory.clear() }, ...modules);

const results = input.calls.map(({ fn, args }) => {
    try {
        const value = typeof functions[fn] === 'function' ? functions[fn](...args) : functions[fn];
        return value === undefined ? null : value;
    } catch (e) {
        return { __error__: String((e && e.message) || e) };
    }
});
process.stdout.write(JSON.stringify({ results }));
