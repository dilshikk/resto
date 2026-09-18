import { apiClient } from "./client.ts";

export type Branch = {
  id: number;
  name: string;
  address?: string;
  city?: string;
  timezone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type BranchCreate = {
  name: string;
  address?: string;
  city?: string;
  timezone: string;
};

export async function listBranches(): Promise<Branch[]> {
  const res = await apiClient.get<Branch[]>("/branches");
  return res.data;
}

export async function createBranch(data: BranchCreate): Promise<Branch> {
  const res = await apiClient.post<Branch>("/branches", data);
  return res.data;
}

export async function updateBranch(id: number, data: BranchCreate): Promise<Branch> {
  const res = await apiClient.patch<Branch>(`/branches/${id}`, data);
  return res.data;
}

export async function deactivateBranch(id: number): Promise<void> {
  await apiClient.delete(`/branches/${id}`);
}
