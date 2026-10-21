import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { UserX, UserCheck, X } from "lucide-react";
import type { PayrollDay, PlanMode } from "@/api/attendance.ts";
import { listEmployees } from "@/api/employees.ts";
import { cn } from "@/lib/utils.ts";
import { formatNumber, shortDate } from "../_lib/utils.ts";

type Scope = "day" | "weekday" | "period";

type Props = {
  employeeName: string;
  date: string;
  /** Все дни текущего периода - для «применить к нескольким дням» */
  periodDates: string[];
  day: PayrollDay | undefined;
  linkedEmployeeId: number | null;
  /** Дата увольнения (YYYY-MM-DD), если сотрудник уволен. null/undefined - активен */
  terminatedFrom?: string | null;
  saving: boolean;
  terminating: boolean;
  lateFinePerMinute: number;
  lateGraceMinutes: number;
  earlyFinePerMinute: number;
  onSave: (mode: PlanMode, start: string | null, end: string | null, dates: string[]) => void;
  onLink: (employeeId: number | null) => void;
  /** null - восстановить (убрать увольнение) */
  onTerminate: (terminatedFrom: string | null) => void;
  onClose: () => void;
};

// Частые варианты смен - выбираются одним нажатием
const PRESETS: { start: string; end: string }[] = [
  { start: "09:00", end: "01:00" },
  { start: "10:00", end: "23:00" },
  { start: "12:00", end: "00:00" },
  { start: "08:00", end: "20:00" },
];

const WEEKDAYS = ["воскресенья", "понедельники", "вторники", "среды", "четверги", "пятницы", "субботы"];

const weekday = (iso: string): number => new Date(`${iso}T00:00:00`).getDay();

function scopeDates(scope: Scope, date: string, periodDates: string[]): string[] {
  if (scope === "period") return periodDates;
  if (scope === "weekday") return periodDates.filter((d) => weekday(d) === weekday(date));
  return [date];
}

