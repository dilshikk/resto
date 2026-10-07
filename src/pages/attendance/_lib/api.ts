import type { AccessLog } from "./types.ts";

const BASE_URL = import.meta.env.VITE_ATTENDANCE_API_URL ?? "";

export async function fetchLogs(params: {
  date_from: string;
  date_to: string;
  employee_id?: string;
}): Promise<AccessLog[]> {
  const query = new URLSearchParams({ date_from: params.date_from, date_to: params.date_to });
  if (params.employee_id) query.set("employee_id", params.employee_id);

  const res = await fetch(`${BASE_URL}/attendance/logs?${query.toString()}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<AccessLog[]>;
}

export async function fetchEmployees(): Promise<{ employee_id: string; first_name: string; last_name: string }[]> {
  const res = await fetch(`${BASE_URL}/attendance/employees`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<{ employee_id: string; first_name: string; last_name: string }[]>;
}
