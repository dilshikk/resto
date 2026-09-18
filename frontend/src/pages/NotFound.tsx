import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";

export default function NotFound() {
  const location = useLocation();

  useEffect(() => {
    console.error("404: Страница не найдена:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-6">
        <h1 className="text-6xl font-bold text-muted-foreground">404</h1>
        <h2 className="text-2xl font-semibold">Страница не найдена</h2>
        <Link
          to="/"
          className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90"
        >
          На главную
        </Link>
      </div>
    </div>
  );
}