// График смены в табеле: во сколько должен прийти и уйти (Shift+клик по ячейке)
export default function PlanDialog({
  employeeName,
  date,
  periodDates,
  day,
  linkedEmployeeId,
  terminatedFrom,
  saving,
  terminating,
  lateFinePerMinute,
  lateGraceMinutes,
  earlyFinePerMinute,
  onSave,
  onLink,
  onTerminate,
  onClose,
}: Props) {
  const [start, setStart] = useState(day?.planned_start ?? "");
  const [end, setEnd] = useState(day?.planned_end ?? "");
  const [scope, setScope] = useState<Scope>("day");
  const [showLink, setShowLink] = useState(false);
  const isTerminated = Boolean(terminatedFrom);

  const { data: staff, isLoading: staffLoading } = useQuery({
    queryKey: ["employees", "active"],
    queryFn: () => listEmployees({ status: "active" }),
    enabled: showLink || linkedEmployeeId !== null,
  });
  const linkedName = staff?.find((e) => e.id === linkedEmployeeId)?.full_name;

  // Закрытие диалога по клавише ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const dates = scopeDates(scope, date, periodDates);
  const canSet = Boolean(start || end);
  const fromShifts = day?.plan_source === "shifts";
  const fromTabel = day?.plan_source === "tabel";

  const scopes: { id: Scope; label: string }[] = [
    { id: "day", label: `Только ${shortDate(date)}` },
    { id: "weekday", label: `Все ${WEEKDAYS[weekday(date)]} периода` },
    { id: "period", label: "Весь период" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-md flex-col rounded-xl bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold">График: {employeeName}</h2>
            <p className="text-sm text-muted-foreground">Смена от {date}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer rounded-lg p-1.5 hover:bg-muted"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-4 overflow-y-auto px-5 py-4">
          {isTerminated && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/30 dark:text-red-300">
              Сотрудник уволен с {terminatedFrom ? shortDate(terminatedFrom) : ""}. Скрыт из табеля в
              периодах без данных за него.
            </p>
          )}

          {fromShifts && (
            <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
              Сейчас график взят из раздела «Смены». Если сохранить здесь, табель будет
              считать по новому времени.
            </p>
          )}

          <div className="grid grid-cols-2 gap-3">
            <TimeInput label="Должен прийти" value={start} onChange={setStart} />
            <TimeInput label="Должен уйти" value={end} onChange={setEnd} />
          </div>

          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => {
              const active = p.start === start && p.end === end;
              return (
                <button
                  key={`${p.start}-${p.end}`}
                  type="button"
                  onClick={() => {
                    setStart(p.start);
                    setEnd(p.end);
                  }}
                  className={cn(
                    "cursor-pointer rounded-full border px-3 py-1 text-xs font-medium tabular-nums transition-colors",
                    active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted",
                  )}
                >
                  {p.start}–{p.end}
                </button>
              );
            })}
          </div>

          <p className="text-xs text-muted-foreground">
            Ночной уход вводите как есть (например 01:00). Опоздание до {lateGraceMinutes} мин не
            штрафуется, дальше - {formatNumber(lateFinePerMinute)} за каждую минуту. Ранний уход -{" "}
            {formatNumber(earlyFinePerMinute)} за минуту.
          </p>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold">Применить к</h3>
            <div className="flex flex-wrap gap-1 rounded-lg bg-secondary p-1">
              {scopes.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setScope(s.id)}
                  className={cn(
                    "cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                    scope === s.id
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {s.label}
                </button>
              ))}
            </div>
            {scope !== "day" && (
              <p className="text-xs text-muted-foreground">Будет изменено дней: {dates.length}</p>
            )}
          </div>

          {/* Привязка к сотруднику системы - чтобы график брался из «Смен» */}
          <div className="space-y-2 border-t pt-4">
            <div className="flex items-baseline justify-between gap-2">
              <h3 className="text-sm font-semibold">График из раздела «Смены»</h3>
              {!showLink && (
                <button
                  type="button"
                  onClick={() => setShowLink(true)}
                  className="cursor-pointer text-xs text-primary underline"
                >
                  {linkedEmployeeId ? "изменить" : "привязать"}
                </button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {linkedEmployeeId
                ? `Привязан к сотруднику: ${linkedName ?? "…"}. Смены из раздела «Смены» попадают в табель сами.`
                : "Не привязан. Привяжите к сотруднику системы, чтобы табель брал его смены из раздела «Смены»."}
            </p>
            {showLink && (
              <select
                value={linkedEmployeeId ?? ""}
                disabled={staffLoading}
                onChange={(e) => {
                  const value = e.target.value;
                  onLink(value ? Number(value) : null);
                  setShowLink(false);
                }}
                className="h-9 w-full cursor-pointer rounded-lg border bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="">{staffLoading ? "Загрузка…" : "— не привязан —"}</option>
                {(staff ?? []).map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.full_name}
                    {e.primary_branch_name ? ` (${e.primary_branch_name})` : ""}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Статус сотрудника: уволен/активен. Дата смены используется как дата увольнения. */}
          <div className="space-y-2 border-t pt-4">
            <h3 className="text-sm font-semibold">Статус сотрудника</h3>
            <p className="text-xs text-muted-foreground">
              {isTerminated
                ? `Уволен с ${terminatedFrom ? shortDate(terminatedFrom) : ""}. Восстановите, если это ошибка.`
                : "Сотрудник активен. Уволенные скрываются из табеля в периодах без данных за них."}
            </p>
            {isTerminated ? (
              <button
                type="button"
                onClick={() => onTerminate(null)}
                disabled={terminating}
                className="flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
              >
                <UserCheck className="h-4 w-4" />
                {terminating ? "Сохранение…" : "Восстановить сотрудника"}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => onTerminate(date)}
                disabled={terminating}
                className="flex h-9 w-full cursor-pointer items-center justify-center gap-2 rounded-lg border border-red-300 bg-red-50 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-800 dark:bg-red-950/30 dark:text-red-300"
              >
                <UserX className="h-4 w-4" />
                {terminating ? "Сохранение…" : `Уволен с ${shortDate(date)}`}
              </button>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-5 py-4">
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => onSave("day_off", null, null, dates)}
              disabled={saving}
              className="cursor-pointer rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
            >
              Выходной
            </button>
            <button
              type="button"
              onClick={() => onSave("clear", null, null, dates)}
              disabled={saving || (scope === "day" && !fromTabel)}
              title="Убрать график, заданный в табеле"
              className="cursor-pointer rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40"
            >
              Очистить
            </button>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="cursor-pointer rounded-lg px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => onSave("set", start || null, end || null, dates)}
              disabled={saving || !canSet}
              className="cursor-pointer rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Сохранение…" : "Сохранить"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TimeInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium">{label}</label>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-10 w-full rounded-lg border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
    </div>
  );
}
