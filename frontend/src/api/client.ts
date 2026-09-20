import axios from "axios";

const baseURL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api/v1`
  : "/api/v1";

// Main client — used by all API modules.
export const apiClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// Bare client used exclusively for the token-refresh call.
// It has NO response interceptor, so a 401 from /auth/refresh
// will not trigger another refresh attempt (infinite-loop guard).
const refreshClient = axios.create({
  baseURL,
  headers: { "Content-Type": "application/json" },
});

// ── Request interceptor ────────────────────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
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
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
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

    const storedRefreshToken = localStorage.getItem("refresh_token");
    if (!storedRefreshToken) {
      // No refresh token at all — go straight to login.
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
    originalRequest._retry = true;
    isRefreshing = true;

    try {
      const { data } = await refreshClient.post<{
        access_token: string;
        refresh_token: string;
      }>("/auth/refresh", { refresh_token: storedRefreshToken });

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      // Inject the new token into the original request and all queued ones.
      originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
      processQueue(null, data.access_token);

      return apiClient(originalRequest);
    } catch (refreshError) {
      // Refresh failed (expired / revoked refresh token) — log the user out.
      processQueue(refreshError, null);
      clearAuthAndRedirect();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);
