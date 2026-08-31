"use client";

import { useRouter } from "next/navigation";
import { useAuthContext } from "@/lib/auth-context";

/**
 * Shows the logged-in user's name and a logout button in the header.
 * For guest users, shows a "Guest" badge instead of capital.
 */
export default function HeaderUser() {
  const { user, logout, loading } = useAuthContext();
  const router = useRouter();

  if (loading || !user) return null;

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="flex items-center gap-2 whitespace-nowrap">
      <span className="text-sm text-slate-400 hidden md:inline">{user.name}</span>
      {user.is_guest ? (
        <span className="text-xs text-amber-400 bg-amber-950/30 px-2 py-0.5 rounded">Guest</span>
      ) : (
        <span className="text-xs text-emerald-400 bg-emerald-950/30 px-2 py-0.5 rounded">
          ₹{(user.capital / 100000).toFixed(0)}L
        </span>
      )}
      <button
        onClick={handleLogout}
        className="text-xs text-slate-500 hover:text-red-400 px-2 py-1 rounded transition-colors"
      >
        Logout
      </button>
    </div>
  );
}
