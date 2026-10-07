// Request limits from GET /config that the browser checks before sending: printable names of
// bounded length, the JSON body size, circuit text size. Pure: no DOM, no network.

const _NOT_PRINTABLE = /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}]/gu;

/** Characters of `text` as the server counts them (code points). */
export function charCount(text) {
    let n = 0;
    for (const _ of String(text ?? '')) n++;
    return n;
}

/** `text` with control, invisible formatting and line-separator characters removed, cut to `max` characters. */
export function printableLabel(text, max = 200) {
    const clean = String(text ?? '').replace(_NOT_PRINTABLE, '').trim();
    return charCount(clean) <= max ? clean : Array.from(clean).slice(0, max).join('').trim();
}

/** Why the server would reject `text` as a name, or null. */
export function labelProblem(text, max = 200, what = 'The name') {
    const value = String(text ?? '');
    if (new RegExp(_NOT_PRINTABLE.source, 'u').test(value)) {
        return `${what} must not contain control characters, invisible formatting characters (such as direction overrides) or line separators.`;
    }
    const n = charCount(value);
    return n > max ? `${what} has ${n} characters; at most ${max} are allowed.` : null;
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
