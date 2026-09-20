import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  bootstrapDirector,
  claimProfile,
  getMyProfile,
  hasAnyEmployees,
} from "@/api/employees.ts";
import { useAuth } from "@/context/auth-context.tsx";

// Application display name — keep in sync with LoginPage.tsx.
const APP_NAME = "MADO Checklist";

// Comprehensive list of IANA timezones with UTC offset labels.
// Groups: Americas → Europe → Africa → Asia/CIS → East Asia → Pacific.
const TIMEZONES: { value: string; label: string }[] = [
  { value: "Pacific/Honolulu",      label: "Pacific/Honolulu (UTC−10)" },
  { value: "America/Anchorage",     label: "America/Anchorage (UTC−9)" },
  { value: "America/Los_Angeles",   label: "America/Los_Angeles (UTC−8)" },
  { value: "America/Denver",        label: "America/Denver (UTC−7)" },
  { value: "America/Chicago",       label: "America/Chicago (UTC−6)" },
  { value: "America/New_York",      label: "America/New_York (UTC−5)" },
  { value: "America/Halifax",       label: "America/Halifax (UTC−4)" },
  { value: "America/Sao_Paulo",     label: "America/Sao_Paulo (UTC−3)" },
  { value: "Atlantic/Azores",       label: "Atlantic/Azores (UTC−1)" },
  { value: "Europe/London",         label: "Europe/London (UTC+0)" },
  { value: "Europe/Paris",          label: "Europe/Paris (UTC+1)" },
  { value: "Europe/Helsinki",       label: "Europe/Helsinki (UTC+2)" },
  { value: "Africa/Cairo",          label: "Africa/Cairo (UTC+2)" },
  { value: "Europe/Moscow",         label: "Europe/Moscow (UTC+3)" },
  { value: "Africa/Nairobi",        label: "Africa/Nairobi (UTC+3)" },
  { value: "Asia/Tbilisi",          label: "Asia/Tbilisi (UTC+4)" },
  { value: "Asia/Yerevan",          label: "Asia/Yerevan (UTC+4)" },
  { value: "Asia/Baku",             label: "Asia/Baku (UTC+4)" },
  { value: "Asia/Dubai",            label: "Asia/Dubai (UTC+4)" },
  { value: "Europe/Astrakhan",      label: "Europe/Astrakhan (UTC+4)" },
  { value: "Asia/Ashgabat",         label: "Asia/Ashgabat (UTC+5)" },
  { value: "Asia/Dushanbe",         label: "Asia/Dushanbe (UTC+5)" },
  { value: "Asia/Tashkent",         label: "Asia/Tashkent (UTC+5)" },
  { value: "Asia/Samarkand",        label: "Asia/Samarkand (UTC+5)" },
  { value: "Asia/Karachi",          label: "Asia/Karachi (UTC+5)" },
  { value: "Asia/Kolkata",          label: "Asia/Kolkata (UTC+5:30)" },
  { value: "Asia/Bishkek",          label: "Asia/Bishkek (UTC+6)" },
  { value: "Asia/Almaty",           label: "Asia/Almaty (UTC+6)" },
  { value: "Asia/Dhaka",            label: "Asia/Dhaka (UTC+6)" },
  { value: "Asia/Bangkok",          label: "Asia/Bangkok (UTC+7)" },
  { value: "Asia/Novosibirsk",      label: "Asia/Novosibirsk (UTC+7)" },
  { value: "Asia/Shanghai",         label: "Asia/Shanghai (UTC+8)" },
  { value: "Asia/Singapore",        label: "Asia/Singapore (UTC+8)" },
  { value: "Asia/Irkutsk",          label: "Asia/Irkutsk (UTC+8)" },
  { value: "Asia/Tokyo",            label: "Asia/Tokyo (UTC+9)" },
  { value: "Asia/Seoul",            label: "Asia/Seoul (UTC+9)" },
  { value: "Asia/Yakutsk",          label: "Asia/Yakutsk (UTC+9)" },
  { value: "Australia/Sydney",      label: "Australia/Sydney (UTC+10/11)" },
  { value: "Asia/Vladivostok",      label: "Asia/Vladivostok (UTC+10)" },
  { value: "Pacific/Auckland",      label: "Pacific/Auckland (UTC+12/13)" },
];

/**
 * Shown when a logged-in web user has no linked employee profile yet
 * (AppLayout redirects here when GET /employees/me comes back empty).
 *
 * Two distinct flows, mirroring what the backend already supports:
 *  1. No employees exist anywhere yet -> this is the very first user.
 *     Let them bootstrap themselves as Director + create the first branch.
 *  2. Employees already exist, but this account isn't linked to one ->
 *     they must have an invite code from their manager to claim a profile.
 */
