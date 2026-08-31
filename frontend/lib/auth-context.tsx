"use client";

import { createContext, useContext } from "react";
import { useAuth } from "./auth";
import type { User } from "./api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  logout: () => {},
});

/**
 * Auth provider that calls useAuth() ONCE and shares the result
 * across all consumers via React context. Without this, every component
 * that calls useAuth() independently triggers a separate /api/auth/me
 * network call — AuthGate, NavDropdown, and HeaderUser each fetched
 * separately on every page load (3 redundant calls).
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const auth = useAuth();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  return useContext(AuthContext);
}
