import { useState } from "react";
import type { EmployeeDay } from "../utils.ts";
import { formatMinutes, formatMoney } from "../utils.ts";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils.ts";

type Props = { rows: EmployeeDay[] };

export default function AttendanceTable({ rows }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border py-16 text-center text-muted-foreground">
        Нет данных за выбранный период
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs text-muted-foreground">
              <th className="w-8 px-2 py-3" />
              <th className="px-3 py-3 text-left font-semibold">Сотрудник</th>
              <th className="px-3 py-3 text-left font-semibold">Дата</th>
              <th className="px-3 py-3 text-left font-semibold">Приход</th>
              <th className="px-3 py-3 text-left font-semibold">Уход</th>
              <th className="px-3 py-3 text-left font-semibold">Отработано</th>
              <th className="px-3 py-3 text-left font-semibold">Ставка/смена</th>
              <th className="px-3 py-3 text-left font-semibold">Устройство</th>
              <th className="px-3 py-3 text-left font-semibold">Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = `${row.employee_id}__${row.date}`;
              const isOpen = expanded.has(key);
              return (
                <>
                  <tr
                    key={key}
                    onClick={() => toggle(key)}
                    className={cn(
                      "cursor-pointer border-b transition-colors hover:bg-muted/30",
                      row.absent && "opacity-60",
                    )}
                  >
                    <td className="px-2 py-3 text-center">
                      {isOpen ? (
                        <ChevronDown className="inline-block h-3.5 w-3.5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="inline-block h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </td>
                    <td className="px-3 py-3 font-medium">{row.full_name}</td>
                    <td className="px-3 py-3 text-muted-foreground">{row.date}</td>
                    <td className="px-3 py-3">
                      {row.first_in ? (
                        <span className={row.is_late ? "font-medium text-amber-600" : "font-medium text-emerald-600"}>
                          {row.first_in}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {row.last_out ? (
                        <span className={row.left_early ? "font-medium text-blue-600" : ""}>
                          {row.last_out}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {row.worked_minutes != null ? (
                        <span className="font-medium">{formatMinutes(row.worked_minutes)}</span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {row.rate_per_shift != null && row.rate_per_shift > 0 ? (
                        <span className="font-medium text-emerald-600">
                          {formatMoney(row.rate_per_shift, row.currency)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground text-xs">не задана</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-muted-foreground">{row.device_name ?? "—"}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1">
                        {row.absent && (
                          <span className="rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-medium text-destructive">
                            Отсутствует
                          </span>
                        )}
                        {row.is_late && (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            Опоздание
                          </span>
                        )}
                        {row.left_early && (
                          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                            Ранний уход
                          </span>
                        )}
                        {!row.absent && !row.is_late && !row.left_early && (
                          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                            Норма
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr key={`${key}__detail`} className="border-b bg-muted/20">
                      <td colSpan={9} className="px-4 py-3 pl-10">
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Все события за {row.date}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {row.logs.map((log) => (
                            <div
                              key={log.id}
                              className={cn(
                                "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs",
                                log.direction?.toLowerCase() === "in"
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30"
                                  : "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-950/30",
                              )}
                            >
                              <span className="font-medium">{log.access_time}</span>
                              <span>{log.direction?.toLowerCase() === "in" ? "↑ вход" : "↓ выход"}</span>
                              {log.device_name && <span className="opacity-70">{log.device_name}</span>}
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
