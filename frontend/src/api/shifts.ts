import { apiClient } from "./client.ts";

export type ShiftStatus = "planned" | "active" | "completed" | "no_show";

export type Shift = {
  id: number;
  employee_id: number;
  employee_name: string;
  branch_id: number;
  branch_name: string;
  shift_date: string; // YYYY-MM-DD
  starts_at: string; // HH:MM
  ends_at: string; // HH:MM
  status: ShiftStatus;
  created_at: string;
  updated_at: string;
};

export type ShiftCreate = {
  employee_id: number;
  branch_id: number;
  shift_date: string;
  starts_at: string;
  ends_at: string;
};

export type ShiftUpdate = {
  starts_at?: string;
  ends_at?: string;
  status?: ShiftStatus;
};

export async function listShifts(params?: {
  branch_id?: number;
  employee_id?: number;
  shift_date?: string;
}): Promise<Shift[]> {
  const res = await apiClient.get<Shift[]>("/shifts", { params });
  return res.data;
}

export async function getMyCurrentShift(): Promise<Shift | null> {
  const res = await apiClient.get<Shift | null>("/shifts/my-current");
  return res.data;
}

export async function createShift(data: ShiftCreate): Promise<Shift> {
  const res = await apiClient.post<Shift>("/shifts", data);
  return res.data;
}

export async function updateShift(id: number, data: ShiftUpdate): Promise<Shift> {
  const res = await apiClient.patch<Shift>(`/shifts/${id}`, data);
  return res.data;
}
