import type { AccessLog } from "@/api/attendance.ts";

export type EmployeeDay = {
  employee_id: string;
  full_name: string;
  device_name: string | null;
  /** Дата начала смены (YYYY-MM-DD) */
  date: string;
  first_in: string | null;
  last_out: string | null;
  worked_minutes: number | null;
  is_late: boolean;
  left_early: boolean;
  absent: boolean;
  /** Ставка за смену (из основной БД) */
  rate_per_shift: number | null;
  currency: string;
  logs: AccessLog[];
};

export type ReportPeriod = "day" | "week" | "month";

// Смена: 06:00 → 05:59 следующего дня.
const SHIFT_CUTOFF_MINUTES = 6 * 60; // 06:00

const WORK_START = "09:00";
// Ожидаемый уход — 01:00 следующего дня
const WORK_END = "01:00";

function parseTime(timeStr: string): number {
  const [h, m] = timeStr.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

function toShiftMinutes(timeStr: string): number {
  const mins = parseTime(timeStr);
  return mins < SHIFT_CUTOFF_MINUTES ? mins + 24 * 60 : mins;
}

/** Дата YYYY-MM-DD в локальном часовом поясе (toISOString даёт UTC и сдвигает день в Ташкенте). */
export function toLocalIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function shiftDate(accessDate: string, accessTime: string): string {
  const mins = parseTime(accessTime);
  if (mins < SHIFT_CUTOFF_MINUTES) {
    const [y, m, d] = accessDate.split("-").map(Number);
    return toLocalIso(new Date(y ?? 1970, (m ?? 1) - 1, (d ?? 1) - 1));
  }
  return accessDate;
}

export function groupLogsByEmployeeDay(logs: AccessLog[]): EmployeeDay[] {
  const map = new Map<string, AccessLog[]>();

  for (const log of logs) {
    if (!log.employee_id || !log.access_date || !log.access_time) continue;
    const sd = shiftDate(log.access_date, log.access_time);
    const key = `${log.employee_id}__${sd}`;
    const arr = map.get(key) ?? [];
    arr.push(log);
    map.set(key, arr);
  }

  const result: EmployeeDay[] = [];

  for (const [key, dayLogs] of map.entries()) {
    const [employee_id, date] = key.split("__") as [string, string];

    const sorted = [...dayLogs].sort((a, b) => {
      const ta = toShiftMinutes(a.access_time ?? "00:00");
      const tb = toShiftMinutes(b.access_time ?? "00:00");
      return ta - tb;
    });

    const ins = sorted.filter((l) => l.direction?.toLowerCase() === "in");
    const outs = sorted.filter((l) => l.direction?.toLowerCase() === "out");

    const first_in = ins[0]?.access_time?.slice(0, 5) ?? null;
    const last_out = outs[outs.length - 1]?.access_time?.slice(0, 5) ?? null;

    let worked_minutes: number | null = null;
    if (first_in && last_out) {
      const inMins = toShiftMinutes(first_in);
      const outMins = toShiftMinutes(last_out);
      worked_minutes = outMins > inMins ? outMins - inMins : null;
    }

    const is_late = first_in
      ? toShiftMinutes(first_in) > toShiftMinutes(WORK_START) + 5
      : false;

    const workEndShift = toShiftMinutes(WORK_END);
    const left_early = last_out
      ? toShiftMinutes(last_out) < workEndShift - 5
      : false;

    const sample = sorted[0];
    const full_name =
      [sample?.first_name, sample?.last_name].filter(Boolean).join(" ") || employee_id;

    // Ставка берётся из первого лога смены (все логи одного сотрудника имеют одну ставку)
    const rate_per_shift = sample?.rate_per_shift ?? null;
    const currency = sample?.currency ?? "UZS";

    result.push({
      employee_id,
      full_name,
      device_name: sample?.device_name ?? null,
      date,
      first_in,
      last_out,
      worked_minutes,
      is_late,
      left_early,
      absent: false,
      rate_per_shift,
      currency,
      logs: sorted,
    });
  }

  return result.sort(
    (a, b) => a.date.localeCompare(b.date) || a.full_name.localeCompare(b.full_name),
  );
}

export function formatMinutes(minutes: number): string {
  if (minutes < 0) return `—`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}ч ${m}м`;
}

export function formatMoney(amount: number, currency: string): string {
  if (currency === "UZS") {
    return new Intl.NumberFormat("ru-UZ").format(Math.round(amount)) + " сум";
  }
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency }).format(amount);
}

/** Число с пробелами между тысячами, без валюты. */
export function formatNumber(amount: number): string {
  return new Intl.NumberFormat("ru-RU").format(Math.round(amount));
}

/** "2026-10-08" -> "08.10" */
export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d ?? ""}.${m ?? ""}`;
}

export function todayStr(): string {
  return toLocalIso(new Date());
}

export function weekAgoStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 6);
  return toLocalIso(d);
}

export function monthStartStr(): string {
  const d = new Date();
  return toLocalIso(new Date(d.getFullYear(), d.getMonth(), 1));
}

export type DateRange = { from: string; to: string };

/** Месяц целиком: offset 0 - текущий, -1 - прошлый. */
export function monthRange(offset = 0): DateRange {
  const d = new Date();
  return {
    from: toLocalIso(new Date(d.getFullYear(), d.getMonth() + offset, 1)),
    to: toLocalIso(new Date(d.getFullYear(), d.getMonth() + offset + 1, 0)),
  };
}

/** Половина текущего месяца: 1-15 или 16-конец. */
export function halfMonthRange(half: 1 | 2): DateRange {
  const full = monthRange(0);
  const prefix = full.from.slice(0, 8);
  return half === 1 ? { from: `${prefix}01`, to: `${prefix}15` } : { from: `${prefix}16`, to: full.to };
}

/** Число дней в периоде включительно. */
export function periodLength(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000) + 1;
}
