import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAttendanceLogs, fetchAttendanceEmployees } from "@/api/attendance.ts";
import {
  groupLogsByEmployeeDay,
  todayStr,
  weekAgoStr,
  formatMinutes,
  formatMoney,
  type EmployeeDay,
  type ReportPeriod,
} from "./utils.ts";
import FiltersBar from "./_components/FiltersBar.tsx";
import StatsCards from "./_components/StatsCards.tsx";
import AttendanceTable from "./_components/AttendanceTable.tsx";
import RatesDialog from "./_components/RatesDialog.tsx";
import { Download } from "lucide-react";
import * as XLSX from "xlsx";

export default function AttendancePage() {
  const [period, setPeriod] = useState<ReportPeriod>("day");
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [employeeId, setEmployeeId] = useState("");
  const [rows, setRows] = useState<EmployeeDay[]>([]);
  const [loading, setLoading] = useState(false);

  const { data: employees = [] } = useQuery({
    queryKey: ["attendance-employees"],
    queryFn: fetchAttendanceEmployees,
  });

  const applyPeriod = (p: ReportPeriod) => {
    setPeriod(p);
    const today = todayStr();
    if (p === "day") {
      setDateFrom(today);
      setDateTo(today);
    } else if (p === "week") {
      setDateFrom(weekAgoStr());
      setDateTo(today);
    } else {
      const d = new Date();
      const first = new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
      setDateFrom(first);
      setDateTo(today);
    }
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const logs = await fetchAttendanceLogs({
        date_from: dateFrom,
        date_to: dateTo,
        employee_id: employeeId || undefined,
      });
      setRows(groupLogsByEmployeeDay(logs));
    } catch {
      toast.error("Не удалось загрузить данные посещаемости");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, employeeId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Итоговая сумма зарплаты за период
  const totalSalary = rows.reduce((sum, r) => sum + (r.rate_per_shift ?? 0), 0);
  const hasSalary = rows.some((r) => r.rate_per_shift != null && r.rate_per_shift > 0);
  // Валюта — берём из первой строки с ненулевой ставкой
  const salCurrency = rows.find((r) => r.rate_per_shift != null)?.currency ?? "UZS";

  const exportExcel = () => {
    const data = rows.map((r) => ({
      Сотрудник: r.full_name,
      Дата: r.date,
      Приход: r.first_in ?? "—",
      Уход: r.last_out ?? "—",
      Отработано: r.worked_minutes != null ? formatMinutes(r.worked_minutes) : "—",
      "Ставка за смену": r.rate_per_shift != null ? r.rate_per_shift : "—",
      Валюта: r.currency,
      Устройство: r.device_name ?? "—",
      Опоздание: r.is_late ? "Да" : "Нет",
      "Ранний уход": r.left_early ? "Да" : "Нет",
      Отсутствие: r.absent ? "Да" : "Нет",
    }));
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Посещаемость");
    XLSX.writeFile(wb, `attendance_${dateFrom}_${dateTo}.xlsx`);
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Посещаемость (FaceID)</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Учёт посещаемости сотрудников на основе Face ID
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <RatesDialog />
          <button
            type="button"
            onClick={exportExcel}
            disabled={rows.length === 0}
            className="flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Download className="h-4 w-4" />
            Экспорт Excel
          </button>
        </div>
      </div>

      {/* Filters */}
      <FiltersBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        employeeId={employeeId}
        period={period}
        employees={employees}
        loading={loading}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        onEmployee={setEmployeeId}
        onPeriod={applyPeriod}
        onRefresh={() => void loadData()}
      />

      {/* Stats */}
      <StatsCards rows={rows} totalEmployees={employees.length || rows.length} />

      {/* Итог зарплаты */}
      {hasSalary && (
        <div className="rounded-xl border bg-card px-6 py-4 shadow-sm">
          <p className="text-sm text-muted-foreground">Итого зарплата за период</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">
            {formatMoney(totalSalary, salCurrency)}
          </p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {rows.filter((r) => r.rate_per_shift != null && r.rate_per_shift > 0).length} смен(ы) с заданной ставкой
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent opacity-60" />
        </div>
      )}

      {/* Table */}
      {!loading && <AttendanceTable rows={rows} />}
    </div>
  );
}
