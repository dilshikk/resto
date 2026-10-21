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
  /** Отображаемое имя из основной БД (приоритет над FaceID-именем) */
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

/** Вид ручного штрафа за смену */
export type ShiftFineKind = "late" | "absence";

export type ShiftFine = {
  kind: ShiftFineKind;
  amount: number;
  /** Плановое начало смены (для опоздания) */
  planned_start?: string | null;
  late_minutes?: number | null;
  note?: string | null;
};

/** Откуда взят график: задан в табеле или из раздела «Смены» */
export type PlanSource = "tabel" | "shifts";

/** set - задать время, day_off - выходной, clear - убрать график табеля */
export type PlanMode = "set" | "day_off" | "clear";

export type PayrollDay = {
  /** Первый приход за смену (ручной, если есть, иначе FaceID) */
  arrival: string | null;
  /** Последний закрытый уход за смену */
  departure: string | null;
  faceid_arrival: string | null;
  faceid_departure: string | null;
  /** Время прихода/ухода было изменено вручную */
  manual: boolean;
  /** Смена засчитана: есть хотя бы один закрытый отрезок вход -> выход */
  counted: boolean;
  /** Фактически отработано минут за смену (сумма отрезков) */
  minutes: number | null;
  /** Оплачиваемые минуты: не больше 10 часов за смену */
  paid_minutes: number | null;
  /** Переработка сверх 10 часов, не оплачивается */
  overtime_minutes: number;
  /** После последнего входа нет выхода */
  open: boolean;
  /** Отрезки работы за смену, например "06:58-12:25" */
  segments: string[];
  /** В FaceID нет прихода или ухода за смену - начислен штраф */
  missing_punch?: boolean;
  /** Сумма штрафа за пропущенную отметку за смену */
  missing_punch_fine?: number;
  /** Ручные штрафы за смену (опоздание, невыход) */
  fines?: ShiftFine[];
  /** График: во сколько должен прийти и уйти */
  planned_start?: string | null;
  planned_end?: string | null;
  plan_source?: PlanSource | null;
  /** По графику выходной */
  day_off?: boolean;
  /** Отклонение от графика в минутах */
  late_minutes?: number;
  early_minutes?: number;
  /** Автоштрафы по графику */
  late_fine?: number;
  early_fine?: number;
};

export type PayrollEmployee = {
  employee_id: string;
  name: string;
  /** Имя из FaceID (для сверки в диалоге ставок) */
  faceid_name?: string | null;
  position: string | null;
  /** Сотрудник системы, по которому берётся график из «Смен» */
  linked_employee_id?: number | null;
  /** Дата увольнения (YYYY-MM-DD), если сотрудник уволен. null - активен */
  terminated_from?: string | null;
  /** Ставка за час */
  rate_per_hour: number;
  currency: string;
  /** Ключ - дата начала смены YYYY-MM-DD */
  days: Record<string, PayrollDay>;
  worked_days: number;
  /** Фактически отработано минут (включая переработку) */
  worked_minutes: number;
  /** Оплачиваемые минуты (не больше 10 часов за смену) */
  paid_minutes: number;
  /** Переработка за период, не оплачивается */
  overtime_minutes: number;
  /** Оплачиваемые часы за период (с точностью до сотых) */
  hours: number;
  /** Часы переработки за период */
  overtime_hours: number;
  bonus: number;
  /** Ручной штраф за период */
  fine: number;
  /** Смен без прихода или ухода и автоматический штраф за них */
  missing_punch_count?: number;
  missing_punch_fine?: number;
  /** Ручные штрафы за смены (опоздания, невыходы) */
  shift_fines_count?: number;
  shift_fines_total?: number;
  /** Автоштрафы по графику */
  late_count?: number;
  late_fine_total?: number;
  early_count?: number;
  early_fine_total?: number;
  /** Ручная посуда за период */
  posuda: number;
  /** Автоматическая посуда за отработанные смены */
  posuda_auto?: number;
  /** Вся посуда к удержанию (ручная + автоматическая) */
  posuda_total?: number;
  gross: number;
  net: number;
};

export type Payroll = {
  date_from: string;
  date_to: string;
  dates: string[];
  /** Максимум оплачиваемых минут за смену (600 = 10 часов) */
  max_paid_minutes_per_shift: number;
  /** Штраф за одну смену без прихода или ухода */
  missing_punch_fine_amount?: number;
  /** Посуда за одну смену */
  posuda_per_shift?: number;
  /** Штраф за минуту опоздания */
  late_fine_per_minute?: number;
  /** Опоздание до стольких минут не штрафуется */
  late_grace_minutes?: number;
  /** Штраф за минуту раннего ухода */
  early_leave_fine_per_minute?: number;
  employees: PayrollEmployee[];
};

export type AdjustmentField = "bonus" | "fine" | "posuda";

export async function fetchPayroll(
  dateFrom: string,
  dateTo: string,
  includeTerminated = false,
): Promise<Payroll> {
  const { data } = await apiClient.get<Payroll>("/attendance-payroll", {
    params: { date_from: dateFrom, date_to: dateTo, include_terminated: includeTerminated },
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

/** Штраф за смену. amount 0 - удалить штраф этого вида */
export async function saveShiftFine(body: {
  faceid_employee_id: string;
  shift_date: string;
  kind: ShiftFineKind;
  amount: number;
  planned_start?: string | null;
  late_minutes?: number | null;
  note?: string | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/shift-fine", body);
}

/** График в табеле на один или несколько дней */
export async function savePayrollPlan(body: {
  faceid_employee_id: string;
  shift_dates: string[];
  mode: PlanMode;
  planned_start: string | null;
  planned_end: string | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/plan", body);
}

/** Привязка сотрудника FaceID к сотруднику системы (график из «Смен»). null - отвязать */
export async function savePayrollLink(body: {
  faceid_employee_id: string;
  employee_id: number | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/link", body);
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

/** Уволить сотрудника с указанной даты (terminated_from) или восстановить (null) */
export async function savePayrollTermination(body: {
  faceid_employee_id: string;
  terminated_from: string | null;
}): Promise<void> {
  await apiClient.put("/attendance-payroll/termination", body);
}
