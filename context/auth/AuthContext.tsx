"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearStoredToken, getStoredToken, setUnauthorizedHandler, storeToken } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { AuthUser, AuthUserUpdate, TokenResponse } from "@/lib/api/types";

function mapLoginError(error: unknown): Error {
  const generic = new Error("Connexion impossible. Veuillez réessayer.");
  if (!(error instanceof Error)) return generic;
  const message = error.message.toLowerCase();
  if (message.includes("invalid") || message.includes("email") || message.includes("password") || message.includes("auth")) {
    return new Error("Email ou mot de passe invalide.");
  }
  if (message.includes("disabled") || message.includes("désactiv") || message.includes("suspend")) {
    return new Error("Ce compte est désactivé. Contactez un administrateur.");
  }
  return generic;
}

export type AuthState = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  updateProfile: (payload: AuthUserUpdate) => Promise<AuthUser>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setUser(null);
    setError(null);
    router.push("/login");
  }, [router]);

  const loadProfile = useCallback(async () => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    setToken(stored);
    try {
      const profile = await apiFetch<AuthUser>(endpoints.auth.me);
      setUser(profile);
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const tokenResponse = await apiFetch<TokenResponse>(endpoints.auth.login, {
          method: "POST",
          body: { email, password },
          auth: false,
        });
        storeToken(tokenResponse.access_token);
        setToken(tokenResponse.access_token);
        const profile = await apiFetch<AuthUser>(endpoints.auth.me);
        setUser(profile);
        return profile;
      } catch (error) {
        console.error("Login failed", error);
        throw mapLoginError(error);
      }
    },
    [],
  );

  const updateProfile = useCallback(async (payload: AuthUserUpdate) => {
    setError(null);
    const profile = await apiFetch<AuthUser>(endpoints.auth.updateMe, {
      method: "PATCH",
      body: payload,
    });
    setUser(profile);
    return profile;
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => logout());
    loadProfile();
    return () => setUnauthorizedHandler(null);
  }, [loadProfile, logout]);

  const value = useMemo(
    () => ({ user, token, loading, error, login, updateProfile, logout }),
    [user, token, loading, error, login, updateProfile, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
