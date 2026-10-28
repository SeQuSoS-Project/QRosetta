// For test_v7_api_restart.py: runs the page's pollJobStatus (static/js/api.js) against a scripted
// server on a virtual clock. stdin: {phases: [{for_ms, answer}]}, each answer {kind: "json" |
// "html" | "network", status, body}; the last phase lasts until the poll ends. stdout: {outcome,
// message, terminal, stopped, elapsed_ms, polls: [[t_ms, answer kind, status]], kicker: [texts]}.
import { readFileSync } from 'node:fs';

const kicker = [];
const memory = new Map();
globalThis.localStorage = { getItem: k => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: k => memory.delete(k) };
globalThis.sessionStorage = globalThis.localStorage;
globalThis.window = Object.assign(globalThis, { location: { hostname: 'localhost', origin: 'http://localhost' } });
const kickerNode = { set textContent(text) { kicker.push(text); }, get textContent() { return kicker.at(-1) ?? ''; } };
globalThis.document = {
    getElementById: id => (id === 'loader-kicker' ? kickerNode : null),
    querySelector: () => null, querySelectorAll: () => [], addEventListener: () => {},
};

let now = 0;
const timers = [];
let nextId = 1;
globalThis.setTimeout = (fn, ms) => { const id = nextId++; timers.push({ id, at: now + (ms || 0), fn }); return id; };
globalThis.clearTimeout = id => { const i = timers.findIndex(t => t.id === id); if (i >= 0) timers.splice(i, 1); };
Date.now = () => now;
console.warn = () => {};

const input = JSON.parse(readFileSync(0, 'utf8'));
const polls = [];

function answerAt(t) {
    let start = 0;
    for (const phase of input.phases) {
        if (phase.for_ms === undefined || t < start + phase.for_ms) return phase.answer;
        start += phase.for_ms;
    }
    return input.phases.at(-1).answer;
}

globalThis.fetch = async url => {
    const answer = answerAt(now);
    polls.push([now, answer.kind, answer.status ?? null, String(url)]);
    if (answer.kind === 'network') throw new TypeError('Failed to fetch');
    const isHtml = answer.kind === 'html';
    const text = isHtml ? (answer.body ?? '<html><head><title>502 Bad Gateway</title></head><body><center><h1>502 Bad Gateway</h1></center><hr><center>nginx</center></body></html>')
        : JSON.stringify(answer.body ?? {});
    const status = answer.status ?? 200;
    return {
        status, ok: status >= 200 && status < 300, statusText: '',
        headers: { get: name => (name.toLowerCase() === 'content-type' ? (isHtml ? 'text/html' : 'application/json') : null) },
        text: async () => text,
        json: async () => JSON.parse(text),
    };
};

const { pollJobStatus } = await import('../../static/js/api.js');
const flush = () => new Promise(resolve => setImmediate(resolve));

let result = null;
pollJobStatus('job-1').then(
    value => { result = { outcome: 'resolved', value }; },
    err => { result = { outcome: 'rejected', message: String(err.message), terminal: !!err.terminal, stopped: !!err.stopped }; },
);
for (let step = 0; step < 10000 && !result; step++) {
    for (let i = 0; i < 20; i++) await flush();
    if (result || !timers.length) break;
    timers.sort((a, b) => a.at - b.at);
    const timer = timers.shift();
    now = timer.at;
    timer.fn();
}
for (let i = 0; i < 20 && !result; i++) await flush();
process.stdout.write(JSON.stringify({ ...(result || { outcome: 'pending' }), elapsed_ms: now, polls, kicker, timers_left: timers.length }));
