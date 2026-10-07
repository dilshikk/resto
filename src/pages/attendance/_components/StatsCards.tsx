import type { EmployeeDay } from "../_lib/types.ts";
import { Card, CardContent } from "@/components/ui/card.tsx";
import { Users, Clock, AlertTriangle, UserX } from "lucide-react";

type Props = {
  rows: EmployeeDay[];
  totalEmployees: number;
};

export default function StatsCards({ rows, totalEmployees }: Props) {
  const present = rows.filter((r) => !r.absent).length;
  const absent = totalEmployees - present;
  const late = rows.filter((r) => r.is_late).length;
  const leftEarly = rows.filter((r) => r.left_early).length;

  const stats = [
    {
      label: "Присутствуют",
      value: present,
      icon: Users,
      color: "text-emerald-500",
      bg: "bg-emerald-50 dark:bg-emerald-950/30",
    },
    {
      label: "Отсутствуют",
      value: absent < 0 ? 0 : absent,
      icon: UserX,
      color: "text-rose-500",
      bg: "bg-rose-50 dark:bg-rose-950/30",
    },
    {
      label: "Опоздания",
      value: late,
      icon: AlertTriangle,
      color: "text-amber-500",
      bg: "bg-amber-50 dark:bg-amber-950/30",
    },
    {
      label: "Ранний уход",
      value: leftEarly,
      icon: Clock,
      color: "text-blue-500",
      bg: "bg-blue-50 dark:bg-blue-950/30",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((s) => (
        <Card key={s.label} className="border-0 shadow-sm">
          <CardContent className="flex items-center gap-3 py-4">
            <div className={`rounded-xl p-2.5 ${s.bg}`}>
              <s.icon className={`w-5 h-5 ${s.color}`} />
            </div>
            <div>
              <p className="text-2xl font-bold leading-none">{s.value}</p>
              <p className="text-xs text-muted-foreground mt-1">{s.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
