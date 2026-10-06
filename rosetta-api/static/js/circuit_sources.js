// The circuits the Quantum Algorithms menu offers: generated algorithms, bundled examples
// (GET /examples), MQT Bench algorithms (sized by the Qubits field) and QASMBench circuits
// (fixed size). Menu values: an algorithm id, or 'example:', 'mqt:' or 'qasmbench:' + a name.

import { BASE_URL, fetchMQTBench, fetchMQTList, fetchQASMBench, fetchQASMBenchList, formatApiError } from './api.js';

let _examples = [];
let _mqtSizes = {};
let _qasmbench = [];

/** Fetch the examples and both benchmark lists; a list that fails to load is left empty. */
export async function loadCircuitSources() {
    const [examples, mqt, qasmbench] = await Promise.all([
        fetch(`${BASE_URL}/examples`).then(async r => (r.ok ? r.json() : Promise.reject(new Error(await formatApiError(r))))),
        fetchMQTList(),
        fetchQASMBenchList(),
    ].map(p => p.catch(e => { console.warn('Circuit source not loaded', e); return null; })));
    _examples = Array.isArray(examples) ? examples : [];
    _mqtSizes = mqt && typeof mqt === 'object' ? mqt : {};
    _qasmbench = Array.isArray(qasmbench) ? qasmbench : [];
}

/** Qubit count encoded in a QASMBench file name (`adder_n10` → 10), or 0. */
export function qasmbenchQubits(name) {
    const m = String(name).match(/_n(\d+)$/);
    return m ? parseInt(m[1], 10) : 0;
}

/** The menu's option groups: [label, [[value, text], ...]], empty groups left out. */
export function menuGroups(algorithms) {
    return [
        ['Algorithms', algorithms.map(a => [a.id, a.name])],
        ['Examples', _examples.map(ex => [`example:${ex.name}`, `${ex.title} (${ex.qubits}q)`])],
        ['MQT Bench', Object.keys(_mqtSizes).map(a => [`mqt:${a}`, a])],
        ['QASMBench', _qasmbench.map(n => [`qasmbench:${n}`, n])],
    ].filter(([, items]) => items.length);
}

/**
 * What a menu value names.
 * @returns {{ kind: 'algorithm'|'example'|'mqt'|'qasmbench', name: string, example?: object,
 *             sizes?: number[], qubits?: number }}
 */
export function selectionFor(value) {
    const v = String(value || '');
    if (v.startsWith('example:')) {
        const name = v.slice(8);
        const example = _examples.find(e => e.name === name) || null;
        return { kind: 'example', name, example, qubits: example?.qubits };
    }
    if (v.startsWith('mqt:')) {
        const name = v.slice(4);
        return { kind: 'mqt', name, sizes: [...(_mqtSizes[name] || [])].sort((a, b) => a - b) };
    }
    if (v.startsWith('qasmbench:')) {
        const name = v.slice(10);
        return { kind: 'qasmbench', name, qubits: qasmbenchQubits(name) };
    }
    return { kind: 'algorithm', name: v };
}

/** The available MQT Bench size closest to `qubits`. */
export function nearestSize(sizes, qubits) {
    if (!sizes.length) return qubits;
    return sizes.reduce((best, s) => (Math.abs(s - qubits) < Math.abs(best - qubits) ? s : best), sizes[0]);
}

/** OpenQASM text and editor title of a non-algorithm selection. */
export async function fetchSelection(sel, qubits) {
    if (sel.kind === 'example') {
        const res = await fetch(`${BASE_URL}/examples/${encodeURIComponent(sel.name)}`);
        if (!res.ok) throw new Error(await formatApiError(res));
        return { qasm: (await res.json()).qasm, title: `${sel.example?.title || sel.name} (${sel.qubits}q)` };
    }
    if (sel.kind === 'mqt') {
        const data = await fetchMQTBench(sel.name, qubits);
        return { qasm: data.qasm, title: `MQT Bench: ${sel.name} (${qubits}q)` };
    }
    const data = await fetchQASMBench(sel.name);
    return { qasm: data.qasm, title: `QASMBench: ${sel.name}` };
}

/** A playlist item for a non-algorithm selection; benchmark items stay references the server resolves. */
export async function playlistItemFor(sel, qubits) {
    if (sel.kind === 'mqt') return { source: 'mqt', algorithm: sel.name, qubits, name: sel.name, qasm_string: null };
    if (sel.kind === 'qasmbench') return { source: 'qasmbench', algorithm: sel.name, qubits: sel.qubits, name: sel.name, qasm_string: null };
    const { qasm } = await fetchSelection(sel, qubits);
    return { algorithm: sel.name.replace(/\.qasm$/, ''), qubits: sel.qubits, name: sel.example?.title || sel.name, qasm_string: qasm };
}
