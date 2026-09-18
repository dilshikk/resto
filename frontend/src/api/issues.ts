import { apiClient } from "./client.ts";

export type IssueComment = {
  id: number;
  issue_id: number;
  author_name: string;
  text: string;
  created_at: string;
};

export type Issue = {
  id: number;
  title: string;
  description?: string;
  branch_id: number;
  branch_name: string;
  category: string;
  priority: "low" | "medium" | "high" | "critical";
  status: "open" | "in_progress" | "closed";
  photo_urls: string[];
  reported_by_name: string;
  assigned_to_name?: string;
  resolved_at?: string;
  created_at: string;
  updated_at: string;
  comment_count: number;
};

export type IssueDetail = Issue & { comments: IssueComment[] };

export type IssueCreate = {
  title: string;
  description?: string;
  branch_id: number;
  category: string;
  priority: string;
  photo_urls: string[];
  checklist_id?: number;
};

export type IssueStatusUpdate = {
  status: string;
  assigned_to_employee_id?: number;
};

export async function listIssues(params: {
  status?: string;
  branch_id?: number;
  priority?: string;
}): Promise<Issue[]> {
  const res = await apiClient.get<Issue[]>("/issues", { params });
  return res.data;
}

export async function getIssue(id: number): Promise<IssueDetail> {
  const res = await apiClient.get<IssueDetail>(`/issues/${id}`);
  return res.data;
}

export async function createIssue(data: IssueCreate): Promise<Issue> {
  const res = await apiClient.post<Issue>("/issues", data);
  return res.data;
}

export async function updateIssueStatus(id: number, data: IssueStatusUpdate): Promise<Issue> {
  const res = await apiClient.patch<Issue>(`/issues/${id}/status`, data);
  return res.data;
}

export async function addIssueComment(id: number, text: string): Promise<IssueComment> {
  const res = await apiClient.post<IssueComment>(`/issues/${id}/comments`, { text });
  return res.data;
}

export async function uploadIssuePhoto(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await apiClient.post<{ url: string }>("/issues/upload-photo", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data.url;
}

// Build an authenticated URL for a photo served from the backend
export function photoSrc(url: string): string {
  if (url.startsWith("http")) return url;
  const base = import.meta.env.VITE_API_URL ?? "";
  return `${base}${url}`;
}
