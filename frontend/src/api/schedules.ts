import { apiClient } from "./client.ts";

export type Schedule = {
  id: number;
  template_id: number;
  template_name: string;
  branch_id: number;
  branch_name: string;
  shift: string;
  start_date: string; // YYYY-MM-DD
  end_date: string | null;
  weekdays: number[]; // 1 = Mon ... 7 = Sun
  window_start: string; // HH:MM[:SS]
  window_end: string;
  is_active: boolean;
  created_at: string;
};

export type ScheduleFields = {
  template_id: number;
  shift: string;
  start_date: string;
  end_date: string | null;
  weekdays: number[];
  window_start: string;
  window_end: string;
};

export type ScheduleCreate = ScheduleFields & { branch_ids: number[] };
export type ScheduleUpdate = ScheduleFields & { branch_id: number; is_active: boolean };

export async function listSchedules(): Promise<Schedule[]> {
  const res = await apiClient.get<Schedule[]>("/schedules");
  return res.data;
}

export async function createSchedules(data: ScheduleCreate): Promise<Schedule[]> {
  const res = await apiClient.post<Schedule[]>("/schedules", data);
  return res.data;
}

export async function updateSchedule(id: number, data: ScheduleUpdate): Promise<Schedule> {
  const res = await apiClient.put<Schedule>(`/schedules/${id}`, data);
  return res.data;
}

export async function deleteSchedule(id: number): Promise<void> {
  await apiClient.delete(`/schedules/${id}`);
}

export function scheduleToUpdate(s: Schedule, patch: Partial<ScheduleUpdate> = {}): ScheduleUpdate {
  return {
    template_id: s.template_id,
    branch_id: s.branch_id,
    shift: s.shift,
    start_date: s.start_date,
    end_date: s.end_date,
    weekdays: s.weekdays,
    window_start: s.window_start.slice(0, 5),
    window_end: s.window_end.slice(0, 5),
    is_active: s.is_active,
    ...patch,
  };
}
