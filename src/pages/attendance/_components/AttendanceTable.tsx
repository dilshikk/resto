import { useState } from "react";
import type { EmployeeDay } from "../_lib/types.ts";
import { formatMinutes } from "../_lib/utils.ts";
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

type Props = {
  rows: EmployeeDay[];
};

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
      <div className="text-center py-16 text-muted-foreground">
        Нет данных за выбранный период
      </div>
    );
  }

  return (
    <div className="rounded-xl border overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="w-8" />
            <TableHead>Сотрудник</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Приход</TableHead>
            <TableHead>Уход</TableHead>
            <TableHead>Отработано</TableHead>
            <TableHead>Филиал</TableHead>
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
                    "cursor-pointer hover:bg-muted/30 transition-colors",
                    row.absent && "opacity-60"
                  )}
                  onClick={() => toggle(key)}
                >
                  <TableCell className="py-3">
                    <Button variant="ghost" size="icon" className="w-6 h-6">
                      {isOpen ? (
                        <ChevronDown className="w-3 h-3" />
                      ) : (
                        <ChevronRight className="w-3 h-3" />
                      )}
                    </Button>
                  </TableCell>
                  <TableCell className="font-medium">{row.full_name}</TableCell>
                  <TableCell className="text-muted-foreground">{row.date}</TableCell>
                  <TableCell>
                    {row.first_in ? (
                      <span className={row.is_late ? "text-amber-600 font-medium" : "text-emerald-600 font-medium"}>
                        {row.first_in}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.last_out ? (
                      <span className={row.left_early ? "text-blue-600 font-medium" : "text-foreground"}>
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
                  <TableCell className="text-muted-foreground text-sm">
                    {row.device_name ?? "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-wrap">
                      {row.absent && <Badge variant="destructive" className="text-xs">Отсутствует</Badge>}
                      {row.is_late && <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-xs">Опоздание</Badge>}
                      {row.left_early && <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">Ранний уход</Badge>}
                      {!row.absent && !row.is_late && !row.left_early && (
                        <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200 text-xs">Норма</Badge>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
                {isOpen && (
                  <TableRow key={`${key}__detail`} className="bg-muted/20">
                    <TableCell colSpan={8} className="py-0">
                      <div className="py-3 pl-8">
                        <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                          Все события за {row.date}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {row.logs.map((log) => (
                            <div
                              key={log.id}
                              className={cn(
                                "flex items-center gap-2 text-xs px-3 py-1.5 rounded-full border",
                                log.direction?.toLowerCase() === "in"
                                  ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                                  : "bg-rose-50 border-rose-200 text-rose-700"
                              )}
                            >
                              <span className="font-medium">{log.access_time}</span>
                              <span>{log.direction?.toLowerCase() === "in" ? "↑ вход" : "↓ выход"}</span>
                              {log.device_name && <span className="opacity-70">{log.device_name}</span>}
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
