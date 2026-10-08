// Frontend logic for auth functionality.

import { BASE_URL, apiDetailText, formatApiError, getAuthHeaders } from './api.js';
import { dispatch, getState } from './state.js';
import { setSideLoading } from './utils.js';
import { charCount } from './request_limits.js';
import { announceWorkspaceChange } from './dom.js';
import { readPref, writePref } from './session_store.js';

const SKEW_KEY = 'rosetta_token_clock_skew_ms';

/** @type {null | (() => void)} */
let _afterLogin = null;

/** Run `cb` once after the next successful sign-in. */
export function onNextLogin(cb) {
    _afterLogin = cb;
}

export function openAuthModal() {
    document.getElementById('auth-modal').classList.remove('hidden');
    toggleAuthMode('login');
}

export function closeAuthModal() {
    document.getElementById('auth-modal').classList.add('hidden');
    document.getElementById('login-email').value = '';
    document.getElementById('login-password').value = '';
    document.getElementById('register-email').value = '';
    document.getElementById('register-password').value = '';
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('register-error').classList.add('hidden');
}

export function toggleAuthMode(mode) {
    if (mode === 'login') {
        document.getElementById('login-form-container').classList.remove('hidden');
        document.getElementById('register-form-container').classList.add('hidden');
    } else {
        document.getElementById('login-form-container').classList.add('hidden');
        document.getElementById('register-form-container').classList.remove('hidden');
    }
}

/** The claims of a JWT (`sub`, `exp` in seconds), or null when it cannot be read. */
export function tokenClaims(token) {
    try {
        const part = String(token).split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        const claims = JSON.parse(atob(part + '='.repeat((4 - part.length % 4) % 4)));
        return claims && typeof claims === 'object' ? claims : null;
    } catch (_) {
        return null;
    }
}

/** The signed-in account's email, or null when nobody is signed in. */
export function signedInAccount() {
    const token = getState().authToken;
    if (!token) return null;
    return tokenClaims(token)?.sub || 'signed-in';
}

/** Server clock minus this browser's clock (ms), from a token's issue time read on arrival. */
export function clockSkewMs(token, nowMs) {
    const iat = tokenClaims(token)?.iat;
    return typeof iat === 'number' && Number.isFinite(iat) ? iat * 1000 - nowMs : 0;
}

/** A token's expiry on this browser's clock (epoch ms), or null when it has none. */
export function localExpiry(token, skewMs) {
    const exp = tokenClaims(token)?.exp;
    return typeof exp === 'number' && Number.isFinite(exp) ? exp * 1000 - (Number.isFinite(skewMs) ? skewMs : 0) : null;
}

/** Store a new sign-in token together with the clock difference measured as it arrived. */
function _setToken(token) {
    writePref(SKEW_KEY, token ? String(clockSkewMs(token, Date.now())) : null);
    dispatch('SET_AUTH_TOKEN', token);
}

/** When the current sign-in expires (epoch ms on this browser's clock), or null when unknown or not signed in. */
function _expiresAt() {
    const token = getState().authToken;
    return token ? localExpiry(token, Number(readPref(SKEW_KEY, '0'))) : null;
}

let _expiryTimer = null;

/** Sign out because the sign-in expired; the page says so and offers to sign in again. */
function _expireSession() {
    const at = _expiresAt();
    _setToken(null);
    updateAuthUI();
    document.dispatchEvent(new CustomEvent('session-expired', { detail: { at } }));
}

function _scheduleExpiry() {
    clearTimeout(_expiryTimer);
    _expiryTimer = null;
    const at = _expiresAt();
    if (at === null) return;
    _expiryTimer = setTimeout(_expireSession, Math.max(0, Math.min(at - Date.now(), 2 ** 31 - 1)));
}

/** Before a run: when the sign-in has expired, say that the run would not be saved and let the
 * user sign in first. Returns false when the run should not start now. */
export function confirmUnsavedRun() {
    const at = _expiresAt();
    if (at === null || at > Date.now() + 5000) return true;
    _expireSession();
    const when = new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (confirm(`Your sign-in expired at ${when}, so this run would not be saved to your History.\n\nOK runs it without saving; Cancel lets you sign in first.`)) return true;
    openAuthModal();
    return false;
}

