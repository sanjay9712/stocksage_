"use client";

import { useEffect, useState, useCallback } from "react";
import { getStoredUser, getToken, clearToken, fetchMe, ApiError, type User } from "./api";

/**
 * Client-side auth hook. Reads JWT + user from localStorage on mount,
 * validates the token against /api/auth/me, and listens for auth-change
 * events so login/logout in other components updates this state immediately.
 *
 * Performance: when a stored user is available (e.g. right after login),
 * we show the UI immediately and validate in the background. This avoids
 * a ~0.5s loading spinner on every login/page-load.
 *
 * Error handling: only clear the token on 401 Unauthorized (token expired
 * or invalid). On network errors or 5xx server errors, keep the stored
 * user so the app remains usable during transient backend issues. This is
 * especially important for guest users who can't re-login with credentials.
 */
export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(() => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    // If we have a stored user, show it immediately and validate in the
    // background.  This makes login feel instant — no loading spinner.
    const stored = getStoredUser();
    if (stored) {
      setUser(stored);
      setLoading(false);
      // Validate token in background; only clear on 401 (auth failure).
      fetchMe()
        .then((u) => setUser(u))
        .catch((err) => {
          if (err instanceof ApiError && err.status === 401) {
            clearToken();
            setUser(null);
          }
          // On network/5xx errors: keep the stored user so the app
          // remains usable during transient backend issues.
        });
    } else {
      // No stored user — must fetch (first page load with stale token).
      setLoading(true);
      fetchMe()
        .then((u) => setUser(u))
        .catch((err) => {
          if (err instanceof ApiError && err.status === 401) {
            clearToken();
            setUser(null);
          }
        })
        .finally(() => setLoading(false));
    }
  }, []);

  useEffect(() => {
    refresh();
    // Listen for token changes from login/logout/guest in other components.
    window.addEventListener("auth-change", refresh);
    return () => window.removeEventListener("auth-change", refresh);
  }, [refresh]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  return { user, loading, logout };
}
