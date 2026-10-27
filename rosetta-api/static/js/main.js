// Entry point. The browser loads only this file; everything else arrives through the
// module graph, so load order is derived from imports rather than from the order of
// <script> tags in index.html.
//
// index.html carries no inline event handlers (the Content-Security-Policy allows scripts
// from this origin only). CONTROLS wires its static controls; tests/unit/test_inline_handlers.py
// checks every selector against the HTML.

import { generateCircuit } from './app.js';
import { closeAuthModal, closeDeleteAccountModal, handleDeleteAccount, handleLoginSubmit, handleLogout, handleRegisterSubmit, openAuthModal, submitDeleteAccount, toggleAuthMode } from './auth.js';
import { addEditorToPlaylist, addToBatch, applyPreset, clearBatch, closeGeneratorModal, importPlaylist, openGeneratorModal, runAutoGeneration } from './batch.js';
import { bmAddAllShown, bmAddSelectedToBatch, bmRenderChecklist, bmToggleSelectAll, toggleBenchSuite } from './benchmarks_select.js';
import { watchBidi } from './bidi_isolation.js';
import { runWorkspace, stopWaiting, updateWorkspace } from './workspace.js';
import { keepFocusClearOf } from './notice_focus.js';
import { closeHistoryModal, deleteSelectedHistory, downloadSelectedHistory, openHistoryModal, toggleSelectAllHistory } from './history.js';
import { closeVisualizer, generateAndVisualize, renderSuiteSummary } from './renderers.js';
import { getState } from './state.js';
import { copyCircuitQasm, exportPlaylist, exportQasm, importQasm, resetAgreementThresholds } from './utils.js';

// Imported for their side effects (state store, bootstrap, render registration).
import './api.js';
import './autosave.js';
import './tables_renderer.js';
import { initTooltips } from './tooltip.js';

initTooltips();
watchBidi(document.body);
keepFocusClearOf(['busy-toast', 'history-save-notice']);

/** @param {() => void} action */
const onEnter = action => (/** @type {Event} */ e) => { if (/** @type {KeyboardEvent} */ (e).key === 'Enter') action(); };

/** [selector, event type, listener]: each element the selector matches gets the listener. */
/** @type {[string, string, (e: Event) => void][]} */
const CONTROLS = [
    // Header and account
    ['#btn-login-modal', 'click', () => openAuthModal()],
    ['#btn-history', 'click', () => openHistoryModal()],
    ['#btn-logout', 'click', () => handleLogout()],
    ['#btn-delete-account', 'click', () => handleDeleteAccount()],
    // Generate Circuits and Editor
    ['#btn-load', 'click', () => generateCircuit()],
    ['#btn-add-to-batch', 'click', () => addToBatch()],
    ['#btn-import-qasm', 'click', () => document.getElementById('qasm-upload')?.click()],
    ['#btn-export-qasm', 'click', () => exportQasm()],
    ['#btn-copy-qasm', 'click', e => copyCircuitQasm(e.currentTarget)],
    ['#btn-visualize', 'click', () => generateAndVisualize()],
    ['#btn-editor-to-playlist', 'click', () => addEditorToPlaylist()],
    ['#qasm-upload', 'change', e => importQasm(e.currentTarget)],
    // Playlist and Bench
    ['#btn-import-playlist', 'click', () => document.getElementById('playlist-upload')?.click()],
    ['#btn-export-playlist', 'click', () => exportPlaylist()],
    ['#playlist-upload', 'change', e => importPlaylist(e.currentTarget)],
    ['#btn-clear-playlist', 'click', () => clearBatch()],
    ['#btn-apply-preset', 'click', () => applyPreset()],
    ['#btn-open-generator', 'click', () => openGeneratorModal()],
    ['input[name="bench-suite"]', 'change', () => toggleBenchSuite()],
    ['#bench-filter', 'input', () => bmRenderChecklist()],
    ['#bench-max-qubits', 'input', () => bmRenderChecklist()],
    ['#bench-select-all', 'change', () => bmToggleSelectAll()],
    ['#btn-bench-add-selected', 'click', () => bmAddSelectedToBatch()],
    ['#btn-bench-add-all', 'click', () => bmAddAllShown()],
    // Run footer and settings
    ['input[name="run-source"]', 'change', () => updateWorkspace()],
    ['#mode-statevector', 'change', () => updateWorkspace()],
    ['#mode-measured', 'change', () => updateWorkspace()],
    ['#btn-run', 'click', () => runWorkspace()],
    ['#btn-reset-thresholds', 'click', () => resetAgreementThresholds()],
    // Results
    ['#btn-stop-waiting', 'click', () => stopWaiting()],
    ['#btn-back-to-suite', 'click', () => renderSuiteSummary(getState().currentSuiteData, getState().currentSuiteTitle)],
    ['#visualizer-close', 'click', () => closeVisualizer()],
    // Auto-Gen dialog
    ['#gen-modal-backdrop', 'click', () => closeGeneratorModal()],
    ['#btn-run-autogen', 'click', () => runAutoGeneration()],
    ['#btn-cancel-generator', 'click', () => closeGeneratorModal()],
    // Sign-in dialog
    ['#auth-modal-backdrop', 'click', () => closeAuthModal()],
    ['#login-password', 'keydown', onEnter(handleLoginSubmit)],
    ['#btn-login-submit', 'click', () => handleLoginSubmit()],
    ['#btn-login-cancel', 'click', () => closeAuthModal()],
    ['#btn-show-register', 'click', () => toggleAuthMode('register')],
    ['#register-password', 'keydown', onEnter(handleRegisterSubmit)],
    ['#btn-register-submit', 'click', () => handleRegisterSubmit()],
    ['#btn-register-cancel', 'click', () => closeAuthModal()],
    ['#btn-show-login', 'click', () => toggleAuthMode('login')],
    // Delete Account dialog
    ['#delete-account-backdrop', 'click', () => closeDeleteAccountModal()],
    ['#delete-account-password', 'keydown', onEnter(submitDeleteAccount)],
    ['#btn-delete-account-confirm', 'click', () => submitDeleteAccount()],
    ['#btn-delete-account-cancel', 'click', () => closeDeleteAccountModal()],
    // History dialog
    ['#history-modal-backdrop', 'click', () => closeHistoryModal()],
    ['#history-select-all', 'click', () => toggleSelectAllHistory()],
    ['#btn-history-close', 'click', () => closeHistoryModal()],
    ['#btn-history-download', 'click', () => downloadSelectedHistory()],
    ['#btn-history-delete', 'click', () => deleteSelectedHistory()],
];

for (const [selector, type, listener] of CONTROLS) {
    document.querySelectorAll(selector).forEach(el => el.addEventListener(type, listener));
}
