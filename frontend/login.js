(() => {
  'use strict';

  const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:8000/api`;
  const form = document.querySelector('#login-form');
  const button = document.querySelector('#login-button');
  const message = document.querySelector('#login-message');
  let csrfToken = '';

  async function csrf() {
    const response = await fetch(`${API_BASE_URL}/auth/csrf/`, { credentials: 'include', headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Unable to connect securely to the sign-in service.');
    const data = await response.json();
    csrfToken = data.csrfToken;
  }
  function showMessage(text) {
    message.textContent = text;
    message.classList.remove('hidden');
  }
  async function redirectIfSignedIn() {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/me/`, { credentials: 'include', headers: { Accept: 'application/json' } });
      if (response.ok) window.location.replace('./index.html');
    } catch { /* The form will display a connection error when submitted. */ }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    message.classList.add('hidden');
    button.disabled = true;
    button.textContent = 'Signing in…';
    try {
      if (!csrfToken) await csrf();
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST', credentials: 'include',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ username: form.elements.username.value.trim(), password: form.elements.password.value })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Sign-in failed. Check your username and password.');
      window.location.replace('./index.html');
    } catch (error) {
      showMessage(error instanceof TypeError ? 'Cannot reach Django. Make sure the backend is running at 127.0.0.1:8000.' : error.message);
    } finally {
      button.disabled = false;
      button.textContent = 'Sign in';
    }
  });
  csrf().catch(() => showMessage('Cannot reach Django. Make sure the backend is running at 127.0.0.1:8000.'));
  redirectIfSignedIn();
})();
