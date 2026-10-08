import { Calendar, RefreshCw } from "lucide-react";
import type { AttendanceEmployee } from "@/api/attendance.ts";
import type { ReportPeriod } from "../utils.ts";
import { cn } from "@/lib/utils.ts";

type Props = {
  dateFrom: string;
  dateTo: string;
  employeeId: string;
  period: ReportPeriod;
  employees: AttendanceEmployee[];
  loading: boolean;
  onDateFrom: (v: string) => void;
  onDateTo: (v: string) => void;
  onEmployee: (v: string) => void;
  onPeriod: (v: ReportPeriod) => void;
  onRefresh: () => void;
};

export default function FiltersBar({
  dateFrom,
  dateTo,
  employeeId,
  period,
  employees,
  loading,
  onDateFrom,
  onDateTo,
  onEmployee,
  onPeriod,
  onRefresh,
}: Props) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      {/* Period quick select */}
      <div className="flex gap-1 rounded-lg bg-secondary p-1">
        {(["day", "week", "month"] as ReportPeriod[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPeriod(p)}
            className={cn(
              "cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              period === p
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {p === "day" ? "День" : p === "week" ? "Неделя" : "Месяц"}
          </button>
        ))}
      </div>

      {/* Date range */}
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <input
          type="date"
          value={dateFrom}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => onDateFrom(e.target.value)}
          className="h-9 w-36 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <span className="text-sm text-muted-foreground">—</span>
        <input
          type="date"
          value={dateTo}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => onDateTo(e.target.value)}
          className="h-9 w-36 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
      </div>

      {/* Employee filter */}
      <select
        value={employeeId || "all"}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
          onEmployee(e.target.value === "all" ? "" : e.target.value)
        }
        className="h-9 w-52 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="all">Все сотрудники</option>
        {employees.map((emp) => (
          <option key={emp.employee_id} value={emp.employee_id}>
            {[emp.first_name, emp.last_name].filter(Boolean).join(" ") || emp.employee_id}
          </option>
        ))}
      </select>

      <button
        type="button"
        onClick={onRefresh}
        disabled={loading}
        className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border bg-secondary px-4 text-sm font-medium transition-colors hover:bg-secondary/80 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
        Обновить
      </button>
    </div>
  );
}
