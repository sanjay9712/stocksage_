"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6">
      <div className="rounded-lg border border-rose-800/50 bg-rose-950/20 p-8 text-center max-w-md">
        <h2 className="text-lg font-semibold text-rose-300">Something went wrong</h2>
        <p className="text-xs text-slate-400 mt-2">{error.message || "An unexpected error occurred."}</p>
        {error.digest && (
          <p className="text-[10px] text-slate-600 mt-1">Error ID: {error.digest}</p>
        )}
        <button
          onClick={reset}
          className="mt-4 rounded-md bg-slate-700 hover:bg-slate-600 px-4 py-2 text-sm"
        >
          Try again
        </button>
      </div>
    </div>
  );
}
