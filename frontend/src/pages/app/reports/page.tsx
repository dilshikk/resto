import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { getSummary, getByDay, getBranchesRanking, getViolations, buildExportUrl } from "@/api/analytics.ts";
import { listBranches } from "@/api/branches.ts";
import {
  Download, TrendingUp, CheckSquare, AlertTriangle, ClipboardList,
  Clock, CheckCircle2, XCircle, Timer,
} from "lucide-react";
import { cn } from "@/lib/utils.ts";

// ── date helpers ───────────────────────────────────────────────────────────

const PRESETS = [
  { label: "7 дней", days: 7 },
  { label: "30 дней", days: 30 },
  { label: "90 дней", days: 90 },
];

function daysAgo(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - (n - 1));
  return d.toISOString().slice(0, 10);
}
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ── stat card ─────────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm space-y-3">
      <div className="flex items-center gap-3">
        <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", color)}>
          {icon}
        </div>
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
      </div>
      <p className="text-3xl font-bold">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

// ── custom tooltip ──────────────────────────────────────────────────────────

function DayTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border bg-card px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{label}</p>
      <p className="text-muted-foreground">Выполнение: <span className="text-foreground font-semibold">{payload[0]?.value}%</span></p>
    </div>
  );
}

// ── deadline status row ─────────────────────────────────────────────────────

function DeadlineStatsRow({
  onTime,
  overdue,
  notCompleted,
  onTimePct,
  avgMin,
}: {
  onTime: number;
  overdue: number;
  notCompleted: number;
  onTimePct: number | null;
  avgMin: number | null;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="size-4 text-green-500" />
          <span>В срок</span>
        </div>
        <p className="text-2xl font-bold text-green-600 dark:text-green-400">{onTime}</p>
      </div>
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="size-4 text-destructive" />
          <span>Просрочено</span>
        </div>
        <p className="text-2xl font-bold text-destructive">{overdue}</p>
      </div>
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <XCircle className="size-4 text-zinc-400" />
          <span>Не выполнено</span>
        </div>
        <p className="text-2xl font-bold text-zinc-500 dark:text-zinc-400">{notCompleted}</p>
      </div>
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <TrendingUp className="size-4 text-blue-500" />
          <span>% в срок</span>
        </div>
        <p className="text-2xl font-bold">
          {onTimePct !== null ? `${onTimePct}%` : <span className="text-muted-foreground text-base">—</span>}
        </p>
      </div>
      <div className="rounded-xl border bg-card p-4 shadow-sm space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Timer className="size-4 text-amber-500" />
          <span>Среднее время</span>
        </div>
        <p className="text-2xl font-bold">
          {avgMin !== null
            ? avgMin >= 60
              ? `${Math.floor(avgMin / 60)}ч ${Math.round(avgMin % 60)}м`
              : `${avgMin}м`
            : <span className="text-muted-foreground text-base">—</span>}
        </p>
      </div>
    </div>
  );
}

