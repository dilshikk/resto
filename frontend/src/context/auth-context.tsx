import React, { createContext, useContext, useState, useCallback } from "react";
import {
  login as apiLogin,
  logout as apiLogout,
  verify2fa as apiVerify2fa,
} from "@/api/auth.ts";
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
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<LoginResult>;
  verify2fa: (preAuthToken: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function saveTokens(access_token: string, refresh_token: string) {
  localStorage.setItem("access_token", access_token);
  localStorage.setItem("refresh_token", refresh_token);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    () => !!localStorage.getItem("access_token"),
  );
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (data: LoginRequest): Promise<LoginResult> => {
    setIsLoading(true);
    try {
      const response = await apiLogin(data);

      if (response.requires_2fa) {
        // Server needs a TOTP code before issuing real tokens.
        // Return the pre-auth token so the UI can render the 2FA step.
        return { status: "requires_2fa", preAuthToken: response.pre_auth_token };
      }

      saveTokens(response.access_token, response.refresh_token);
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
        const tokens = await apiVerify2fa(preAuthToken, code);
        saveTokens(tokens.access_token, tokens.refresh_token);
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
      // ignore errors on logout
    } finally {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
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
