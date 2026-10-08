import type { AccessLog } from "@/api/attendance.ts";

export type EmployeeDay = {
  employee_id: string;
  full_name: string;
  device_name: string | null;
  /** Дата начала смены (YYYY-MM-DD) — день, когда смена открылась в 06:00 */
  date: string;
  first_in: string | null;
  last_out: string | null;
  worked_minutes: number | null;
  is_late: boolean;
  left_early: boolean;
  absent: boolean;
  logs: AccessLog[];
};

export type ReportPeriod = "day" | "week" | "month";

// ── Параметры смены ──────────────────────────────────────────────────────────
// Смена открывается в SHIFT_START и закрывается в SHIFT_END следующего дня.
// Все события с 00:00 до SHIFT_CUTOFF-1 считаются ещё прошлым днём смены.
const SHIFT_START_MINUTES = 6 * 60; // 06:00 — начало смены
const SHIFT_END_MINUTES = 24 * 60 + 5 * 60; // 30:00 = 06:00 след. дня (крайняя граница)
const SHIFT_CUTOFF_MINUTES = 6 * 60; // события до 06:00 → смена предыдущего дня

// Эталонное начало смены (опоздание считается от этого времени)
const WORK_START = "09:00";
// Ожидаемый уход (ранний уход — если ушёл раньше)
const WORK_END = "01:00"; // 01:00 следующего дня → 25 * 60 = 1500 мин в "смено-минутах"

function parseTime(timeStr: string): number {
  const [h, m] = timeStr.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

/**
 * Переводим access_time (HH:MM:SS) в "минуты смены".
 * Если время < SHIFT_CUTOFF (до 06:00) — считаем это продолжением ночи,
 * добавляем 24*60 чтобы оно оказалось после полуночи в шкале смены.
 */
function toShiftMinutes(timeStr: string): number {
  const mins = parseTime(timeStr);
  return mins < SHIFT_CUTOFF_MINUTES ? mins + 24 * 60 : mins;
}

/**
 * По access_date (YYYY-MM-DD) и access_time (HH:MM:SS) определяем
 * "дату смены" — день, когда смена началась.
 *
 * Правило: если время < 06:00 → смена принадлежит предыдущему дню.
 */
function shiftDate(accessDate: string, accessTime: string): string {
  const mins = parseTime(accessTime);
  if (mins < SHIFT_CUTOFF_MINUTES) {
    // Вычитаем один день
    const d = new Date(`${accessDate}T00:00:00`);
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
  }
  return accessDate;
}

export function groupLogsByEmployeeDay(logs: AccessLog[]): EmployeeDay[] {
  // Группируем по (employee_id, дата-смены)
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

    // Сортируем по "смено-минутам" — ночные события встают в конец
    const sorted = [...dayLogs].sort((a, b) => {
      const ta = toShiftMinutes(a.access_time ?? "00:00");
      const tb = toShiftMinutes(b.access_time ?? "00:00");
      return ta - tb;
    });

    const ins = sorted.filter((l) => l.direction?.toLowerCase() === "in");
    const outs = sorted.filter((l) => l.direction?.toLowerCase() === "out");

    const firstInLog = ins[0];
    const lastOutLog = outs[outs.length - 1];

    const first_in = firstInLog?.access_time?.slice(0, 5) ?? null;
    const last_out = lastOutLog?.access_time?.slice(0, 5) ?? null;

    // Отработано в минутах смены
    let worked_minutes: number | null = null;
    if (first_in && last_out) {
      const inMins = toShiftMinutes(first_in);
      const outMins = toShiftMinutes(last_out);
      worked_minutes = outMins > inMins ? outMins - inMins : null;
    }

    // Опоздание: пришёл позже WORK_START + 5 мин
    const is_late = first_in
      ? toShiftMinutes(first_in) > toShiftMinutes(WORK_START) + 5
      : false;

    // Ранний уход: ушёл до WORK_END - 5 мин
    // WORK_END "01:00" — в смено-минутах это 25*60=1500
    const workEndShift = toShiftMinutes(WORK_END);
    const left_early = last_out
      ? toShiftMinutes(last_out) < workEndShift - 5
      : false;

    const sample = sorted[0];
    const full_name =
      [sample?.first_name, sample?.last_name].filter(Boolean).join(" ") || employee_id;

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

export function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function weekAgoStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 6);
  return d.toISOString().slice(0, 10);
}
