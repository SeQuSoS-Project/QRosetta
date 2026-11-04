// Frontend logic for auth functionality.

import { BASE_URL, apiDetailText, formatApiError, getAuthHeaders } from './api.js';
import { dispatch, getState } from './state.js';
import { setSideLoading } from './utils.js';
import { charCount } from './request_limits.js';
import { announceWorkspaceChange } from './dom.js';
import { forgetAccountJobs, readPref, writePref } from './session_store.js';
import { closeModal, isModalOpen, openModal } from './modal.js';
import { announce } from './announce.js';

const SKEW_KEY = 'rosetta_token_clock_skew_ms';

/** @type {null | (() => void)} */
let _afterLogin = null;

/** Run `cb` once after the next successful sign-in. */
export function onNextLogin(cb) {
    _afterLogin = cb;
}

const _FIELDS = { login: ['login-email', 'login-password'], register: ['register-email', 'register-password'] };

export function openAuthModal() {
    const modal = document.getElementById('auth-modal');
    _setMode('login');
    openModal(modal, { initialFocus: '#login-email', onEscape: closeAuthModal });
}

export function closeAuthModal() {
    const modal = document.getElementById('auth-modal');
    [..._FIELDS.login, ..._FIELDS.register].forEach(id => { /** @type {HTMLInputElement} */ (document.getElementById(id)).value = ''; });
    _clearAuthError('login');
    _clearAuthError('register');
    if (isModalOpen(modal)) {
        closeModal(modal, { returnFocus: getState().authToken ? '#account-menu summary' : '#btn-login-modal' });
    } else {
        modal.classList.add('hidden');
    }
}

/** Show the login or the register form; the dialog takes that form's heading as its name. */
function _setMode(mode) {
    const login = mode === 'login';
    document.getElementById('login-form-container').classList.toggle('hidden', !login);
    document.getElementById('register-form-container').classList.toggle('hidden', login);
    document.getElementById('auth-modal').setAttribute('aria-labelledby', login ? 'auth-modal-title' : 'register-modal-title');
    _clearAuthError(login ? 'register' : 'login');
}

export function toggleAuthMode(mode) {
    _setMode(mode);
    /** @type {HTMLElement|null} */ (document.getElementById(mode === 'login' ? 'login-email' : 'register-email'))?.focus();
}

/** Show `message` in the login or register form's error box and mark `fields` (input ids) invalid. */
function _showAuthError(mode, message, fields = _FIELDS[mode]) {
    const box = document.getElementById(`${mode}-error`);
    box.textContent = message;
    box.classList.remove('hidden');
    _FIELDS[mode].forEach(id => {
        const input = document.getElementById(id);
        if (fields.includes(id)) input.setAttribute('aria-invalid', 'true');
        else input.removeAttribute('aria-invalid');
    });
    /** @type {HTMLElement|null} */ (document.getElementById(fields[0]))?.focus();
}

function _clearAuthError(mode) {
    const box = document.getElementById(`${mode}-error`);
    box.textContent = '';
    box.classList.add('hidden');
    _FIELDS[mode].forEach(id => document.getElementById(id).removeAttribute('aria-invalid'));
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
    if (confirm(`Sign-in expired at ${when}; this run would not be saved to History.\n\nOK: run without saving. Cancel: sign in first.`)) return true;
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

/** The message for a 429 from the sign-in or registration route, with the wait from Retry-After. */
function _rateLimitedText(res, what) {
    const wait = Number(res.headers.get('Retry-After'));
    return `Too many ${what} from this network address. Try again in ${wait > 0 ? `${wait} s` : 'a minute'}.`;
}

export async function handleLoginSubmit() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        _showAuthError('login', "Email and password are required.", _FIELDS.login.filter(id => !document.getElementById(id).value.trim()));
        return;
    }

    setSideLoading(true, "Logging in...");
    _clearAuthError('login');

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

        if (res.status === 429) throw new Error(_rateLimitedText(res, 'sign-in attempts'));
        const data = await res.json();

        if (!res.ok) {
            throw new Error(apiDetailText(data.detail) || "Login failed.");
        }

        _setToken(data.access_token);

        updateAuthUI();
        closeAuthModal();
        announce(`Signed in as ${email}.`);
        document.dispatchEvent(new Event('signed-in'));
        const next = _afterLogin;
        _afterLogin = null;
        if (next) next();

    } catch (e) {
        _showAuthError('login', e.message);
    } finally {
        setSideLoading(false);
    }
}

