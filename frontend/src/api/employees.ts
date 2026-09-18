import { apiClient } from "./client.ts";

export type Role = {
  id: number;
  code: string;
  name_ru: string;
  category: "staff" | "management";
  permission_level: number;
};

export type Employee = {
  id: number;
  full_name: string;
  phone?: string;
  role_id: number;
  role_name: string;
  role_level: number;
  primary_branch_id: number;
  primary_branch_name: string;
  additional_branch_ids: number[];
  status: "active" | "inactive" | "fired";
  invite_code: string;
  has_claimed_account: boolean;
  hired_at?: string;
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
  status: "active" | "inactive" | "fired";
};

export type MyProfile = {
  id: number;
  full_name: string;
  status: "active" | "inactive" | "fired";
  role_id: number;
  role_name: string;
  role_code: string;
  role_level: number;
  primary_branch_id: number;
  primary_branch_name: string;
  additional_branch_ids: number[];
};

export async function listEmployees(branchId?: number): Promise<Employee[]> {
  const res = await apiClient.get<Employee[]>("/employees", {
    params: branchId ? { branch_id: branchId } : undefined,
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

export async function regenerateInviteCode(id: number): Promise<{ invite_code: string }> {
  const res = await apiClient.post<{ invite_code: string }>(`/employees/${id}/regenerate-invite`);
  return res.data;
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
