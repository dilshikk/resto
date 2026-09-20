import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : "/api/v1";

// ── In-memory access token ─────────────────────────────────────────────────
// The access token is held only in module-level memory — it is NEVER written
// to localStorage or sessionStorage.  An XSS script that runs in the same
// page context could technically read this variable, but:
//   • The token is short-lived (default 60 min).
//   • The refresh token lives in an httpOnly cookie that JS cannot touch at
//     all, so an attacker cannot silently extend the session after the access
//     token expires.
// On page reload the token is lost; AuthProvider calls silentRefresh() on
// mount to restore it transparently via the httpOnly cookie.
let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// ── Axios instances ────────────────────────────────────────────────────────
// withCredentials: true is required so the browser attaches the httpOnly
// refresh-token cookie on every request to the same API origin.
export const apiClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// Bare client used exclusively for the token-refresh call.
// It has NO response interceptor, so a 401 from /auth/refresh will not
// trigger another refresh attempt (infinite-loop guard).
export const refreshClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
  withCredentials: true, // must send the httpOnly cookie
});

// ── Request interceptor ────────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  if (_accessToken) {
    config.headers.Authorization = `Bearer ${_accessToken}`;
  }
  return config;
});

// ── Refresh-token queue ────────────────────────────────────────────────────
// While a refresh is in flight every new 401 is queued here.
// Once the refresh resolves / rejects, all queued promises are settled.
type QueueEntry = {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
};

let isRefreshing = false;
let waitingQueue: QueueEntry[] = [];

function processQueue(error: unknown, token: string | null) {
  for (const entry of waitingQueue) {
    if (error || token === null) {
      entry.reject(error);
    } else {
      entry.resolve(token);
    }
  }
  waitingQueue = [];
}

function clearAuthAndRedirect() {
  // Wipe the in-memory token — no localStorage cleanup needed.
  _accessToken = null;
  window.location.href = "/login";
}

// ── Response interceptor ───────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Only handle 401s that have not already been retried.
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }

    // Never try to refresh the refresh call itself.
    if (originalRequest.url?.includes("/auth/refresh")) {
      clearAuthAndRedirect();
      return Promise.reject(error);
    }

    // If a refresh is already in flight, queue this request until it settles.
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        waitingQueue.push({ resolve, reject });
      }).then((newToken) => {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      });
    }

    // We are the first to discover the expired token — start the refresh.
    // The refresh token lives in the httpOnly cookie; no body is needed.
    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const { data } = await refreshClient.post<{ access_token: string }>(
        "/auth/refresh",
      );

      _accessToken = data.access_token;

      // Retry the original request and all queued ones with the new token.
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      processQueue(null, data.access_token);

      return apiClient(originalRequest);
    } catch (refreshError) {
      // Refresh failed (expired / revoked cookie) — log the user out.
      processQueue(refreshError, null);
      clearAuthAndRedirect();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);
