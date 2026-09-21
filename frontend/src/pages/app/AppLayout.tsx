import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getMyProfile } from "@/api/employees.ts";
import { useAuth } from "@/context/auth-context.tsx";
import { cn } from "@/lib/utils.ts";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Building2,
  Users,
  ClipboardList,
  AlertTriangle,
  BarChart3,
  ChefHat,
  LogOut,
  CalendarDays,
  BookOpen,
  Camera,
} from "lucide-react";

const NAV_ITEMS = [
  { to: "/app", label: "Дашборд", icon: LayoutDashboard, minLevel: 1 },
  { to: "/app/checklists", label: "Чек-листы", icon: ClipboardList, minLevel: 0 },
  { to: "/app/issues", label: "Проблемы", icon: AlertTriangle, minLevel: 1 },
  { to: "/app/photos", label: "Фотоотчёты", icon: Camera, minLevel: 0 },
  { to: "/app/employees", label: "Сотрудники", icon: Users, minLevel: 1 },
  { to: "/app/shifts", label: "Смены", icon: CalendarDays, minLevel: 1 },
  { to: "/app/branches", label: "Филиалы", icon: Building2, minLevel: 2 },
  { to: "/app/templates", label: "Шаблоны", icon: ClipboardList, minLevel: 1 },
  { to: "/app/standards", label: "Стандарты", icon: BookOpen, minLevel: 2 },
  { to: "/app/reports", label: "Аналитика", icon: BarChart3, minLevel: 1 },
];

function NavLink({
  to,
  label,
  icon: Icon,
  active,
  onNavigate,
}: {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  active: boolean;
  onNavigate: (to: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onNavigate(to)}
      className={cn(
        "flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-sidebar-primary text-sidebar-primary-foreground"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {label}
    </button>
  );
}

function SidebarContent({ onNavigate }: { onNavigate: (to: string) => void }) {
  const location = useLocation();
  const { logout } = useAuth();
  const { data: profile } = useQuery({
    queryKey: ["my-profile"],
    queryFn: getMyProfile,
  });

  const visibleItems = NAV_ITEMS.filter(
    (item) => (profile?.role_level ?? 0) >= item.minLevel,
  );

  const handleSignOut = async () => {
    try {
      await logout();
    } catch {
      toast.error("Не удалось выйти");
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center gap-2 px-2">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
          <ChefHat className="size-5" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-sidebar-foreground">MADO Checklist</p>
          {profile && (
            <p className="truncate text-xs text-sidebar-foreground/60">
              {profile.role_name} · {profile.primary_branch_name}
            </p>
          )}
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            label={item.label}
            icon={item.icon}
            active={
              item.to === "/app"
                ? location.pathname === "/app"
                : location.pathname.startsWith(item.to)
            }
            onNavigate={onNavigate}
          />
        ))}
      </nav>

      <button
        type="button"
        onClick={handleSignOut}
        className="flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
      >
        <LogOut className="size-4 shrink-0" />
        Выйти
      </button>
    </div>
  );
}

function AppShell({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar md:block">
        <SidebarContent onNavigate={(to) => navigate(to)} />
      </aside>

      <div className="flex flex-1 flex-col">
        <main className="flex-1 overflow-auto pb-20 md:pb-0">{children}</main>
      </div>

      <nav className="fixed bottom-0 left-0 right-0 z-40 flex justify-around border-t border-sidebar-border bg-sidebar px-1 py-1 md:hidden">
        {NAV_ITEMS.slice(0, 5).map((item) => {
          const Icon = item.icon;
          const active =
            item.to === "/app"
              ? location.pathname === "/app"
              : location.pathname.startsWith(item.to);
          return (
            <button
              key={item.to}
              type="button"
              onClick={() => navigate(item.to)}
              className={cn(
                "flex flex-1 cursor-pointer flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] font-medium",
                active ? "text-sidebar-primary" : "text-sidebar-foreground/60",
              )}
            >
              <Icon className="size-5" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

export default function AppLayout() {
  const { isAuthenticated } = useAuth();
  const { data: profile, isLoading } = useQuery({
    queryKey: ["my-profile"],
    queryFn: getMyProfile,
    enabled: isAuthenticated,
    retry: 1,
  });

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }

  if (!profile) return <Navigate to="/onboarding" replace />;

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}
