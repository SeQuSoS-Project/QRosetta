// Request limits from GET /config that the browser checks before sending: printable names of
// bounded length, the JSON body size, circuit text size. Pure: no DOM, no network.

const _NOT_PRINTABLE = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/u;
const _OTHER_SYMBOL = /\p{So}/u;
const _isEmojiModifier = cp => cp === 0xFE0F || (cp >= 0x1F3FB && cp <= 0x1F3FF);
const _isTag = cp => cp >= 0xE0020 && cp <= 0xE007E;

/** Positions (in code points) of the formatting characters that belong to an emoji sequence: a
 * zero-width joiner between two symbols (👩‍🔬, 🏳️‍🌈) and the tags of a flag (🏴 + tags + U+E007F).
 * Mirrors schemas/benchmark.py _emoji_sequence_positions. */
function _emojiSequencePositions(chars) {
    const allowed = new Set();
    chars.forEach((ch, i) => {
        const cp = /** @type {number} */ (ch.codePointAt(0));
        if (cp === 0x200D) {
            let j = i - 1;
            while (j >= 0 && _isEmojiModifier(/** @type {number} */ (chars[j].codePointAt(0)))) j--;
            if (j >= 0 && _OTHER_SYMBOL.test(chars[j]) && i + 1 < chars.length && _OTHER_SYMBOL.test(chars[i + 1])) allowed.add(i);
        } else if (cp === 0x1F3F4) {
            let k = i + 1;
            while (k < chars.length && _isTag(/** @type {number} */ (chars[k].codePointAt(0)))) k++;
            if (k > i + 1 && k < chars.length && chars[k].codePointAt(0) === 0xE007F) {
                for (let m = i + 1; m <= k; m++) allowed.add(m);
            }
        }
    });
    return allowed;
}

/** The first character of `text` the server refuses in a name (control, invisible formatting
 * outside an emoji sequence, line separator), as { position (1-based), code: 'U+00AD' }, or null. */
export function firstUnprintable(text) {
    const chars = Array.from(String(text ?? ''));
    const allowed = _emojiSequencePositions(chars);
    const i = chars.findIndex((ch, k) => !allowed.has(k) && _NOT_PRINTABLE.test(ch));
    if (i < 0) return null;
    const code = /** @type {number} */ (chars[i].codePointAt(0)).toString(16).toUpperCase().padStart(4, '0');
    return { position: i + 1, code: `U+${code}` };
}

/** Characters of `text` as the server counts them (code points). */
export function charCount(text) {
    let n = 0;
    for (const _ of String(text ?? '')) n++;
    return n;
}

/** `text` with the characters the server refuses in a name removed, cut to `max` characters. */
export function printableLabel(text, max = 200) {
    const chars = Array.from(String(text ?? ''));
    const allowed = _emojiSequencePositions(chars);
    const clean = chars.filter((ch, k) => allowed.has(k) || !_NOT_PRINTABLE.test(ch)).join('').trim();
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