export function updateAuthUI() {
    const loginBtn = document.getElementById('btn-login-modal');
    const userProfile = document.getElementById('user-profile');
    const emailDisplay = document.getElementById('user-email-display');

    if (getState().authToken) {
        if (loginBtn) loginBtn.classList.add('hidden');
        if (userProfile) userProfile.classList.remove('hidden');
        const email = tokenClaims(getState().authToken)?.sub || 'User (Logged In)';
        if (emailDisplay) emailDisplay.textContent = email;
        const full = document.getElementById('user-email-full');
        if (full) full.textContent = email;
    } else {
        if (loginBtn) loginBtn.classList.remove('hidden');
        if (userProfile) userProfile.classList.add('hidden');
        if (emailDisplay) emailDisplay.textContent = '';
        /** @type {HTMLDetailsElement|null} */ (document.getElementById('account-menu'))?.removeAttribute('open');
    }
    _scheduleExpiry();
    announceWorkspaceChange();
}

export async function handleLoginSubmit() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');

    if (!email || !password) {
        errorDiv.textContent = "Email and password are required.";
        errorDiv.classList.remove('hidden');
        return;
    }

    setSideLoading(true, "Logging in...");
    errorDiv.classList.add('hidden');

    try {
        const requestToken = (pw) => fetch(`${BASE_URL}/auth/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ username: email, password: pw }).toString(),
        });
        let res = await requestToken(password);
        // An account can hold the trimmed form of a password typed with spaces around it.
        if (res.status === 401 && password.trim() !== password && password.trim()) {
            res = await requestToken(password.trim());
        }

        const data = await res.json();

        if (!res.ok) {
            throw new Error(apiDetailText(data.detail) || "Login failed.");
        }

        _setToken(data.access_token);

        updateAuthUI();
        closeAuthModal();
        const next = _afterLogin;
        _afterLogin = null;
        if (next) next();

    } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.classList.remove('hidden');
    } finally {
        setSideLoading(false);
    }
}

export async function handleRegisterSubmit() {
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const errorDiv = document.getElementById('register-error');

    if (!email || !password) {
        errorDiv.textContent = "Email and password are required.";
        errorDiv.classList.remove('hidden');
        return;
    }
    const { emailMaxLength, passwordMinChars, passwordMaxBytes } = getState();
    const problem = charCount(email) > emailMaxLength ? `The email address can have at most ${emailMaxLength} characters.`
        : charCount(password) < passwordMinChars ? `The password needs at least ${passwordMinChars} characters.`
        : new TextEncoder().encode(password).length > passwordMaxBytes
            ? `The password can be at most ${passwordMaxBytes} bytes long (UTF-8; most accented letters and symbols take two or more bytes).`
            : null;
    if (problem) {
        errorDiv.textContent = problem;
        errorDiv.classList.remove('hidden');
        return;
    }

    setSideLoading(true, "Creating account...");
    errorDiv.classList.add('hidden');

    try {
        const payload = { email: email, password: password };
        const res = await fetch(`${BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            throw new Error(apiDetailText(data.detail) || `Registration failed (HTTP ${res.status}).`);
        }

        toggleAuthMode('login');
        document.getElementById('login-email').value = email;
        document.getElementById('login-password').value = password;
        await handleLoginSubmit();

    } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.classList.remove('hidden');
    } finally {
        setSideLoading(false);
    }
}

/** Sign out; the signed-out account's results and saved runs leave the screen. */
export function handleLogout() {
    _setToken(null);
    updateAuthUI();
    document.dispatchEvent(new Event('signed-out'));
}

export async function verifySession() {
    if (!getState().authToken) return;
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            headers: getAuthHeaders()
        });
        if (res.status === 401 && _expiresAt() !== null && /** @type {number} */ (_expiresAt()) <= Date.now()) {
            _expireSession();
        } else if (!res.ok) {
            handleLogout();
        }
    } catch (e) {
        console.error("Session verification failed", e);
    }
}

export async function handleDeleteAccount() {
    if (!confirm("Are you sure you want to permanently delete your account? This action cannot be undone.")) {
        return;
    }

    setSideLoading(true, "Deleting account...");
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!res.ok) throw new Error(await formatApiError(res));

        handleLogout();
        alert("Your account and its saved runs were deleted, and you are signed out.");
    } catch (e) {
        console.error("Account deletion failed:", e);
        alert("The account was not deleted. " + e.message);
    } finally {
        setSideLoading(false);
    }
}
/** The account menu in the header closes on a click outside it and on Escape. */
document.addEventListener('click', e => {
    const menu = document.getElementById('account-menu');
    if (menu?.hasAttribute('open') && e.target instanceof Node && !menu.contains(e.target)) menu.removeAttribute('open');
});
document.addEventListener('keydown', e => {
    const menu = document.getElementById('account-menu');
    if (e.key !== 'Escape' || !menu?.hasAttribute('open')) return;
    menu.removeAttribute('open');
    /** @type {HTMLElement|null} */ (menu.querySelector('summary'))?.focus();
});
