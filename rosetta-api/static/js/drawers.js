// Slide-over drawer controller (Config / Benchmarks / Batch panels).
// Panels are fixed off-canvas (translate-x-full) and slide in when opened; only one is
// open at a time. A click on the shared backdrop closes the drawer and is passed on to
// the control underneath it; Escape also closes.
export const DRAWER_IDS = ['config-panel', 'benchmarks-panel', 'playlist-section'];

export function openDrawer(panelId) {
    DRAWER_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('translate-x-full', id !== panelId);
    });
    const backdrop = document.getElementById('drawer-backdrop');
    if (backdrop) backdrop.classList.remove('hidden');
}

export function closeDrawers() {
    DRAWER_IDS.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('translate-x-full');
    });
    const backdrop = document.getElementById('drawer-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
}

export function isDrawerOpen(panelId) {
    const el = document.getElementById(panelId);
    return !!el && !el.classList.contains('translate-x-full');
}

document.getElementById('drawer-backdrop')?.addEventListener('click', (e) => {
    closeDrawers();
    const target = document.elementFromPoint(e.clientX, e.clientY);
    const control = target instanceof HTMLElement
        ? target.closest('button, a, input, select, label, [role="tab"]') : null;
    if (control instanceof HTMLElement) control.click();
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawers();
});

export function toggleBenchPanel() {
    if (isDrawerOpen('benchmarks-panel')) closeDrawers();
    else openDrawer('benchmarks-panel');
}
