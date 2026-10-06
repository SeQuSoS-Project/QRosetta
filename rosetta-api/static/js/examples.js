// Bundled example circuits from GET /examples: the list (fetched once) and each one's text.
// In the Quantum Algorithms menu an example's option value is EXAMPLE_PREFIX + its file name.

import { BASE_URL, formatApiError } from './api.js';

export const EXAMPLE_PREFIX = 'example:';

let _examples = [];

/** Fetch the example list; an empty list when the server has none or the request fails. */
export async function loadExamples() {
    try {
        const res = await fetch(`${BASE_URL}/examples`);
        if (!res.ok) throw new Error(await formatApiError(res));
        _examples = await res.json();
    } catch (e) {
        console.warn('Example circuits not loaded', e);
        _examples = [];
    }
    return _examples;
}

/** The example a menu value names, or null when the value is an algorithm. */
export function exampleForValue(value) {
    if (!String(value || '').startsWith(EXAMPLE_PREFIX)) return null;
    const name = String(value).slice(EXAMPLE_PREFIX.length);
    return _examples.find(e => e.name === name) || null;
}

/** An example's OpenQASM text. */
export async function fetchExampleQasm(example) {
    const res = await fetch(`${BASE_URL}/examples/${encodeURIComponent(example.name)}`);
    if (!res.ok) throw new Error(await formatApiError(res));
    return (await res.json()).qasm;
}
