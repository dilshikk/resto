import { apiClient } from "./client.ts";

export type AccessLog = {
  id: number;
  employee_id: string | null;
  access_datetime: string | null;
  access_date: string | null;
  access_time: string | null;
  auth_result: string | null;
  auth_type: string | null;
  device_name: string | null;
  device_sn: string | null;
  first_name: string | null;
  last_name: string | null;
  card_no: string | null;
  direction: string | null;
  /** Ставка за час (имя поля историческое) */
  rate_per_shift: number | null;
  currency: string;
};

export type AttendanceEmployee = {
  employee_id: string;
  first_name: string | null;
  last_name: string | null;
  /** Ставка за час (имя поля историческое) */
  rate_per_shift: number | null;
  currency: string;
};

export type AttendanceRate = {
  faceid_employee_id: string;
  display_name: string | null;
  /** Ставка за час (имя поля историческое) */
  rate_per_shift: number;
  currency: string;
};

export async function fetchAttendanceLogs(params: {
  date_from: string;
  date_to: string;
  employee_id?: string;
}): Promise<AccessLog[]> {
  const query = new URLSearchParams({ date_from: params.date_from, date_to: params.date_to });
  if (params.employee_id) query.set("employee_id", params.employee_id);
  const { data } = await apiClient.get<AccessLog[]>(`/attendance/logs?${query.toString()}`);
  return data;
}

export async function fetchAttendanceEmployees(): Promise<AttendanceEmployee[]> {
  const { data } = await apiClient.get<AttendanceEmployee[]>("/attendance/employees");
  return data;
}

export async function fetchAttendanceRates(): Promise<AttendanceRate[]> {
  const { data } = await apiClient.get<AttendanceRate[]>("/attendance-rates");
  return data;
}

export async function upsertAttendanceRate(
  faceidEmployeeId: string,
  body: { display_name?: string; rate_per_shift: number; currency: string },
): Promise<AttendanceRate> {
  const { data } = await apiClient.put<AttendanceRate>(
    `/attendance-rates/${encodeURIComponent(faceidEmployeeId)}`,
    { faceid_employee_id: faceidEmployeeId, ...body },
  );
  return data;
}

// ── Табель и расчёт зарплаты ─────────────────────────────────────────────────

export type PayrollDay = {
  /** Итоговое время прихода (ручное, если есть, иначе FaceID) */
  arrival: string | null;
  departure: string | null;
  faceid_arrival: string | null;
  faceid_departure: string | null;
  /** Время прихода/ухода было изменено вручную */
  manual: boolean;
  /** Смена засчитана: есть и приход, и уход, уход позже прихода */
  counted: boolean;
  /** Отработано минут за смену */
  minutes: number | null;
};

export type PayrollEmployee = {
  employee_id: string;
  name: string;
  position: string | null;
  /** Ставка за час */
  rate_per_hour: number;
  currency: string;
  /** Ключ - дата начала смены YYYY-MM-DD */
  days: Record<string, PayrollDay>;
  worked_days: number;
  worked_minutes: number;
  /** Часы за период (с точностью до сотых) */
  hours: number;
  bonus: number;
  fine: number;
  posuda: number;
  gross: number;
  net: number;
};

export type Payroll = {
  date_from: string;
  date_to: string;
  dates: string[];
  employees: PayrollEmployee[];
};

export type AdjustmentField = "bonus" | "fine" | "posuda";

export async function fetchPayroll(dateFrom: string, dateTo: string): Promise<Payroll> {
  const { data } = await apiClient.get<Payroll>("/attendance-payroll", {
    params: { date_from: dateFrom, date_to: dateTo },
  });
  return data;
}

export async function savePayrollPunch(body: {
  faceid_employee_id: string;
  shift_date: string;
  arrival: string | null;
  departure: string | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/punch", body);
}

export async function savePayrollAdjustment(body: {
  faceid_employee_id: string;
  date_from: string;
  date_to: string;
  bonus?: number;
  fine?: number;
  posuda?: number;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/adjustment", body);
}

export async function savePayrollPosition(body: {
  faceid_employee_id: string;
  position: string | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/position", body);
}
