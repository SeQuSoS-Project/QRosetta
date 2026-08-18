// Entry point. The browser loads only this file; everything else arrives through the
// module graph, so load order is derived from imports rather than from the order of
// <script> tags in index.html.
//
// index.html wires controls with inline on*= attributes, which resolve against the
// global scope. Module scope is not global, so the functions those attributes name are
// published on window below. That list is asserted against the HTML by
// tests/unit/test_inline_handlers.py, so a renamed or deleted handler fails the suite
// instead of becoming a button that silently does nothing.

import { generateCircuit, handleRun, runBatchQueue, toggleBatchMode, toggleSingleMode } from './app.js';
import { closeAuthModal, handleDeleteAccount, handleLoginSubmit, handleLogout, handleRegisterSubmit, openAuthModal, toggleAuthMode } from './auth.js';
import { addToBatch, applyPreset, clearBatch, closeGeneratorModal, importPlaylist, openGeneratorModal, runAutoGeneration, togglePlaylist } from './batch.js';
import { addBenchmarkToBatch, bmAddAllOfSuite, bmAddSelectedToBatch, bmRenderChecklist, bmToggleSelectAll, loadBenchmark, toggleBenchSuite } from './benchmarks_select.js';
import { setAllOptLevels, toggleConfigPanel } from './config.js';
import { closeDrawers, toggleBenchPanel } from './drawers.js';
import { downloadExperimentBundle, runExperiment, toggleExperimentMode } from './experiment.js';
import { closeHistoryModal, deleteSelectedHistory, downloadSelectedHistory, openHistoryModal, toggleSelectAllHistory } from './history.js';
import { closeVisualizer, copyRawJson, downloadRawJson, generateAndVisualize, renderSuiteSummary } from './renderers.js';
import { copyCircuitQasm, downloadFullReport, exportPlaylist, exportQasm, exportRoCrate, importQasm, resetAgreementThresholds, togglePublicationOptions } from './utils.js';

// Imported for their side effects (state store, bootstrap, render registration).
import './api.js';
import './artifacts_renderer.js';
import './autosave.js';
import './state.js';
import './tables_renderer.js';

Object.assign(window, {
    // app.js
    generateCircuit,
    handleRun,
    runBatchQueue,
    toggleBatchMode,
    toggleSingleMode,
    // auth.js
    closeAuthModal,
    handleDeleteAccount,
    handleLoginSubmit,
    handleLogout,
    handleRegisterSubmit,
    openAuthModal,
    toggleAuthMode,
    // batch.js
    addToBatch,
    applyPreset,
    clearBatch,
    closeGeneratorModal,
    importPlaylist,
    openGeneratorModal,
    runAutoGeneration,
    togglePlaylist,
    // benchmarks_select.js
    addBenchmarkToBatch,
    bmAddAllOfSuite,
    bmAddSelectedToBatch,
    bmRenderChecklist,
    bmToggleSelectAll,
    loadBenchmark,
    toggleBenchSuite,
    // config.js
    setAllOptLevels,
    toggleConfigPanel,
    // drawers.js
    closeDrawers,
    toggleBenchPanel,
    // experiment.js
    downloadExperimentBundle,
    runExperiment,
    toggleExperimentMode,
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
});
