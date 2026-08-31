"use client";

import { SWRConfig } from "swr";

/**
 * Global SWR configuration provider.
 *
 * revalidateOnFocus: false — prevents ALL SWR hooks from refetching when the
 * browser tab regains focus. This was the #1 cause of slow tab switching:
 * dozens of hooks would fire simultaneously on every tab switch.
 *
 * dedupingInterval: 0 — allows each hook to refetch at its own refreshInterval
 * without SWR silently skipping requests it considers "duplicates".
 *
 * keepPreviousData: true — shows stale data while refreshing instead of
 * loading spinners, preventing visual flicker.
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
        dedupingInterval: 0,
        keepPreviousData: true,
      }}
    >
      {children}
    </SWRConfig>
  );
}
