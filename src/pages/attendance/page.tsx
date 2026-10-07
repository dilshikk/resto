import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { fetchLogs, fetchEmployees } from "./_lib/api.ts";
import type { EmployeeDay, ReportPeriod } from "./_lib/types.ts";
import {
  groupLogsByEmployeeDay,
  todayStr,
  weekAgoStr,
} from "./_lib/utils.ts";
import FiltersBar from "./_components/FiltersBar.tsx";
import StatsCards from "./_components/StatsCards.tsx";
import AttendanceTable from "./_components/AttendanceTable.tsx";
import { Button } from "@/components/ui/button.tsx";
import { Download } from "lucide-react";
import * as XLSX from "xlsx";

type Employee = { employee_id: string; first_name: string; last_name: string };

export default function AttendancePage() {
  const [period, setPeriod] = useState<ReportPeriod>("day");
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [employeeId, setEmployeeId] = useState("");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [rows, setRows] = useState<EmployeeDay[]>([]);
  const [loading, setLoading] = useState(false);

  // Load employee list once
  useEffect(() => {
    fetchEmployees()
      .then(setEmployees)
      .catch(() => {/* employees list optional */});
  }, []);

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
      const logs = await fetchLogs({ date_from: dateFrom, date_to: dateTo, employee_id: employeeId || undefined });
      setRows(groupLogsByEmployeeDay(logs));
    } catch {
      toast.error("Не удалось загрузить данные. Проверьте VITE_ATTENDANCE_API_URL.");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, employeeId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const exportExcel = () => {
    const data = rows.map((r) => ({
      "Сотрудник": r.full_name,
      "Дата": r.date,
      "Приход": r.first_in ?? "—",
      "Уход": r.last_out ?? "—",
      "Отработано": r.worked_minutes != null ? `${Math.floor(r.worked_minutes / 60)}:${String(r.worked_minutes % 60).padStart(2, "0")}` : "—",
      "Филиал": r.device_name ?? "—",
      "Опоздание": r.is_late ? "Да" : "Нет",
      "Ранний уход": r.left_early ? "Да" : "Нет",
      "Отсутствие": r.absent ? "Да" : "Нет",
    }));
    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Посещаемость");
    XLSX.writeFile(wb, `attendance_${dateFrom}_${dateTo}.xlsx`);
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">FaceID Attendance</h1>
            <p className="text-muted-foreground text-sm mt-0.5">
              Учёт посещаемости сотрудников на основе Face ID
            </p>
          </div>
          <Button onClick={exportExcel} disabled={rows.length === 0} className="gap-2">
            <Download className="w-4 h-4" />
            Экспорт Excel
          </Button>
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

        {/* Table */}
        <AttendanceTable rows={rows} />
      </div>
    </div>
  );
}
