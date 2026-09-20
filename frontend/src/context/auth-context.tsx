import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import {
  login as apiLogin,
  logout as apiLogout,
  verify2fa as apiVerify2fa,
  silentRefresh,
} from "@/api/auth.ts";
import { setAccessToken } from "@/api/client.ts";
import type { LoginRequest } from "@/api/auth.ts";

/**
 * When the server responds with requires_2fa=true, the login flow pauses and
 * the UI must collect a TOTP code from the user.  login() signals this by
 * returning "requires_2fa" instead of void, carrying the opaque pre_auth_token
 * the user must then pass to verify2fa() along with their TOTP code.
 */
export type LoginResult =
  | { status: "ok" }
  | { status: "requires_2fa"; preAuthToken: string };

type AuthContextValue = {
  isAuthenticated: boolean;
  /** True while the initial silent-refresh check is running on page load. */
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<LoginResult>;
  verify2fa: (preAuthToken: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Start unauthenticated; the useEffect below attempts a silent refresh.
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  // Show a loading state until we know whether the cookie session is valid.
  const [isLoading, setIsLoading] = useState(true);

  // ── Silent refresh on mount ───────────────────────────────────────────────
  // The access token lives only in memory, so it vanishes on page reload.
  // The refresh token lives in an httpOnly cookie that persists across reloads.
  // On mount we attempt to exchange the cookie for a fresh access token so
  // the user doesn't have to log in again after a page refresh.
  useEffect(() => {
    let cancelled = false;

    const restore = async () => {
      try {
        const { access_token } = await silentRefresh();
        if (!cancelled) {
          setAccessToken(access_token);
          setIsAuthenticated(true);
        }
      } catch {
        // No valid cookie — user is not authenticated.  This is expected when
        // the user has never logged in or after their refresh token expired.
        if (!cancelled) {
          setIsAuthenticated(false);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };

    restore();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (data: LoginRequest): Promise<LoginResult> => {
    setIsLoading(true);
    try {
      const response = await apiLogin(data);

      if (response.requires_2fa) {
        // Server needs a TOTP code before issuing real tokens.
        return { status: "requires_2fa", preAuthToken: response.pre_auth_token };
      }

      // Store the access token in memory only — never in localStorage.
      setAccessToken(response.access_token);
      setIsAuthenticated(true);
      return { status: "ok" };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const verify2fa = useCallback(
    async (preAuthToken: string, code: string): Promise<void> => {
      setIsLoading(true);
      try {
        const { access_token } = await apiVerify2fa(preAuthToken, code);
        setAccessToken(access_token);
        setIsAuthenticated(true);
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Ignore errors on logout — we always clear local state.
    } finally {
      // Clear the in-memory token.  The server already cleared the cookie.
      setAccessToken(null);
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, verify2fa, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
