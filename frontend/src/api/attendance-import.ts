import { apiClient } from "./client.ts";

export type ImportSkippedReason = {
  reason: string;
  count: number;
};

export type ImportJsonResult = {
  /** Сколько событий было в JSON */
  total: number;
  /** Сколько новых отметок добавлено в базу */
  inserted: number;
  /** Сколько уже было в базе (тот же сотрудник, дата и минута) */
  duplicates: number;
  skipped: number;
  skipped_reasons: ImportSkippedReason[];
  date_from: string | null;
  date_to: string | null;
};

/** Отправляет JSON терминала (AcsEvent.InfoList) и добавляет события в базу FaceID */
export async function importFaceidJson(payload: object): Promise<ImportJsonResult> {
  const { data } = await apiClient.post<ImportJsonResult>("/attendance-import/json", payload);
  return data;
}
