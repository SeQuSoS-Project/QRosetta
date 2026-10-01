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

/** `text` split into code and comment segments; string literals stay in code segments. */
function _segments(text) {
    const segments = [];
    let code = '';
    let i = 0;
    const flush = () => { if (code) segments.push({ comment: false, text: code }); code = ''; };
    while (i < text.length) {
        const ch = text[i];
        if (ch === '"') {
            const end = text.indexOf('"', i + 1);
            const stop = end === -1 ? text.length : end + 1;
            code += text.slice(i, stop);
            i = stop;
        } else if (ch === '/' && (text[i + 1] === '/' || text[i + 1] === '*')) {
            let stop;
            if (text[i + 1] === '/') {
                stop = i;
                while (stop < text.length && text[stop] !== '\n' && text[stop] !== '\r') stop++;
            } else {
                const end = text.indexOf('*/', i + 2);
                stop = end === -1 ? text.length : end + 2;
            }
            flush();
            segments.push({ comment: true, text: text.slice(i, stop) });
            i = stop;
        } else {
            code += ch;
            i++;
        }
    }
    flush();
    return segments;
}

/** `text` with // and block comments removed (a block comment keeps its line breaks). */
export function stripComments(text) {
    return _segments(text).map(seg => seg.comment ? seg.text.replace(/[^\r\n]/g, '') : seg.text).join('');
}

const _HEADER = /^\s*(OPENQASM\s+[0-9.]+\s*;|include\s+"[^"]*"\s*;)\s*$/;
const _HEADER_STATEMENT = /\bOPENQASM\s+[0-9.]+\s*;[ \t]*|\binclude\s+"[^"]*"\s*;[ \t]*/g;

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
 * Lines to compare for `text`. `comments` drops // and block comments, blank lines and
 * trailing whitespace; `header` drops the OPENQASM version and include statements;
 * `whitespace` puts one statement per line with single spaces, and each kept comment on a
 * line of its own. With no option set this is splitLines(text).
 */
export function comparableLines(text, { comments = false, header = false, whitespace = false } = {}) {
    if (typeof text !== 'string') return [];
    let source = comments ? stripComments(text) : text;
    if (header) {
        source = _segments(source).map(seg => seg.comment ? seg.text
            : seg.text.replace(_HEADER_STATEMENT, '')).join('');
    }
    if (!whitespace) {
        const lines = splitLines(source);
        if (!comments && !header) return lines;
        return lines.map(line => comments ? line.replace(/\s+$/, '') : line).filter(line => line.trim() !== '');
    }
    const lines = [];
    let code = '';
    const flushCode = () => {
        lines.push(..._statements(code.replace(/\r\n|\r|\n/g, ' ')).map(_canonical));
        code = '';
    };
    for (const seg of _segments(source)) {
        if (!seg.comment) {
            code += seg.text;
            continue;
        }
        const tail = Math.max(code.lastIndexOf(';'), code.lastIndexOf('{'), code.lastIndexOf('}'));
        const pending = code.slice(tail + 1);
        code = code.slice(0, tail + 1);
        flushCode();
        lines.push(seg.text.replace(/\s+/g, ' ').trim());
        code = pending;
    }
    flushCode();
    return lines.filter(line => line !== '' && line !== ';').filter(line => !(header && _HEADER.test(line)));
}

/** True when `a` and `b` differ only in their line-break characters (CRLF, CR, LF). */
export function differOnlyInLineBreaks(a, b) {
    return typeof a === 'string' && typeof b === 'string' && a !== b
        && a.replace(/\r\n|\r/g, '\n') === b.replace(/\r\n|\r/g, '\n');
}
