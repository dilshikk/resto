import { useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { AdjustmentField, Payroll, PayrollDay, PayrollEmployee } from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";
import { formatNumber, shortDate } from "../_lib/utils.ts";
import { formatHours } from "../_lib/format-hours.ts";
import type { PayrollSort, SortKey } from "../_lib/payroll-sort.ts";

type Props = {
  payroll: Payroll;
  /** Сотрудники в нужном порядке (уже отсортированные) */
  employees: PayrollEmployee[];
  sort: PayrollSort;
  onSort: (key: SortKey) => void;
  onEditDay: (employeeId: string, date: string) => void;
  onAdjust: (employeeId: string, field: AdjustmentField, value: number) => void;
  onRate: (employee: PayrollEmployee, value: number) => void;
  onPosition: (employeeId: string, position: string | null) => void;
};

const CELL = "border px-2 py-1 text-sm";
const HEAD = "border bg-muted px-2 py-2 text-center text-xs font-semibold text-muted-foreground";
const STICKY_NUM = "sticky left-0 z-10 w-10 min-w-10 bg-background";
const STICKY_NAME = "sticky left-10 z-10 min-w-44 bg-background";
// Переработка: выделяется фиолетовым, в зарплату не идёт
const OVERTIME = "bg-violet-50 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300";
// Смена без прихода или ухода в FaceID - штраф
const MISSING = "bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300";

// Список стандартных должностей для ресторана
const POSITIONS = [
  "Повар",
  "Су-шеф",
  "Шеф-повар",
  "Официант",
  "Старший официант",
  "Хостес",
  "Кассир",
  "Раннер",
  "Бармен",
  "Менеджер",
  "Администратор",
  "Посудамойщик",
  "Уборщик",
  "Охранник",
  "Другое",
];

// Итоговые удержания: ручная сумма + автоматическая
const fineTotal = (e: PayrollEmployee) => e.fine + (e.missing_punch_fine ?? 0);
const posudaTotal = (e: PayrollEmployee) => e.posuda_total ?? e.posuda;

export default function PayrollTable({
  payroll,
  employees,
  sort,
  onSort,
  onEditDay,
  onAdjust,
  onRate,
  onPosition,
}: Props) {
  const { dates } = payroll;
  const maxHours = Math.round((payroll.max_paid_minutes_per_shift ?? 600) / 60);
  const fineAmount = payroll.missing_punch_fine_amount ?? 30000;
  const posudaAmount = payroll.posuda_per_shift ?? 5000;
  const total = (pick: (e: PayrollEmployee) => number) =>
    employees.reduce((acc, e) => acc + pick(e), 0);

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        За смену оплачивается не больше {maxHours} ч. Время сверх этого показано как{" "}
        <span className={cn("rounded px-1 font-medium", OVERTIME)}>переработка</span> и в
        зарплату не засчитывается. Смена без прихода или ухода{" "}
        <span className={cn("rounded px-1 font-medium", MISSING)}>
          штраф {formatNumber(fineAmount)}
        </span>
        . Посуда удерживается автоматически: {formatNumber(posudaAmount)} за каждую смену.
      </p>
      <div className="overflow-x-auto rounded-xl border">
        <table className="w-max min-w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className={cn(HEAD, STICKY_NUM, "bg-muted")}>№</th>
              <th className={cn(HEAD, STICKY_NAME, "bg-muted text-left")}>
                <SortButton label="Имя" sortKey="name" sort={sort} onSort={onSort} />
              </th>
              <th className={HEAD}>
                <SortButton label="Должность" sortKey="position" sort={sort} onSort={onSort} />
              </th>
              <th className={HEAD}>
                <SortButton label="Ставка/час" sortKey="rate" sort={sort} onSort={onSort} />
              </th>
              {dates.map((date) => (
                <th key={date} className={cn(HEAD, "min-w-14")}>
                  {shortDate(date)}
                </th>
              ))}
              <th className={HEAD} title={`Оплачиваемые часы, не больше ${maxHours} ч за смену`}>
                Часы
              </th>
              <th className={cn(HEAD, OVERTIME)} title="Не оплачивается">
                Переработка
              </th>
              <th className={HEAD}>Премия</th>
              <th className={HEAD}>Начислено</th>
              <th className={HEAD} title="Ручной штраф + штраф за пропущенные отметки">
                Штраф
              </th>
              <th className={HEAD} title="Ручная посуда + посуда за смены">
                Посуда
              </th>
              <th className={HEAD}>К выдаче</th>
              <th className={HEAD}>Подпись</th>
            </tr>
          </thead>

          {employees.map((emp, index) => (
            <tbody key={emp.employee_id}>
              <tr>
                <td rowSpan={2} className={cn(CELL, STICKY_NUM, "text-center text-muted-foreground")}>
                  {index + 1}
                </td>
                <td rowSpan={2} className={cn(CELL, STICKY_NAME, "font-medium")}>
                  {emp.name}
                </td>
                <td rowSpan={2} className="border p-0">
                  <PositionSelect
                    key={`${emp.employee_id}-${emp.position ?? ""}`}
                    value={emp.position ?? ""}
                    onCommit={(v) => onPosition(emp.employee_id, v || null)}
                  />
                </td>
                <td rowSpan={2} className="border p-0">
                  <MoneyInput
                    key={`${emp.employee_id}-rate-${emp.rate_per_hour}`}
                    value={emp.rate_per_hour}
                    placeholder="ставка"
                    className={cn(
                      "w-24",
                      emp.rate_per_hour <= 0 &&
                        emp.worked_minutes > 0 &&
                        "bg-amber-50 placeholder:text-amber-600 dark:bg-amber-950/30",
                    )}
                    onCommit={(v) => onRate(emp, v)}
                  />
                </td>
                {dates.map((date) => (
                  <DayCell
                    key={date}
                    day={emp.days[date]}
                    kind="arrival"
                    onClick={() => onEditDay(emp.employee_id, date)}
                  />
                ))}
                <td rowSpan={2} className={cn(CELL, "text-center font-semibold tabular-nums")}>
                  {formatHours(emp.paid_minutes ?? emp.worked_minutes)}
                </td>
                <td
                  rowSpan={2}
                  className={cn(
                    CELL,
                    "text-center tabular-nums",
                    emp.overtime_minutes > 0 ? cn(OVERTIME, "font-semibold") : "text-muted-foreground",
                  )}
                >
                  {emp.overtime_minutes > 0 ? formatHours(emp.overtime_minutes) : "-"}
                </td>
                <AdjustCell rowSpan={2} emp={emp} field="bonus" onAdjust={onAdjust} />
                <td rowSpan={2} className={cn(CELL, "text-right font-medium tabular-nums")}>
                  {formatNumber(emp.gross)}
                </td>
                <AdjustCell
                  rowSpan={2}
                  emp={emp}
                  field="fine"
                  onAdjust={onAdjust}
                  auto={emp.missing_punch_fine ?? 0}
                  autoLabel={`за отметки (${emp.missing_punch_count ?? 0} см.)`}
                  totalValue={fineTotal(emp)}
                />
                <AdjustCell
                  rowSpan={2}
                  emp={emp}
                  field="posuda"
                  onAdjust={onAdjust}
                  auto={emp.posuda_auto ?? 0}
                  autoLabel={`за смены (${emp.worked_days} см.)`}
                  totalValue={posudaTotal(emp)}
                />
                <td
                  rowSpan={2}
                  className={cn(CELL, "text-right font-semibold tabular-nums text-emerald-600")}
                >
                  {formatNumber(emp.net)}
                </td>
                <td rowSpan={2} className={cn(CELL, "min-w-28")} />
              </tr>
              <tr>
                {dates.map((date) => (
                  <DayCell
                    key={date}
                    day={emp.days[date]}
                    kind="departure"
                    onClick={() => onEditDay(emp.employee_id, date)}
                  />
                ))}
              </tr>
            </tbody>
          ))}

          <tfoot>
            <tr className="bg-muted/60 font-semibold">
              <td colSpan={4 + dates.length} className={cn(CELL, "text-right")}>
                Итог
              </td>
              <td className={cn(CELL, "text-center tabular-nums")}>
                {formatHours(total((e) => e.paid_minutes ?? e.worked_minutes))}
              </td>
              <td className={cn(CELL, "text-center tabular-nums", OVERTIME)}>
                {formatHours(total((e) => e.overtime_minutes ?? 0))}
              </td>
              <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.bonus))}</td>
              <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.gross))}</td>
              <td className={cn(CELL, "text-right tabular-nums text-red-600")}>
                {formatNumber(total(fineTotal))}
              </td>
              <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total(posudaTotal))}</td>
              <td className={cn(CELL, "text-right tabular-nums text-emerald-600")}>
                {formatNumber(total((e) => e.net))}
              </td>
              <td className={CELL} />
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function SortButton({
  label,
  sortKey,
  sort,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  sort: PayrollSort;
  onSort: (key: SortKey) => void;
}) {
  const active = sort?.key === sortKey;
  const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      title="Сортировать"
      className={cn(
        "inline-flex cursor-pointer items-center gap-1 transition-colors hover:text-foreground",
        active && "text-foreground",
      )}
    >
      {label}
      <Icon className={cn("h-3.5 w-3.5", !active && "opacity-50")} />
    </button>
  );
}

