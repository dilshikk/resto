import type { EmployeeDay } from "../utils.ts";
import { Users, Clock, AlertTriangle, UserX } from "lucide-react";
import { cn } from "@/lib/utils.ts";

type Props = {
  rows: EmployeeDay[];
  totalEmployees: number;
};

export default function StatsCards({ rows, totalEmployees }: Props) {
  const present = rows.filter((r) => !r.absent).length;
  const absent = Math.max(0, totalEmployees - present);
  const late = rows.filter((r) => r.is_late).length;
  const leftEarly = rows.filter((r) => r.left_early).length;

  const stats = [
    {
      label: "Присутствуют",
      value: present,
      Icon: Users,
      color: "text-emerald-600",
      bg: "bg-emerald-100 dark:bg-emerald-900/30",
    },
    {
      label: "Отсутствуют",
      value: absent,
      Icon: UserX,
      color: "text-destructive",
      bg: "bg-destructive/10",
    },
    {
      label: "Опоздания",
      value: late,
      Icon: AlertTriangle,
      color: "text-amber-600",
      bg: "bg-amber-100 dark:bg-amber-900/30",
    },
    {
      label: "Ранний уход",
      value: leftEarly,
      Icon: Clock,
      color: "text-blue-600",
      bg: "bg-blue-100 dark:bg-blue-900/30",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      {stats.map((s) => (
        <div key={s.label} className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-3 flex items-center gap-3">
            <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", s.bg)}>
              <s.Icon className={cn("size-5", s.color)} />
            </div>
          </div>
          <p className="text-3xl font-bold">{s.value}</p>
          <p className="mt-1 text-xs text-muted-foreground">{s.label}</p>
        </div>
      ))}
    </div>
  );
}
