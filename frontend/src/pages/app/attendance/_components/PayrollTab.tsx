import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarClock, Calendar, Download, RefreshCw, Briefcase, Users } from "lucide-react";
import {
  fetchPayroll,
  type AdjustmentField,
  type PayrollEmployee,
  type PlanMode,
} from "@/api/attendance.ts";
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
import PayrollTable, { POSITIONS } from "./PayrollTable.tsx";
import PunchDialog, { type ShiftFineDraft } from "./PunchDialog.tsx";
import PlanDialog from "./PlanDialog.tsx";

const MAX_DAYS = 62;

const PRESETS: { label: string; range: () => DateRange }[] = [
  { label: "Этот месяц", range: () => monthRange(0) },
  { label: "Прошлый месяц", range: () => monthRange(-1) },
  { label: "1–10", range: () => monthPartRange(1) },
  { label: "11–20", range: () => monthPartRange(2) },
  { label: "21–30", range: () => monthPartRange(3) },
];

// Должности без "Другое" - это значение открывает текстовое поле, а не фильтрует список
const POSITION_FILTER_OPTIONS = POSITIONS.filter((p) => p !== "Другое");

// kind: punch - приход/уход и штрафы, plan - график
type Editing = { employeeId: string; date: string; kind: "punch" | "plan" };

