// OpenQASM text as diffable lines, raw or normalised (comments, header, whitespace).
// Pure, no imports.

const _FORMAT_CHARACTER = /\p{Cf}/gu;

/**
 * `text` with every invisible formatting character (direction overrides, zero-width
 * characters) replaced by a visible marker such as ⟨U+202E⟩, and how many were replaced.
 */
export function visibleFormatCharacters(text) {
    if (typeof text !== 'string') return { text, count: 0 };
    let count = 0;
    const shown = text.replace(_FORMAT_CHARACTER, ch => {
        count += 1;
        return `⟨U+${ch.codePointAt(0).toString(16).toUpperCase().padStart(4, '0')}⟩`;
    });
    return { text: shown, count };
}

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

const _LAYOUT_COMMENT = /^\/\/ [io](?: \d+)+\s*$/;

/**
 * `text` with // and block comments removed (a block comment keeps its line breaks). A
 * QMAP layout line ('// i 0 2 1', '// o ...') is kept: it says which qubit is which.
 */
export function stripComments(text) {
    return _segments(text).map(seg => !seg.comment ? seg.text
        : _LAYOUT_COMMENT.test(seg.text) ? seg.text : seg.text.replace(/[^\r\n]/g, '')).join('');
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

const _FUNCTIONS = { sin: Math.sin, cos: Math.cos, tan: Math.tan, exp: Math.exp, ln: Math.log, sqrt: Math.sqrt };
const _EXPR_TOKEN = /\s*(?:(\d+\.?\d*(?:[eE][-+]?\d+)?|\.\d+(?:[eE][-+]?\d+)?)|([A-Za-z_][A-Za-z0-9_]*)|(.))/y;

/** The value of an OpenQASM 2.0 parameter expression with no variables, or null. */
export function evaluateAngle(expression) {
    const tokens = [];
    _EXPR_TOKEN.lastIndex = 0;
    const text = String(expression).trim();
    while (_EXPR_TOKEN.lastIndex < text.length) {
        const m = _EXPR_TOKEN.exec(text);
        if (!m) return null;
        if (m[1] !== undefined) tokens.push({ num: Number(m[1]) });
        else if (m[2] !== undefined) tokens.push({ name: m[2] });
        else if (m[3] !== undefined && m[3].trim()) tokens.push({ op: m[3] });
    }
    let i = 0;
    const peek = () => tokens[i];
    const take = op => (tokens[i] && tokens[i].op === op ? (i++, true) : false);
    const primary = () => {
        const t = tokens[i++];
        if (!t) throw new Error('end');
        if (t.num !== undefined) return t.num;
        if (t.name === 'pi') return Math.PI;
        if (t.name !== undefined && _FUNCTIONS[t.name] && take('(')) {
            const v = sum();
            if (!take(')')) throw new Error(')');
            return _FUNCTIONS[t.name](v);
        }
        if (t.op === '(') {
            const v = sum();
            if (!take(')')) throw new Error(')');
            return v;
        }
        if (t.op === '-') return -power();
        if (t.op === '+') return power();
        throw new Error('token');
    };
    const power = () => {
        const base = primary();
        return take('^') ? Math.pow(base, power()) : base;
    };
    const product = () => {
        let v = power();
        for (;;) {
            if (take('*')) v *= power();
            else if (take('/')) v /= power();
            else return v;
        }
    };
    const sum = () => {
        let v = product();
        for (;;) {
            if (take('+')) v += product();
            else if (take('-')) v -= product();
            else return v;
        }
    };
    try {
        const value = sum();
        return i === tokens.length && Number.isFinite(value) ? value : null;
    } catch (_) {
        return null;
    }
}

const ANGLE_DIGITS = 12;

function _canonicalAngle(value) {
    const rounded = Number.parseFloat(value.toPrecision(ANGLE_DIGITS));
    return String(Object.is(rounded, -0) ? 0 : rounded);
}

function _splitArguments(text) {
    const parts = [];
    let depth = 0, current = '';
    for (const ch of text) {
        if (ch === ',' && depth === 0) {
            parts.push(current);
            current = '';
            continue;
        }
        if (ch === '(') depth++;
        if (ch === ')') depth--;
        current += ch;
    }
    parts.push(current);
    return parts;
}

const _PARAMETER_LIST = /\b([A-Za-z_][A-Za-z0-9_]*)\s*\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)/g;
const _NOT_GATES = new Set(['if', ...Object.keys(_FUNCTIONS)]);

/**
 * `line` with every gate parameter that evaluates to a number (no variables) written as
 * that number in radians to 12 significant digits, so pi/4, 0.25*pi and
 * 0.7853981633974483 read the same. Parameters with variables are kept as written.
 */
export function canonicalAngles(line) {
    return line.replace(_PARAMETER_LIST, (whole, name, args) => {
        if (_NOT_GATES.has(name)) return whole;
        const rewritten = _splitArguments(args).map(arg => {
            const value = evaluateAngle(arg);
            return value === null ? arg.trim() : _canonicalAngle(value);
        });
        return `${name}(${rewritten.join(', ')})`;
    });
}

/**
 * Lines to compare for `text`. `comments` drops // and block comments, blank lines and
 * trailing whitespace; `header` drops the OPENQASM version and include statements;
 * `whitespace` puts one statement per line with single spaces, and each kept comment on a
 * line of its own; `angles` rewrites numeric gate parameters with canonicalAngles. With no
 * option set this is splitLines(text).
 */
export function comparableLines(text, { comments = false, header = false, whitespace = false, angles = false } = {}) {
    if (typeof text !== 'string') return [];
    if (angles) return comparableLines(text, { comments, header, whitespace }).map(canonicalAngles);
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
