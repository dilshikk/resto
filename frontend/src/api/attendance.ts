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
  rate_per_shift: number | null;
  currency: string;
};

export type AttendanceEmployee = {
  employee_id: string;
  first_name: string | null;
  last_name: string | null;
  rate_per_shift: number | null;
  currency: string;
};

export type AttendanceRate = {
  faceid_employee_id: string;
  display_name: string | null;
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
