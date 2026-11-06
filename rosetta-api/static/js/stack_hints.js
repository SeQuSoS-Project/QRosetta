// What the Backends and Compile-only services popovers say about a service a local stack
// lists but does not run (GET /runners or /compilers: available false, unavailable_reason
// "unreachable"), and the qrosetta commands that add it. Text parts are {text} or {code}.
// Leaf module: no imports.

const NOT_RUNNING = 'unreachable';

/** True for an enabled service that a local stack lists and does not run. */
export function notRunningLocally(row, executionMode) {
    return executionMode === 'local' && !!row && row.enabled !== false && row.available === false
        && row.unavailable_reason === NOT_RUNNING;
}

/** The command that fetches images for this stack: `build` when the running services report
 * locally built images and none a release image, else `pull`. */
export function imageVerb(rows) {
    const sources = (rows || []).map(r => r?.versions?.image_identity?.source).filter(s => typeof s === 'string');
    return sources.includes('built_locally') && !sources.includes('release') ? 'build' : 'pull';
}

/** Parts of the note for one service that is not running. */
export function serviceHintParts(id, verb) {
    return [
        { text: 'Not running in this stack. To add it: ' }, { code: `qrosetta ${verb} ${id}` },
        { text: ', then ' }, { code: `qrosetta start -d ${id}` },
    ];
}

/** Parts of the line at the top of a popover (`noun`: "backends" or "compile-only services"),
 * or null when no enabled service is listed as not running. */
export function stackSummaryParts(rows, executionMode, noun, verb) {
    const enabled = (rows || []).filter(r => r && r.enabled !== false);
    if (!enabled.some(r => notRunningLocally(r, executionMode))) return null;
    const running = enabled.filter(r => r.available !== false).length;
    return [
        { text: `${running} of ${enabled.length} ${noun} run in this stack. To add all: ` },
        { code: `qrosetta ${verb} --profile full` }, { text: ', then ' },
        { code: 'qrosetta start -d --profile full' }, { text: '.' },
    ];
}

/** The parts as plain text (for a title attribute). */
export function partsText(parts) {
    return parts.map(p => p.code ?? p.text).join('');
}

/** A `tag` element of class `className` holding the parts, each command in a selectable <code>. */
export function partsElement(tag, className, parts) {
    const el = document.createElement(tag);
    el.className = className;
    for (const part of parts) {
        if (part.code === undefined) {
            el.appendChild(document.createTextNode(part.text));
        } else {
            const code = document.createElement('code');
            code.className = 'select-all whitespace-nowrap rounded bg-gray-100 px-1 text-gray-800';
            code.textContent = part.code;
            el.appendChild(code);
        }
    }
    return el;
}
