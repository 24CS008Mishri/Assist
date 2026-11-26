export async function liveRequest(path, options = {}) {
  const { timeoutMs = 45000, ...init } = options;
  try {
    const response = await fetch(path, { ...init, signal: AbortSignal.timeout(timeoutMs) });
    if (response.ok) return response.status === 204 ? null : response.json();
    const data = await response.json().catch(() => null);
    const message = typeof data?.detail === 'string' ? data.detail : 'The consultation service is unavailable. Please retry.';
    const failure = new Error(message);
    failure.status = response.status;
    throw failure;
  } catch (failure) {
    if (failure.name === 'TimeoutError') throw new Error('The request took too long. Please retry.');
    if (failure instanceof TypeError) throw new Error('Unable to reach the consultation service.');
    throw failure;
  }
}

export function logoutVerifiedDesigner() {
  return liveRequest('/api/designer-auth/logout', { method: 'POST' });
}
