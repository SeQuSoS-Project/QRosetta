// Slide-over drawer controller (the benchmark-suite picker).
// Panels are fixed off-canvas (translate-x-full) and slide in when opened; only one is
// open at a time. A click on the shared backdrop or Escape closes it.
export const DRAWER_IDS = ['benchmarks-panel'];

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

document.getElementById('drawer-backdrop')?.addEventListener('click', closeDrawers);

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeDrawers();
});

export function toggleBenchPanel() {
    if (isDrawerOpen('benchmarks-panel')) closeDrawers();
    else openDrawer('benchmarks-panel');
}
