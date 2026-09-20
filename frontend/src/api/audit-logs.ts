import { apiClient } from "./client.ts";

export type AuditLog = {
  id: number;
  actor_id: number | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
};

export async function listAuditLogs(params: {
  entity_type?: string;
  entity_id?: number;
  actor_id?: number;
  limit?: number;
}): Promise<AuditLog[]> {
  const res = await apiClient.get<AuditLog[]>("/audit-logs", { params });
  return res.data;
}
