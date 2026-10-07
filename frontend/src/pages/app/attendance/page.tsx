import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchAttendanceLogs,
  fetchAttendanceEmployees,
} from "@/api/attendance.ts";
import {
  groupLogsByEmployeeDay,
  todayStr,
  weekAgoStr,
  type EmployeeDay,
  type ReportPeriod,
} from "./utils.ts";
import FiltersBar from "./_components/FiltersBar.tsx";
import StatsCards from "./_components/StatsCards.tsx";
import AttendanceTable from "./_components/AttendanceTable.tsx";
import { Button } from "@/components/ui/button.tsx";
import { Download } from "lucide-react";
import * as XLSX from "xlsx";
import { formatMinutes } from "./utils.ts";

export default function AttendancePage() {
  const [period, setPeriod] = useState<ReportPeriod>("day");
  const [dateFrom, setDateFrom] = useState(todayStr());
  const [dateTo, setDateTo] = useState(todayStr());
  const [employeeId, setEmployeeId] = useState("");
  const [rows, setRows] = useState<EmployeeDay[]>([]);

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
      const first = new Date(d.getFullYear(), d.getMonth(), 1)
        .toISOString()
        .slice(0, 10);
      setDateFrom(first);
      setDateTo(today);
    }
  };

  const [loading, setLoading] = useState(false);

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

  const exportExcel = () => {
    const data = rows.map((r) => ({
      Сотрудник: r.full_name,
      Дата: r.date,
      Приход: r.first_in ?? "—",
      Уход: r.last_out ?? "—",
      Отработано:
        r.worked_minutes != null ? formatMinutes(r.worked_minutes) : "—",
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
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
        {/* Header */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Посещаемость (FaceID)
            </h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Учёт посещаемости сотрудников на основе Face ID
            </p>
          </div>
          <Button
            onClick={exportExcel}
            disabled={rows.length === 0}
            className="gap-2"
          >
            <Download className="h-4 w-4" />
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
        <StatsCards
          rows={rows}
          totalEmployees={employees.length || rows.length}
        />

        {/* Table */}
        <AttendanceTable rows={rows} />
      </div>
    </div>
  );
}
