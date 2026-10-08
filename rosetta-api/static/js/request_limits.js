// Request limits from GET /config that the browser checks before sending: printable names of
// bounded length, the JSON body size, circuit text size. Pure: no DOM, no network.

/** Code point ranges refused in names (mirror schemas/benchmark.py _REFUSED_IN_NAMES): controls,
 * line and paragraph separators, direction marks, embeddings, overrides and isolates, and named
 * invisible characters. */
const _REFUSED_IN_NAMES = [
    [0x0000, 0x001F], [0x007F, 0x009F],
    [0x00AD, 0x00AD], [0x061C, 0x061C], [0x115F, 0x1160], [0x180E, 0x180E],
    [0x200B, 0x200B], [0x200E, 0x200F], [0x2028, 0x202E], [0x2060, 0x2064],
    [0x2066, 0x206F], [0x3164, 0x3164], [0xD800, 0xDFFF], [0xFEFF, 0xFEFF],
    [0xFFA0, 0xFFA0], [0xFFF9, 0xFFFB], [0xE0001, 0xE0001],
];
/** Invisible characters allowed in names (joiners, variation selectors, tags); mirror
 * schemas/benchmark.py _INVISIBLE_ALLOWED. */
const _INVISIBLE_ALLOWED = [[0x200C, 0x200D], [0xFE00, 0xFE0F], [0xE0020, 0xE007F], [0xE0100, 0xE01EF]];
const _SPACE = /^\s$/u;

/** @param {string} ch @param {number[][]} ranges */
const _inRanges = (ch, ranges) => {
    const cp = /** @type {number} */ (ch.codePointAt(0));
    return ranges.some(([lo, hi]) => lo <= cp && cp <= hi);
};
const _refused = (/** @type {string} */ ch) => _inRanges(ch, _REFUSED_IN_NAMES);

/** The first character of `text` the server refuses in a name (control, line separator, direction
 * control, listed invisible character), as { position (1-based), code: 'U+00AD' }, or null. */
export function firstUnprintable(text) {
    const chars = Array.from(String(text ?? ''));
    const i = chars.findIndex(_refused);
    if (i < 0) return null;
    const code = /** @type {number} */ (chars[i].codePointAt(0)).toString(16).toUpperCase().padStart(4, '0');
    return { position: i + 1, code: `U+${code}` };
}

/** True when `text` has no visible character: only whitespace, joiners, variation selectors or
 * tag characters (mirror schemas/benchmark.py is_blank_name). */
export function isBlankName(text) {
    return Array.from(String(text ?? '')).every(ch => _SPACE.test(ch) || _inRanges(ch, _INVISIBLE_ALLOWED));
}

/** Characters of `text` as the server counts them (code points). */
export function charCount(text) {
    let n = 0;
    for (const _ of String(text ?? '')) n++;
    return n;
}

/** `text` with the characters the server refuses in a name removed, cut to `max` characters; ''
 * when nothing visible is left. */
export function printableLabel(text, max = 200) {
    const clean = Array.from(String(text ?? '')).filter(ch => !_refused(ch)).join('').trim();
    if (isBlankName(clean)) return '';
    return charCount(clean) <= max ? clean : Array.from(clean).slice(0, max).join('').trim();
}

/** Why the server would reject `text` as a name, or null. */
export function labelProblem(text, max = 200, what = 'The name') {
    const value = String(text ?? '');
    const bad = firstUnprintable(value);
    if (bad) {
        return `${what} must not contain control characters, invisible formatting characters (such as direction overrides) `
            + `or line separators; character ${bad.position} is ${bad.code}.`;
    }
    const n = charCount(value);
    return n > max ? `${what} has ${n} characters; at most ${max} are allowed.` : null;
}

/**
 * Why Load refuses to generate a circuit of `qubits` qubits for the ticked modes, or null. The
 * limit is the ticked modes' qubit limit: statevector, else measured, else compile-only.
 * @param {number} qubits
 * @param {{ statevector: boolean, measured: boolean }} modes
 * @param {{ statevector: number, measured: number, compile: number }} limits
 */
export function loadQubitProblem(qubits, modes, limits) {
    const refuse = (what, max) => `${what} runs allow at most ${max} qubits, so Load does not generate a ${qubits}-qubit circuit while ${what} is ticked.`;
    if (modes.statevector && qubits > limits.statevector) {
        const other = modes.measured ? 'Statevector' : 'Statevector and tick Measured';
        return refuse('Statevector', limits.statevector)
            + (qubits <= limits.measured ? ` Untick ${other} to load it for a measured run (up to ${limits.measured} qubits).` : '');
    }
    if (modes.measured && qubits > limits.measured) return refuse('Measured', limits.measured);
    if (!modes.statevector && !modes.measured && qubits > limits.compile) {
        return `Compile-only runs allow at most ${limits.compile} qubits, so Load does not generate a ${qubits}-qubit circuit.`;
    }
    return null;
}

/** Bytes of `value` as JSON in UTF-8, the size of the request body that carries it. */
export function jsonBytes(value) {
    return new TextEncoder().encode(JSON.stringify(value)).length;
}

/** `n` with thousands separators. */
export function groupDigits(n) {
    return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/** A byte count for messages: "1,048,576 bytes (1.00 MiB)". */
export function formatBytes(n) {
    return `${groupDigits(n)} bytes (${(n / 1048576).toFixed(2)} MiB)`;
}
