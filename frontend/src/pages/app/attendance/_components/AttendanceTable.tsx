import { useState } from "react";
import type { EmployeeDay } from "../utils.ts";
import { formatMinutes } from "../utils.ts";
import { Badge } from "@/components/ui/badge.tsx";
import { Button } from "@/components/ui/button.tsx";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table.tsx";
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
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="w-8" />
            <TableHead>Сотрудник</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Приход</TableHead>
            <TableHead>Уход</TableHead>
            <TableHead>Отработано</TableHead>
            <TableHead>Устройство</TableHead>
            <TableHead>Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const key = `${row.employee_id}__${row.date}`;
            const isOpen = expanded.has(key);
            return (
              <>
                <TableRow
                  key={key}
                  className={cn(
                    "cursor-pointer transition-colors hover:bg-muted/30",
                    row.absent && "opacity-60",
                  )}
                  onClick={() => toggle(key)}
                >
                  <TableCell className="py-3">
                    <Button variant="ghost" size="icon" className="h-6 w-6">
                      {isOpen ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </Button>
                  </TableCell>
                  <TableCell className="font-medium">{row.full_name}</TableCell>
                  <TableCell className="text-muted-foreground">{row.date}</TableCell>
                  <TableCell>
                    {row.first_in ? (
                      <span
                        className={
                          row.is_late
                            ? "font-medium text-amber-600"
                            : "font-medium text-emerald-600"
                        }
                      >
                        {row.first_in}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.last_out ? (
                      <span
                        className={
                          row.left_early ? "font-medium text-blue-600" : "text-foreground"
                        }
                      >
                        {row.last_out}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.worked_minutes != null ? (
                      <span className="font-medium">{formatMinutes(row.worked_minutes)}</span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {row.device_name ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {row.absent && (
                        <Badge variant="destructive" className="text-xs">
                          Отсутствует
                        </Badge>
                      )}
                      {row.is_late && (
                        <Badge className="border-amber-200 bg-amber-100 text-xs text-amber-700">
                          Опоздание
                        </Badge>
                      )}
                      {row.left_early && (
                        <Badge className="border-blue-200 bg-blue-100 text-xs text-blue-700">
                          Ранний уход
                        </Badge>
                      )}
                      {!row.absent && !row.is_late && !row.left_early && (
                        <Badge className="border-emerald-200 bg-emerald-100 text-xs text-emerald-700">
                          Норма
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
                {isOpen && (
                  <TableRow key={`${key}__detail`} className="bg-muted/20">
                    <TableCell colSpan={8} className="py-0">
                      <div className="py-3 pl-8">
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
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-rose-200 bg-rose-50 text-rose-700",
                              )}
                            >
                              <span className="font-medium">{log.access_time}</span>
                              <span>
                                {log.direction?.toLowerCase() === "in" ? "↑ вход" : "↓ выход"}
                              </span>
                              {log.device_name && (
                                <span className="opacity-70">{log.device_name}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
