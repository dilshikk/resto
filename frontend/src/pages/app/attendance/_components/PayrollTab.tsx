import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Calendar, Download, RefreshCw } from "lucide-react";
import { fetchPayroll, type AdjustmentField, type PayrollEmployee } from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";
import {
  formatNumber,
  monthPartRange,
  monthRange,
  periodLength,
  type DateRange,
} from "../_lib/utils.ts";
import { exportPayrollExcel } from "../_lib/payroll-export.ts";
import { formatHours } from "../_lib/format-hours.ts";
import { sortEmployees, usePayrollSort } from "../_lib/payroll-sort.ts";
import { usePayrollMutations } from "../_hooks/use-payroll-mutations.ts";
import PayrollTable from "./PayrollTable.tsx";
import PunchDialog from "./PunchDialog.tsx";

const MAX_DAYS = 62;

const PRESETS: { label: string; range: () => DateRange }[] = [
  { label: "Этот месяц", range: () => monthRange(0) },
  { label: "Прошлый месяц", range: () => monthRange(-1) },
  { label: "1–10", range: () => monthPartRange(1) },
  { label: "11–20", range: () => monthPartRange(2) },
  { label: "21–30", range: () => monthPartRange(3) },
];

type Editing = { employeeId: string; date: string };

export default function PayrollTab() {
  const initial = monthRange(0);
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [editing, setEditing] = useState<Editing | null>(null);
  const { punch, adjustment, position, rate } = usePayrollMutations();
  const { sort, toggle } = usePayrollSort();

  const length = dateFrom && dateTo ? periodLength(dateFrom, dateTo) : 0;
  const validPeriod = length >= 1 && length <= MAX_DAYS;

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ["attendance-payroll", dateFrom, dateTo],
    queryFn: () => fetchPayroll(dateFrom, dateTo),
    enabled: validPeriod,
  });

  const employees = useMemo(() => sortEmployees(data?.employees ?? [], sort), [data, sort]);
  const editingEmployee = employees.find((e) => e.employee_id === editing?.employeeId);

  const handleAdjust = (employeeId: string, field: AdjustmentField, value: number) =>
    adjustment.mutate({
      faceid_employee_id: employeeId,
      date_from: dateFrom,
      date_to: dateTo,
      [field]: value,
    });

  const handleRate = (employee: PayrollEmployee, value: number) =>
    rate.mutate({
      employeeId: employee.employee_id,
      name: employee.name,
      rate: value,
      currency: employee.currency,
    });

  const handleSavePunch = (arrival: string | null, departure: string | null) => {
    if (!editing) return;
    punch.mutate(
      {
        faceid_employee_id: editing.employeeId,
        shift_date: editing.date,
        arrival,
        departure,
      },
      { onSuccess: () => setEditing(null) },
    );
  };

  const totalNet = employees.reduce((acc, e) => acc + e.net, 0);
  const totalMinutes = employees.reduce((acc, e) => acc + e.worked_minutes, 0);
  const withoutRate = employees.filter((e) => e.rate_per_hour <= 0 && e.worked_minutes > 0).length;

  return (
    <div className="space-y-4">
      {/* Период */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-wrap gap-1 rounded-lg bg-secondary p-1">
          {PRESETS.map((preset) => {
            const range = preset.range();
            const active = range.from === dateFrom && range.to === dateTo;
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setDateFrom(range.from);
                  setDateTo(range.to);
                }}
                className={cn(
                  "cursor-pointer rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {preset.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-muted-foreground" />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-9 w-36 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <span className="text-sm text-muted-foreground">—</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-9 w-36 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <button
          type="button"
          onClick={() => void refetch()}
          disabled={!validPeriod || isFetching}
          className="flex h-9 cursor-pointer items-center gap-2 rounded-lg border bg-secondary px-4 text-sm font-medium transition-colors hover:bg-secondary/80 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          Обновить
        </button>

        <button
          type="button"
          onClick={() => data && exportPayrollExcel(data, employees)}
          disabled={employees.length === 0}
          className="ml-auto flex h-9 cursor-pointer items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          Экспорт Excel
        </button>
      </div>

      {!validPeriod && (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
          Укажите период: дата окончания не раньше начала, не более {MAX_DAYS} дней.
        </p>
      )}

      {/* Сводка */}
      {employees.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span className="text-muted-foreground">Сотрудников: {employees.length}</span>
          <span className="text-muted-foreground">Часов всего: {formatHours(totalMinutes)}</span>
          <span>
            <span className="text-muted-foreground">К выдаче всего: </span>
            <span className="font-semibold text-emerald-600">{formatNumber(totalNet)}</span>
          </span>
          {withoutRate > 0 && (
            <span className="text-amber-600">
              У {withoutRate} сотр. не задана ставка - введите её в колонке «Ставка/час»
            </span>
          )}
        </div>
      )}

      {isLoading && validPeriod && (
        <div className="flex items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent opacity-60" />
        </div>
      )}

      {isError && (
        <div className="rounded-xl border py-16 text-center text-muted-foreground">
          Не удалось загрузить табель. Требуются права менеджера.
        </div>
      )}

      {data && employees.length === 0 && (
        <div className="rounded-xl border py-16 text-center text-muted-foreground">
          Нет данных за выбранный период
        </div>
      )}

      {data && employees.length > 0 && (
        <>
          <PayrollTable
            payroll={data}
            employees={employees}
            sort={sort}
            onSort={toggle}
            onEditDay={(employeeId, date) => setEditing({ employeeId, date })}
            onAdjust={handleAdjust}
            onRate={handleRate}
            onPosition={(employeeId, value) =>
              position.mutate({ faceid_employee_id: employeeId, position: value })
            }
          />
          <p className="text-xs text-muted-foreground">
            Оплата почасовая: часы считаются по минутам от прихода до ухода. Ставку за час, премию,
            штраф и посуду можно менять прямо в таблице, сохраняется при выходе из поля. Нажмите на
            время, чтобы указать приход и уход вручную. Синим выделено ручное время, жёлтым - смена
            без прихода или ухода (не считается). Нажмите на заголовок «Имя», «Должность» или
            «Ставка/час», чтобы отсортировать - выбор запоминается.
          </p>
        </>
      )}

      {editing && editingEmployee && (
        <PunchDialog
          key={`${editing.employeeId}-${editing.date}`}
          employeeName={editingEmployee.name}
          date={editing.date}
          day={editingEmployee.days[editing.date]}
          saving={punch.isPending}
          onSave={handleSavePunch}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
