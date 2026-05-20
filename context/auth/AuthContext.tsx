"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
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
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearClientAuthStorage = useCallback(() => {
    if (typeof window === "undefined") return;
    const keyMatchers = [
      "weefarm_token",
      "token",
      "session",
      "auth",
      "user",
      "profile",
      "role",
      "cooperative",
      "institution",
    ];
    const clearStore = (store: Storage) => {
      const toDelete: string[] = [];
      for (let i = 0; i < store.length; i += 1) {
        const key = store.key(i);
        if (!key) continue;
        const lowered = key.toLowerCase();
        if (keyMatchers.some((matcher) => lowered.includes(matcher))) {
          toDelete.push(key);
        }
      }
      toDelete.forEach((key) => store.removeItem(key));
    };
    clearStore(window.localStorage);
    clearStore(window.sessionStorage);
  }, []);

  const resetScopeState = useCallback(async () => {
    await queryClient.cancelQueries();
    queryClient.clear();
    clearStoredToken();
    clearClientAuthStorage();
    setToken(null);
    setUser(null);
    setError(null);
  }, [clearClientAuthStorage, queryClient]);

  const logout = useCallback(async () => {
    setLoading(true);
    await resetScopeState();
    router.replace("/login");
    setLoading(false);
  }, [resetScopeState, router]);

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
      await resetScopeState();
    } finally {
      setLoading(false);
    }
  }, [resetScopeState]);

  const login = useCallback(
    async (email: string, password: string) => {
      setError(null);
      setLoading(true);
      try {
        await resetScopeState();
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
      } finally {
        setLoading(false);
      }
    },
    [resetScopeState],
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
    setUnauthorizedHandler(() => {
      void logout();
    });
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
