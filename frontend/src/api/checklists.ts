import { apiClient } from "./client.ts";

// ── Template types ────────────────────────────────────────────────────────

export type ChecklistTemplateItem = {
  id: number;
  template_id: number;
  title: string;
  description?: string;
  sort_order: number;
  is_required: boolean;
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

export type ChecklistItem = {
  id: number;
  checklist_id: number;
  title: string;
  description?: string;
  is_required: boolean;
  sort_order: number;
  is_completed: boolean;
  completed_by_name?: string;
  completed_at?: string;
  note?: string;
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
  created_at: string;
};

export type ChecklistDetail = Checklist & { items: ChecklistItem[] };

export type ChecklistCreate = {
  template_id: number;
  branch_id: number;
  shift: string;
  date: string;
};

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
  data: { title: string; description?: string; sort_order?: number; is_required?: boolean },
): Promise<ChecklistTemplateItem> {
  const res = await apiClient.post<ChecklistTemplateItem>(`/templates/${templateId}/items`, data);
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

export async function toggleChecklistItem(
  checklistId: number,
  itemId: number,
  note?: string,
): Promise<{ is_completed: boolean }> {
  const res = await apiClient.patch<{ is_completed: boolean }>(
    `/checklists/${checklistId}/items/${itemId}/toggle`,
    { note },
  );
  return res.data;
}

export async function completeChecklist(checklistId: number): Promise<void> {
  await apiClient.post(`/checklists/${checklistId}/complete`);
}