// ── page ────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [preset, setPreset] = useState(30);
  const [branchId, setBranchId] = useState<number | undefined>(undefined);

  const dateFrom = useMemo(() => daysAgo(preset), [preset]);
  const dateTo = useMemo(() => todayStr(), []);
  const params = useMemo(
    () => ({ date_from: dateFrom, date_to: dateTo, branch_id: branchId }),
    [dateFrom, dateTo, branchId],
  );

  const { data: branches } = useQuery({ queryKey: ["branches"], queryFn: listBranches });
  const { data: summary, isLoading: sumLoading } = useQuery({
    queryKey: ["analytics-summary", params],
    queryFn: () => getSummary(params),
  });
  const { data: byDay, isLoading: dayLoading } = useQuery({
    queryKey: ["analytics-day", params],
    queryFn: () => getByDay(params),
  });
  const { data: branchRanking } = useQuery({
    queryKey: ["analytics-branches", { date_from: dateFrom, date_to: dateTo }],
    queryFn: () => getBranchesRanking({ date_from: dateFrom, date_to: dateTo }),
  });
  const { data: violations } = useQuery({
    queryKey: ["analytics-violations", params],
    queryFn: () => getViolations({ ...params, limit: 10 }),
  });

  const chartData = useMemo(() => {
    if (!byDay) return [];
    const step = byDay.length > 30 ? 3 : 1;
    return byDay.map((d, i) => ({
      ...d,
      label: i % step === 0 ? d.date.slice(5) : "",
    }));
  }, [byDay]);

  const exportUrl = buildExportUrl(params);
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : "";

  const handleExport = async () => {
    const res = await fetch(exportUrl, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `mado_report_${dateFrom}_${dateTo}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-4 md:p-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Аналитика</h1>
          <p className="text-sm text-muted-foreground">Выполняемость стандартов и нарушения</p>
        </div>
        <button
          type="button"
          onClick={handleExport}
          className="flex items-center gap-2 rounded-lg border bg-card px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
        >
          <Download className="size-4" />Экспорт CSV
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border overflow-hidden">
          {PRESETS.map((p) => (
            <button
              key={p.days}
              type="button"
              onClick={() => setPreset(p.days)}
              className={cn(
                "px-4 py-2 text-sm font-medium transition-colors",
                preset === p.days
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted text-foreground",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <select
          className="rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={branchId ?? ""}
          onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : undefined)}
        >
          <option value="">Все филиалы</option>
          {branches?.map((b) => (
            <option key={b.id} value={b.id}>{b.name}</option>
          ))}
        </select>
      </div>

      {/* Summary cards */}
      {sumLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl border bg-muted" />
          ))}
        </div>
      ) : summary && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            icon={<ClipboardList className="size-5 text-primary" />}
            color="bg-primary/10"
            label="Чек-листов всего"
            value={summary.total_checklists}
            sub={`Завершено: ${summary.completed_checklists}`}
          />
          <StatCard
            icon={<TrendingUp className="size-5 text-blue-600" />}
            color="bg-blue-100 dark:bg-blue-900/30"
            label="Выполнение чек-листов"
            value={`${summary.checklist_completion_pct}%`}
          />
          <StatCard
            icon={<CheckSquare className="size-5 text-green-600" />}
            color="bg-green-100 dark:bg-green-900/30"
            label="Выполнение пунктов"
            value={`${summary.item_completion_pct}%`}
            sub={`${summary.completed_items} из ${summary.total_items}`}
          />
          <StatCard
            icon={<AlertTriangle className="size-5 text-destructive" />}
            color="bg-destructive/10"
            label="Пропущено обязательных"
            value={summary.missed_required_items}
            sub="невыполненных пунктов"
          />
        </div>
      )}

      {/* Deadline KPI row */}
      {summary && (summary.deadline.on_time > 0 || summary.deadline.overdue > 0 || summary.deadline.not_completed > 0) && (
        <div className="space-y-3">
          <h2 className="font-semibold flex items-center gap-2 text-sm text-muted-foreground uppercase tracking-wide">
            <Clock className="size-4" />
            Контроль сроков
          </h2>
          <DeadlineStatsRow
            onTime={summary.deadline.on_time}
            overdue={summary.deadline.overdue}
            notCompleted={summary.deadline.not_completed}
            onTimePct={summary.deadline.on_time_pct}
            avgMin={summary.deadline.avg_completion_minutes}
          />
        </div>
      )}

      {/* Daily chart */}
      <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
        <h2 className="font-semibold">Выполняемость по дням, %</h2>
        {dayLoading ? (
          <div className="h-52 animate-pulse rounded-lg bg-muted" />
        ) : chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -28, bottom: 0 }}>
              <defs>
                <linearGradient id="pctGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-primary)" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="var(--color-primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
              />
              <Tooltip content={<DayTooltip />} />
              <Area
                type="monotone"
                dataKey="pct"
                stroke="var(--color-primary)"
                strokeWidth={2}
                fill="url(#pctGrad)"
                dot={false}
                activeDot={{ r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <p className="py-12 text-center text-sm text-muted-foreground">Данных нет</p>
        )}
      </div>

      {/* Branch ranking + violations */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Branch ranking */}
        <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
          <h2 className="font-semibold">Рейтинг филиалов</h2>
          {!branchRanking || branchRanking.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Данных нет</p>
          ) : (
            <div className="space-y-3">
              {branchRanking.map((b, i) => (
                <div key={b.branch_id} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={cn(
                          "shrink-0 size-6 rounded-full text-xs font-bold flex items-center justify-center",
                          i === 0
                            ? "bg-yellow-400 text-yellow-900"
                            : i === 1
                            ? "bg-slate-300 text-slate-700"
                            : i === 2
                            ? "bg-amber-600 text-white"
                            : "bg-muted text-muted-foreground",
                        )}
                      >
                        {i + 1}
                      </span>
                      <span className="text-sm font-medium truncate">{b.branch_name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {b.overdue > 0 && (
                        <span className="text-xs text-destructive font-medium">{b.overdue} просроч.</span>
                      )}
                      <span className="text-sm font-semibold">{b.pct}%</span>
                    </div>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all",
                        b.pct >= 80 ? "bg-green-500" : b.pct >= 50 ? "bg-yellow-500" : "bg-destructive",
                      )}
                      style={{ width: `${b.pct}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Завершено {b.completed} из {b.total}
                    {b.on_time > 0 && ` · В срок: ${b.on_time}`}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top violations */}
        <div className="rounded-xl border bg-card p-5 shadow-sm space-y-4">
          <h2 className="font-semibold">Топ нарушений</h2>
          <p className="text-xs text-muted-foreground -mt-2">
            Обязательные пункты, не выполненные чаще всего
          </p>
          {!violations || violations.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Нарушений нет — отлично!</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(violations.length * 36, 120)}>
              <BarChart
                layout="vertical"
                data={violations}
                margin={{ top: 0, right: 0, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="title"
                  width={140}
                  tick={{ fontSize: 11, fill: "var(--color-foreground)" }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 20) + "…" : v}
                />
                <Tooltip
                  formatter={(v: number) => [`${v} раз`, "Пропущено"]}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid var(--color-border)",
                    background: "var(--color-card)",
                  }}
                />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={24}>
                  {violations.map((_, i) => (
                    <Cell
                      key={i}
                      fill={i < 3 ? "var(--color-destructive)" : "var(--color-primary)"}
                      fillOpacity={1 - i * 0.06}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
