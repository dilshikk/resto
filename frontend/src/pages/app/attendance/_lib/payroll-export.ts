import * as XLSX from "xlsx";
import type { Payroll } from "@/api/attendance.ts";
import { shortDate } from "../utils.ts";

type Cell = string | number;

const FIXED_LEFT = 4; // №, Isim, Lavozim, Kunlik
const TAIL_HEADERS = ["Kun", "Mukofoti", "Chiqqan maoshi", "Shtraf", "Posuda", "Chiqqan maoshi", "Imzo"];

/** Выгрузка табеля в Excel в том же виде, что и бумажная ведомость: на сотрудника две строки (приход / уход). */
export function exportPayrollExcel(payroll: Payroll): void {
  const { dates, employees } = payroll;
  const header: Cell[] = [
    "№",
    "Isim",
    "Lavozim",
    "Kunlik",
    ...dates.map(shortDate),
    ...TAIL_HEADERS,
  ];
  const rows: Cell[][] = [header];
  const merges: XLSX.Range[] = [];
  const tailStart = FIXED_LEFT + dates.length;

  employees.forEach((emp, index) => {
    const top = rows.length;
    rows.push([
      index + 1,
      emp.name,
      emp.position ?? "",
      emp.rate_per_shift,
      ...dates.map((date) => emp.days[date]?.arrival ?? "-"),
      emp.worked_days,
      emp.bonus,
      emp.gross,
      emp.fine,
      emp.posuda,
      emp.net,
      "",
    ]);
    rows.push([
      "",
      "",
      "",
      "",
      ...dates.map((date) => emp.days[date]?.departure ?? "-"),
      ...TAIL_HEADERS.map(() => ""),
    ]);

    // Объединяем две строки сотрудника в левых и правых колонках
    for (let col = 0; col < FIXED_LEFT; col += 1) {
      merges.push({ s: { r: top, c: col }, e: { r: top + 1, c: col } });
    }
    for (let col = tailStart; col < tailStart + TAIL_HEADERS.length; col += 1) {
      merges.push({ s: { r: top, c: col }, e: { r: top + 1, c: col } });
    }
  });

  const sum = (pick: (e: Payroll["employees"][number]) => number) =>
    employees.reduce((acc, e) => acc + pick(e), 0);

  rows.push([
    "",
    "Итог",
    "",
    "",
    ...dates.map(() => ""),
    sum((e) => e.worked_days),
    sum((e) => e.bonus),
    sum((e) => e.gross),
    sum((e) => e.fine),
    sum((e) => e.posuda),
    sum((e) => e.net),
    "",
  ]);

  const ws = XLSX.utils.aoa_to_sheet(rows);
  ws["!merges"] = merges;
  ws["!cols"] = [
    { wch: 4 },
    { wch: 24 },
    { wch: 14 },
    { wch: 10 },
    ...dates.map(() => ({ wch: 6 })),
    { wch: 5 },
    { wch: 11 },
    { wch: 15 },
    { wch: 10 },
    { wch: 10 },
    { wch: 15 },
    { wch: 14 },
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Tabel");
  XLSX.writeFile(wb, `tabel_${payroll.date_from}_${payroll.date_to}.xlsx`);
}