export default function OnboardingPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { logout } = useAuth();

  const { data: anyEmployees, isLoading, isError } = useQuery({
    queryKey: ["has-any-employees"],
    queryFn: hasAnyEmployees,
  });

  const [fullName, setFullName] = useState("");
  const [branchName, setBranchName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Tashkent");
  const [inviteCode, setInviteCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const afterSuccess = async () => {
    await queryClient.invalidateQueries({ queryKey: ["my-profile"] });
    await queryClient.refetchQueries({ queryKey: ["my-profile"] });
    navigate("/app", { replace: true });
  };

  const handleBootstrap = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !branchName.trim()) return;
    setSubmitting(true);
    try {
      await bootstrapDirector({
        full_name: fullName.trim(),
        branch_name: branchName.trim(),
        timezone,
      });
      toast.success("Система настроена, вы назначены Директором");
      await afterSuccess();
    } catch {
      toast.error("Не удалось настроить систему. Возможно, она уже настроена.");
      await queryClient.invalidateQueries({ queryKey: ["has-any-employees"] });
    } finally {
      setSubmitting(false);
    }
  };

  const handleClaim = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteCode.trim()) return;
    setSubmitting(true);
    try {
      await claimProfile(inviteCode.trim().toUpperCase());
      toast.success("Профиль успешно привязан");
      await afterSuccess();
    } catch {
      toast.error("Код приглашения неверен, уже использован или профиль деактивирован");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecheck = async () => {
    setSubmitting(true);
    try {
      const profile = await getMyProfile();
      if (profile) {
        await afterSuccess();
        return;
      }
    } catch {
      // still not linked — expected
    } finally {
      setSubmitting(false);
    }
    toast.info("Профиль пока не найден. Попробуйте позже.");
  };

  const handleSignOut = async () => {
    try {
      await logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg text-3xl">
          🍽️
        </div>
        <h1 className="text-3xl font-bold tracking-tight">{APP_NAME}</h1>
        <p className="max-w-sm text-muted-foreground">Настройка доступа к системе</p>
      </div>

      <div className="w-full max-w-sm rounded-2xl border bg-card p-6 shadow-sm space-y-4">
        {isLoading && (
          <div className="space-y-3">
            <div className="h-5 w-2/3 animate-pulse rounded bg-muted" />
            <div className="h-10 w-full animate-pulse rounded-lg bg-muted" />
            <div className="h-10 w-full animate-pulse rounded-lg bg-muted" />
          </div>
        )}

        {isError && !isLoading && (
          <div className="space-y-3 text-center">
            <h2 className="text-lg font-semibold">Не удалось загрузить данные</h2>
            <p className="text-sm text-muted-foreground">
              Проверьте подключение к интернету и попробуйте снова.
            </p>
            <button
              type="button"
              onClick={() => queryClient.invalidateQueries({ queryKey: ["has-any-employees"] })}
              className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90"
            >
              Повторить
            </button>
          </div>
        )}

        {!isLoading && !isError && anyEmployees === false && (
          <>
            <h2 className="text-xl font-semibold text-center">Настройте вашу систему</h2>
            <p className="text-sm text-muted-foreground text-center">
              Вы первый пользователь. Заполните данные, и мы назначим вас
              Директором с первым филиалом.
            </p>
            <form onSubmit={handleBootstrap} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="full_name" className="text-sm font-medium">
                  Ваше имя
                </label>
                <input
                  id="full_name"
                  type="text"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Алишер Каримов"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="branch_name" className="text-sm font-medium">
                  Название первого филиала
                </label>
                <input
                  id="branch_name"
                  type="text"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  placeholder="Tashkent City Mall"
                  value={branchName}
                  onChange={(e) => setBranchName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="timezone" className="text-sm font-medium">
                  Часовой пояс
                </label>
                <select
                  id="timezone"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                >
                  {TIMEZONES.map((tz) => (
                    <option key={tz.value} value={tz.value}>
                      {tz.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
              >
                {submitting ? "Настраиваем..." : "Начать работу"}
              </button>
            </form>
          </>
        )}

        {!isLoading && !isError && anyEmployees === true && (
          <>
            <h2 className="text-xl font-semibold text-center">
              Ваш профиль ещё не настроен
            </h2>
            <p className="text-sm text-muted-foreground text-center">
              Обратитесь к своему менеджеру — он выдаст вам код приглашения,
              либо уже добавит вас в систему.
            </p>
            <form onSubmit={handleClaim} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="invite_code" className="text-sm font-medium">
                  Код приглашения
                </label>
                <input
                  id="invite_code"
                  type="text"
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm uppercase tracking-widest outline-none focus:ring-2 focus:ring-ring"
                  placeholder="ABCD1234"
                  maxLength={8}
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={submitting || !inviteCode.trim()}
                  className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition hover:opacity-90 disabled:opacity-50"
                >
                  {submitting ? "Проверяем..." : "Привязать профиль"}
                </button>
              </div>
            </form>

            <div className="flex items-center gap-3">
              <div className="h-px flex-1 bg-border" />
              <span className="text-xs text-muted-foreground">или</span>
              <div className="h-px flex-1 bg-border" />
            </div>

            <button
              type="button"
              onClick={handleRecheck}
              disabled={submitting}
              className="w-full rounded-lg border bg-background px-4 py-2 text-sm font-semibold transition hover:bg-accent disabled:opacity-50"
            >
              Проверить снова
            </button>

            <button
              type="button"
              onClick={handleSignOut}
              className="w-full text-center text-xs text-muted-foreground hover:text-foreground"
            >
              Выйти из аккаунта
            </button>
          </>
        )}
      </div>
    </div>
  );
}
