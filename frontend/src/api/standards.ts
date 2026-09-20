import { apiClient } from "./client.ts";

export const STANDARD_CATEGORIES = [
  { value: "service", label: "Сервис" },
  { value: "cleanliness", label: "Чистота" },
  { value: "uniform", label: "Форма" },
  { value: "kitchen", label: "Кухня" },
  { value: "bar", label: "Бар" },
  { value: "cashier", label: "Касса" },
  { value: "warehouse", label: "Склад" },
  { value: "grill", label: "Гриль" },
  { value: "delivery", label: "Доставка" },
  { value: "safety", label: "Безопасность" },
] as const;

export type Standard = {
  code: string;
  category: string;
  title: string;
  description?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type StandardCreate = {
  code: string;
  category: string;
  title: string;
  description?: string;
};

export type StandardUpdate = {
  category?: string;
  title?: string;
  description?: string;
  is_active?: boolean;
};

export async function listStandards(params?: {
  category?: string;
  include_inactive?: boolean;
}): Promise<Standard[]> {
  const res = await apiClient.get<Standard[]>("/standards", { params });
  return res.data;
}

export async function getStandard(code: string): Promise<Standard> {
  const res = await apiClient.get<Standard>(`/standards/${code}`);
  return res.data;
}

export async function createStandard(data: StandardCreate): Promise<Standard> {
  const res = await apiClient.post<Standard>("/standards", data);
  return res.data;
}

export async function updateStandard(code: string, data: StandardUpdate): Promise<Standard> {
  const res = await apiClient.patch<Standard>(`/standards/${code}`, data);
  return res.data;
}
