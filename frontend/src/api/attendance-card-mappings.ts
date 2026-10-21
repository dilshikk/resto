import { apiClient } from "./client.ts";

export type CardMapping = {
  hashed_id: string;
  faceid_employee_id: string;
  note: string | null;
};

export async function fetchCardMappings(): Promise<CardMapping[]> {
  const { data } = await apiClient.get<CardMapping[]>("/attendance-card-mappings");
  return data;
}

export async function upsertCardMapping(
  hashedId: string,
  body: { faceid_employee_id: string; note?: string | null },
): Promise<CardMapping> {
  const { data } = await apiClient.put<CardMapping>(
    `/attendance-card-mappings/${encodeURIComponent(hashedId)}`,
    body,
  );
  return data;
}

export async function deleteCardMapping(hashedId: string): Promise<void> {
  await apiClient.delete(`/attendance-card-mappings/${encodeURIComponent(hashedId)}`);
}
