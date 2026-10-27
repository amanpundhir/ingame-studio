/**
 * InGame Studio - the viewer's own match session.
 *
 * Every browser tab makes up a random session id the first time it loads and keeps it in
 * sessionStorage (so a reload continues the same match). The id goes to the server on every API
 * request (X-Session-Id header) and on the WebSocket (?session=), and the server gives that id
 * its own match: its own clock, play state, score and analytics. Pressing Play or Pause here
 * never affects anyone else's match.
 */

const STORAGE_KEY = 'ingame_session_id';
let memoryId: string | null = null;

function makeId(): string {
  const cryptoApi = (typeof crypto !== 'undefined' ? crypto : undefined) as Crypto | undefined;
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') {
    return cryptoApi.randomUUID();
  }
  let id = '';
  for (let i = 0; i < 32; i += 1) {
    id += Math.floor(Math.random() * 16).toString(16);
  }
  return id;
}

export function getSessionId(): string {
  try {
    let id = sessionStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = makeId();
      sessionStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    // Storage can be blocked (private windows, embedded views): keep one id for this page load.
    if (!memoryId) memoryId = makeId();
    return memoryId;
  }
}

/** Makes every request to our own /api/ carry the viewer's session id. */
export function installSessionFetch(): void {
  const original = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname : input.url;
    if (url.startsWith('/api/')) {
      const headers = new Headers(init?.headers);
      headers.set('X-Session-Id', getSessionId());
      return original(input, { ...init, headers });
    }
    return original(input, init);
  };
}