export default function PayrollTab() {
  const initial = monthRange(0);
  const [dateFrom, setDateFrom] = useState(initial.from);
  const [dateTo, setDateTo] = useState(initial.to);
  const [positionFilter, setPositionFilter] = useState("");
  // Уволенные без данных за выбранный период скрыты, если этот переключатель выключен
  const [showTerminated, setShowTerminated] = useState(false);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [savingDay, setSavingDay] = useState(false);
  // На телефоне нет Shift - этот переключатель делает обычное нажатие «графиком»
  const [planMode, setPlanMode] = useState(false);
  const { punch, shiftFine, plan, link, adjustment, position, termination, rate } =
    usePayrollMutations();
  const { sort, toggle } = usePayrollSort();

  const length = dateFrom && dateTo ? periodLength(dateFrom, dateTo) : 0;
  const validPeriod = length >= 1 && length <= MAX_DAYS;

  const { data, isLoading, isFetching, isError, refetch } = useQuery({
    queryKey: ["attendance-payroll", dateFrom, dateTo, showTerminated],
    queryFn: () => fetchPayroll(dateFrom, dateTo, showTerminated),
    enabled: validPeriod,
  });

  // Должности, которые реально встречаются в загруженных данных (для случаев, когда
  // сотруднику задана должность вне стандартного списка, например введена вручную)
  const availablePositions = useMemo(() => {
    const extra = new Set((data?.employees ?? []).map((e) => e.position?.trim()).filter(Boolean) as string[]);
    for (const p of POSITION_FILTER_OPTIONS) extra.delete(p);
    return [...POSITION_FILTER_OPTIONS, ...[...extra].sort((a, b) => a.localeCompare(b, "ru"))];
  }, [data]);

  const filteredByPosition = useMemo(() => {
    const all = data?.employees ?? [];
    if (!positionFilter) return all;
    return all.filter((e) => (e.position?.trim() ?? "") === positionFilter);
  }, [data, positionFilter]);

  const employees = useMemo(
    () => sortEmployees(filteredByPosition, sort),
    [filteredByPosition, sort],
  );
  const editingEmployee = employees.find((e) => e.employee_id === editing?.employeeId);
  const terminatedCount = employees.filter((e) => e.terminated_from).length;

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

  const handleEditDay = (employeeId: string, date: string, withShift: boolean) =>
    setEditing({ employeeId, date, kind: withShift !== planMode ? "plan" : "punch" });

  // Сохраняет время смены и штрафы за смену одним нажатием
  const handleSaveDay = async (
    arrival: string | null,
    departure: string | null,
    fines: ShiftFineDraft[],
  ) => {
    if (!editing) return;
    const base = { faceid_employee_id: editing.employeeId, shift_date: editing.date };
    setSavingDay(true);
    try {
      await punch.mutateAsync({ ...base, arrival, departure });
      await Promise.all(fines.map((fine) => shiftFine.mutateAsync({ ...base, ...fine })));
      setEditing(null);
    } catch {
      // Ошибку уже показал toast в мутации
    } finally {
      setSavingDay(false);
    }
  };

  const handleSavePlan = async (
    mode: PlanMode,
    start: string | null,
    end: string | null,
    dates: string[],
  ) => {
    if (!editing) return;
    try {
      await plan.mutateAsync({
        faceid_employee_id: editing.employeeId,
        shift_dates: dates,
        mode,
        planned_start: start,
        planned_end: end,
      });
      setEditing(null);
    } catch {
      // Ошибку уже показал toast в мутации
    }
  };

  const totalNet = employees.reduce((acc, e) => acc + e.net, 0);
  const totalMinutes = employees.reduce((acc, e) => acc + e.worked_minutes, 0);
  const withoutRate = employees.filter((e) => e.rate_per_hour <= 0 && e.worked_minutes > 0).length;
  const editingDay = editing ? editingEmployee?.days[editing.date] : undefined;

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

        {/* Фильтр по должности: показывает только сотрудников выбранной должности */}
        <div className="flex items-center gap-2">
          <Briefcase className="h-4 w-4 text-muted-foreground" />
          <select
            value={positionFilter}
            onChange={(e) => setPositionFilter(e.target.value)}
            className="h-9 w-44 rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="">Все должности</option>
            {availablePositions.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        {/* Уволенные без данных за период скрыты по умолчанию - этот переключатель их показывает */}
        <button
          type="button"
          onClick={() => setShowTerminated((v) => !v)}
          aria-pressed={showTerminated}
          title="Уволенные сотрудники без отметок за выбранный период скрыты из табеля"
          className={cn(
            "flex h-9 cursor-pointer items-center gap-2 rounded-lg border px-4 text-sm font-medium transition-colors",
            showTerminated
              ? "border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300"
              : "bg-secondary hover:bg-secondary/80",
          )}
        >
          <Users className="h-4 w-4" />
          Показать уволенных
        </button>

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
          onClick={() => setPlanMode((v) => !v)}
          aria-pressed={planMode}
          title="Включите, чтобы нажатие на ячейку открывало график (удобно на телефоне)"
          className={cn(
            "flex h-9 cursor-pointer items-center gap-2 rounded-lg border px-4 text-sm font-medium transition-colors",
            planMode
              ? "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300"
              : "bg-secondary hover:bg-secondary/80",
          )}
        >
          <CalendarClock className="h-4 w-4" />
          {planMode ? "Режим графика: вкл" : "Режим графика"}
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
          {terminatedCount > 0 && (
            <span className="text-red-600">Уволенных в списке: {terminatedCount}</span>
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
          {positionFilter
            ? `Нет сотрудников с должностью «${positionFilter}» за выбранный период`
            : "Нет данных за выбранный период"}
        </div>
      )}

      {data && employees.length > 0 && (
        <>
          <PayrollTable
            payroll={data}
            employees={employees}
            sort={sort}
            onSort={toggle}
            onEditDay={handleEditDay}
            onAdjust={handleAdjust}
            onRate={handleRate}
            onPosition={(employeeId, value) =>
              position.mutate({ faceid_employee_id: employeeId, position: value })
            }
          />
          <p className="text-xs text-muted-foreground">
            Оплата почасовая: часы считаются по минутам от прихода до ухода. Ставку за час, премию,
            штраф и посуду можно менять прямо в таблице, сохраняется при выходе из поля. Нажмите на
            время, чтобы указать приход и уход вручную или поставить штраф за невыход.{" "}
            <b>Shift+клик</b> (или «Режим графика» на телефоне) - задать, во сколько сотрудник
            должен прийти и уйти: за опоздание больше {data.late_grace_minutes ?? 5} мин и за ранний уход
            штраф начислится сам по минутам, или отметить сотрудника уволенным. Синим выделено
            ручное время, жёлтым - смена без прихода или ухода (не считается), красной точкой -
            смена с ручным штрафом. Нажмите на заголовок «Имя», «Должность» или «Ставка/час», чтобы
            отсортировать - выбор запоминается.
          </p>
        </>
      )}

      {editing?.kind === "punch" && editingEmployee && (
        <PunchDialog
          key={`${editing.employeeId}-${editing.date}`}
          employeeName={editingEmployee.name}
          date={editing.date}
          day={editingDay}
          saving={savingDay}
          lateFinePerMinute={data?.late_fine_per_minute ?? 1000}
          onSave={(a, d, fines) => void handleSaveDay(a, d, fines)}
          onClose={() => setEditing(null)}
        />
      )}

      {editing?.kind === "plan" && editingEmployee && data && (
        <PlanDialog
          key={`plan-${editing.employeeId}-${editing.date}`}
          employeeName={editingEmployee.name}
          date={editing.date}
          periodDates={data.dates}
          day={editingDay}
          linkedEmployeeId={editingEmployee.linked_employee_id ?? null}
          terminatedFrom={editingEmployee.terminated_from ?? null}
          saving={plan.isPending}
          terminating={termination.isPending}
          lateFinePerMinute={data.late_fine_per_minute ?? 1000}
          lateGraceMinutes={data.late_grace_minutes ?? 5}
          earlyFinePerMinute={data.early_leave_fine_per_minute ?? 1000}
          onSave={(mode, start, end, dates) => void handleSavePlan(mode, start, end, dates)}
          onLink={(employeeId) =>
            link.mutate({ faceid_employee_id: editingEmployee.employee_id, employee_id: employeeId })
          }
          onTerminate={(terminatedFrom) =>
            termination.mutate({
              faceid_employee_id: editingEmployee.employee_id,
              terminated_from: terminatedFrom,
            })
          }
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
