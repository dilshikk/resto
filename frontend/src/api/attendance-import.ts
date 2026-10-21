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
  /** Зашифрованные ID из этого JSON, для которых ещё нет привязки к сотруднику */
  unmapped_hashes: string[];
};

/**
 * Отправляет JSON терминала (AcsEvent.InfoList) и добавляет события в базу FaceID.
 * overrideEmployeeId — настоящий ID сотрудника, который нужно подставить вместо
 * зашифрованного (хешированного) ID, если терминал прислал такие события.
 * Используется только для входа/выхода, остальные данные события не используются.
 */
export async function importFaceidJson(
  payload: object,
  overrideEmployeeId?: string,
): Promise<ImportJsonResult> {
  const body = overrideEmployeeId
    ? { ...payload, override_employee_id: overrideEmployeeId }
    : payload;
  const { data } = await apiClient.post<ImportJsonResult>("/attendance-import/json", body);
  return data;
}
