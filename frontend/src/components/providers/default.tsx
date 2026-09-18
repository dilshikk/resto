import { AuthProvider } from "@/context/auth-context.tsx";
import { QueryClientProvider } from "./query-client.tsx";
import { ThemeProvider } from "./theme.tsx";
import { Toaster } from "./toaster.tsx";

export function DefaultProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <QueryClientProvider>
        <ThemeProvider>
          <Toaster />
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    </AuthProvider>
  );
}