// Подсказка при наведении: отрезки смены, переработка, штраф и незакрытая смена
function dayTitle(day: PayrollDay | undefined): string | undefined {
  if (!day) return undefined;
  const parts = [...day.segments];
  if (day.overtime_minutes > 0) {
    parts.push(`переработка ${formatHours(day.overtime_minutes)} (не оплачивается)`);
  }
  if (day.open) parts.push("нет ухода после последнего прихода");
  if (day.missing_punch) {
    parts.push(`штраф ${formatNumber(day.missing_punch_fine ?? 0)}: нет прихода или ухода в FaceID`);
  }
  return parts.length > 0 ? parts.join(", ") : undefined;
}

function DayCell({
  day,
  kind,
  onClick,
}: {
  day: PayrollDay | undefined;
  kind: "arrival" | "departure";
  onClick: () => void;
}) {
  const value = day?.[kind] ?? null;
  const overtime = (day?.overtime_minutes ?? 0) > 0;
  const missing = Boolean(day?.missing_punch);
  return (
    <td className="border p-0 text-center text-xs tabular-nums">
      <button
        type="button"
        title={dayTitle(day)}
        onClick={onClick}
        className={cn(
          "block h-full w-full cursor-pointer px-1.5 py-1 transition-colors hover:bg-muted",
          !value && "text-muted-foreground",
          value && overtime && OVERTIME,
          value && day && (!day.counted || day.open) && "bg-amber-50 text-amber-700 dark:bg-amber-950/30",
          missing && MISSING,
          value && day?.manual && "font-semibold text-blue-600",
        )}
      >
        {value ?? (missing ? "нет" : "-")}
      </button>
    </td>
  );
}