export async function handleRegisterSubmit() {
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;

    if (!email || !password) {
        _showAuthError('register', "Email and password are required.", _FIELDS.register.filter(id => !document.getElementById(id).value.trim()));
        return;
    }
    const { emailMaxLength, passwordMinChars, passwordMaxBytes } = getState();
    const emailProblem = charCount(email) > emailMaxLength ? `The email address can have at most ${emailMaxLength} characters.` : null;
    const problem = emailProblem
        || (charCount(password) < passwordMinChars ? `The password needs at least ${passwordMinChars} characters.`
        : new TextEncoder().encode(password).length > passwordMaxBytes
            ? `The password can be at most ${passwordMaxBytes} bytes (accented letters and symbols take 2 or more).`
            : null);
    if (problem) {
        _showAuthError('register', problem, [emailProblem ? 'register-email' : 'register-password']);
        return;
    }

    setSideLoading(true, "Creating account...");
    _clearAuthError('register');

    try {
        const payload = { email: email, password: password };
        const res = await fetch(`${BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.status === 429) throw new Error(_rateLimitedText(res, 'registrations'));
        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
            throw new Error(apiDetailText(data.detail) || `Registration failed (HTTP ${res.status}).`);
        }

        _setMode('login');
        document.getElementById('login-email').value = email;
        document.getElementById('login-password').value = password;
        await handleLoginSubmit();

    } catch (e) {
        _showAuthError('register', e.message);
    } finally {
        setSideLoading(false);
    }
}

/** Sign out on the server, which then refuses every earlier token of the account on any
 * device, and on this page, and forget the account's recorded jobs in this browser. The page
 * signs out even when the server cannot be reached. An expired session keeps the jobs, so they
 * can be resumed after signing in again. */
export async function signOut() {
    forgetAccountJobs(signedInAccount());
    if (getState().authToken) {
        try {
            await fetch(`${BASE_URL}/auth/logout`, { method: 'POST', headers: getAuthHeaders() });
        } catch (e) {
            console.error("Sign-out request failed", e);
        }
    }
    handleLogout();
}

/** Sign out on this page; the signed-out account's results and saved runs leave the screen. */
export function handleLogout() {
    const hadFocus = document.getElementById('user-profile')?.contains(document.activeElement);
    _setToken(null);
    updateAuthUI();
    document.dispatchEvent(new Event('signed-out'));
    if (hadFocus) /** @type {HTMLElement|null} */ (document.getElementById('btn-login-modal'))?.focus();
    announce('Signed out.');
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

const _deletePassword = () => /** @type {HTMLInputElement} */ (document.getElementById('delete-account-password'));

function _showDeleteError(message) {
    const box = document.getElementById('delete-account-error');
    box.textContent = message;
    box.classList.toggle('hidden', !message);
    if (message) _deletePassword().setAttribute('aria-invalid', 'true');
    else _deletePassword().removeAttribute('aria-invalid');
}

const _currentPassword = () => /** @type {HTMLInputElement} */ (document.getElementById('change-password-current'));
const _newPassword = () => /** @type {HTMLInputElement} */ (document.getElementById('change-password-new'));

function _showChangePasswordError(message, field = null) {
    const box = document.getElementById('change-password-error');
    box.textContent = message;
    box.classList.toggle('hidden', !message);
    for (const input of [_currentPassword(), _newPassword()]) {
        if (message && (field === null || input === field)) input.setAttribute('aria-invalid', 'true');
        else input.removeAttribute('aria-invalid');
    }
}

/** Open the Change Password dialog. */
export function handleChangePassword() {
    _currentPassword().value = '';
    _newPassword().value = '';
    _showChangePasswordError('');
    openModal(document.getElementById('change-password-modal'),
        { initialFocus: '#change-password-current', onEscape: closeChangePasswordModal });
}

export function closeChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    _currentPassword().value = '';
    _newPassword().value = '';
    _showChangePasswordError('');
    if (isModalOpen(modal)) closeModal(modal, { returnFocus: '#account-menu summary' });
    else modal.classList.add('hidden');
}

/** Change the signed-in account's password (POST /auth/password). The server ends every earlier
 * session and answers with a new token, which keeps this page signed in. */
export async function submitChangePassword() {
    const current = _currentPassword().value;
    const next = _newPassword().value;
    if (!current) { _showChangePasswordError("Enter your current password.", _currentPassword()); _currentPassword().focus(); return; }
    if (!next) { _showChangePasswordError("Enter a new password.", _newPassword()); _newPassword().focus(); return; }

    setSideLoading(true, "Changing password...");
    try {
        const res = await fetch(`${BASE_URL}/auth/password`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ current_password: current, new_password: next }),
        });
        if (res.status === 429) throw new Error(_rateLimitedText(res, 'password changes'));
        if (res.status === 403) {
            _showChangePasswordError("The current password is not correct.", _currentPassword());
            _currentPassword().focus();
            return;
        }
        if (!res.ok) throw new Error(await formatApiError(res));
        const data = await res.json();
        _setToken(data.access_token);
        closeChangePasswordModal();
        announce('Password changed. Other sessions of this account are signed out.');
    } catch (e) {
        console.error("Password change failed:", e);
        _showChangePasswordError("The password was not changed. " + e.message, _newPassword());
        _newPassword().focus();
    } finally {
        setSideLoading(false);
    }
}

/** Open the Delete Account dialog, which asks for the account's password. */
export function handleDeleteAccount() {
    _deletePassword().value = '';
    _showDeleteError('');
    openModal(document.getElementById('delete-account-modal'),
        { initialFocus: '#delete-account-password', onEscape: closeDeleteAccountModal });
}

export function closeDeleteAccountModal() {
    const modal = document.getElementById('delete-account-modal');
    _deletePassword().value = '';
    _showDeleteError('');
    if (isModalOpen(modal)) closeModal(modal, { returnFocus: '#account-menu summary' });
    else modal.classList.add('hidden');
}

/** Delete the signed-in account after the server checks the password typed in the dialog. */
export async function submitDeleteAccount() {
    const password = _deletePassword().value;
    if (!password) {
        _showDeleteError("Enter your password.");
        _deletePassword().focus();
        return;
    }

    setSideLoading(true, "Deleting account...");
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            method: 'DELETE',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ password }),
        });

        if (res.status === 429) throw new Error(_rateLimitedText(res, 'account deletion attempts'));
        if (!res.ok) throw new Error(await formatApiError(res));

        closeDeleteAccountModal();
        forgetAccountJobs(signedInAccount());
        handleLogout();
        alert("Account and saved runs deleted; signed out.");
    } catch (e) {
        console.error("Account deletion failed:", e);
        _showDeleteError("The account was not deleted. " + e.message);
        _deletePassword().focus();
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
