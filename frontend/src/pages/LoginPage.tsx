import { useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/auth-context.tsx";
import { toast } from "sonner";

/**
 * Two-step login page.
 *
 * Step 1 – email + password
 *   → server returns tokens immediately  →  navigate to /app
 *   → server returns requires_2fa=true   →  move to step 2
 *
 * Step 2 – 6-digit TOTP code
 *   → correct code  →  tokens saved, navigate to /app
 *   → wrong code    →  error toast, stay on step 2 (pre_auth_token is still valid)
 *
 * The pre_auth_token lives for 5 minutes on the server.  "Back" resets to
 * step 1 so the user can re-enter credentials if needed.
 */
export default function LoginPage() {
  const { isAuthenticated, login, verify2fa } = useAuth();
  const navigate = useNavigate();

  // ── step 1 state ────────────────────────────────────────────────────────────
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // ── step 2 state ────────────────────────────────────────────────────────────
  // preAuthToken is set when the server asks for 2FA; null means step 1.
  const [preAuthToken, setPreAuthToken] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const totpInputRef = useRef<HTMLInputElement>(null);

  const [submitting, setSubmitting] = useState(false);

  if (isAuthenticated) return <Navigate to="/app" replace />;

  // ── handlers ────────────────────────────────────────────────────────────────

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const result = await login({ email, password });
      if (result.status === "ok") {
        navigate("/app", { replace: true });
      } else {
        // Server needs a TOTP code — switch to step 2.
        setPreAuthToken(result.preAuthToken);
        setTotpCode("");
        // Focus the code input after the component re-renders.
        setTimeout(() => totpInputRef.current?.focus(), 50);
      }
    } catch {
      toast.error("Неверный email или пароль");
    } finally {
      setSubmitting(false);
    }
  };

  const handleTotpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!preAuthToken) return;
    setSubmitting(true);
    try {
      await verify2fa(preAuthToken, totpCode.trim());
      navigate("/app", { replace: true });
    } catch {
      toast.error("Неверный код. Проверьте время на устройстве и попробуйте снова.");
      setTotpCode("");
      totpInputRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  const handleBackToPassword = () => {
    setPreAuthToken(null);
    setTotpCode("");
  };

  // Auto-submit when the user has entered all 6 digits (no button press needed).
  const handleTotpChange = (value: string) => {
    // Allow only digits, max 6 characters.
    const cleaned = value.replace(/\D/g, "").slice(0, 6);
    setTotpCode(cleaned);
    if (cleaned.length === 6 && preAuthToken && !submitting) {
      setSubmitting(true);
      verify2fa(preAuthToken, cleaned)
        .then(() => navigate("/app", { replace: true }))
        .catch(() => {
          toast.error("Неверный код. Проверьте время на устройстве и попробуйте снова.");
          setTotpCode("");
          totpInputRef.current?.focus();
        })
        .finally(() => setSubmitting(false));
    }
  };

  // ── render ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4">
      {/* Logo + title */}
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
        {/* ── Step 1: email + password ── */}
        {preAuthToken === null && (
          <>
            <h2 className="text-xl font-semibold text-center">Вход</h2>
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="email" className="text-sm font-medium">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="example@mado.uz"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium">
                  Пароль
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
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
          </>
        )}

        {/* ── Step 2: TOTP code ── */}
        {preAuthToken !== null && (
          <>
            <div className="flex flex-col items-center gap-1 text-center">
              <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-2xl">
                🔐
              </div>
              <h2 className="text-xl font-semibold">Двухфакторная аутентификация</h2>
              <p className="text-sm text-muted-foreground">
                Введите 6-значный код из приложения-аутентификатора
              </p>
            </div>

            <form onSubmit={handleTotpSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="totp" className="text-sm font-medium">
                  Код подтверждения
                </label>
                <input
                  ref={totpInputRef}
                  id="totp"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-center text-xl tracking-[0.4em] font-mono outline-none focus:ring-2 focus:ring-ring"
                  placeholder="000000"
                  value={totpCode}
                  onChange={(e) => handleTotpChange(e.target.value)}
                  maxLength={6}
                  required
                />
                <p className="text-xs text-muted-foreground text-center">
                  Код вводится автоматически после 6 цифр
                </p>
              </div>
              <button
                type="submit"
                disabled={submitting || totpCode.length !== 6}
                className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Проверяем..." : "Подтвердить"}
              </button>
            </form>

            <button
              type="button"
              onClick={handleBackToPassword}
              className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition"
            >
              ← Вернуться к вводу пароля
            </button>
          </>
        )}
      </div>
    </div>
  );
}
