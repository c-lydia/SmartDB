let session = null;
try {
  session = JSON.parse(sessionStorage.getItem('smartdb-session'));
} catch {}
let refreshing;
export const signedIn = () => Boolean(session);
export function saveSession(value) {
  session = value;
  if (value) sessionStorage.setItem('smartdb-session', JSON.stringify(value));
  else sessionStorage.removeItem('smartdb-session');
}
export async function api(path, options = {}, retry = true) {
  const response = await fetch('/api/v1' + path, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(session ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...options.headers,
    },
  });
  if (response.status === 401 && session && retry && !path.startsWith('/auth/')) {
    refreshing ||= api(
      '/auth/refresh',
      { method: 'POST', body: JSON.stringify({ refresh_token: session.refresh_token }) },
      false,
    )
      .then(saveSession)
      .catch((error) => {
        saveSession(null);
        window.dispatchEvent(new Event('smartdb-logout'));
        throw error;
      })
      .finally(() => {
        refreshing = null;
      });
    await refreshing;
    return api(path, options, false);
  }
  if (response.status === 204) return null;
  if (response.ok && options.binary)
    return { blob: await response.blob(), headers: response.headers };
  const data = await response.json().catch(() => ({ message: 'Server response was not JSON.' }));
  if (!response.ok) {
    const error = new Error(data.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}
export const send = (path, body, method = 'POST') =>
  api(path, { method, body: JSON.stringify(body) });
