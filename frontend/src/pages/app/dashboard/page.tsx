import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { listBranches } from "@/api/branches.ts";
import { getMyProfile, listEmployees } from "@/api/employees.ts";
import { listChecklists } from "@/api/checklists.ts";
import { listIssues } from "@/api/issues.ts";
import { listNotifications, markNotificationRead } from "@/api/notifications.ts";
import {
  Building2,
  Users,
  ClipboardList,
  AlertTriangle,
  Bell,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils.ts";

function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

const NOTIFICATION_LABELS: Record<string, string> = {
  reminder: "Напоминание",
  overdue: "Просрочка",
  escalation: "Эскалация",
  issue_assigned: "Назначена проблема",
};

function StatCard({
  icon,
  label,
  value,
  sub,
  color,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  onClick?: () => void;
}) {
  const Comp = onClick ? "button" : "div";
  return (
    <Comp
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={cn(
        "rounded-xl border bg-card p-5 shadow-sm text-left",
        onClick && "cursor-pointer transition-shadow hover:shadow-md",
      )}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", color)}>
          {icon}
        </div>
        <span className="font-semibold text-base">{label}</span>
      </div>
      <p className="text-3xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Comp>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const today = todayDate();

  const { data: profile } = useQuery({ queryKey: ["my-profile"], queryFn: getMyProfile });
  const { data: branches, isLoading: branchesLoading } = useQuery({
    queryKey: ["branches"],
    queryFn: listBranches,
  });
  const { data: employees, isLoading: employeesLoading } = useQuery({
    queryKey: ["employees"],
    queryFn: () => listEmployees(),
  });
  const { data: todayChecklists, isLoading: checklistsLoading } = useQuery({
    queryKey: ["checklists", today],
    queryFn: () => listChecklists({ date: today }),
  });
  const { data: openIssues, isLoading: issuesLoading } = useQuery({
    queryKey: ["issues", "open"],
    queryFn: () => listIssues({ status: "open" }),
  });
  const { data: notifications } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => listNotifications(true),
  });

  const markReadMut = useMutation({
    mutationFn: (id: number) => markNotificationRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const loading = branchesLoading || employeesLoading;

  const totalItems = todayChecklists?.reduce((sum, c) => sum + c.total_items, 0) ?? 0;
  const completedItems = todayChecklists?.reduce((sum, c) => sum + c.completed_items, 0) ?? 0;
  const completionPct = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;
  const completedChecklists = todayChecklists?.filter((c) => c.status === "completed").length ?? 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          {profile ? `Здравствуйте, ${profile.full_name.split(" ")[0]}` : "Дашборд"}
        </h1>
        <p className="text-sm text-muted-foreground">Обзор системы MADO Checklist · {today}</p>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 w-full animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={<Building2 className="size-5" />}
            color="bg-primary/10 text-primary"
            label="Филиалы"
            value={branches?.length ?? 0}
          />
          <StatCard
            icon={<Users className="size-5" />}
            color="bg-primary/10 text-primary"
            label="Сотрудники"
            value={employees?.length ?? 0}
          />
          <StatCard
            icon={<ClipboardList className="size-5 text-blue-600" />}
            color="bg-blue-100 dark:bg-blue-900/30"
            label="Чек-листы сегодня"
            value={checklistsLoading ? "…" : `${completionPct}%`}
            sub={
              checklistsLoading
                ? undefined
                : todayChecklists && todayChecklists.length > 0
                ? `Завершено ${completedChecklists} из ${todayChecklists.length}`
                : "Нет чек-листов на сегодня"
            }
            onClick={() => navigate("/app/checklists")}
          />
          <StatCard
            icon={<AlertTriangle className="size-5 text-destructive" />}
            color="bg-destructive/10"
            label="Открытые проблемы"
            value={issuesLoading ? "…" : openIssues?.length ?? 0}
            sub="Требуют внимания"
            onClick={() => navigate("/app/issues")}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Open issues preview */}
        <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <AlertTriangle className="size-4 text-destructive" />
              Проблемы, требующие внимания
            </h2>
            <button
              type="button"
              onClick={() => navigate("/app/issues")}
              className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Все проблемы <ArrowRight className="size-3" />
            </button>
          </div>
          {issuesLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
              ))}
            </div>
          ) : !openIssues || openIssues.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <CheckCircle2 className="size-8 text-green-600" />
              <p className="text-sm text-muted-foreground">Открытых проблем нет</p>
            </div>
          ) : (
            <div className="space-y-2">
              {openIssues.slice(0, 5).map((issue) => (
                <button
                  key={issue.id}
                  type="button"
                  onClick={() => navigate("/app/issues")}
                  className="flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg border px-3 py-2.5 text-left hover:bg-muted/50 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate">{issue.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{issue.branch_name}</p>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 rounded-full px-2 py-0.5 text-xs font-medium",
                      issue.priority === "critical"
                        ? "bg-destructive/15 text-destructive"
                        : "bg-secondary text-secondary-foreground",
                    )}
                  >
                    {issue.priority}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Notifications preview */}
        <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold flex items-center gap-2">
              <Bell className="size-4 text-primary" />
              Уведомления
            </h2>
            {notifications && notifications.length > 0 && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                {notifications.length} новых
              </span>
            )}
          </div>
          {!notifications || notifications.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-8 text-center">
              <Bell className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Нет новых уведомлений</p>
            </div>
          ) : (
            <div className="space-y-2">
              {notifications.slice(0, 5).map((n) => (
                <div
                  key={n.id}
                  className="flex items-start justify-between gap-2 rounded-lg border px-3 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-primary">{NOTIFICATION_LABELS[n.type] ?? n.type}</p>
                    <p className="text-sm font-medium truncate">{n.title}</p>
                    {n.message && <p className="text-xs text-muted-foreground truncate">{n.message}</p>}
                    <p className="mt-0.5 text-xs text-muted-foreground">{fmtTime(n.created_at)}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => markReadMut.mutate(n.id)}
                    disabled={markReadMut.isPending}
                    className="shrink-0 rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                    title="Отметить прочитанным"
                  >
                    <CheckCircle2 className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
