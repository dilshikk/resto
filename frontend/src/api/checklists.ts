import { apiClient } from "./client.ts";

// ── Template types ────────────────────────────────────────────────────────

export type ChecklistTemplateItem = {
  id: number;
  template_id: number;
  title: string;
  description?: string;
  sort_order: number;
  is_required: boolean;
  standard_code?: string;
};

export type ChecklistTemplate = {
  id: number;
  name: string;
  description?: string;
  category: string;
  branch_id?: number;
  branch_name?: string;
  is_active: boolean;
  item_count: number;
  created_at: string;
};

export type ChecklistTemplateDetail = ChecklistTemplate & {
  items: ChecklistTemplateItem[];
};

export type TemplateCreate = {
  name: string;
  description?: string;
  category: string;
  branch_id?: number;
};

// ── Checklist types ───────────────────────────────────────────────────────

export type ChecklistItemPhoto = {
  id: number;
  url: string;
  uploaded_by_name: string;
  created_at: string;
};

export type ChecklistItem = {
  id: number;
  checklist_id: number;
  title: string;
  description?: string;
  is_required: boolean;
  sort_order: number;
  is_completed: boolean;
  is_skipped: boolean;
  completed_by_name?: string;
  completed_at?: string;
  note?: string;
  photos: ChecklistItemPhoto[];
  standard_code?: string;
  standard_title?: string;
};

export type Checklist = {
  id: number;
  template_id: number;
  template_name: string;
  branch_id: number;
  branch_name: string;
  shift: string;
  date: string;
  status: "open" | "completed";
  total_items: number;
  completed_items: number;
  skipped_items: number;
  created_at: string;
};

export type ChecklistDetail = Checklist & { items: ChecklistItem[] };

export type ChecklistCreate = {
  template_id: number;
  branch_id: number;
  shift: string;
  date: string;
};

/** Returned by GET /checklists/{id}/current-item. null = all done, ready to complete. */
export type CurrentItem = {
  id: number;
  checklist_id: number;
  title: string;
  description?: string;
  is_required: boolean;
  sort_order: number;
  total_items: number;
  current_position: number;
  standard_code?: string;
  standard_title?: string;
} | null;

// ── Templates API ─────────────────────────────────────────────────────────

export async function listTemplates(): Promise<ChecklistTemplate[]> {
  const res = await apiClient.get<ChecklistTemplate[]>("/templates");
  return res.data;
}

export async function getTemplate(id: number): Promise<ChecklistTemplateDetail> {
  const res = await apiClient.get<ChecklistTemplateDetail>(`/templates/${id}`);
  return res.data;
}

export async function createTemplate(data: TemplateCreate): Promise<ChecklistTemplate> {
  const res = await apiClient.post<ChecklistTemplate>("/templates", data);
  return res.data;
}

export async function updateTemplate(id: number, data: TemplateCreate): Promise<ChecklistTemplate> {
  const res = await apiClient.patch<ChecklistTemplate>(`/templates/${id}`, data);
  return res.data;
}

export async function deactivateTemplate(id: number): Promise<void> {
  await apiClient.delete(`/templates/${id}`);
}

export async function addTemplateItem(
  templateId: number,
  data: { title: string; description?: string; sort_order?: number; is_required?: boolean; standard_code?: string },
): Promise<ChecklistTemplateItem> {
  const res = await apiClient.post<ChecklistTemplateItem>(`/templates/${templateId}/items`, data);
  return res.data;
}

export async function updateTemplateItem(
  templateId: number,
  itemId: number,
  data: { title: string; description?: string; sort_order?: number; is_required?: boolean; standard_code?: string },
): Promise<ChecklistTemplateItem> {
  const res = await apiClient.patch<ChecklistTemplateItem>(`/templates/${templateId}/items/${itemId}`, data);
  return res.data;
}

export async function removeTemplateItem(templateId: number, itemId: number): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/items/${itemId}`);
}

// ── Checklists API ────────────────────────────────────────────────────────

export async function listChecklists(params: {
  date?: string;
  branch_id?: number;
  status?: string;
}): Promise<Checklist[]> {
  const res = await apiClient.get<Checklist[]>("/checklists", { params });
  return res.data;
}

export async function getChecklist(id: number): Promise<ChecklistDetail> {
  const res = await apiClient.get<ChecklistDetail>(`/checklists/${id}`);
  return res.data;
}

export async function createChecklist(data: ChecklistCreate): Promise<Checklist> {
  const res = await apiClient.post<Checklist>("/checklists", data);
  return res.data;
}

/** Step-by-step: get the current (next pending) item. Returns null when all done. */
export async function getCurrentItem(checklistId: number): Promise<CurrentItem> {
  const res = await apiClient.get<CurrentItem>(`/checklists/${checklistId}/current-item`);
  return res.data;
}

/** Mark an item as completed (or un-complete it). */
export async function toggleChecklistItem(
  checklistId: number,
  itemId: number,
  note?: string,
): Promise<{ is_completed: boolean; is_skipped: boolean }> {
  const res = await apiClient.patch<{ is_completed: boolean; is_skipped: boolean }>(
    `/checklists/${checklistId}/items/${itemId}/toggle`,
    { note },
  );
  return res.data;
}

/** Skip an optional (is_required=false) item. Required items return 400. */
export async function skipChecklistItem(
  checklistId: number,
  itemId: number,
  note?: string,
): Promise<{ is_skipped: boolean }> {
  const res = await apiClient.post<{ is_skipped: boolean }>(
    `/checklists/${checklistId}/items/${itemId}/skip`,
    { note },
  );
  return res.data;
}

export async function completeChecklist(checklistId: number): Promise<void> {
  await apiClient.post(`/checklists/${checklistId}/complete`);
}
