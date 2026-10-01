// OpenQASM text as diffable lines, raw or normalised (comments, header, whitespace).
// Pure, no imports.

/** Lines of `text`; a final line break does not start another line. */
export function splitLines(text) {
    if (typeof text !== 'string' || text === '') return [];
    const lines = text.split(/\r\n|\r|\n/);
    if (lines[lines.length - 1] === '') lines.pop();
    return lines;
}

export function endsWithNewline(text) {
    return typeof text === 'string' && /(\r\n|\r|\n)$/.test(text);
}

/** `text` with // and block comments removed; string literals are left intact. */
export function stripComments(text) {
    let out = '';
    let i = 0;
    while (i < text.length) {
        const ch = text[i];
        if (ch === '"') {
            const end = text.indexOf('"', i + 1);
            const stop = end === -1 ? text.length : end + 1;
            out += text.slice(i, stop);
            i = stop;
        } else if (ch === '/' && text[i + 1] === '/') {
            while (i < text.length && text[i] !== '\n' && text[i] !== '\r') i++;
        } else if (ch === '/' && text[i + 1] === '*') {
            const end = text.indexOf('*/', i + 2);
            const body = text.slice(i, end === -1 ? text.length : end + 2);
            out += body.replace(/[^\r\n]/g, '');
            i += body.length;
        } else {
            out += ch;
            i++;
        }
    }
    return out;
}

const _HEADER = /^\s*(OPENQASM\s+[0-9.]+\s*;|include\s+"[^"]*"\s*;)\s*$/;

function _statements(text) {
    const parts = [];
    let current = '';
    for (const ch of text) {
        if (ch === ';' || ch === '{') {
            parts.push(current + ch);
            current = '';
        } else if (ch === '}') {
            if (current.trim()) parts.push(current);
            parts.push('}');
            current = '';
        } else {
            current += ch;
        }
    }
    if (current.trim()) parts.push(current);
    return parts;
}

const _TOKEN = /"[^"]*"|[A-Za-z_][A-Za-z0-9_]*|(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?|->|==|\S/g;
const _WORD = /^["A-Za-z0-9_.]/;

/** One statement with single spaces between words, after commas and around ->. */
function _canonical(statement) {
    const tokens = statement.match(_TOKEN) || [];
    let out = '';
    tokens.forEach((tok, i) => {
        const prev = tokens[i - 1];
        const spaced = i > 0 && ((_WORD.test(prev) && _WORD.test(tok)) || prev === ','
            || (prev === ')' && _WORD.test(tok)) || tok === '{' || tok === '->' || prev === '->');
        out += (spaced ? ' ' : '') + tok;
    });
    return out;
}

/**
 * Lines to compare for `text`. `comments` drops // and block comments, `header` drops the
 * OPENQASM version and include statements, `whitespace` puts one statement per line with
 * single spaces. With no option set this is splitLines(text).
 */
export function comparableLines(text, { comments = false, header = false, whitespace = false } = {}) {
    if (typeof text !== 'string') return [];
    let source = comments ? stripComments(text) : text;
    if (header) {
        source = splitLines(source).map(line => _HEADER.test(line) ? '' : line).join('\n');
    }
    if (!whitespace) {
        const lines = splitLines(source);
        return (comments || header) ? lines.filter(line => line.trim() !== '') : lines;
    }
    return _statements(source.replace(/\r\n|\r|\n/g, ' '))
        .map(_canonical)
        .filter(line => line !== '' && line !== ';')
        .filter(line => !(header && _HEADER.test(line)));
}
