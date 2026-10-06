// Entry point. The browser loads only this file; everything else arrives through the
// module graph, so load order is derived from imports rather than from the order of
// <script> tags in index.html.
//
// index.html wires controls with inline on*= attributes, which resolve against the
// global scope. Module scope is not global, so the functions those attributes name are
// published on window below. That list is asserted against the HTML by
// tests/unit/test_inline_handlers.py, so a renamed or deleted handler fails the suite
// instead of becoming a button that silently does nothing.

import { generateCircuit } from './app.js';
import { closeAuthModal, handleDeleteAccount, handleLoginSubmit, handleLogout, handleRegisterSubmit, openAuthModal, toggleAuthMode } from './auth.js';
import { addEditorToPlaylist, addToBatch, applyPreset, clearBatch, closeGeneratorModal, importPlaylist, openGeneratorModal, runAutoGeneration } from './batch.js';
import { bmAddAllShown, bmAddSelectedToBatch, bmRenderChecklist, bmToggleSelectAll, toggleBenchSuite } from './benchmarks_select.js';
import { runWorkspace, stopWaiting, updateWorkspace } from './workspace.js';
import { closeHistoryModal, deleteSelectedHistory, downloadSelectedHistory, openHistoryModal, toggleSelectAllHistory } from './history.js';
import { closeVisualizer, copyRawJson, downloadRawJson, generateAndVisualize, renderSuiteSummary } from './renderers.js';
import { copyCircuitQasm, downloadFullReport, exportPlaylist, exportQasm, exportRoCrate, importQasm, resetAgreementThresholds, togglePublicationOptions } from './utils.js';

// Imported for their side effects (state store, bootstrap, render registration).
import './api.js';
import './artifacts_renderer.js';
import './autosave.js';
import './state.js';
import './tables_renderer.js';
import { initTooltips } from './tooltip.js';

initTooltips();

Object.assign(window, {
    // app.js
    generateCircuit,
    // auth.js
    closeAuthModal,
    handleDeleteAccount,
    handleLoginSubmit,
    handleLogout,
    handleRegisterSubmit,
    openAuthModal,
    toggleAuthMode,
    // batch.js
    addEditorToPlaylist,
    addToBatch,
    applyPreset,
    clearBatch,
    closeGeneratorModal,
    importPlaylist,
    openGeneratorModal,
    runAutoGeneration,
    // benchmarks_select.js
    bmAddAllShown,
    bmAddSelectedToBatch,
    bmRenderChecklist,
    bmToggleSelectAll,
    toggleBenchSuite,
    // history.js
    closeHistoryModal,
    deleteSelectedHistory,
    downloadSelectedHistory,
    openHistoryModal,
    toggleSelectAllHistory,
    // renderers.js
    closeVisualizer,
    copyRawJson,
    downloadRawJson,
    generateAndVisualize,
    renderSuiteSummary,
    // utils.js
    copyCircuitQasm,
    downloadFullReport,
    exportPlaylist,
    exportQasm,
    exportRoCrate,
    importQasm,
    resetAgreementThresholds,
    togglePublicationOptions,
    // workspace.js
    runWorkspace,
    stopWaiting,
    updateWorkspace,
});
