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
import type { ReportPeriod } from "../_lib/types.ts";

type Employee = { employee_id: string; first_name: string; last_name: string };

type Props = {
  dateFrom: string;
  dateTo: string;
  employeeId: string;
  period: ReportPeriod;
  employees: Employee[];
  loading: boolean;
  onDateFrom: (v: string) => void;
  onDateTo: (v: string) => void;
  onEmployee: (v: string) => void;
  onPeriod: (v: ReportPeriod) => void;
  onRefresh: () => void;
};

export default function FiltersBar({
  dateFrom, dateTo, employeeId, period, employees,
  loading, onDateFrom, onDateTo, onEmployee, onPeriod, onRefresh,
}: Props) {
  return (
    <div className="flex flex-wrap gap-3 items-end">
      {/* Period quick select */}
      <div className="flex gap-1 bg-muted rounded-lg p-1">
        {(["day", "week", "month"] as ReportPeriod[]).map((p) => (
          <button
            key={p}
            onClick={() => onPeriod(p)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors cursor-pointer ${
              period === p
                ? "bg-background shadow-sm text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p === "day" ? "День" : p === "week" ? "Неделя" : "Месяц"}
          </button>
        ))}
      </div>

      {/* Date range */}
      <div className="flex items-center gap-2">
        <Calendar className="w-4 h-4 text-muted-foreground" />
        <Input
          type="date"
          value={dateFrom}
          onChange={(e) => onDateFrom(e.target.value)}
          className="w-36 h-9"
        />
        <span className="text-muted-foreground text-sm">—</span>
        <Input
          type="date"
          value={dateTo}
          onChange={(e) => onDateTo(e.target.value)}
          className="w-36 h-9"
        />
      </div>

      {/* Employee filter */}
      <Select value={employeeId || "all"} onValueChange={(v) => onEmployee(v === "all" ? "" : v)}>
        <SelectTrigger className="w-48 h-9">
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

      <Button variant="secondary" size="sm" onClick={onRefresh} disabled={loading} className="h-9">
        <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? "animate-spin" : ""}`} />
        Обновить
      </Button>
    </div>
  );
}
