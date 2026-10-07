// Long-lived element references shared across modules, assigned once by initDomRefs.
// Importers see the live bindings without importing app.js.
// Everything is null until initDomRefs runs on load.

export let qasmInput = null;
export let loader = null;
export let tabNav = null;
export let welcomeMessage = null;
export let backButtonContainer = null;
export let queueList = null;
export let queueCount = null;
export let panelElements = {};
export let allButtons = [];

/** Resolve every shared element reference. Called once, from the load handler. */
export function initDomRefs() {
    qasmInput = document.getElementById('qasm-input');
    loader = document.getElementById('loader');
    tabNav = document.getElementById('tab-nav');
    welcomeMessage = document.getElementById('welcome-message');
    backButtonContainer = document.getElementById('back-button-container');

    queueList = document.getElementById('queue-list');
    queueCount = document.getElementById('queue-count');

    panelElements = {
        'summary': document.getElementById('summary-panel'),
        'performance': document.getElementById('performance-panel'),
        'resources': document.getElementById('resources-panel'),
        'divergence': document.getElementById('divergence-panel'),
        'agreement': document.getElementById('agreement-panel'),
        'circuits': document.getElementById('circuits-panel'),
        'export': document.getElementById('export-panel'),
        'suite-summary': document.getElementById('suite-summary-panel'),
        'experiment': document.getElementById('experiment-panel'),
        'visualizer': document.getElementById('visualizer-panel'),
    };
}

/** Register the buttons that are disabled while a run is in flight. */
export function setAllButtons(buttons) {
    allButtons = buttons;
}

let _workspaceChangeQueued = false;
/** Dispatch one `workspace-change` on `document` for any number of calls in the same task,
 * so a change that several handlers report refreshes the workspace once. */
export function announceWorkspaceChange() {
    if (_workspaceChangeQueued) return;
    _workspaceChangeQueued = true;
    queueMicrotask(() => {
        _workspaceChangeQueued = false;
        document.dispatchEvent(new Event('workspace-change'));
    });
}
