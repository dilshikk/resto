import { Input } from "@/components/ui/input.tsx";
import { Button } from "@/components/ui/button.tsx";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.tsx";
import { Calendar, RefreshCw } from "lucide-react";
import type { AttendanceEmployee } from "@/api/attendance.ts";
import type { ReportPeriod } from "../utils.ts";

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
      <div className="flex gap-1 rounded-lg bg-muted p-1">
        {(["day", "week", "month"] as ReportPeriod[]).map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPeriod(p)}
            className={`cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              period === p
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p === "day" ? "День" : p === "week" ? "Неделя" : "Месяц"}
          </button>
        ))}
      </div>

      {/* Date range */}
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFrom(e.target.value)}
          className="h-9 w-36"
        />
        <span className="text-sm text-muted-foreground">—</span>
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => onDateTo(e.target.value)}
          className="h-9 w-36"
        />
      </div>

      {/* Employee filter */}
      <Select
        value={employeeId || "all"}
        onValueChange={(v) => onEmployee(v === "all" ? "" : v)}
      >
        <SelectTrigger className="h-9 w-48">
          <SelectValue placeholder="Все сотрудники" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Все сотрудники</SelectItem>
          {employees.map((e) => (
            <SelectItem key={e.employee_id} value={e.employee_id}>
              {[e.first_name, e.last_name].filter(Boolean).join(" ") || e.employee_id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Button
        variant="secondary"
        size="sm"
        onClick={onRefresh}
        disabled={loading}
        className="h-9"
      >
        <RefreshCw className={`mr-1.5 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        Обновить
      </Button>
    </div>
  );
}
