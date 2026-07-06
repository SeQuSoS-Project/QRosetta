// Slide-over drawer controller (Config / Benchmarks / Batch panels).
// Panels are fixed off-canvas (translate-x-full) and slide in when opened; only one is
// open at a time, with a shared backdrop that closes on click or Escape.

// --- Slide-over drawer controller (Config / Bench / Batch) ---
// Panels are fixed off-canvas (translate-x-full) and slide in when opened. Only one
// is open at a time; a shared backdrop dims the page and closes on click / Escape.
const DRAWER_IDS = ['config-panel', 'benchmarks-panel', 'playlist-section'];

function openDrawer(panelId) {
    DRAWER_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('translate-x-full', id !== panelId);
    });
    const backdrop = document.getElementById('drawer-backdrop');
    if (backdrop) backdrop.classList.remove('hidden');
}

function closeDrawers() {
    DRAWER_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('translate-x-full');
    });
    const backdrop = document.getElementById('drawer-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
}

function isDrawerOpen(panelId) {
    const el = document.getElementById(panelId);
    return !!el && !el.classList.contains('translate-x-full');
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawers();
});

function toggleBenchPanel() {
    if (isDrawerOpen('benchmarks-panel')) closeDrawers();
    else openDrawer('benchmarks-panel');
}