function AdjustCell({
  emp,
  field,
  rowSpan,
  onAdjust,
  auto = 0,
  autoLabel,
  totalValue,
}: {
  emp: PayrollEmployee;
  field: AdjustmentField;
  rowSpan: number;
  onAdjust: Props["onAdjust"];
  /** Автоматическая сумма, которая прибавляется к ручной */
  auto?: number;
  autoLabel?: string;
  totalValue?: number;
}) {
  const value = emp[field];
  return (
    <td rowSpan={rowSpan} className="border p-0 align-top">
      <MoneyInput
        key={`${emp.employee_id}-${field}-${value}`}
        value={value}
        placeholder={auto > 0 ? "вручную" : "0"}
        className="w-28"
        onCommit={(v) => onAdjust(emp.employee_id, field, v)}
      />
      {auto > 0 && (
        <div className="space-y-0.5 border-t px-2 py-1 text-right text-[11px] leading-tight tabular-nums">
          <div className="text-muted-foreground" title={autoLabel}>
            +{formatNumber(auto)} {autoLabel}
          </div>
          <div className="font-semibold text-red-600">= {formatNumber(totalValue ?? value + auto)}</div>
        </div>
      )}
    </td>
  );
}

// Сохраняется при потере фокуса или Enter, только если значение изменилось
function MoneyInput({
  value,
  onCommit,
  placeholder = "0",
  className,
}: {
  value: number;
  onCommit: (v: number) => void;
  placeholder?: string;
  className?: string;
}) {
  const [text, setText] = useState(value ? String(value) : "");

  const commit = () => {
    const parsed = Number(text.replace(/\s/g, "").replace(",", "."));
    const next = Number.isFinite(parsed) && parsed >= 0 ? parsed : value;
    setText(next ? String(next) : "");
    if (next !== value) onCommit(next);
  };

  return (
    <input
      type="text"
      inputMode="decimal"
      value={text}
      placeholder={placeholder}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className={cn(
        "h-full min-h-10 bg-transparent px-2 text-right text-sm tabular-nums focus:bg-muted/50 focus:outline-none",
        className,
      )}
    />
  );
}

/**
 * Выпадающий список должностей с возможностью ввода произвольного значения.
 * Если текущая должность не входит в стандартный список — показывается
 * текстовое поле для ввода вручную.
 * Сохраняется сразу при выборе из списка или при потере фокуса текстового поля.
 */
function PositionSelect({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  // Если текущее значение не в списке — считаем режим "Другое"
  const isCustom = value !== "" && !POSITIONS.includes(value) && value !== "Другое";
  const [selectVal, setSelectVal] = useState(isCustom ? "Другое" : value);
  const [customText, setCustomText] = useState(isCustom ? value : "");
  const showCustom = selectVal === "Другое";

  const handleSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setSelectVal(next);
    if (next !== "Другое") {
      setCustomText("");
      onCommit(next === "" ? "" : next);
    }
  };

  const handleCustomBlur = () => {
    const next = customText.trim();
    onCommit(next || "");
  };

  return (
    <div className="flex min-w-[9rem] flex-col gap-0.5 px-1 py-0.5">
      <select
        value={selectVal}
        onChange={handleSelect}
        className="h-8 w-full cursor-pointer rounded border-0 bg-transparent text-sm focus:outline-none focus:ring-1 focus:ring-ring"
      >
        <option value="">—</option>
        {POSITIONS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      {showCustom && (
        <input
          type="text"
          autoFocus
          value={customText}
          placeholder="Введите должность"
          onChange={(e) => setCustomText(e.target.value)}
          onBlur={handleCustomBlur}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
          }}
          className="h-7 w-full rounded border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
        />
      )}
    </div>
  );
}
