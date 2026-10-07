// Optional auto-save of completed runs to a local folder via the File System Access API
// (Chrome and Edge; other browsers show the control disabled with a note). Off by default.
// The user picks a folder once per session; each completed run is written there as a JSON
// file, with no upload. The folder handle lives in memory, so a reload asks again.

export let _autosaveDirHandle = null;

export function _autosaveSupported() {
    return typeof window !== 'undefined' && typeof window.showDirectoryPicker === 'function';
}

export function _autosaveEl(id) { return document.getElementById(id); }

export function _autosaveSetFolderLabel() {
    const label = _autosaveEl('autosave-folder');
    if (label) label.textContent = _autosaveDirHandle ? `saving to “${_autosaveDirHandle.name}”` : 'no folder chosen';
}

export function _autosaveNote(text, isError) {
    const el = _autosaveEl('autosave-status');
    if (!el) return;
    el.textContent = text;
    el.className = 'text-[11px] mt-1 ' + (isError ? 'text-red-600' : 'text-emerald-600');
}

export async function _autosaveChooseFolder() {
    try {
        _autosaveDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        _autosaveSetFolderLabel();
    } catch (e) {
        if (e && e.name !== 'AbortError') console.warn('[autosave] folder pick failed:', e.message);
    }
}

/** Write a completed run to the chosen folder; nothing happens unless auto-save is on with a folder. */
export async function autosaveRun(results, name) {
    const toggle = _autosaveEl('autosave-toggle');
    if (!toggle || !toggle.checked || !_autosaveDirHandle || !results) return;
    try {
        if (_autosaveDirHandle.queryPermission) {
            const perm = await _autosaveDirHandle.queryPermission({ mode: 'readwrite' });
            if (perm !== 'granted' && (await _autosaveDirHandle.requestPermission({ mode: 'readwrite' })) !== 'granted') {
                return;
            }
        }
        const slug = String(name || 'run').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'run';
        const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const filename = `qrosetta_${slug}_${stamp}.json`;
        const fileHandle = await _autosaveDirHandle.getFileHandle(filename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(JSON.stringify(results, null, 2));
        await writable.close();
        _autosaveNote(`✓ saved ${filename}`);
    } catch (e) {
        console.warn('[autosave] write failed:', e && e.message);
        _autosaveNote('Auto-save failed — see console', true);
    }
}

export function initAutosave() {
    const card = _autosaveEl('autosave-card');
    if (!card) return;
    const toggle = _autosaveEl('autosave-toggle');
    const detail = _autosaveEl('autosave-detail');
    const chooseBtn = _autosaveEl('autosave-choose');
    const unsupported = _autosaveEl('autosave-unsupported');

    if (!_autosaveSupported()) {
        if (toggle) { toggle.disabled = true; toggle.checked = false; }
        if (unsupported) unsupported.classList.remove('hidden');
        return;
    }

    if (toggle && detail) {
        toggle.addEventListener('change', async () => {
            if (toggle.checked) {
                detail.classList.remove('hidden');
                if (!_autosaveDirHandle) await _autosaveChooseFolder();
                if (!_autosaveDirHandle) {
                    toggle.checked = false;
                    detail.classList.add('hidden');
                    toggle.dispatchEvent(new Event('change', { bubbles: true }));
                }
            } else {
                detail.classList.add('hidden');
            }
        });
    }
    if (chooseBtn) chooseBtn.addEventListener('click', _autosaveChooseFolder);
    _autosaveSetFolderLabel();
}
