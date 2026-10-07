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

export type EmployeeDay = {
  employee_id: string;
  full_name: string;
  device_name: string | null;
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
