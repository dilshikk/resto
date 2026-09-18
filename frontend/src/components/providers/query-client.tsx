import { QueryClient, QueryClientProvider as TanstackProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export function QueryClientProvider({ children }: { children: ReactNode }) {
  return <TanstackProvider client={queryClient}>{children}</TanstackProvider>;
}
