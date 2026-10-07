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
};

export type AttendanceEmployee = {
  employee_id: string;
  first_name: string;
  last_name: string;
};

export async function fetchAttendanceLogs(params: {
  date_from: string;
  date_to: string;
  employee_id?: string;
}): Promise<AccessLog[]> {
  const query = new URLSearchParams({
    date_from: params.date_from,
    date_to: params.date_to,
  });
  if (params.employee_id) query.set("employee_id", params.employee_id);
  const { data } = await apiClient.get<AccessLog[]>(
    `/attendance/logs?${query.toString()}`,
  );
  return data;
}

export async function fetchAttendanceEmployees(): Promise<AttendanceEmployee[]> {
  const { data } = await apiClient.get<AttendanceEmployee[]>("/attendance/employees");
  return data;
}
