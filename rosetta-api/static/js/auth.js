// Frontend logic for auth functionality.

import { BASE_URL, apiDetailText, formatApiError, getAuthHeaders } from './api.js';
import { dispatch, getState } from './state.js';
import { setLoading } from './utils.js';
import { announceWorkspaceChange } from './dom.js';

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

export function updateAuthUI() {
    const loginBtn = document.getElementById('btn-login-modal');
    const userProfile = document.getElementById('user-profile');
    const emailDisplay = document.getElementById('user-email-display');

    if (getState().authToken) {
        if (loginBtn) loginBtn.classList.add('hidden');
        if (userProfile) userProfile.classList.remove('hidden');
        try {
            const payload = JSON.parse(atob(getState().authToken.split('.')[1]));
            if (emailDisplay) emailDisplay.textContent = payload.sub || 'User';
        } catch (e) {
            if (emailDisplay) emailDisplay.textContent = 'User (Logged In)';
        }
    } else {
        if (loginBtn) loginBtn.classList.remove('hidden');
        if (userProfile) userProfile.classList.add('hidden');
        if (emailDisplay) emailDisplay.textContent = '';
    }
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

    setLoading(true, "Logging in...");
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

        dispatch('SET_AUTH_TOKEN', data.access_token);

        updateAuthUI();
        closeAuthModal();
        const next = _afterLogin;
        _afterLogin = null;
        if (next) next();

    } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.classList.remove('hidden');
    } finally {
        setLoading(false);
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

    setLoading(true, "Creating account...");
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
        setLoading(false);
    }
}

export function handleLogout() {
    dispatch('SET_AUTH_TOKEN', null);

    updateAuthUI();
}

export async function verifySession() {
    if (!getState().authToken) return;
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            headers: getAuthHeaders()
        });
        if (!res.ok) {
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

    setLoading(true, "Deleting account...");
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!res.ok) throw new Error(await formatApiError(res));

        alert("Your account has been securely deleted.");
        handleLogout();
    } catch (e) {
        console.error("Account deletion failed:", e);
        alert("Error deleting account: " + e.message);
    } finally {
        setLoading(false);
    }
}