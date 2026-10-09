import { useState } from "react";
import type { AdjustmentField, Payroll, PayrollDay, PayrollEmployee } from "@/api/attendance.ts";
import { cn } from "@/lib/utils.ts";
import { formatNumber, shortDate } from "../utils.ts";
import { formatHours } from "../_lib/format-hours.ts";

type Props = {
  payroll: Payroll;
  onEditDay: (employeeId: string, date: string) => void;
  onAdjust: (employeeId: string, field: AdjustmentField, value: number) => void;
  onRate: (employee: PayrollEmployee, value: number) => void;
  onPosition: (employeeId: string, position: string | null) => void;
};

const CELL = "border px-2 py-1 text-sm";
const HEAD = "border bg-muted px-2 py-2 text-center text-xs font-semibold text-muted-foreground";
const STICKY_NUM = "sticky left-0 z-10 w-10 min-w-10 bg-background";
const STICKY_NAME = "sticky left-10 z-10 min-w-44 bg-background";

export default function PayrollTable({ payroll, onEditDay, onAdjust, onRate, onPosition }: Props) {
  const { dates, employees } = payroll;
  const total = (pick: (e: PayrollEmployee) => number) =>
    employees.reduce((acc, e) => acc + pick(e), 0);

  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-max min-w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className={cn(HEAD, STICKY_NUM, "bg-muted")}>№</th>
            <th className={cn(HEAD, STICKY_NAME, "bg-muted text-left")}>Isim</th>
            <th className={HEAD}>Lavozim</th>
            <th className={HEAD}>Soatlik</th>
            {dates.map((date) => (
              <th key={date} className={cn(HEAD, "min-w-14")}>
                {shortDate(date)}
              </th>
            ))}
            <th className={HEAD}>Soat</th>
            <th className={HEAD}>Mukofoti</th>
            <th className={HEAD}>Chiqqan maoshi</th>
            <th className={HEAD}>Shtraf</th>
            <th className={HEAD}>Posuda</th>
            <th className={HEAD}>Chiqqan maoshi</th>
            <th className={HEAD}>Imzo</th>
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
              <td rowSpan={2} className={CELL}>
                <PositionInput
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
                {formatHours(emp.worked_minutes)}
              </td>
              <AdjustCell rowSpan={2} emp={emp} field="bonus" onAdjust={onAdjust} />
              <td rowSpan={2} className={cn(CELL, "text-right font-medium tabular-nums")}>
                {formatNumber(emp.gross)}
              </td>
              <AdjustCell rowSpan={2} emp={emp} field="fine" onAdjust={onAdjust} />
              <AdjustCell rowSpan={2} emp={emp} field="posuda" onAdjust={onAdjust} />
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
              {formatHours(total((e) => e.worked_minutes))}
            </td>
            <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.bonus))}</td>
            <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.gross))}</td>
            <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.fine))}</td>
            <td className={cn(CELL, "text-right tabular-nums")}>{formatNumber(total((e) => e.posuda))}</td>
            <td className={cn(CELL, "text-right tabular-nums text-emerald-600")}>
              {formatNumber(total((e) => e.net))}
            </td>
            <td className={CELL} />
          </tr>
        </tfoot>
      </table>
    </div>
  );
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
  return (
    <td className="border p-0 text-center text-xs tabular-nums">
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "block h-full w-full cursor-pointer px-1.5 py-1 transition-colors hover:bg-muted",
          !value && "text-muted-foreground",
          value && day && !day.counted && "bg-amber-50 text-amber-700 dark:bg-amber-950/30",
          value && day?.manual && "font-semibold text-blue-600",
        )}
      >
        {value ?? "-"}
      </button>
    </td>
  );
}

function AdjustCell({
  emp,
  field,
  rowSpan,
  onAdjust,
}: {
  emp: PayrollEmployee;
  field: AdjustmentField;
  rowSpan: number;
  onAdjust: Props["onAdjust"];
}) {
  const value = emp[field];
  return (
    <td rowSpan={rowSpan} className="border p-0">
      <MoneyInput
        key={`${emp.employee_id}-${field}-${value}`}
        value={value}
        className="w-28"
        onCommit={(v) => onAdjust(emp.employee_id, field, v)}
      />
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

function PositionInput({ value, onCommit }: { value: string; onCommit: (v: string) => void }) {
  const [text, setText] = useState(value);
  return (
    <input
      type="text"
      value={text}
      placeholder="—"
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        const next = text.trim();
        if (next !== value) onCommit(next);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
      className="w-24 bg-transparent text-sm focus:outline-none"
    />
  );
}
