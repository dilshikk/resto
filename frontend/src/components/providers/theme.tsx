import { useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme] = useState<Theme>(() => {
    return (localStorage.getItem("theme") as Theme) ?? "system";
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.toggle("dark", prefersDark);
    } else {
      root.classList.toggle("dark", theme === "dark");
    }
  }, [theme]);

  return <>{children}</>;
}
