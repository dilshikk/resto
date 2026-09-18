import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/auth-context.tsx";
import { toast } from "sonner";

export default function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) return <Navigate to="/app" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await login({ email, password });
      navigate("/app", { replace: true });
    } catch {
      toast.error("Неверный email или пароль");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg text-3xl">
          🍽️
        </div>
        <h1 className="text-3xl font-bold tracking-tight">MADO Checklist</h1>
        <p className="max-w-sm text-muted-foreground">
          Контроль выполнения операционных чек-листов персоналом ресторанов MADO
        </p>
      </div>

      <div className="w-full max-w-sm rounded-2xl border bg-card p-6 shadow-sm space-y-4">
        <h2 className="text-xl font-semibold text-center">Вход</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="email" className="text-sm font-medium">Email</label>
            <input
              id="email"
              type="email"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="manager@mado.uz"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm font-medium">Пароль</label>
            <input
              id="password"
              type="password"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
