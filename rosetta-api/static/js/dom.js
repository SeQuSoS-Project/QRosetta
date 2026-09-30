// Long-lived element references shared across modules, assigned once by initDomRefs.
// Importers see the live bindings without importing app.js.
// Everything is null until initDomRefs runs on load.

export let qasmInput = null;
export let loader = null;
export let tabNav = null;
export let welcomeMessage = null;
export let backButtonContainer = null;
export let jsonOutput = null;
export let playlistSection = null;
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
    jsonOutput = document.getElementById('json-output');

    playlistSection = document.getElementById('playlist-section');
    queueList = document.getElementById('queue-list');
    queueCount = document.getElementById('queue-count');

    panelElements = {
        'summary': document.getElementById('summary-panel'),
        'performance': document.getElementById('performance-panel'),
        'resources': document.getElementById('resources-panel'),
        'divergence': document.getElementById('divergence-panel'),
        'agreement': document.getElementById('agreement-panel'),
        'artifacts': document.getElementById('artifacts-panel'),
        'raw': document.getElementById('raw-panel'),
        'suite-summary': document.getElementById('suite-summary-panel'),
        'visualizer': document.getElementById('visualizer-panel'),
    };
}

/** Register the buttons that are disabled while a run is in flight. */
export function setAllButtons(buttons) {
    allButtons = buttons;
}
