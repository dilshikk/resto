import React, { createContext, useContext, useState, useCallback } from "react";
import { login as apiLogin, logout as apiLogout } from "@/api/auth.ts";
import type { LoginRequest } from "@/api/auth.ts";

type AuthContextValue = {
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(
    () => !!localStorage.getItem("access_token"),
  );
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (data: LoginRequest) => {
    setIsLoading(true);
    try {
      const tokens = await apiLogin(data);
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      setIsAuthenticated(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

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
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
