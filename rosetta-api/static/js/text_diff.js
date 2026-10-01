// Line diff of two texts: Myers' O(ND) algorithm in linear space, with an edit budget.
// Pure, no imports.

export const DEFAULT_MAX_EDITS = 4000;

function _intern(aLines, bLines) {
    const ids = new Map();
    const encode = lines => Int32Array.from(lines, line => {
        let id = ids.get(line);
        if (id === undefined) {
            id = ids.size;
            ids.set(line, id);
        }
        return id;
    });
    return [encode(aLines), encode(bLines)];
}

/**
 * The middle snake of a[aLo..aHi) against b[bLo..bHi): the edit distance d and the snake
 * (x, y) -> (u, v) in local coordinates, or null when d would exceed maxD.
 */
function _middleSnake(a, aLo, aHi, b, bLo, bHi, maxD) {
    const n = aHi - aLo;
    const m = bHi - bLo;
    const delta = n - m;
    const odd = (delta & 1) !== 0;
    const limit = Math.min(Math.ceil((n + m) / 2), Math.ceil(maxD / 2));
    const off = limit + 1;
    const vf = new Int32Array(2 * limit + 3);
    const vb = new Int32Array(2 * limit + 3);
    for (let d = 0; d <= limit; d++) {
        for (let k = -d; k <= d; k += 2) {
            let x = (k === -d || (k !== d && vf[off + k - 1] < vf[off + k + 1]))
                ? vf[off + k + 1] : vf[off + k - 1] + 1;
            let y = x - k;
            const x0 = x, y0 = y;
            while (x < n && y < m && a[aLo + x] === b[bLo + y]) { x++; y++; }
            vf[off + k] = x;
            const c = delta - k;
            if (odd && c >= -(d - 1) && c <= d - 1 && x + vb[off + c] >= n) {
                return { d: 2 * d - 1, x: x0, y: y0, u: x, v: y };
            }
        }
        for (let c = -d; c <= d; c += 2) {
            let x = (c === -d || (c !== d && vb[off + c - 1] < vb[off + c + 1]))
                ? vb[off + c + 1] : vb[off + c - 1] + 1;
            let y = x - c;
            const x0 = x, y0 = y;
            while (x < n && y < m && a[aHi - 1 - x] === b[bHi - 1 - y]) { x++; y++; }
            vb[off + c] = x;
            const k = delta - c;
            if (!odd && k >= -d && k <= d && vf[off + k] + x >= n) {
                return { d: 2 * d, x: n - x, y: m - y, u: n - x0, v: m - y0 };
            }
        }
    }
    return null;
}

/**
 * Append the matched index pairs [i, j] of a minimal-edit common subsequence, in order.
 * False when the edit distance exceeds maxD.
 */
function _matches(a, aLo, aHi, b, bLo, bHi, out, maxD = Infinity) {
    while (aLo < aHi && bLo < bHi && a[aLo] === b[bLo]) out.push([aLo++, bLo++]);
    const tail = [];
    while (aLo < aHi && bLo < bHi && a[aHi - 1] === b[bHi - 1]) tail.push([--aHi, --bHi]);
    if (Math.abs((aHi - aLo) - (bHi - bLo)) > maxD) return false;
    if (aLo < aHi && bLo < bHi) {
        const s = _middleSnake(a, aLo, aHi, b, bLo, bHi, maxD);
        if (s === null) return false;
        _matches(a, aLo, aLo + s.x, b, bLo, bLo + s.y, out);
        for (let i = s.x, j = s.y; i < s.u; i++, j++) out.push([aLo + i, bLo + j]);
        _matches(a, aLo + s.u, aHi, b, bLo + s.v, bHi, out);
    }
    for (let i = tail.length - 1; i >= 0; i--) out.push(tail[i]);
    return true;
}

/**
 * Diff two arrays of lines. Returns {complete: true, ops, deleted, inserted} where ops is a
 * list of {type: 'equal'|'delete'|'insert', a, b} with a and b the line indices (null on
 * the side a line is absent from), or {complete: false} when roughly more than maxEdits lines
 * would have to be deleted or inserted.
 */
export function diffLines(aLines, bLines, maxEdits = DEFAULT_MAX_EDITS) {
    const [a, b] = _intern(aLines, bLines);
    const pairs = [];
    if (!_matches(a, 0, a.length, b, 0, b.length, pairs, maxEdits)) return { complete: false };
    pairs.push([a.length, b.length]);
    const ops = [];
    let i = 0, j = 0;
    for (const [mi, mj] of pairs) {
        while (i < mi) ops.push({ type: 'delete', a: i++, b: null });
        while (j < mj) ops.push({ type: 'insert', a: null, b: j++ });
        if (mi < a.length) ops.push({ type: 'equal', a: i++, b: j++ });
    }
    return { complete: true, ops, deleted: a.length - pairs.length + 1, inserted: b.length - pairs.length + 1 };
}

/**
 * Group diff ops into hunks with `context` equal lines around each change. Equal runs
 * between hunks are returned as {type: 'skip', count, ops} so a viewer can expand them.
 */
export function diffHunks(ops, context = 3) {
    const out = [];
    let run = [];
    const flushRun = (isStart, isEnd) => {
        if (!run.length) return;
        const head = isStart ? 0 : context;
        const tail = isEnd ? 0 : context;
        if (run.length <= head + tail) {
            out.push(...run);
        } else {
            out.push(...run.slice(0, head));
            out.push({ type: 'skip', count: run.length - head - tail, ops: run.slice(head, run.length - tail) });
            out.push(...run.slice(run.length - tail));
        }
        run = [];
    };
    let seenChange = false;
    for (const op of ops) {
        if (op.type === 'equal') {
            run.push(op);
        } else {
            flushRun(!seenChange, false);
            seenChange = true;
            out.push(op);
        }
    }
    flushRun(!seenChange, true);
    return out;
}
