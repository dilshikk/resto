import type { AccessLog, EmployeeDay } from "./types.ts";

// Work schedule constants (can be made configurable)
const WORK_START = "09:00";
const WORK_END = "18:00";

function parseTime(timeStr: string): number {
  const [h, m] = timeStr.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

export function groupLogsByEmployeeDay(logs: AccessLog[]): EmployeeDay[] {
  const map = new Map<string, AccessLog[]>();

  for (const log of logs) {
    if (!log.employee_id || !log.access_date) continue;
    const key = `${log.employee_id}__${log.access_date}`;
    const arr = map.get(key) ?? [];
    arr.push(log);
    map.set(key, arr);
  }

  const result: EmployeeDay[] = [];

  for (const [key, dayLogs] of map.entries()) {
    const [employee_id, date] = key.split("__") as [string, string];
    const sorted = [...dayLogs].sort((a, b) =>
      (a.access_time ?? "").localeCompare(b.access_time ?? "")
    );

    const ins = sorted.filter((l) => l.direction?.toLowerCase() === "in");
    const outs = sorted.filter((l) => l.direction?.toLowerCase() === "out");

    const first_in = ins[0]?.access_time ?? null;
    const last_out = outs[outs.length - 1]?.access_time ?? null;

    let worked_minutes: number | null = null;
    if (first_in && last_out) {
      worked_minutes = parseTime(last_out) - parseTime(first_in);
    }

    const is_late = first_in ? parseTime(first_in) > parseTime(WORK_START) + 5 : false;
    const left_early = last_out ? parseTime(last_out) < parseTime(WORK_END) - 5 : false;

    const sample = sorted[0];
    const full_name = [sample?.first_name, sample?.last_name].filter(Boolean).join(" ") || employee_id;

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

  return result.sort((a, b) => a.date.localeCompare(b.date) || a.full_name.localeCompare(b.full_name));
}

export function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}ч ${m}м`;
}

export function getDatesInRange(from: string, to: string): string[] {
  const dates: string[] = [];
  const cur = new Date(from);
  const end = new Date(to);
  while (cur <= end) {
    dates.push(cur.toISOString().slice(0, 10));
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

export function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

export function weekAgoStr(): string {
  const d = new Date();
  d.setDate(d.getDate() - 6);
  return d.toISOString().slice(0, 10);
}
