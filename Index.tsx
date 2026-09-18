import { Navigate } from "react-router-dom";
import { useState } from "react";
import { Authenticated, AuthLoading, Unauthenticated, useMutation, useQuery } from "convex/react";
import { api } from "@/convex/_generated/api.js";
import { SignInButton } from "@/components/ui/signin.tsx";
import { Skeleton } from "@/components/ui/skeleton.tsx";
import { Button } from "@/components/ui/button.tsx";
import { Input } from "@/components/ui/input.tsx";
import { Label } from "@/components/ui/label.tsx";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card.tsx";
import { toast } from "sonner";
import { ConvexError } from "convex/values";
import { ChefHat, ClipboardCheck } from "lucide-react";

function errorMessage(err: unknown, fallback: string) {
  if (err instanceof ConvexError) {
    const data = err.data as { message?: string };
    return data.message ?? fallback;
  }
  return fallback;
}

function BootstrapForm() {
  const bootstrap = useMutation(api.employees.bootstrapDirector);
  const [fullName, setFullName] = useState("");
  const [branchName, setBranchName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await bootstrap({
        fullName,
        branchName,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось настроить систему"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="fullName">Ваше ФИО</Label>
        <Input
          id="fullName"
          placeholder="Иван Иванов"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="branchName">Название первого филиала</Label>
        <Input
          id="branchName"
          placeholder="Tashkent City Mall"
          value={branchName}
          onChange={(e) => setBranchName(e.target.value)}
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Настраиваем..." : "Стать директором и начать"}
      </Button>
    </form>
  );
}

function ClaimInviteForm() {
  const claim = useMutation(api.employees.claimEmployeeProfile);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await claim({ inviteCode: code });
    } catch (err) {
      toast.error(errorMessage(err, "Не удалось привязать профиль"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="code">Код приглашения</Label>
        <Input
          id="code"
          placeholder="ABCD1234"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          className="uppercase tracking-widest"
          maxLength={8}
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={submitting}>
        {submitting ? "Проверяем..." : "Привязать профиль"}
      </Button>
    </form>
  );
}

function OnboardingCard() {
  const hasAnyEmployees = useQuery(api.employees.hasAnyEmployees, {});

  if (hasAnyEmployees === undefined) {
    return <Skeleton className="h-64 w-full max-w-md" />;
  }

  return (
    <Card className="w-full max-w-md">
      <CardHeader className="text-center">
        <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
          <ChefHat className="size-6" />
        </div>
        <CardTitle className="text-xl">Добро пожаловать в MADO Checklist</CardTitle>
        <CardDescription>
          {hasAnyEmployees
            ? "Введите код приглашения, который вам выдал менеджер"
            : "Вы первый пользователь. Настройте систему и станьте директором."}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {hasAnyEmployees ? <ClaimInviteForm /> : <BootstrapForm />}
      </CardContent>
    </Card>
  );
}

function WelcomeScreen() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
          <ClipboardCheck className="size-8" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">MADO Checklist</h1>
        <p className="max-w-sm text-muted-foreground">
          Контроль выполнения операционных чек-листов персоналом ресторанов MADO
        </p>
      </div>
      <SignInButton size="lg" signInText="Войти" />
    </div>
  );
}

function AuthenticatedHome() {
  const profile = useQuery(api.employees.getMyEmployeeProfile, {});

  if (profile === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Skeleton className="h-64 w-full max-w-md" />
      </div>
    );
  }

  if (profile) {
    return <Navigate to="/app" replace />;
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 bg-background px-4 py-12">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex size-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
          <ChefHat className="size-7" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Почти готово</h1>
      </div>
      <OnboardingCard />
    </div>
  );
}

export default function Index() {
  return (
    <>
      <AuthLoading>
        <div className="flex min-h-screen items-center justify-center bg-background">
          <Skeleton className="h-12 w-48" />
        </div>
      </AuthLoading>
      <Unauthenticated>
        <WelcomeScreen />
      </Unauthenticated>
      <Authenticated>
        <AuthenticatedHome />
      </Authenticated>
    </>
  );
}
