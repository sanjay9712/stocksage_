"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthContext } from "@/lib/auth-context";

/** Pages that require a registered (non-guest) account. */
const RESTRICTED_PATHS = ["/mf", "/advanced", "/bot"];

/**
 * Wraps the app. Redirects to /login if unauthenticated.
 * Guest users are redirected to /login when accessing restricted pages
 * (paper trading, funds).
 */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuthContext();
  const router = useRouter();
  const pathname = usePathname();
  const isAuthPage = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    if (loading) return;
    if (!user && !isAuthPage) {
      router.replace("/login");
    } else if (user && !user.is_guest && isAuthPage) {
      // Fully registered users don't need to see login/register pages.
      // Guests are allowed through so they can sign up or log in.
      router.replace("/");
    } else if (user?.is_guest && RESTRICTED_PATHS.some((p) => pathname.startsWith(p))) {
      // Guest trying to access paper trading or funds → redirect to login.
      router.replace("/login?reason=guest");
    }
  }, [user, loading, isAuthPage, router, pathname]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-slate-500">Loading…</div>
      </div>
    );
  }

  if (isAuthPage && user && !user.is_guest) return null;
  if (!user && !isAuthPage) return null;
  if (user?.is_guest && RESTRICTED_PATHS.some((p) => pathname.startsWith(p))) return null;

  return <>{children}</>;
}
