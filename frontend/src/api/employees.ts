import { apiClient } from "./client.ts";

export type Role = {
  id: number;
  code: string;
  name_ru: string;
  category: "staff" | "management";
  permission_level: number;
};

// "pending"  — self-registered via Telegram, awaiting manager review
// "active"   — confirmed, has checklist access
// "blocked"  — access revoked (worked before)
// "archived" — no longer works here
// "inactive"/"fired" are legacy values kept for backward compatibility with
// employees created before self-registration existed.
export type EmployeeStatus = "pending" | "active" | "blocked" | "archived" | "inactive" | "fired";

export type Employee = {
  id: number;
  full_name: string;
  phone?: string;
  // Optional: a self-registered ("pending") employee has no role/branch yet.
  role_id: number | null;
  role_name: string | null;
  role_level: number;
  primary_branch_id: number | null;
  primary_branch_name: string | null;
  additional_branch_ids: number[];
  status: EmployeeStatus;
  invite_code: string | null;
  has_claimed_account: boolean;
  telegram_linked: boolean;
  telegram_id: number | null;
  telegram_username?: string;
  hired_at?: string;
  last_activity_at: string | null;
  created_at: string;
  updated_at: string;
};

export type EmployeeCreate = {
  full_name: string;
  phone?: string;
  role_id: number;
  primary_branch_id: number;
  additional_branch_ids: number[];
  hired_at?: string;
};

export type EmployeeUpdate = EmployeeCreate & {
  status: EmployeeStatus;
};

export type EmployeeApprove = {
  role_id: number;
  primary_branch_id: number;
  additional_branch_ids: number[];
  hired_at?: string;
};

export type MyProfile = {
  id: number;
  full_name: string;
  status: EmployeeStatus;
  role_id: number;
  role_name: string;
  role_code: string;
  role_level: number;
  primary_branch_id: number;
  primary_branch_name: string;
  additional_branch_ids: number[];
};

export async function listEmployees(params?: {
  branchId?: number;
  q?: string;
  status?: EmployeeStatus;
}): Promise<Employee[]> {
  const res = await apiClient.get<Employee[]>("/employees", {
    params: {
      branch_id: params?.branchId,
      q: params?.q || undefined,
      status: params?.status,
    },
  });
  return res.data;
}

export async function createEmployee(data: EmployeeCreate): Promise<Employee> {
  const res = await apiClient.post<Employee>("/employees", data);
  return res.data;
}

export async function updateEmployee(id: number, data: EmployeeUpdate): Promise<Employee> {
  const res = await apiClient.patch<Employee>(`/employees/${id}`, data);
  return res.data;
}

export async function approveEmployee(id: number, data: EmployeeApprove): Promise<Employee> {
  const res = await apiClient.post<Employee>(`/employees/${id}/approve`, data);
  return res.data;
}

export async function rejectEmployee(id: number): Promise<void> {
  await apiClient.post(`/employees/${id}/reject`);
}

export async function regenerateInviteCode(id: number): Promise<{ invite_code: string }> {
  const res = await apiClient.post<{ invite_code: string }>(`/employees/${id}/regenerate-invite`);
  return res.data;
}

export async function unlinkEmployeeAccount(id: number): Promise<void> {
  await apiClient.delete(`/employees/${id}/account`);
}

export async function getMyProfile(): Promise<MyProfile> {
  const res = await apiClient.get<MyProfile>("/employees/me");
  return res.data;
}

export async function listRoles(): Promise<Role[]> {
  const res = await apiClient.get<Role[]>("/roles");
  return res.data;
}

export async function claimProfile(invite_code: string): Promise<void> {
  await apiClient.post("/employees/claim", { invite_code });
}

export async function hasAnyEmployees(): Promise<boolean> {
  const res = await apiClient.get<{ exists: boolean }>("/employees/any");
  return res.data.exists;
}

export async function bootstrapDirector(data: {
  full_name: string;
  branch_name: string;
  timezone: string;
}): Promise<void> {
  await apiClient.post("/employees/bootstrap", data);
}
